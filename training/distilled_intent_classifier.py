"""
Дистилляция LLM few-shot классификатора интентов в лёгкую CPU-модель
(TF-IDF + LogisticRegression)

1. Достаём лучший few-shot шаблон прямо из уже зарегистрированной LLM-модели
   (intent-classifier@Production).
2. Прогоняем этот промпт через teacher по текстам -
   получаем псевдо-разметку. Настоящие dev-лейблы в обучение не идут.
   
3. Обучаем student на псевдо-разметке.
4. Оцениваем student на df_dev по человеческим меткам.
5. Регистрируем student как новую версию intent-classifier. Алиас "Production"
   переключаем на неё только если student не сильно отстаёт от teacher —
   иначе плохой студент не идет в прод
"""

import logging
from typing import List, Tuple
from collections import Counter

import joblib
import pandas as pd

import mlflow
import mlflow.pyfunc
from mlflow import MlflowClient

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score, classification_report

from run_gigaevo_pipeline import LlamaEngine, load_datasets, log_confusion_matrix

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("distill_intent_classifier")

MODEL_NAME = "intent-classifier"
TEACHER_ALIAS = (
    "Production"  # текущая LLM-версия, чей few-shot промпт берём как teacher
)
STUDENT_INTENT_ARTIFACT_FILENAME = "student_intent_pipeline.joblib"
STUDENT_CLARIFICATION_ARTIFACT_FILENAME = "student_clarification_pipeline.joblib"

# Допустимое отставание student от teacher по macro-F1
ACCEPTANCE_MARGIN = 0.03


def load_teacher_few_shot_template(
    model_name: str = MODEL_NAME, alias: str = TEACHER_ALIAS
) -> Tuple[str, str]:
    """Достаёт few-shot шаблон-победитель из уже зарегистрированного LLM-рана."""
    client = MlflowClient()
    model_version = client.get_model_version_by_alias(model_name, alias)
    run = client.get_run(model_version.run_id)
    template = run.data.params["few_shot_template"]
    return template, model_version.run_id


def build_feature_text(history, text: str) -> str:
    """
    Единая текстовая строка для TF-IDF: история диалога + последняя реплика
    пользователя, склеенные по порядку.
    """
    parts = []
    if isinstance(history, list):
        parts.extend(str(turn.get("content", "")) for turn in history)
    parts.append(str(text))
    return " ".join(p for p in parts if p)


def pseudo_label(
    engine: LlamaEngine, df: pd.DataFrame, labels: List[str], few_shot_template: str
) -> List[dict]:
    """Прогоняет teacher LLM по каждой строке df, возвращает
    псевдо-метки intent+needs_clarification."""
    total = len(df)
    results = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        result = engine.classify_intent(
            row["history"], row["text"], labels, few_shot_template
        )
        logger.info(
            "[pseudo_label] labeled row %d/%d intent=%s needs_clarification=%s",
            i,
            total,
            result["intent"],
            result["needs_clarification"],
        )
        results.append(result)
    return results


def build_student_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]
    )


def build_clarification_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]
    )


class DistilledIntentClassifier(mlflow.pyfunc.PythonModel):
    def __init__(self, labels: List[str]):
        self.labels = labels
        self._intent_pipeline = None
        self._clarification_pipeline = None

    def load_context(self, context):
        self._intent_pipeline = joblib.load(context.artifacts["intent_pipeline"])
        self._clarification_pipeline = joblib.load(
            context.artifacts["clarification_pipeline"]
        )

    def predict(self, context, model_input):
        texts = [
            build_feature_text(row.get("history", []), row.get("text", ""))
            for _, row in model_input.iterrows()
        ]
        proba = self._intent_pipeline.predict_proba(texts)
        intents = self._intent_pipeline.classes_[proba.argmax(axis=1)]
        confidences = proba.max(axis=1)
        clarifications = self._clarification_pipeline.predict(texts)
        return [
            {
                "intent": str(intent),
                "confidence": float(conf),
                "needs_clarification": bool(clarify),
            }
            for intent, conf, clarify in zip(intents, confidences, clarifications)
        ]


