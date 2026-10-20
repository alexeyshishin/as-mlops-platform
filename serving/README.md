# Serving

FastAPI-сервис классификации intent пользовательских реплик: обёртка над моделью из MLflow Registry, с историей диалогов в Redis. В кластере — Argo CD Application `serving` (namespace `mlops`, sync-wave 6: после mlflow/airflow, до ingress-main).

Фаза 1: контракт `/classify` ещё не залочен с DS. Эндпоинт — тонкая обёртка вокруг `mlflow.pyfunc`: зовёт `model.predict()` непрозрачно и отдаёт результат как есть, без argmax/порогов/fallback. Схема ответа, пороги и эмбеддер — Фаза 2.

## Структура

```text
.
├── tests                  # pytest, MLflow/boto3/Redis замоканы
├── main.py                # FastAPI-приложение и эндпоинты
├── model.py               # обёртка Model над mlflow.pyfunc
├── history.py             # Redis-обвязка истории диалогов
├── config.py              # конфиг из env
├── intent_actions.json    # карта intent → действие (route)
├── requirements.txt
└── Dockerfile
```

- `main.py` — `lifespan` грузит модель при старте; ошибку логирует и проглатывает: под остаётся `not-ready`, но не падает. CORS сужен до `https://app.alexshishin.ru`, методов `GET/POST/DELETE`, без credentials
- `model.py` — резолвит модель по `MODEL_NAME@MODEL_ALIAS`, артефакт грузит из MinIO; от клиента принимается только alias. `dataset_version` — из тега версии модели, иначе из тегов рана
- `history.py` — реплики (`chat:{session_id}`), intents (`chat:{session_id}:intents`), метаданные (`dialog:meta:{session_id}`), per-user счётчик и sorted-set индекс. Без `session_id` — no-op (stateless), без `user_id` ключи в общем неймспейсе. TTL 24 часа, скользящий
- `intent_actions.json` — синхронизируется вручную с `training/labels.json`, риск дрифта

## Эндпоинты

- `GET /health` — liveness, не зависит от модели
- `GET /ready` — 503, пока модель не загружена, затем 200
- `POST /classify` — `{session_id?, user_id?, history?, text}` → `{intent?, confidence?, needs_clarification?, route?}` (только не-`None` поля). Реплика пишется в Redis до вызова модели; для неизвестного intent `route` отсутствует (не 500). Каждый вызов логирует JSON: `intent`, `confidence`, `model_version`, `dataset_version`, `latency_ms`
- `GET /dialogs?user_id=` — последние 20 диалогов (лимит захардкожен)
- `GET /dialogs/{session_id}` — метаданные диалога или 404
- `GET /dialogs/{session_id}/turns` — реплики попарно с intent, или 404
- `DELETE /dialogs/{session_id}?user_id=` — 204 или 404

## Запуск

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Тесты (`pytest`, `fakeredis`, `httpx` в `requirements.txt` не входят, ставить отдельно):

```bash
pytest tests/
```

Docker:

```bash
docker build -t serving .
docker run -p 8000:8000 \
  -e MLFLOW_TRACKING_URI=http://mlflow.mlops.svc.cluster.local:5000 \
  -e REDIS_HOST=redis-master.mlops.svc.cluster.local \
  serving
```

Смена версии модели = промоут alias в MLflow Registry + рестарт пода, без пересборки образа.

## Переменные окружения

- `MLFLOW_TRACKING_URI` — `http://mlflow.mlops.svc.cluster.local:5000`
- `MLFLOW_TRACKING_USERNAME` / `MLFLOW_TRACKING_PASSWORD` — секрет `mlflow-basic-auth-secret`
- `MODEL_NAME` — `intent-classifier`
- `MODEL_ALIAS` — `Serving-Production`
- `MLFLOW_S3_ENDPOINT_URL` — `http://minio.mlops.svc.cluster.local:9000`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — секрет `minio-secret`
- `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` — `redis-master.mlops.svc.cluster.local` / `6379` / `1`
- `REDIS_PASSWORD` — секрет `redis-secret`
- `DEBUG` — `false`
