import json
import subprocess
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ew import api, artifacts, jobs, judge_agent as J, public_training as P


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "JOBS", tmp_path / "jobs")
    monkeypatch.setattr(P, "_processes", {})
    monkeypatch.setattr(P, "configuration", lambda: {"enabled": True})
    monkeypatch.setattr(P.subprocess, "Popen", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(P.threading, "Thread", lambda **k: SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(api, "STATIC_MODE", True)
    return tmp_path


def test_public_api_consent_origin_seed_and_owner_boundaries(isolated):
    c, other = TestClient(api.app), TestClient(api.app)
    c.get("/api/judge/config")
    assert c.post("/api/public-training/start", json={"consent": False}).status_code == 403
    for seed in (-1, 100000, True, 1.5):
        assert c.post("/api/public-training/start", json={"consent": True, "seed": seed}).status_code == 422
    assert c.post("/api/public-training/start", headers={"Origin": "https://evil.invalid"}, json={"consent": True}).status_code == 403
    trial = c.post("/api/public-training/start", json={"consent": True, "seed": 13}).json()
    assert trial["budget"] == 4096 and trial["seed"] == 13
    assert "owner" not in trial and "pid" not in trial
    sid = trial["id"]
    assert c.get(f"/api/public-training/sessions/{sid}").status_code == 200
    assert other.get(f"/api/public-training/sessions/{sid}").status_code == 404
    other.get("/api/judge/config")
    assert other.post("/api/public-training/cancel", json={"session_id": sid}).status_code == 404
    assert c.get(f"/api/public-training/sessions/{sid}/bundle").status_code == 404
    cancelled = c.post("/api/public-training/cancel", json={"session_id": sid}).json()
    assert cancelled["state"] == "cancelling"
    assert (P._root() / (sid + ".cancel")).exists()
    assert c.post("/api/train", json={}).status_code == 403
    assert c.post("/api/evaluate", json={}).status_code == 403


def test_single_flight_restart_and_quotas(isolated):
    token, other = J.visitor(None), J.visitor(None)
    first = P.start(token, consent=True)
    assert P.start(token, consent=True)["id"] == first["id"]
    with pytest.raises(P.Limited, match="Another"):
        P.start(other, consent=True)
    P._processes.clear()
    assert P.status(first["id"], token)["state"] == "interrupted"
    second = P.start(token, consent=True)
    P._processes.clear()
    P.status(second["id"], token)
    with pytest.raises(P.Limited, match="two"):
        P.start(token, consent=True)
    for _ in range(P.DAILY_RUNS - 2):
        t = J.visitor(None)
        s = P.start(t, consent=True)
        P._processes.clear()
        P.status(s["id"], t)
    with pytest.raises(P.Limited, match="shared"):
        P.start(J.visitor(None), consent=True)


def test_worker_has_no_cloud_or_model_credentials(monkeypatch):
    for key in ("OPENROUTER_API_KEY", "GROQ_API_KEY", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "RENDER_API_KEY", "DATABASE_URL"):
        monkeypatch.setenv(key, "private-test-value")
    env = P._worker_env()
    assert "private-test-value" not in env.values()
    assert env["OMP_NUM_THREADS"] == "1"


def test_timeout_kills_only_own_process_and_does_not_claim_gate(isolated):
    s = P.start(J.visitor(None), consent=True)
    events = []
    def wait(timeout=None):
        if timeout == P.MAX_SECONDS:
            raise subprocess.TimeoutExpired("worker", timeout)
        return -15
    proc = SimpleNamespace(wait=wait, terminate=lambda: events.append("terminate"), kill=lambda: events.append("kill"))
    P._watch(s["id"], proc)
    raw = json.loads(P._path(s["id"]).read_text())
    assert raw["state"] == "timed_out" and raw["gate"] is None and events == ["terminate"]
    assert s["id"] not in P._processes


def test_model_cannot_launch_ppo_without_training_consent(isolated, monkeypatch):
    monkeypatch.setenv("EW_PUBLIC_AGENT", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    monkeypatch.setattr(J, "_threads", {})
    calls = []
    def completion(messages, config, remaining):
        if not calls:
            calls.append(True)
            return {"choices": [{"message": {"tool_calls": [{"id": "c1", "function": {"name": "run_ppo_flow", "arguments": "{}"}}]}}]}
        return {"choices": [{"message": {"content": "Training was not authorized."}}]}
    monkeypatch.setattr(J, "_completion", completion)
    s = J.start("Please run training", True, J.visitor(None))
    J._run(json.loads(J._path(s["id"]).read_text()))
    result = json.loads(J._path(s["id"]).read_text())
    assert result["training_started"] is False and result["training_session_id"] is None
    assert "error" in result["calls"][0]["result"]
    assert not list(P._root().glob("ppo-*.json"))
