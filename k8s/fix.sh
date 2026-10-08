#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

echo "==> Patching statefulset postgres memory limit to 256Mi..."
kubectl patch statefulset postgres -n agnitia --type=json -p '[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "256Mi"}]'

echo "==> Waiting for rollout to complete..."
kubectl rollout status statefulset/postgres -n agnitia --timeout=120s
kubectl wait --namespace agnitia --for=condition=ready pod/postgres-0 --timeout=60s

echo "==> postgres-0 patched to 256Mi and ready!"
