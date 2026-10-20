import os
import json
import uuid
import random
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd
import boto3
from botocore.client import Config
import redis.asyncio as aioredis
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import mlflow
import mlflow.pyfunc
from mlflow import MlflowClient

from sklearn.metrics import f1_score, confusion_matrix
from sklearn.model_selection import StratifiedKFold

from llama_cpp import Llama

from gigaevo.evolution.engine.core import EvolutionEngine
from gigaevo.evolution.engine.config import EngineConfig
from gigaevo.evolution.mutation.base import MutationOperator, MutationSpec
from gigaevo.evolution.strategies.base import EvolutionStrategy
from gigaevo.database.redis_program_storage import RedisProgramStorage, RedisProgramStorageConfig
from gigaevo.programs.program import Program
from gigaevo.programs.program_state import ProgramState
from gigaevo.programs.metrics.context import MetricsContext, MetricSpec
from gigaevo.utils.trackers.base import LogWriter
from gigaevo.utils.metrics_tracker import MetricsTracker

logging.basicConfig(level=os.getenv("GIGAEVO_LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gigaevo_pipeline")


# Конфиги
@dataclass(frozen=True)
class S3Config:
    endpoint: str = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://minio.mlops.svc.cluster.local:9000")
    access_key: str = os.getenv("AWS_ACCESS_KEY_ID", "access_key")
    secret_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "secret_key")
    bucket: str = "llm-weights"
    key: str = "model-q4_K.gguf"
    local_dir: str = "/tmp/gguf_model"

    @property
    def local_filename(self) -> str:
        return os.path.basename(self.key)

    @property
    def local_path(self) -> str:
        return os.path.join(self.local_dir, self.local_filename)


@dataclass(frozen=True)
class LlamaConfig:
    n_threads: int = int(os.getenv("LLAMA_N_THREADS", str(os.cpu_count() or 4)))
    n_ctx: int = int(os.getenv("LLAMA_N_CTX", "2048"))
    n_batch: int = 256


HF_MODEL_ID = "IlyaGusev/saiga_llama3_8b_gguf"
SAMPLE_PER_CLASS = 5
GIGAEVO_KEY_PREFIX = "gigaevo"

S3 = S3Config()
LLAMA = LlamaConfig()

FEW_SHOT_BATCH_SIZE = 8
SEED_POPULATION_SIZE = 3

MLFLOW_EXTERNAL_TRACKING_URI = "https://mlflow.alexshishin.ru"
PRODUCTION_MODEL_NAME = "intent-classifier"
PRODUCTION_MODEL_ALIAS = "Production"


def setup_mlflow_uris() -> None:
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", MLFLOW_EXTERNAL_TRACKING_URI)
    registry_uri = os.getenv("MLFLOW_REGISTRY_URI", tracking_uri)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(registry_uri)


# S3-загрузка весов + обертка нал лламой
class S3ModelFetcher:
    """Скачивает и кэширует GGUF-веса модели из приватного MinIO."""

    def __init__(self, config: S3Config = S3):
        self._config = config

    def fetch(self) -> str:
        cfg = self._config
        os.makedirs(cfg.local_dir, exist_ok=True)
        if os.path.exists(cfg.local_path):
            logger.info("S3 cache hit: %s", cfg.local_path)
            return cfg.local_path

        logger.info("Downloading %s from bucket %s...", cfg.key, cfg.bucket)
        client = boto3.client(
            "s3",
            endpoint_url=cfg.endpoint,
            aws_access_key_id=cfg.access_key,
            aws_secret_access_key=cfg.secret_key,
            config=Config(signature_version="s3v4"),
        )
        client.download_file(cfg.bucket, cfg.key, cfg.local_path)
        logger.info("Model weights saved to %s", cfg.local_path)
        return cfg.local_path


