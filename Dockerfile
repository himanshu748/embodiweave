# syntax=docker/dockerfile:1
# Hosted evidence studio and bounded remote agent: pinned FalkorDB plus FastAPI in one container.
# Real CPU PPO runs in one short-lived subprocess; generic training endpoints remain blocked.
FROM falkordb/falkordb@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-hosted.txt requirements.lock .
RUN --mount=type=secret,id=ca,required=false python3 -m venv .venv \
    && if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi \
    && .venv/bin/pip install --no-cache-dir torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu \
    && .venv/bin/pip install --no-cache-dir -r requirements-hosted.txt -c requirements.lock
COPY ew ew
COPY web web
COPY artifacts artifacts
COPY evidence/mujoco-v1 evidence/mujoco-v1
COPY evidence/mujoco-v2 evidence/mujoco-v2
COPY evidence/physics-adapt-v1 evidence/physics-adapt-v1
COPY evidence/mcp-agent-v1 evidence/mcp-agent-v1
COPY evidence/mcp-agent evidence/mcp-agent
COPY evidence/mcp-agent-v2 evidence/mcp-agent-v2
COPY evidence/mcp-agent-v3 evidence/mcp-agent-v3
COPY evidence/mcp-agent-v3-retry evidence/mcp-agent-v3-retry
COPY sim sim
COPY scripts/hosted.sh scripts/hosted.sh
ENV EW_STATIC=1 PYTHONPATH=/app PORT=8000 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2
EXPOSE 8000
ENTRYPOINT []
CMD ["/app/scripts/hosted.sh"]
