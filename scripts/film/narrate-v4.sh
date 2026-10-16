#!/usr/bin/env bash
# Existing key enters only the child process environment. Never echo or persist it.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ -z "${DEEPGRAM_API_KEY:-}" ]; then
  read -rsp 'Deepgram key (hidden): ' DEEPGRAM_API_KEY
  printf '\n'
  export DEEPGRAM_API_KEY
fi
exec "${EW_FILM_PYTHON:-../prd-audit-venv/bin/python}" -m scripts.film.mcp_update voice
