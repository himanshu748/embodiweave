#!/usr/bin/env bash
# Start FalkorDB (pinned), the single worker and the studio API. Run from the repo root.
set -e
cd "$(dirname "$0")/.."
IMG=falkordb/falkordb@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
docker start falkordb >/dev/null 2>&1 || docker run -d --name falkordb -p 6379:6379 -p 3000:3000 $IMG >/dev/null
mkdir -p logs
export PYTHONPATH=.
[ -f logs/worker.pid ] && kill "$(cat logs/worker.pid)" 2>/dev/null || true
[ -f logs/api.pid ] && kill "$(cat logs/api.pid)" 2>/dev/null || true
sleep 1
nohup .venv/bin/python -m ew.jobs >> logs/worker.log 2>&1 & echo $! > logs/worker.pid
nohup .venv/bin/uvicorn ew.api:app --host 127.0.0.1 --port "${PORT:-8000}" >> logs/api.log 2>&1 & echo $! > logs/api.pid
echo "studio: http://127.0.0.1:${PORT:-8000}"
