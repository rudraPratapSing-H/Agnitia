#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

REASON=$(kubectl get pod postgres-0 -n agnitia -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}' 2>/dev/null || echo "None")
EXIT_CODE=$(kubectl get pod postgres-0 -n agnitia -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}' 2>/dev/null || echo "None")
RESTARTS=$(kubectl get pod postgres-0 -n agnitia -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo "0")
PHASE=$(kubectl get pod postgres-0 -n agnitia -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")

echo "Pod:                     postgres-0 (namespace: agnitia)"
echo "Phase:                   ${PHASE}"
echo "Last Termination Reason: ${REASON:-None}"
echo "Last Exit Code:          ${EXIT_CODE:-None}"
echo "Restart Count:           ${RESTARTS:-0}"
