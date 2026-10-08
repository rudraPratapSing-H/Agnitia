#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Removing any existing memory-hog job..."
kubectl delete job memory-hog -n agnitia --ignore-not-found=true

echo "==> Applying memory-hog job..."
kubectl apply -f "${SCRIPT_DIR}/memory-hog.yaml"

echo "==> Waiting for memory-hog to trigger OOM on postgres-0..."
for i in $(seq 1 30); do
  REASON=$(kubectl get pod postgres-0 -n agnitia -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}' 2>/dev/null || true)
  if [ "${REASON}" = "OOMKilled" ]; then
    echo "==> postgres-0 was OOMKilled!"
    exit 0
  fi
  sleep 1
done

echo "==> Hog applied. Run ./status.sh to inspect pod termination status."
