# ci-templates

Переиспользуемые CI/CD-шаблоны для Gitea Actions. Репозитории платформы (`frontend`, `serving`, `training`) клонируют этот репозиторий в раннере и запускают его скрипты как шаги своего workflow. Раннер — Gitea Act Runner (`runs-on: shell`), registry — Gitea (`git.alexshishin.ru`).

## Структура

```text
.
├── templates
│   ├── build-and-retag.yaml       # push в main: сборка, пуш образа, ретег, sync
│   └── validate-dags.yaml         # push с изменением *.py: проверка Airflow DAG
└── scripts
    ├── kaniko-build-push.sh       # сборка и пуш образа Kaniko-подом
    ├── retag-kustomization.sh     # newTag в kustomization.yaml репозитория манифестов
    ├── argocd-sync.sh             # sync Application в ArgoCD через API
    └── validate-airflow-dag.sh    # py_compile для каждого *.py в DAG_DIR
```

`templates/` — заготовки для `.gitea/workflows`, `CHANGE_ME` заменить на реальные значения. Шаблоны вызывают скрипты из `ci-templates-src/scripts/`, а не копируют их, чтобы не расходиться по копиям.

## Скрипты

Все берут параметры из env и падают с понятной ошибкой, если обязательная переменная не задана — это их интерфейс, от конкретного репозитория они не зависят.

- `kaniko-build-push.sh` — отдельный Kaniko-под, без доступа к Docker-демону хоста. Контекст — read-only `hostPath` `/opt/ci-workspace` (раннер и под на одной ноде), креды push — секрет `kaniko-registry-creds`. Пушит теги `TAG` и `latest`, под удаляется после сборки в любом случае
- `retag-kustomization.sh` — клонирует репозиторий манифестов (`K3S_REPO_URL`), правит `newTag`, пушит коммит в `main` (`x-access-token` с деплой-токеном в URL). При конфликте с параллельным джобом ретраится до 5 раз с `git reset --hard origin/main`
- `argocd-sync.sh` — sync через API (`ARGOCD_SYNC_TOKEN`). Токен чистить от `\r\n` и пробелов — частая причина 401
- `validate-airflow-dag.sh` — падает при синтаксической ошибке, предупреждает, если нет `dag_id`

## Подключение

```bash
mkdir -p .gitea/workflows
cp templates/build-and-retag.yaml .gitea/workflows/
# заменить CHANGE_ME на имя образа и путь до kustomization.yaml в k3s
```

Секреты в целевом репозитории (Settings → Actions → Secrets):

- `K3S_DEPLOY_TOKEN` — push в репозиторий манифестов
- `ARGOCD_SYNC_TOKEN` — sync в ArgoCD

`kaniko-registry-creds` — Kubernetes Secret в `mlops`, создаётся отдельно (см. `k3s/README.md`).

Локально:

```bash
DAG_DIR=dags bash scripts/validate-airflow-dag.sh
```
