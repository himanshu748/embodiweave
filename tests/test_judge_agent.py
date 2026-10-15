import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from ew import api, artifacts, jobs, judge_agent as J
from ew.graph import db


@pytest.fixture
def public_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "JOBS", tmp_path / "jobs")
    monkeypatch.setattr(J, "_threads", {})
    monkeypatch.setenv("EW_PUBLIC_AGENT", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-provider-secret")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(api, "STATIC_MODE", True)
    monkeypatch.setattr(J.threading, "Thread", lambda **kw: SimpleNamespace(start=lambda: None))
    return tmp_path


def test_session_consent_isolation_and_no_secret_exposure(public_agent):
    c, other = TestClient(api.app), TestClient(api.app)
    cfg = c.get("/api/judge/config")
    assert cfg.json()["enabled"] is True and cfg.json()["model"] == "nvidia/nemotron-3.5-lightning:free"
    assert "HttpOnly" in cfg.headers["set-cookie"] and "SameSite=strict" in cfg.headers["set-cookie"]
    assert c.post("/api/judge/start", json={"question": "Investigate failure", "consent": False}).status_code == 403
    r = c.post("/api/judge/start", json={"question": "Investigate failure", "consent": True})
    assert r.status_code == 200
    sid = r.json()["id"]
    assert "owner" not in r.json() and "pid" not in r.json()
    assert "test-provider-secret" not in r.text
    assert c.get(f"/api/judge/sessions/{sid}").status_code == 200
    assert other.get(f"/api/judge/sessions/{sid}").status_code == 404
    assert c.post("/api/judge/start", json={"question": "A second question", "consent": True}).json()["id"] == sid
    assert c.post("/api/judge/start", headers={"Origin": "https://elsewhere.invalid"}, json={"question": "Investigate failure", "consent": True}).status_code == 403
    assert c.post("/api/train", json={}).status_code == 403


def test_global_single_flight_quota_and_restarts(public_agent):
    a, b = J.visitor(None), J.visitor(None)
    first = J.start("Explain the rejection", True, a)
    with pytest.raises(J.Limited, match="Another"):
        J.start("Explain the rejection", True, b)
    J._threads.clear()
    assert J.status(first["id"], a)["state"] == "interrupted"
    for _ in range(J.VISITOR_HOURLY - 1):
        s = J.start("Explain the rejection", True, a)
        J._threads.clear()
        J.status(s["id"], a)
    with pytest.raises(J.Limited, match="four"):
        J.start("Explain the rejection", True, a)
    for _ in range(J.DAILY_RUNS - J.VISITOR_HOURLY):
        owner = J.visitor(None)
        s = J.start("Explain the rejection", True, owner)
        J._threads.clear()
        J.status(s["id"], owner)
    with pytest.raises(J.Limited, match="shared"):
        J.start("Explain the rejection", True, J.visitor(None))


def test_dispatch_refuses_unbounded_tools_and_arguments(public_agent):
    for name, args in [("start_training", {}), ("query_graph", {"cypher": "MATCH (n) DETACH DELETE n"}),
                       ("inspect_mission", {"path": "/etc/passwd"}), ("propose_adaptation", {"budget": 2000000}),
                       ("propose_adaptation", {"budget": True}), ("check_checkpoint", {"policy_id": "../secret", "extra": 1})]:
        with pytest.raises(ValueError):
            J.execute(name, args)


@pytest.mark.parametrize("finish", ["stop", "length"])
def test_live_loop_selects_tools_then_reports_actual_model(public_agent, monkeypatch, finish):
    owner = J.visitor(None)
    s = J.start("Investigate failure with test-provider-secret", True, owner)
    private = json.loads(J._path(s["id"]).read_text())
    assert "test-provider-secret" not in json.dumps(private)
    messages_seen = []
    def completion(messages, config, remaining):
        messages_seen.append(json.loads(json.dumps(messages)))
        if len(messages_seen) == 1:
            msg = {"tool_calls": [{"id": "call1", "type": "function", "function": {"name": "inspect_mission", "arguments": "{}"}}]}
        else:
            msg = {"content": "Evidence says no new training. test-provider-secret"}
        return {"model": "provider/actual-free-model", "choices": [{"message": msg, "finish_reason": finish}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10}}
    monkeypatch.setattr(J, "_completion", completion)
    monkeypatch.setattr(J, "execute", lambda name, args: {"queries": [{"template": "mission_requirements", "rows": [], "graph_revision": 4}]})
    J._run(private)
    result = J.status(s["id"], owner)
    assert result["state"] == ("completed" if finish == "stop" else "limited")
    assert result["models"] == ["provider/actual-free-model"]
    assert result["calls"][0]["tool"] == "inspect_mission"
    assert result["usage"] == {"prompt_tokens": 40, "completion_tokens": 20}
    assert result["training_started"] is False and "test-provider-secret" not in json.dumps(result)
    assert messages_seen[-1][-1]["role"] == "tool"


@pytest.mark.parametrize("failure,detail", [(J.ProviderFailure("Rate limited"), "Rate limited"),
    (db.GraphUnavailable("test"), "FalkorDB is unavailable")])
def test_provider_or_graph_failure_never_substitutes_recorded_answer(public_agent, monkeypatch, failure, detail):
    owner = J.visitor(None)
    s = J.start("Investigate the failure", True, owner)
    def fail(*a):
        raise failure
    monkeypatch.setattr(J, "_completion", fail)
    J._run(json.loads(J._path(s["id"]).read_text()))
    result = J.status(s["id"], owner)
    assert result["state"] == "failed" and detail in result["detail"] and result["answer"] is None


def test_model_loop_stops_at_turn_limit(public_agent, monkeypatch):
    owner = J.visitor(None)
    s = J.start("Investigate the failure", True, owner)
    monkeypatch.setattr(J, "_completion", lambda *a: {"choices": [{"message": {"tool_calls": [
        {"id": "c", "function": {"name": "inspect_mission", "arguments": "{}"}}]}}]})
    monkeypatch.setattr(J, "execute", lambda *a: {"queries": []})
    J._run(json.loads(J._path(s["id"]).read_text()))
    result = J.status(s["id"], owner)
    assert result["state"] == "limited" and result["turns"] == J.MAX_TURNS
    assert len(result["calls"]) == J.MAX_TURNS


def test_provider_request_is_free_only_and_http_errors_are_sanitized(public_agent, monkeypatch):
    sent = []
    def unavailable(req, **kw):
        sent.append(json.loads(req.data))
        raise HTTPError(req.full_url, 429, "test-provider-secret", {}, None)
    monkeypatch.setattr(J.urllib.request, "urlopen", unavailable)
    with pytest.raises(J.ProviderFailure, match="rate limited") as exc:
        J._completion([{}, {}], J.configuration(), 60)
    assert "test-provider-secret" not in str(exc.value)
    assert sent[0]["model"] == "nvidia/nemotron-3.5-lightning:free" and sent[0]["max_tokens"] == 1200
    assert sent[0]["provider"] == {"only": ["nvidia"], "allow_fallbacks": False}


def test_public_opt_in_and_question_bounds(public_agent, monkeypatch):
    owner = J.visitor(None)
    with pytest.raises(ValueError):
        J.start("x" * 801, True, owner)
    monkeypatch.setenv("EW_PUBLIC_AGENT", "0")
    with pytest.raises(PermissionError):
        J.start("Investigate the failure", True, owner)
