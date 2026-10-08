#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

echo "==> Deleting memory-hog job..."
kubectl delete job memory-hog -n agnitia --ignore-not-found=true

echo "==> Resetting statefulset postgres memory limit to 64Mi..."
kubectl patch statefulset postgres -n agnitia --type=json -p '[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "64Mi"}]'

echo "==> Waiting for rollout to complete..."
kubectl rollout status statefulset/postgres -n agnitia --timeout=120s
kubectl wait --namespace agnitia --for=condition=ready pod/postgres-0 --timeout=60s

echo "==> Reset complete. postgres-0 is running with 64Mi limit."
