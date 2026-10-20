#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:?APP_NAME is required}"
IMAGE_NAME="${IMAGE_NAME:?IMAGE_NAME is required}"
TAG="${TAG:?TAG is required}"
DOCKERFILE_PATH="${DOCKERFILE_PATH:-Dockerfile}"
BUILD_CONTEXT_DIR="${BUILD_CONTEXT_DIR:?BUILD_CONTEXT_DIR is required (absolute path under /ci-workspace)}"
NAMESPACE="${NAMESPACE:-mlops}"
MEMORY_REQUEST="${MEMORY_REQUEST:-2Gi}"
MEMORY_LIMIT="${MEMORY_LIMIT:-4Gi}"
CPU_REQUEST="${CPU_REQUEST:-500m}"
CPU_LIMIT="${CPU_LIMIT:-2}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-1800}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-5}"
KUBECTL=/kaniko-bin/kubectl

POD_NAME="kaniko-build-${APP_NAME}-$(echo "${TAG}" | cut -c1-8)-${RANDOM}"

cat <<EOF | "${KUBECTL}" apply -n "${NAMESPACE}" -f -
apiVersion: v1
kind: Pod
metadata:
  name: ${POD_NAME}
  labels:
    app: kaniko-build
spec:
  restartPolicy: Never
  containers:
    - name: kaniko
      image: gcr.io/kaniko-project/executor:latest
      args:
        - --context=dir://${BUILD_CONTEXT_DIR}
        - --dockerfile=${DOCKERFILE_PATH}
        - --destination=${IMAGE_NAME}:${TAG}
        - --destination=${IMAGE_NAME}:latest
      resources:
        requests:
          cpu: ${CPU_REQUEST}
          memory: ${MEMORY_REQUEST}
        limits:
          cpu: "${CPU_LIMIT}"
          memory: ${MEMORY_LIMIT}
      volumeMounts:
        - name: ci-workspace
          mountPath: /ci-workspace
          readOnly: true
        - name: docker-config
          mountPath: /kaniko/.docker
          readOnly: true
  volumes:
    - name: ci-workspace
      hostPath:
        path: /opt/ci-workspace
        type: Directory
    - name: docker-config
      secret:
        secretName: kaniko-registry-creds
        items:
          - key: .dockerconfigjson
            path: config.json
EOF

echo "waiting for pod ${POD_NAME} in ns ${NAMESPACE} (up to ${MAX_WAIT_SECONDS}s)..."
PHASE=""
ITERATIONS=$((MAX_WAIT_SECONDS / POLL_INTERVAL_SECONDS))
for _ in $(seq 1 "${ITERATIONS}"); do
  PHASE="$("${KUBECTL}" get pod "${POD_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  if [ "${PHASE}" = "Succeeded" ] || [ "${PHASE}" = "Failed" ]; then
    break
  fi
  sleep "${POLL_INTERVAL_SECONDS}"
done

"${KUBECTL}" logs "${POD_NAME}" -n "${NAMESPACE}" || true

EXIT_CODE="$("${KUBECTL}" get pod "${POD_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}' 2>/dev/null || echo 1)"

"${KUBECTL}" delete pod "${POD_NAME}" -n "${NAMESPACE}" --ignore-not-found=true --wait=false >/dev/null 2>&1 || true

if [ "${PHASE}" = "Running" ] || [ "${PHASE}" = "Pending" ]; then
  echo "kaniko build pod timed out after ${MAX_WAIT_SECONDS}s while still ${PHASE} (not a build failure, pod was force-deleted mid-build) — raise MAX_WAIT_SECONDS" >&2
  exit 1
fi

if [ "${PHASE}" != "Succeeded" ] || [ "${EXIT_CODE}" != "0" ]; then
  echo "kaniko build pod failed (phase=${PHASE:-unknown}, exitCode=${EXIT_CODE})" >&2
  exit 1
fi

echo "kaniko build succeeded: ${IMAGE_NAME}:${TAG}"
