import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from ew import agent_sessions as sessions, artifacts, jobs, records
from ew import api


@pytest.fixture
def local_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "JOBS", tmp_path / "jobs")
    monkeypatch.setattr(sessions, "_processes", {})
    for key, _ in sessions.PROVIDERS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-key")
    monkeypatch.setenv("EW_ALLOW_LLM", "1")
    return tmp_path


def test_explicit_agent_consent_and_opt_in(local_agent, monkeypatch):
    with pytest.raises(PermissionError):
        sessions.start(False)
    monkeypatch.setenv("EW_ALLOW_LLM", "0")
    with pytest.raises(PermissionError):
        sessions.start(True)
    assert "test-only-key" not in json.dumps(sessions.configuration())


def test_launch_is_bounded_deduplicated_and_reports_interruption(local_agent, monkeypatch):
    calls = []
    process = SimpleNamespace(pid=43210, poll=lambda: None)
    def spawn(args, **kwargs):
        calls.append((args, kwargs))
        return process
    monkeypatch.setattr(sessions.subprocess, "Popen", spawn)
    first = sessions.start(True)
    assert sessions.start(True)["id"] == first["id"]
    assert len(calls) == 1
    assert calls[0][0][-3:] == ["-m", "ew.agent", "llm"]
    assert calls[0][1]["env"]["EW_AGENT_MAX_TURNS"] == "12"
    assert calls[0][1]["env"]["EW_AGENT_TRAINING_LIMIT"] == "1"
    assert calls[0][1]["env"]["EW_AGENT_SESSION_ID"] == first["id"]
    assert "test-only-key" not in json.dumps(first)
    process.poll = lambda: 1
    assert sessions.status(first["id"])["state"] == "interrupted"


def test_final_trace_is_correlated(local_agent, monkeypatch):
    monkeypatch.setattr(sessions.subprocess, "Popen", lambda *a, **kw: SimpleNamespace(pid=43210,poll=lambda:None))
    started = sessions.start(True)
    monkeypatch.setattr(records, "exists", lambda kind, rid: kind == "agent_trace" and rid == started["id"])
    done = sessions.status(started["id"])
    assert done["state"] == "completed" and done["trace_id"] == started["id"]
    with pytest.raises(ValueError):
        sessions.status("../../anything")


def test_hosted_agent_launcher_disabled(local_agent, monkeypatch):
    monkeypatch.setattr(api, "STATIC_MODE", True)
    client = TestClient(api.app)
    assert client.get("/api/agent/config").json()["enabled"] is False
    assert client.post("/api/agent/start", json={"consent":True}).status_code == 403


def test_agent_api_requires_worker_and_loopback(local_agent, monkeypatch):
    monkeypatch.setattr(api,"STATIC_MODE",False)
    monkeypatch.setattr(api,"_worker_alive",lambda:{"alive":False})
    assert TestClient(api.app).post("/api/agent/start",json={"consent":True}).status_code == 409
    assert TestClient(api.app, client=("192.0.2.1", 1234)).post("/api/agent/start",json={"consent":True}).status_code == 403
