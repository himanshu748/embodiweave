#!/bin/sh
# Hosted bounded studio: FalkorDB and the API in one container. The graph is rebuilt from the committed
# immutable records on every boot, so the live graph always matches the repository.
set -e
redis-server --bind 127.0.0.1 --protected-mode yes --save "" --appendonly no \
  --loadmodule "${FALKORDB_BIN_PATH}/falkordb.so" ${FALKORDB_ARGS} --daemonize yes
until redis-cli ping >/dev/null 2>&1; do sleep 0.2; done
cd /app
# A mounted AWS volume retains new checkpoints, receipts and quotas across container restarts.
if [ "${EW_ARTIFACTS:-/app/artifacts}" != /app/artifacts ]; then
  mkdir -p "$EW_ARTIFACTS"
  cp -an /app/artifacts/. "$EW_ARTIFACTS/"
fi
/app/.venv/bin/python -c "from ew.graph import ingest; ingest.rebuild()"
exec /app/.venv/bin/uvicorn ew.api:app --host 0.0.0.0 --port "${PORT:-8000}"
