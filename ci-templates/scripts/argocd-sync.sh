#!/usr/bin/env bash
set -euo pipefail

ARGOCD_APP="${ARGOCD_APP:?ARGOCD_APP is required}"
ARGOCD_SERVER="${ARGOCD_SERVER:-https://argocd.alexshishin.ru}"
ARGOCD_SYNC_TOKEN="${ARGOCD_SYNC_TOKEN:?ARGOCD_SYNC_TOKEN is required}"
ARGOCD_SYNC_TOKEN="$(printf '%s' "${ARGOCD_SYNC_TOKEN}" | tr -d '\r\n ')"

echo "argocd sync token length: ${#ARGOCD_SYNC_TOKEN}"

if wget -q -O - \
  --header "Authorization: Bearer ${ARGOCD_SYNC_TOKEN}" \
  --header "Content-Type: application/json" \
  --post-data '{}' \
  "${ARGOCD_SERVER}/api/v1/applications/${ARGOCD_APP}/sync"; then
  echo ""
  echo "argocd sync triggered for ${ARGOCD_APP}"
else
  echo "argocd sync request failed (HTTP status printed above by wget)" >&2
  echo "if status is 415: Content-Type mismatch, unlikely given fixed header - re-check token value" >&2
  echo "if status is 401/403: ARGOCD_SYNC_TOKEN is wrong/expired or ci-sync lacks RBAC for this app" >&2
  exit 1
fi
