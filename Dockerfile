# syntax=docker/dockerfile:1
# Hosted, read-only EmbodiWeave studio: pinned FalkorDB plus the FastAPI studio in one container.
# Training and evaluation need torch and the worker; run those locally with scripts/start.sh.
FROM falkordb/falkordb@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-hosted.txt .
RUN --mount=type=secret,id=ca,required=false python3 -m venv .venv \
    && if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi \
    && .venv/bin/pip install --no-cache-dir -r requirements-hosted.txt
COPY ew ew
COPY web web
COPY artifacts artifacts
COPY scripts/hosted.sh scripts/hosted.sh
ENV EW_STATIC=1 PYTHONPATH=/app PORT=8000
EXPOSE 8000
ENTRYPOINT []
CMD ["/app/scripts/hosted.sh"]