class LlamaEngine:
    """
    Обертка над llama.cpp: загрузка квантованной (4-бит, без FP32-деквантования)
    модели, построение чат-промпта и генерация/парсинг JSON-ответа классификатора
    """

    def __init__(self, llama_config: LlamaConfig = LLAMA, s3_fetcher: Optional[S3ModelFetcher] = None):
        self._llama_config = llama_config
        self._s3_fetcher = s3_fetcher or S3ModelFetcher()
        self._llm: Optional[Llama] = None

    def load(self) -> "LlamaEngine":
        model_path = self._s3_fetcher.fetch()
        self._llm = Llama(
            model_path=model_path,
            n_ctx=self._llama_config.n_ctx,
            n_threads=self._llama_config.n_threads,
            n_batch=self._llama_config.n_batch,
            verbose=False,
        )
        return self

    @staticmethod
    def build_prompt(history, text, target_labels, few_shot_examples: str = "") -> str:
        labels_str = ", ".join(target_labels)
        system_prompt = (
            "Ты — точный классификатор намерений ассистента платформы «Меридиан» компании «Аркадия».\n"
            f"Проанализируй диалог и выбери РОВНО ОДИН интент из списка: [{labels_str}].\n\n"
            "ОПРЕДЕЛЕНИЯ КЛАССОВ:\n"
            "- greeting: приветствие или прощание без рабочей задачи.\n"
            "- gratitude: благодарность или сообщение о завершении помощи без нового вопроса.\n"
            "- capabilities: вопрос о САМОМ АССИСТЕНТЕ — что «ты» умеешь, кто ты, какие у тебя функции, ограничения, поддерживаемые задачи. Речь про бота, НЕ про продукт или данные.\n"
            "- support: явная просьба подключить живого оператора, человека или специалиста поддержки.\n"
            "- data_catalog: поиск ОБЪЕКТОВ данных в каталоге (витрины, кубы, таблицы, поля, представления) по названию, атрибуту или владельцу. НЕ объяснение темы и НЕ вычисление чисел.\n"
            "- pivot_table: построить или изменить числовую сводную/таблицу с агрегированными значениями.\n"
            "- no_rag: ответ полностью содержится в предыдущих репликах истории — надо повторить, сократить, перевести, переформатировать, процитировать или извлечь уже сказанное. Новые внешние знания НЕ требуются.\n"
            "- technical: содержательный вопрос о системе, продукте, методике расчёта, регламенте или ошибке, требующий НОВОГО объяснения, которого ещё нет в истории.\n\n"
            "ПОРЯДОК РЕШЕНИЯ:\n"
            "1. Если запрос ссылается на уже сказанное в истории и не требует новых фактов — no_rag.\n"
            "2. Если спрашивают про возможности или личность самого ассистента («ты») — capabilities.\n"
            "3. Если просят найти объекты данных — data_catalog; построить числа — pivot_table; позвать человека — support.\n"
            "4. Иначе, для содержательного предметного вопроса — technical. Technical остаётся классом по умолчанию при истинном сомнении между support/technical, pivot_table/technical или no_rag/technical.\n\n"
            "УТОЧНЕНИЕ: если пользователь просит «информацию» или «сведения» о данных, витринах или кубах, но неясно — нужны объекты каталога ИЛИ объяснение темы — выбирай data_catalog и ставь 'needs_clarification': true. Во всех остальных случаях флаг строго false.\n\n"
            "Выведи только валидный JSON и больше ничего. Не пиши пояснений. Формат ответа:\n"
            "{\"intent\": \"название_интента\", \"needs_clarification\": true/false}"
        )

        prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n{system_prompt}"
        if few_shot_examples:
            prompt += f"\nВот эталонные примеры:\n{few_shot_examples}"
        prompt += "<|eot_id|>"

        if isinstance(history, list):
            for turn in history:
                role = "user" if turn.get("role") == "user" else "assistant"
                prompt += f"<|start_header_id|>{role}<|end_header_id|>\n{turn.get('content', '')}<|eot_id|>"

        prompt += f"<|start_header_id|>user<|end_header_id|>\n{text}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
        return prompt

    def _generate_raw(self, prompt: str) -> str:
        output = self._llm(prompt, max_tokens=50, temperature=0.01, stop=["<|eot_id|>"])
        gen_text = output["choices"][0]["text"].strip()
        return gen_text.replace("```json", "").replace("```", "").strip()

    def classify_intent(self, history, text, labels: List[str], few_shot_examples: str = "", default: str = "technical") -> dict:
        """Генерирует предсказание интента и гарантирует валидный лейбл на выходе"""
        prompt = self.build_prompt(history, text, labels, few_shot_examples)
        gen_text = self._generate_raw(prompt)

        try:
            parsed = json.loads(gen_text)
            intent = parsed.get("intent", default)
            needs_clarification = bool(parsed.get("needs_clarification", False))
        except Exception:
            intent, needs_clarification = default, False

        if intent not in labels:
            intent = default

        needs_clarification = needs_clarification and intent == "data_catalog"
        return {"intent": intent, "needs_clarification": needs_clarification}


