# frontend

Веб-интерфейс MLOps-платформы: чат с классификацией интентов (backend `serving`) и дашборд со ссылками на сервисы платформы (Gitea, ArgoCD, MLflow, Airflow, MinIO, Grafana). Next.js (App Router) + TypeScript + Tailwind, static export, раздаётся nginx. В кластере — Application `frontend` (wave 6, см. `k3s/README.md`).

## Структура

```text
src
├── app
│   ├── page.tsx           # чат
│   ├── analytics          # дашборд сервисов
│   └── layout.tsx         # sidebar и провайдеры контекста
├── components
│   ├── dialogs            # чат: ввод, ответ, история
│   ├── sidebar            # список диалогов, создание и удаление
│   └── analytics          # ServiceTile: плитка сервиса с копированием логина/пароля
└── lib
    ├── api.ts             # клиент backend: classify, listDialogs, getDialog, getDialogTurns, deleteDialog
    └── user.ts            # userId из crypto.randomUUID() в localStorage, без логина
```

## Разработка и сборка

```bash
npm install
cp .env.example .env.local  # NEXT_PUBLIC_API_URL локального backend
npm run dev                 # http://localhost:3000
npm run lint && npm run typecheck && npm run build  # build -> статический export в ./out
```

Docker (`NEXT_PUBLIC_API_URL` по умолчанию `https://api.alexshishin.ru`):

```bash
docker build -t frontend --build-arg NEXT_PUBLIC_API_URL=https://api.alexshishin.ru .
docker run -p 8080:80 frontend
```

## Особенности

- `output: "export"` — Node-рантайм в проде не нужен; `next/image` оптимизация отключена (`images.unoptimized: true`), она требует сервер
- `NEXT_PUBLIC_API_URL` зашивается в бандл на `next build` — смена адреса требует пересборки
- Backend вызывается напрямую из браузера, без BFF; CORS на стороне `serving` сужен до `https://app.alexshishin.ru`
- Типы ответа `/classify` слабые (`confidence`/`intent` опциональны) — ужесточим после лока контракта с DS
- `nginx.conf` — `try_files` с резолвом `.html`, т.к. export кладёт каждую страницу отдельным файлом

## В кластере

- `Deployment` на одну реплику, образ `git.alexshishin.ru/mlops/frontend:latest`, порт 80
- Ресурсы `100m`/`256Mi` (request=limit), readinessProbe `GET /`
- `Service` — ClusterIP, порт 80
- Сборка и выкат — по общему шаблону `ci-templates/templates/build-and-retag.yaml`
