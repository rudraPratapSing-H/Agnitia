#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

echo "==> Deleting kind cluster 'agnitia'..."
kind delete cluster --name agnitia
echo "==> Cluster deleted."