class LlamaMeridianClassifier(mlflow.pyfunc.PythonModel):
    """MLflow pyfunc-обертка для инференса классификатора"""

    def __init__(self, model_id: str, gguf_filename: str, labels: List[str], few_shot_context: str = ""):
        self.model_id = model_id
        self.gguf_filename = gguf_filename
        self.labels = labels
        self.few_shot_context = few_shot_context
        self._engine: Optional[LlamaEngine] = None

    def load_context(self, context):
        self._engine = LlamaEngine().load()

    def predict(self, context, model_input):
        return [
            self._engine.classify_intent(
                row.get("history", []), row.get("text", ""), self.labels, self.few_shot_context
            )
            for _, row in model_input.iterrows()
        ]


# Данные
def load_datasets():
    with open("labels.json", "r", encoding="utf-8") as f:
        labels_schema = json.load(f)
    labels = [item["id"] for item in labels_schema["labels"]]
    schema_version = labels_schema.get("schema_version", "unknown")

    df_orig = pd.read_json("examples.jsonl", lines=True, encoding="utf-8")
    df_aug = pd.read_json("augmented_train.jsonl", lines=True, encoding="utf-8")

    # df_train используется только для мутаций; df_dev — единственный слепой
    # (защита от Data Leakage)
    df_train = pd.concat([df_orig[df_orig["split"] == "train"], df_aug], ignore_index=True)
    df_dev = df_orig[df_orig["split"] == "dev"]
    return labels, schema_version, df_train, df_dev, df_aug


def stratified_sample(df: pd.DataFrame, label_col: str, per_class: int, random_state: int = 42) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    parts = [group.sample(n=min(len(group), per_class), random_state=random_state) for _, group in df.groupby(label_col)]
    return pd.concat(parts, ignore_index=True)



# Фитнес-функция для GigaEvo

def _score_fold(engine: LlamaEngine, val_fold: pd.DataFrame, labels: List[str], few_shot_context: str) -> float:
    y_pred = [
        engine.classify_intent(row["history"], row["text"], labels, few_shot_context)["intent"]
        for _, row in val_fold.iterrows()
    ]
    return f1_score(val_fold["intent"].tolist(), y_pred, average="macro", zero_division=0)


def evaluate_prompt_chromosome(engine: LlamaEngine, df_train: pd.DataFrame, labels: List[str], chromosome: dict) -> float:
    few_shot_context = chromosome["few_shot_template"]
    train_sample = stratified_sample(df_train, "intent", SAMPLE_PER_CLASS)

    min_per_class = train_sample["intent"].value_counts().min()
    if min_per_class < 2:
        # StratifiedKFold требует n_splits >= 2 на каждый класс; при редких классах
        # (если после сэмплинга только 1 пример) CV невозможен.
        logger.warning(
            "Class with only %d example(s) after sampling — skipping StratifiedKFold, scoring on full sample.",
            min_per_class,
        )
        return _score_fold(engine, train_sample, labels, few_shot_context)

    n_splits = min(3, min_per_class)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    fold_scores = [
        _score_fold(engine, train_sample.iloc[val_idx], labels, few_shot_context)
        for _, val_idx in skf.split(train_sample, train_sample["intent"])
    ]
    return float(np.mean(fold_scores))


