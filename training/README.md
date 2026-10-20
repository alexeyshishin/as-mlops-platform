# Training

Пайплайн обучения intent-классификатора для диалогового ассистента «Меридиан». Результат — модель `intent-classifier` в MLflow Registry, которую грузит `serving`.

Схема teacher/student: few-shot LLM (учитель, `Saiga-Llama3-8B` GGUF 4-бит) подбирается эволюцией промпта через GigaEvo, затем дистиллируется в CPU-модель (ученик, TF-IDF + LogisticRegression) — `serving` ограничен 768Mi RAM без GPU, LLM туда не помещается.

## Структура

```text
.
├── dags
│   └── training_dag.py              # Airflow DAG intent-classification-pipeline
├── run_gigaevo_pipeline.py          # эволюция промпта учителя, алиас Production
├── distilled_intent_classifier.py   # псевдоразметка, обучение ученика, алиас Serving-Production
├── labels.json                      # контракт 8 классов интента
├── examples.jsonl                   # базовый датасет, 160 строк
├── augmented_train.jsonl            # LLM-сгенерированные edge-кейсы, 220 строк, только train
└── Dockerfile                       # FROM git.alexshishin.ru/mlops/training-base
```

## Запуск

Расписание отключено (`schedule=None`) — DAG `intent-classification-pipeline` триггерится вручную в Airflow UI.

Граф: `start >> gigaevo_train_and_register >> distill_intent_classifier >> end`. Таймауты: 9ч на DAG, 6ч на учителя, 2ч на дистилляцию. Оба шага — `KubernetesPodOperator` в `mlops`, `requests: 6Gi` / `limits: 10Gi`.

Локально (нужны доступы к MLflow, MinIO, Redis):

```bash
python run_gigaevo_pipeline.py
python distilled_intent_classifier.py
```

## Учитель

- Инференс через `llama-cpp-python` (`LlamaEngine`) в 4-битном виде, без FP32-деквантования
- Веса — из приватного MinIO (`llm-weights/model-q4_K.gguf`) через `boto3`, с диск-кэшем на поде (`S3ModelFetcher`)
- `FewShotBatchMutationOperator` мутирует один пример, `TopNStrategy` отбирает лучших по macro-F1
- Состояние программ — в Redis (`REDIS_DB=2`, отдельно от chat-history в `serving`)
- Мутация оценивается на подвыборке (`SAMPLE_PER_CLASS=5`) через `StratifiedKFold` внутри train; `df_dev` — блайнд-сплит, используется один раз в конце
- Тёплый старт: `few_shot_template` текущей `Production`-версии из MLflow
- `needs_clarification` зануляется для всех интентов, кроме `data_catalog`, независимо от ответа LLM

## Ученик

Регистрируется в MLflow всегда, но алиас `Serving-Production` переставляется только при `teacher_f1 - student_f1 <= 0.03`; иначе в проде остаётся прежняя версия.

## Датасет

`examples.jsonl` — train/dev 16/4 на класс, `group_id` защищает от утечки одной сущности между сплитами. `labels.json` меняется синхронно с `serving/intent_actions.json`.

## Переменные окружения

Задаются в `dags/training_dag.py` (`env_vars`/`secrets` у `KubernetesPodOperator`):

- `MLFLOW_TRACKING_URI` — `http://mlflow.mlops.svc.cluster.local:5000` (вне кластера дефолт в коде — `https://mlflow.alexshishin.ru`)
- `MLFLOW_S3_ENDPOINT_URL` — `http://minio.mlops.svc.cluster.local:9000`
- `MLFLOW_TRACKING_USERNAME` / `MLFLOW_TRACKING_PASSWORD` — секрет `mlflow-basic-auth-secret`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — секрет `minio-secret`
- `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` — `redis-master.mlops.svc.cluster.local` / `6379` / `2`
- `REDIS_PASSWORD` — секрет `redis-secret`
- `LLAMA_N_THREADS` — `6` (дефолт в коде — `os.cpu_count()`)
