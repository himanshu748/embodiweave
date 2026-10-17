#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ -z "${DEEPGRAM_API_KEY:-}" ]; then
  read -rsp 'Deepgram key (hidden): ' DEEPGRAM_API_KEY
  printf '\n'
  export DEEPGRAM_API_KEY
fi
exec "${EW_FILM_PYTHON:-../prd-audit-venv/bin/python}" -m scripts.film.narrated_appendix voice