#логгер, стратегия отбора, оператор мутации
class NoOpLogWriter(LogWriter):
    def bind(self, *args, **kwargs):
        return self

    def scalar(self, *args, **kwargs):
        return None

    def hist(self, *args, **kwargs):
        return None

    def text(self, *args, **kwargs):
        return None

    def close(self):
        return None


class TopNStrategy(EvolutionStrategy):
    def __init__(self):
        self._programs = {}

    async def add(self, program):
        self._programs[program.id] = program
        return True

    async def select_elites(self, total):
        ranked = sorted(
            self._programs.values(),
            key=lambda p: p.metrics.get("macro_f1", float("-inf")),
            reverse=True,
        )
        return ranked[:total]

    async def get_program_ids(self):
        return list(self._programs.keys())


def format_few_shot_example(row: pd.Series) -> str:
    answer = json.dumps(
        {"intent": row["intent"], "needs_clarification": bool(row["needs_clarification"])},
        ensure_ascii=False,
    )
    return f"### Пример:\nЗапрос: {row['text']}\nОтвет: {answer}"


def sample_row_ids(df_train: pd.DataFrame, batch_size: int) -> List[str]:
    return df_train["id"].sample(n=min(batch_size, len(df_train))).tolist()


def swap_one_row_id(df_train: pd.DataFrame, row_ids: List[str]) -> List[str]:
    if not row_ids:
        return sample_row_ids(df_train, FEW_SHOT_BATCH_SIZE)
    all_ids = df_train["id"]
    candidates = all_ids[~all_ids.isin(row_ids)]
    if candidates.empty:
        return list(row_ids)
    new_id = candidates.sample(n=1).iloc[0]
    drop_index = random.randrange(len(row_ids))
    new_row_ids = list(row_ids)
    new_row_ids[drop_index] = new_id
    return new_row_ids


def build_few_shot_prompt_from_ids(df_train: pd.DataFrame, row_ids: List[str]) -> str:
    rows = df_train.set_index("id", drop=False).loc[row_ids]
    return "\n".join(format_few_shot_example(row) for _, row in rows.iterrows())


class FewShotBatchMutationOperator(MutationOperator):
    def __init__(self, df_train: pd.DataFrame, batch_size: int = FEW_SHOT_BATCH_SIZE):
        self._df_train = df_train
        self._batch_size = batch_size
        self._row_ids_by_code: dict = {}

    def sample_fresh_code(self) -> str:
        row_ids = sample_row_ids(self._df_train, self._batch_size)
        code = build_few_shot_prompt_from_ids(self._df_train, row_ids)
        self._row_ids_by_code[code] = row_ids
        return code

    async def mutate_single(self, selected_parents):
        parent_row_ids = self._row_ids_by_code.get(selected_parents[0].code)
        if not parent_row_ids:
            code = self.sample_fresh_code()
        else:
            new_row_ids = swap_one_row_id(self._df_train, parent_row_ids)
            code = build_few_shot_prompt_from_ids(self._df_train, new_row_ids)
            self._row_ids_by_code[code] = new_row_ids
        return MutationSpec(code=code, parents=selected_parents, name=f"swap-{uuid.uuid4().hex[:8]}")


def build_redis_url() -> str:
    host = os.environ["REDIS_HOST"]
    port = os.environ["REDIS_PORT"]
    db = os.environ["REDIS_DB"]
    password = os.environ.get("REDIS_PASSWORD", "")
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{host}:{port}/{db}"


async def clear_key_prefix(redis_url: str, key_prefix: str) -> int:
    client = aioredis.Redis.from_url(redis_url, decode_responses=True)
    cursor, deleted, pattern = 0, 0, f"{key_prefix}:*"
    while True:
        cursor, keys = await client.scan(cursor=cursor, match=pattern, count=500)
        if keys:
            deleted += await client.delete(*keys)
        if cursor == 0:
            break
    await client.aclose()
    return deleted

