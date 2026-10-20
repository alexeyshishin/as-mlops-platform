# as-mlops

## Документация

- [k3s](k3s/README.md) — манифесты кластера и раскатка
- [training](training/README.md) — пайплайн обучения
- [serving](serving/README.md) — сервис классификации
- [frontend](frontend/README.md) — веб-интерфейс
- [golden-images](golden-images/README.md) — базовые образы
- [ci-templates](ci-templates/README.md) — CI/CD-шаблоны

MLOps-платформа на одном k3s-кластере: полный цикл от обучения intent-классификатора для диалогового ассистента «Меридиан» до его выката и веб-интерфейса. 

Репозиторий — монорепо платформы. Обучение (Airflow + GigaEvo + дистилляция) кладёт модель в MLflow Registry, `serving` грузит её по alias, `frontend` общается с ним из браузера. Выкат — Gitea Actions → Kaniko → ретег в манифестах → sync в Argo CD.

## Стек

- **Кластер и GitOps:** k3s, Argo CD, Traefik, cert-manager, Sealed Secrets, Helm/Kustomize
- **Платформа:** Gitea (registry + Act Runner), Airflow (KubernetesExecutor), MLflow, MinIO, PostgreSQL, Redis
- **Наблюдаемость:** Prometheus, Grafana, Gatus
- **ML:** Saiga-Llama3-8B (GGUF, `llama-cpp-python`) как учитель, GigaEvo для эволюции промпта, TF-IDF + LogisticRegression как ученик (scikit-learn)
- **Serving:** Python, FastAPI, MLflow pyfunc, Redis (история диалогов)
- **Frontend:** Next.js (App Router, static export), React, TypeScript, Tailwind, nginx
- **CI/CD:** Gitea Actions, Kaniko

## Структура

```text
.
├── k3s            # манифесты кластера (Argo CD, Helm-values, ingress, секреты)
├── training       # пайплайн обучения: промпт-эволюция, дистилляция, Airflow DAG
├── serving        # FastAPI-сервис /classify поверх модели из MLflow
├── frontend       # веб-чат и дашборд сервисов (Next.js)
├── golden-images  # Dockerfile'ы базовых образов
├── ci-templates   # шаблоны и скрипты CI/CD-пайплайна
└── README.md
```

Подробности — в `README.md` каждой папки. Развёртывание начинать с `k3s/README.md`.
