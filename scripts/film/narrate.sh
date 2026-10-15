#!/usr/bin/env bash
# Interactive input is not echoed or added to shell history. The Python client
# reads the key only from its environment. Do not enable shell tracing.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ -z "${DEEPGRAM_API_KEY:-}" ]; then
  read -rsp 'Deepgram key (hidden): ' DEEPGRAM_API_KEY
  printf '\n'
  export DEEPGRAM_API_KEY
fi
exec "${EW_FILM_PYTHON:-../prd-audit-venv/bin/python}" scripts/film/voice.py "$@"