async def fitness_worker(
    storage: RedisProgramStorage,
    engine: LlamaEngine,
    df_train: pd.DataFrame,
    labels: List[str],
    score_cache: Optional[dict] = None,
):
    if score_cache is None:
        score_cache = {}
    while True:
        fresh = await storage.get_all_by_status(ProgramState.FRESH.value)
        batch_size = len(fresh)
        for i, program in enumerate(fresh, start=1):
            generation = program.metadata.get("iteration", "seed")
            logger.debug(
                "[fitness_worker] gen=%s scoring mutant %d/%d (program_id=%s)",
                generation, i, batch_size, program.id,
            )
            program.state = ProgramState.DAG_PROCESSING_STARTED
            await storage.atomic_state_transition(
                program, ProgramState.FRESH.value, ProgramState.DAG_PROCESSING_STARTED.value
            )
            cached_score = score_cache.get(program.code)
            try:
                if cached_score is not None:
                    score = cached_score
                else:
                    score = await asyncio.to_thread(
                        evaluate_prompt_chromosome, engine, df_train, labels, {"few_shot_template": program.code}
                    )
                    score_cache[program.code] = score
            except Exception:
                logger.exception("evaluate_prompt_chromosome failed for program %s — scoring as 0.0", program.id)
                score = 0.0
            finally:
                program.add_metrics({"macro_f1": score})
                program.state = ProgramState.DAG_PROCESSING_COMPLETED
                await storage.atomic_state_transition(
                    program, ProgramState.DAG_PROCESSING_STARTED.value, ProgramState.DAG_PROCESSING_COMPLETED.value
                )
            logger.debug(
                "[fitness_worker] gen=%s scored mutant %d/%d (program_id=%s) macro_f1=%.4f cache_hit=%s",
                generation, i, batch_size, program.id, score, cached_score is not None,
            )
        await asyncio.sleep(1.0)


def fetch_production_few_shot_template() -> Optional[str]:
    try:
        client = MlflowClient()
        model_version = client.get_model_version_by_alias(PRODUCTION_MODEL_NAME, PRODUCTION_MODEL_ALIAS)
        run = client.get_run(model_version.run_id)
        template = run.data.params.get("few_shot_template")
        if not template:
            logger.warning("Production run %s has no few_shot_template param — skipping warm start.", model_version.run_id)
            return None
        logger.info("Warm start: loaded few_shot_template from %s v%s.", PRODUCTION_MODEL_NAME, model_version.version)
        return template
    except Exception:
        logger.warning("No Production model in MLflow (or fetch failed) — starting evolution from scratch.", exc_info=True)
        return None


async def run_evolution(
    engine: LlamaEngine, df_train: pd.DataFrame, labels: List[str], warm_start_template: Optional[str] = None
) -> Program:
    redis_url = build_redis_url()
    await clear_key_prefix(redis_url, GIGAEVO_KEY_PREFIX)

    storage = RedisProgramStorage(RedisProgramStorageConfig(redis_url=redis_url, key_prefix=GIGAEVO_KEY_PREFIX))
    strategy = TopNStrategy()
    mutation_operator = FewShotBatchMutationOperator(df_train)
    writer = NoOpLogWriter()
    metrics_context = MetricsContext(
        specs={"macro_f1": MetricSpec(description="dev macro F1", higher_is_better=True, is_primary=True)}
    )
    metrics_tracker = MetricsTracker(storage=storage, metrics_context=metrics_context, writer=writer)
    engine_config = EngineConfig(
        max_generations=4,
        max_elites_per_generation=3,
        max_mutations_per_generation=3,
        generation_timeout=2000.0,
    )
    evolution_engine = EvolutionEngine(
        storage=storage,
        strategy=strategy,
        mutation_operator=mutation_operator,
        config=engine_config,
        writer=writer,
        metrics_tracker=metrics_tracker,
    )

    seed_codes = [warm_start_template] if warm_start_template else []
    while len(seed_codes) < SEED_POPULATION_SIZE:
        seed_codes.append(mutation_operator.sample_fresh_code())

    for seed_code in seed_codes:
        await storage.add(Program(id=str(uuid.uuid4()), code=seed_code, metrics={}, metadata={}))

    worker_task = asyncio.create_task(fitness_worker(storage, engine, df_train, labels))
    await evolution_engine.run()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    best = (await strategy.select_elites(total=1))[0]

    await storage.close()
    await clear_key_prefix(redis_url, GIGAEVO_KEY_PREFIX)
    return best


