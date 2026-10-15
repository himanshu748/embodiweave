"""Local-only, explicitly authorized runtime agent launches."""
import json
import os
import re
import subprocess
import sys
import time
import tempfile

from . import artifacts, jobs, records

PROVIDERS = (("OPENROUTER_API_KEY", "OpenRouter"), ("GROQ_API_KEY", "Groq"), ("ANTHROPIC_API_KEY", "Anthropic"))
_processes = {}


def configuration():
    provider = next((name for key, name in PROVIDERS if os.environ.get(key)), None)
    enabled = os.environ.get("EW_ALLOW_LLM") == "1" and bool(provider)
    return {"enabled": enabled, "provider": provider, "max_turns": 12,
            "reason": None if enabled else "Run locally with a provider API key and EW_ALLOW_LLM=1. Keys stay on the server."}


def _path(sid):
    if not re.fullmatch(r"agent-[0-9a-f-]+", sid):
        raise ValueError("invalid agent session id")
    root = artifacts.ROOT / "agent_sessions"
    root.mkdir(parents=True, exist_ok=True)
    return root / (sid + ".json")


def _save(path, session):
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as handle:
        json.dump(session, handle)
    os.replace(name, path)


def status(sid):
    path = _path(sid)
    session = json.loads(path.read_text())
    if records.exists("agent_trace", sid):
        session.update(state="completed", trace_id=sid)
    elif session["state"] == "running":
        process = _processes.get(sid)
        if process is not None:
            alive = process.poll() is None
        else:
            try:
                os.kill(session["pid"], 0)
                alive = True
            except OSError:
                alive = False
        if not alive:
            session.update(state="interrupted", detail="Agent stopped before a final trace was recorded. Worker jobs remain inspectable.")
    _save(path, session)
    return session


def start(consent):
    if consent is not True:
        raise PermissionError("Explicit consent is required for provider API usage and one bounded training run")
    config = configuration()
    if not config["enabled"]:
        raise PermissionError(config["reason"])
    with jobs._lock("agent"):
        root = artifacts.ROOT / "agent_sessions"
        for path in root.glob("agent-*.json") if root.exists() else []:
            existing = status(path.stem)
            if existing["state"] == "running":
                return existing
        sid = records.new_id("agent")
        path = _path(sid)
        env = {**os.environ, "EW_AGENT_SESSION_ID": sid, "EW_AGENT_MAX_TURNS": "12", "EW_AGENT_TRAINING_LIMIT": "1"}
        with open(path.with_suffix(".log"), "w") as log:
            process = subprocess.Popen([sys.executable, "-m", "ew.agent", "llm"], env=env,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        _processes[sid] = process
        session = {"id": sid, "pid": process.pid, "state": "running", "provider": config["provider"],
                   "trace_id": None, "started_at": time.time(), "max_turns": 12}
        _save(path, session)
        return session
