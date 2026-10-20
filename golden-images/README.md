# golden-images

Dockerfile'ы базовых образов для компонентов k3s-кластера (`../k3s`) и тренировочного пайплайна (`../training`). Каждая папка — отдельный build-контекст с одним `Dockerfile`.

## Структура

```text
.
├── act-runner       # Gitea Act Runner + python3
├── airflow-custom   # Airflow + провайдеры kubernetes и amazon
├── training-base    # база для training: llama-cpp-python, gigaevo-core
├── postgres         # pin версии апстрима, не пушится
├── redis            # pin версии апстрима, не пушится
└── sealed-secrets   # pin версии апстрима, не пушится
```

## Образы

- `act-runner` — `docker.gitea.com/runner:2.0.1` + `python3` (apk). Раннер в режиме `shell` (`container.require_docker: false`), шаги идут прямо в ОС раннера; python3 нужен для `validate-airflow-dag.sh` из `ci-templates`. Образ `git.alexshishin.ru/mlops/act-runner:latest` задан как `runner.fullOverride`, `pullPolicy: Always`
- `airflow-custom` — `apache/airflow:3.3.1` + `providers-cncf-kubernetes==10.17.0` (для `KubernetesExecutor`) + `providers-amazon==9.5.0` (логи тасков в MinIO, `s3://airflow-logs/logs`, коннекшн `minio_s3`). Образ `git.alexshishin.ru/mlops/airflow-custom:latest` прописан в `images.airflow.repository`
- `training-base` — см. ниже

## training-base

`python:3.12-slim` + `git`, `libgomp1` (apt) + `requirements.txt` + `gigaevo-core` (pinned-коммит с GitHub, `--no-deps`). Образ `git.alexshishin.ru/mlops/training-base:latest`, от него наследуется `training/Dockerfile`.

- `git` — ставить `gigaevo-core` из GitHub по коммиту
- `libgomp1` — рантайм OpenMP для `llama-cpp-python` и `scikit-learn`
- `MAKEFLAGS="-j1"` — чтобы сборка нативных расширений не упала в OOM на раннере
- `--no-deps` у `gigaevo-core` — версии зависимостей уже зафиксированы в `requirements.txt`
- патч `evolution/mutation/context.py` — убирает пустую строку после `MUTATION_CONTEXT_METADATA_KEY`; защищён `assert` на точный текст маркера (сборка упадёт, если апстрим поменяет файл) и проверяется импортом `EvolutionEngine`

## postgres, redis, sealed-secrets

Точный pin версии апстрима без правок, теги совпадают с `image.tag` в values.yaml:

- postgres — `bitnamilegacy/postgresql:15.10.0-debian-12-r0`
- redis — `bitnamilegacy/redis:7.0.15-debian-11-r0`
- sealed-secrets — `bitnamilegacy/sealed-secrets-controller:0.31.0-debian-12-r0`

Namespace `bitnamilegacy`, не `bitnami`: под старым именем Bitnami больше не публикует версионные теги. Кластер тянет образы с `docker.io` напрямую, эти Dockerfile — только референс версии.

## Сборка

CI нет — собирается и пушится вручную:

```bash
docker build -t git.alexshishin.ru/mlops/act-runner:latest act-runner && docker push git.alexshishin.ru/mlops/act-runner:latest

docker build -t git.alexshishin.ru/mlops/airflow-custom:latest airflow-custom && docker push git.alexshishin.ru/mlops/airflow-custom:latest

docker build -t git.alexshishin.ru/mlops/training-base:latest training-base && docker push git.alexshishin.ru/mlops/training-base:latest
```


