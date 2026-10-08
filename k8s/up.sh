#!/usr/bin/env bash
# Verification command:
# kubectl get pod postgres-0 -n agnitia -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
# Should print OOMKilled after hog.sh.

set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Creating kind cluster 'agnitia'..."
if kind get clusters 2>/dev/null | grep -q "^agnitia$"; then
  echo "kind cluster 'agnitia' already exists."
else
  kind create cluster --config "${SCRIPT_DIR}/kind-config.yaml"
fi

echo "==> Applying postgres manifest..."
kubectl apply -f "${SCRIPT_DIR}/postgres.yaml"

echo "==> Waiting for postgres-0 to become ready..."
kubectl rollout status statefulset/postgres -n agnitia --timeout=120s
kubectl wait --namespace agnitia --for=condition=ready pod/postgres-0 --timeout=120s

# Sync kubeconfig to Windows profile if running in WSL
if [ -d "/mnt/c/Users" ]; then
  WIN_KUBE="/mnt/c/Users/maced/.kube"
  mkdir -p "${WIN_KUBE}" 2>/dev/null || true
  cp -f ~/.kube/config "${WIN_KUBE}/config" 2>/dev/null || true
fi

echo "==> Cluster is up and postgres-0 is ready!"
