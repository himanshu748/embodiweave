#!/usr/bin/env bash
# Run from the checkout. One named database, one worker, loopback-only API.
set -euo pipefail
cd "$(dirname "$0")/.."
IMG=falkordb/falkordb@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
DB_NAME="${EW_DB_CONTAINER:-embodiweave-db}"
PYTHON="${EW_PYTHON:-.venv/bin/python}"
export EW_FALKOR_PORT="${EW_FALKOR_PORT:-6379}"
export PYTHONPATH=.
export EW_DEPLOYED_POLICY="${EW_DEPLOYED_POLICY:-robust-20261016140226-352fd7}"
export EW_LATEST_VALIDATION_POLICY="${EW_LATEST_VALIDATION_POLICY:-robust-20261016140226-352fd7}"
if ! docker inspect "$DB_NAME" >/dev/null 2>&1; then
  docker run -d --name "$DB_NAME" -p "127.0.0.1:$EW_FALKOR_PORT:6379" "$IMG" >/dev/null
else
  docker start "$DB_NAME" >/dev/null
fi
for attempt in {1..30}; do
  if "$PYTHON" -c 'from ew.graph import db; assert db.ping()' 2>/dev/null; then break; fi
  if [ "$attempt" = 30 ]; then echo "FalkorDB did not become ready" >&2; exit 1; fi
  sleep 1
done
"$PYTHON" -c 'from ew.graph import db; from ew.graph.ingest import rebuild; names=[n.decode() if isinstance(n,bytes) else n for n in db._conn().connection.execute_command("GRAPH.LIST")]; rebuild() if db.GRAPH not in names else None'
mkdir -p logs
# Preserve a running worker. Its OS lease also rejects a duplicate process.
if ! [ -f logs/worker.pid ] || ! kill -0 "$(cat logs/worker.pid)" 2>/dev/null; then
  nohup "$PYTHON" -m ew.jobs >> logs/worker.log 2>&1 & echo $! > logs/worker.pid
fi
if ! [ -f logs/api.pid ] || ! kill -0 "$(cat logs/api.pid)" 2>/dev/null; then
  nohup "$PYTHON" -m uvicorn ew.api:app --host 127.0.0.1 --port "${PORT:-8000}" >> logs/api.log 2>&1 & echo $! > logs/api.pid
fi
export PORT="${PORT:-8000}"
for attempt in {1..30}; do
  if "$PYTHON" -c 'import json,os,urllib.request; s=json.load(urllib.request.urlopen("http://127.0.0.1:"+os.environ["PORT"]+"/api/status",timeout=2)); assert s["graph"]["up"] and s["worker"]["alive"]' 2>/dev/null; then break; fi
  if [ "$attempt" = 30 ]; then echo "API or worker did not become ready; inspect logs/" >&2; exit 1; fi
  sleep 1
done
echo "studio: http://127.0.0.1:${PORT}/studio.html"
echo "logs: logs/api.log and logs/worker.log"