# финальная оценка и регистрация в registry

def evaluate_on_dev(engine: LlamaEngine, df_dev: pd.DataFrame, labels: List[str], few_shot_context: str) -> tuple:
    preds = [
        engine.classify_intent(row["history"], row["text"], labels, few_shot_context)["intent"]
        for _, row in df_dev.iterrows()
    ]
    dev_f1 = f1_score(df_dev["intent"].tolist(), preds, average="macro", zero_division=0)
    return dev_f1, preds


def log_confusion_matrix(y_true: List[str], y_pred: List[str], labels: List[str]) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 0.6), max(6, len(labels) * 0.6)))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=90)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted intent")
    ax.set_ylabel("True intent")
    ax.set_title("Dev confusion matrix")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                     color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=7)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()

    mlflow.log_figure(fig, "confusion_matrix.png")
    plt.close(fig)


def register_production_model(model_id: str, gguf_filename: str, labels: List[str], best_program: Program,
                                dev_f1: float, dataset_version: str, dev_y_true: List[str], dev_y_pred: List[str]) -> None:
    mlflow.set_experiment("Meridian_Intent_GigaEvo")
    with mlflow.start_run():
        mlflow.log_params({"few_shot_template": best_program.code, "gigaevo_program_id": best_program.id})
        mlflow.log_metric("dev_macro_f1", dev_f1)
        mlflow.log_metric("gigaevo_train_macro_f1", best_program.metrics.get("macro_f1", 0.0))
        mlflow.set_tag("dataset_version", dataset_version)
        mlflow.set_tag(
            "gigaevo_core_classes",
            "EvolutionEngine,ProgramStateManager,RedisProgramStorage,Program,ProgramState,MetricsTracker,EngineConfig",
        )
        log_confusion_matrix(dev_y_true, dev_y_pred, labels)

        pyfunc_model = LlamaMeridianClassifier(
            model_id=model_id,
            gguf_filename=gguf_filename,
            labels=labels,
            few_shot_context=best_program.code,
        )
        model_info = mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=pyfunc_model,
            registered_model_name=PRODUCTION_MODEL_NAME,
            pip_requirements=["llama-cpp-python", "pandas", "numpy"],
        )

        MlflowClient().set_registered_model_alias(
            name=PRODUCTION_MODEL_NAME,
            alias=PRODUCTION_MODEL_ALIAS,
            version=model_info.registered_model_version,
        )


def main():
    setup_mlflow_uris()
    warm_start_template = fetch_production_few_shot_template()

    labels, schema_version, df_train, df_dev, df_aug = load_datasets()

    logger.info("Loading quantized GGUF (llama.cpp, %d threads): %s", LLAMA.n_threads, S3.local_filename)
    engine = LlamaEngine().load()

    best_program = asyncio.run(run_evolution(engine, df_train, labels, warm_start_template))

    dev_f1, dev_preds = evaluate_on_dev(engine, df_dev, labels, best_program.code)
    dataset_version = f"labels-{schema_version}+aug{len(df_aug)}"

    register_production_model(
        HF_MODEL_ID, S3.local_filename, labels, best_program, dev_f1, dataset_version,
        dev_y_true=df_dev["intent"].tolist(), dev_y_pred=dev_preds,
    )
    logger.info("Evolution finished. Model registered as Production in MLflow.")


if __name__ == "__main__":
    main()