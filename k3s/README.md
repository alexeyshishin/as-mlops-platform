# MLOps

## Установка K3s и kubeconfig

```bash
ssh <user>@<VM_IP>
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.36.4+k3s1" sh -
k3s kubectl get nodes
```

```bash
ssh root@200.169.183.169 "cat /etc/rancher/k3s/k3s.yaml" > ~/.kube/mlops.yaml
sed -i '' "s/127.0.0.1/200.169.183.169/; s/default/mlops/g" ~/.kube/mlops.yaml
chmod 600 ~/.kube/mlops.yaml
export KUBECONFIG=~/.kube/mlops.yaml
kubectl get nodes
```

## Раскатка кластера

Манифесты ArgoCD берёт с GitHub, не из своей Gitea — курица-яйцо: не стянуть то, что сам разворачивает. Gitea в кластере — только Container Registry и Act Runner (CI).

```bash
kubectl apply -k namespaces/dev
kubectl apply -k apps/infra/traefik/dev
```

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm install argocd argo/argo-cd -n argocd -f argocd/values-dev.yaml
kubectl -n argocd get pods -w
```

```bash
cp argocd/secrets/argocd-admin-secret.template.yaml argocd/secrets/argocd-admin-secret.yaml
htpasswd -nbBC 10 "" "<пароль admin>" | tr -d ':\n' | sed 's/^\$2y/\$2a/'
htpasswd -nbBC 10 "" "<пароль readonly>" | tr -d ':\n' | sed 's/^\$2y/\$2a/'
date -u +"%Y-%m-%dT%H:%M:%SZ"
# вписать хэши и timestamp в argocd/secrets/argocd-admin-secret.yaml (НЕ в template — тот в git, только placeholder)
kubectl apply -f argocd/secrets/argocd-admin-secret.yaml
```

Repo-URL уже финальный, менять не нужно.

```bash
kubectl apply -f argocd/bootstrap/root.yaml
kubectl -n argocd get applications -w
```

Дождаться живого sealed-secrets-controller (нужен для kubeseal):

```bash
kubectl -n kube-system get pods -w   # sealed-secrets-controller -> Running
```

Шаблоны + webserver-secret-key:

```bash
cd manual/secrets/dev
cp template-postgres.yaml postgres.yaml
cp template-redis.yaml redis.yaml
cp template-minio.yaml minio.yaml
cp template-gitea.yaml gitea.yaml
cp template-gitea-db-passwd.yaml gitea-db-passwd.yaml
cp template-gitea-act-runner.yaml gitea-act-runner.yaml
cp template-mlflow.yaml mlflow.yaml
cp template-airflow.yaml airflow.yaml
cp template-minio-jury.yaml minio-jury.yaml
cp template-airflow-jury.yaml airflow-jury.yaml
cp template-mlflow-jury.yaml mlflow-jury.yaml
cp template-grafana.yaml grafana.yaml
cp template-grafana-jury.yaml grafana-jury.yaml
openssl rand -hex 32
```

Вписать `REPLACE_WITH_*` в каждом файле (template-* не трогать — это плейсхолдеры в git). `openssl rand -hex 32` — значение для `airflow-webserver-secret.webserver-secret-key`.

`airflow-admin-secret` и `kaniko-registry-creds` — без шаблона, создаются напрямую:

```bash
kubectl create secret generic airflow-admin-secret -n mlops --dry-run=client -o yaml \
  --from-literal=username=<admin-логин> --from-literal=password=<admin-пароль> > airflow-admin.yaml

kubectl create secret docker-registry kaniko-registry-creds -n mlops --dry-run=client -o yaml \
  --docker-server=<registry> --docker-username=<user> --docker-password=<pass> > kaniko-registry-creds.yaml
```

Версия kubeseal — как у контроллера: `0.31.0`.

```bash
brew install kubeseal
kubeseal --version

for f in postgres redis minio gitea gitea-db-passwd gitea-act-runner mlflow airflow minio-jury airflow-jury mlflow-jury airflow-admin kaniko-registry-creds; do
  kubeseal --format=yaml \
    --controller-name=sealed-secrets-controller \
    --controller-namespace=kube-system \
    < "$f.yaml" > "sealed/$f.yaml"
  rm "$f.yaml"
done
kubeseal --format=yaml \
  --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system \
  -n monitoring \
  < grafana.yaml > sealed/grafana.yaml
rm grafana.yaml
kubeseal --format=yaml \
  --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system \
  -n monitoring \
  < grafana-jury.yaml > sealed/grafana-jury.yaml
