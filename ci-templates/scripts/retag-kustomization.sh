#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:?APP_NAME is required}"
IMAGE_NAME="${IMAGE_NAME:?IMAGE_NAME is required}"
NEW_TAG="${NEW_TAG:?NEW_TAG is required}"
K3S_REPO_URL="${K3S_REPO_URL:?K3S_REPO_URL is required}"
K3S_DEPLOY_TOKEN="${K3S_DEPLOY_TOKEN:?K3S_DEPLOY_TOKEN is required}"
KUSTOMIZATION_PATH="${KUSTOMIZATION_PATH:?KUSTOMIZATION_PATH is required}"
GIT_USER_NAME="${GIT_USER_NAME:-ci-templates-bot}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-ci@alexshishin.ru}"

AUTH_URL="$(printf '%s' "${K3S_REPO_URL}" | sed "s#https://#https://x-access-token:${K3S_DEPLOY_TOKEN}@#")"

rm -rf k3s-src
git clone --depth 1 --branch main "${AUTH_URL}" k3s-src
cd k3s-src
git config user.name "${GIT_USER_NAME}"
git config user.email "${GIT_USER_EMAIL}"

patch_tag() {
  if [ ! -f "${KUSTOMIZATION_PATH}" ]; then
    echo "kustomization file ${KUSTOMIZATION_PATH} not found" >&2
    exit 1
  fi
  if grep -q "^images:" "${KUSTOMIZATION_PATH}"; then
    sed -i "s#^\( *newTag: \).*#\1${NEW_TAG}#" "${KUSTOMIZATION_PATH}"
  else
    cat >> "${KUSTOMIZATION_PATH}" <<EOF
images:
  - name: ${IMAGE_NAME}
    newTag: ${NEW_TAG}
EOF
  fi
}

for attempt in 1 2 3 4 5; do
  patch_tag
  if git diff --quiet; then
    echo "kustomization already at tag ${NEW_TAG}, nothing to commit"
    exit 0
  fi
  git add "${KUSTOMIZATION_PATH}"
  git commit -m "chore(${APP_NAME}): bump image tag to ${NEW_TAG}"
  if git push origin HEAD:main; then
    echo "pushed tag bump for ${APP_NAME} to ${NEW_TAG}"
    exit 0
  fi
  echo "push rejected, retrying (attempt ${attempt})" >&2
  git reset --hard HEAD~1
  git fetch origin main --depth 1
  git reset --hard origin/main
  sleep $(( (RANDOM % 3) + 1 ))
done

echo "failed to push after retries" >&2
exit 1
