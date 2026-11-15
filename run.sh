#!/usr/bin/env bash
# Start CaseNote fully offline: Bonsai 9B server (port 8080) + CaseNote app (port 8765).
# First-time setup (needs internet once): ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

if ! curl -s localhost:8080/v1/models >/dev/null 2>&1; then
  echo "Starting Bonsai 9B (PrismML) on :8080 ..."
  .venv/bin/python -m mlx_vlm.server --model models/bonsai2-9B-mlx --port 8080 > logs_bonsai.txt 2>&1 &
  for i in $(seq 1 60); do curl -s localhost:8080/v1/models >/dev/null 2>&1 && break; sleep 1; done
fi
echo "Bonsai ready. Starting CaseNote on http://localhost:8765"
(sleep 2 && open http://localhost:8765) &
exec .venv/bin/python -m uvicorn app.server:app --port 8765