rm grafana-jury.yaml
cd -
```

`sealed/kustomization.yaml` уже содержит все ресурсы — проверить, что `$f.yaml` там есть. `grafana-*-secret` живут в `monitoring` (зашито в шаблонах), флаг `-n monitoring` у kubeseal это дублирует.

Запушить sealed-секреты в GitHub — wave 1 (`secrets`) тянет их из `manual/secrets/dev/sealed`, локальный `kubectl apply` не поможет:

```bash
git add manual/secrets/dev/sealed
git commit -m "chore(secrets): seal dev secrets"
git push
kubectl -n argocd get applications -w
```

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```

```bash
kubectl get certificate -n cert-manager
```

Настроить Gitea (`https://git.alexshishin.ru`, логин из `manual/secrets/dev/gitea.yaml`): включить Container Registry, создать репозиторий (не для GitOps), запушить туда `MLOps/`.

Зарегистрировать Act Runner (Site Administration → Actions → Runners → токен):

```bash
cd manual/secrets/dev
cp template-gitea-act-runner.yaml gitea-act-runner.yaml
# вписать токен
kubeseal --format=yaml \
  --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system \
  < gitea-act-runner.yaml > sealed/gitea-act-runner.yaml
rm gitea-act-runner.yaml
cd -
git add manual/secrets/dev/sealed/gitea-act-runner.yaml
git commit -m "chore(secrets): reseal gitea act runner token"
git push
```

## Проверка манифестов

```bash
kustomize build namespaces/dev
kustomize build argocd/overlays/dev
kustomize build manual/secrets/dev/sealed
kustomize build ingress/main/dev
kustomize build ingress/main/argocd-transport
kustomize build ingress/main-tls/dev
kustomize build apps/infra/traefik/dev
kustomize build apps/platform/serving/dev
kustomize build apps/platform/frontend/dev
```

Dry-run:

```bash
python3 scripts/dry-run-cluster.py
```

## Sync-wave

0 — sealed-secrets-controller, cert-manager
1 — secrets
2 — ingress-tls, postgres, redis, minio
3 — gitea
4 — gitea-act-runner
5 — mlflow, airflow
6 — serving, frontend
7 — ingress-main
8 — prometheus-grafana

## Мониторинг

`prometheus-grafana` (`kube-prometheus-stack`) — Prometheus + Grafana в `monitoring`, создаётся заранее (`kubectl apply -k namespaces/dev`, нужен к wave 1 для grafana-секретов). В скоупе только метрики: Alertmanager, Loki/promtail и алерты `kubeControllerManager`/`kubeScheduler`/`kubeEtcd`/`kubeProxy` выключены — на k3s этих эндпоинтов нет. Его CRD превышают лимит `last-applied-configuration` (262144 байт) — единственный Application с `syncOptions: [CreateNamespace=true, ServerSideApply=true]`.

Grafana — единственная с публичным ingress (`https://grafana.alexshishin.ru`). Роут в `mlops`, сервис — в `monitoring`: нужны `namespace: monitoring` в IngressRoute и `allowCrossNamespace: true` в Traefik. Read-only логин для жюри — `jury`/`jury_pass` (роль `Viewer`): чарт без декларативного multi-user, аккаунт создаёт PostSync Job (`apps/infra/prometheus-grafana/post-sync/job.yaml`) через Grafana Admin API, как `mlflow-jury-secret`.

Prometheus — только `kubectl port-forward`, без ingress/TLS; дефолтные alert-правила считаются и видны в UI, но никуда не маршрутизируются (Alertmanager не развёрнут).

## Секреты

`mlops`:
- `postgres-secret` — postgres-user, postgres-password
- `redis-secret` — redis-password
- `minio-secret` — rootUser, rootPassword, root-user, root-password
- `gitea-secret`, `mlflow-basic-auth-secret` — username, password
- `gitea-db-passwd` — database
- `gitea-act-runner-secret` — token
- `airflow-postgres-secret`, `airflow-redis-secret`, `airflow-minio-conn-secret` — connection
- `airflow-webserver-secret` — webserver-secret-key; `airflow-fernet-key` — fernet-key; `airflow-api-secret-key` — api-secret-key; `airflow-jwt-secret` — jwt-secret
- `airflow-admin-secret` — username, password (без шаблона, вручную)
- `mlflow-jury-secret`, `airflow-jury-secret` — username, password (read-only)
- `minio-jury-secret` — password (read-only)
- `kaniko-registry-creds` — .dockerconfigjson (docker-registry, без шаблона, вручную; imagePullSecrets для gitea-act-runner/kaniko)

`monitoring`:
- `grafana-admin-secret` — username, password
- `grafana-jury-secret` — username, password (роль Viewer, создаётся PostSync Job'ом)

`argocd`:
- `argocd-secret` — admin.{password,passwordMtime}, accounts.readonly.{password,passwordMtime}

Postgres/redis пароли в `airflow.yaml` должны совпадать с `postgres.yaml`/`redis.yaml`.