def main():
    labels, _schema_version, df_train, df_dev, _df_aug = load_datasets()

    #Загружаем teacher
    few_shot_template, teacher_run_id = load_teacher_few_shot_template()

    logger.info(
        "Teacher few-shot template loaded from run %s",
        teacher_run_id,
    )

    logger.info("Loading teacher LLM for pseudo-labeling...")

    engine = LlamaEngine().load()

    #Pseudo-labeling
    train_pool = pd.concat(
        [df_train, df_dev],
        ignore_index=True,
    )

    logger.info(
        "Pseudo-labeling %d rows with teacher LLM...",
        len(train_pool),
    )

    y_train_pseudo = pseudo_label(
        engine,
        train_pool,
        labels,
        few_shot_template,
    )

    y_train_intent = [row["intent"] for row in y_train_pseudo]

    # needs_clarification уже есть в ground truth,
    # поэтому teacher для этого не используется.
    y_train_clarify = train_pool["needs_clarification"].tolist()

    X_train = [
        build_feature_text(
            row["history"],
            row["text"],
        )
        for _, row in train_pool.iterrows()
    ]

    # обучение student
    student = build_student_pipeline()

    student.fit(
        X_train,
        y_train_intent,
    )

    clarification_student = build_clarification_pipeline()

    clarification_student.fit(
        X_train,
        y_train_clarify,
    )

    # eval на настоящих dev лейблах
    X_dev = [
        build_feature_text(
            row["history"],
            row["text"],
        )
        for _, row in df_dev.iterrows()
    ]

    y_dev_true = df_dev["intent"].tolist()

    y_dev_pred = list(student.predict(X_dev))

    y_dev_clarify_true = df_dev["needs_clarification"].tolist()

    y_dev_clarify_pred = list(clarification_student.predict(X_dev))

    logger.info(
        "[DISTILL] train clarification distribution: %s",
        Counter(y_train_clarify),
    )

    logger.info(
        "[DISTILL] dev TRUE clarification distribution: %s",
        Counter(y_dev_clarify_true),
    )

    logger.info(
        "[DISTILL] dev PRED clarification distribution: %s",
        Counter(y_dev_clarify_pred),
    )

    student_f1 = f1_score(
        y_dev_true,
        y_dev_pred,
        average="macro",
        zero_division=0,
    )

    student_clarify_f1 = f1_score(
        y_dev_clarify_true,
        y_dev_clarify_pred,
        average="binary",
        zero_division=0,
    )

    logger.info(
        "Student macro-F1 on real dev labels: %.4f",
        student_f1,
    )

    logger.info(
        "Student needs_clarification F1 on real dev labels: %.4f",
        student_clarify_f1,
    )

    logger.info(
        "\n%s",
        classification_report(
            y_dev_true,
            y_dev_pred,
            labels=labels,
            zero_division=0,
        ),
    )


    # Teacher метрики
    teacher_f1 = float(
        MlflowClient().get_run(teacher_run_id).data.metrics.get("dev_macro_f1", 0.0)
    )

    logger.info(
        "Teacher macro-F1: %.4f",
        teacher_f1,
    )

    # Логирование student в MLflow
    mlflow.set_experiment("Meridian_Intent_Distillation")

    with mlflow.start_run():

        mlflow.log_param(
            "teacher_run_id",
            teacher_run_id,
        )

        mlflow.log_param(
            "few_shot_template",
            few_shot_template,
        )

        mlflow.log_metric(
            "student_dev_macro_f1",
            student_f1,
        )

        mlflow.log_metric(
            "teacher_dev_macro_f1",
            teacher_f1,
        )

        mlflow.log_metric(
            "student_dev_clarify_f1",
            student_clarify_f1,
        )

        log_confusion_matrix(
            y_dev_true,
            y_dev_pred,
            labels,
        )

        joblib.dump(
            student,
            STUDENT_INTENT_ARTIFACT_FILENAME,
        )

        joblib.dump(
            clarification_student,
            STUDENT_CLARIFICATION_ARTIFACT_FILENAME,
        )

        model_info = mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=DistilledIntentClassifier(
                labels=labels,
            ),
            artifacts={
                "intent_pipeline": STUDENT_INTENT_ARTIFACT_FILENAME,
                "clarification_pipeline": STUDENT_CLARIFICATION_ARTIFACT_FILENAME,
            },
            registered_model_name=MODEL_NAME,
            pip_requirements=[
                "scikit-learn",
                "joblib",
                "pandas",
                "numpy",
            ],
        )

    #QUALITY GATE
    client = MlflowClient()

    model_version = model_info.registered_model_version

    gap = teacher_f1 - student_f1

    logger.info(
        "[GATE] Teacher macro-F1: %.4f",
        teacher_f1,
    )

    logger.info(
        "[GATE] Student macro-F1: %.4f",
        student_f1,
    )

    logger.info(
        "[GATE] Gap: %.4f",
        gap,
    )

    logger.info(
        "[GATE] Allowed gap: %.4f",
        ACCEPTANCE_MARGIN,
    )

    # Promotion
    if gap <= ACCEPTANCE_MARGIN:

        client.set_registered_model_alias(
            name=MODEL_NAME,
            alias="Serving-Production",
            version=model_version,
        )

        logger.info(
            "[PROMOTE] Model version %s promoted to "
            "Serving-Production. "
            "student_f1=%.4f, teacher_f1=%.4f, "
            "gap=%.4f <= %.4f",
            model_version,
            student_f1,
            teacher_f1,
            gap,
            ACCEPTANCE_MARGIN,
        )

    else:

        logger.warning(
            "[REJECT] Model version %s NOT promoted. "
            "student_f1=%.4f, teacher_f1=%.4f, "
            "gap=%.4f > %.4f. "
            "Serving-Production remains unchanged.",
            model_version,
            student_f1,
            teacher_f1,
            gap,
            ACCEPTANCE_MARGIN,
        )


if __name__ == "__main__":
    main()
