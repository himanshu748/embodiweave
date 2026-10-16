import json

import pytest

from ew import artifacts, robustness
from ew.graph import db
from ew.recipes import RECIPES
from ew.scenarios import SUITES


def test_collision_clearance_preserves_gate_and_prefers_margin():
    def candidate(pid, passed, collisions):
        return {"policy_id": pid, "passed": passed, "sort_key": [4-passed, 0, 0, -3, pid],
                "validation": {s: {"collision_rate": collisions.get(s, 0)} for s in robustness.SUITES}}
    boundary = candidate("boundary", 4, {"val-crossing-v1": .15})
    margin = candidate("margin", 4, {"val-crossing-v1": .10})
    fail = candidate("goal-failure", 3, {})
    ranked = robustness.with_clearance([boundary, fail, margin])
    assert [r["policy_id"] for r in ranked] == ["margin", "boundary", "goal-failure"]
    assert ranked[0]["clearance_deficit"] == 0
    assert ranked[1]["clearance_deficit"] == 2


def test_robustness_cannot_plan_without_graph(monkeypatch):
    def unavailable(*args, **kwargs):
        raise db.GraphUnavailable("offline")
    monkeypatch.setattr(robustness.Q, "run", unavailable)
    with pytest.raises(db.GraphUnavailable):
        robustness.plan()


def test_confirmation_is_new_disjoint_and_single_use_before_inference(monkeypatch, tmp_path):
    from scripts import robustness_confirmation as confirmation
    p = json.loads(robustness.PROTOCOL_PATH.read_text())
    canonical = {s for suite in SUITES.values() for s in suite.seeds}
    fresh = [s for suite in p["confirmation"]["suites"] for s in suite["seeds"]]
    assert len(set(fresh)) == 400 and not set(fresh) & canonical
    monkeypatch.setattr(artifacts, "ROOT", tmp_path)
    (tmp_path / "robustness-v2-selected.json").write_text(json.dumps({"policy_id": "frozen",
        "artifact_hash": "hash", "protocol_sha256": robustness.protocol_hash(), "selection_stopped": True}))
    monkeypatch.setattr(artifacts, "verify_policy", lambda *a: "hash")
    monkeypatch.setattr(confirmation.service, "promotion_preview", lambda p: {"verdict": "promoted"})
    calls = []
    def crash(*args, **kwargs):
        calls.append(True)
        assert (tmp_path / "robustness-v2-confirmation-started.json").exists()
        raise RuntimeError("interrupted inference")
    monkeypatch.setattr(confirmation.rl, "evaluate_policy", crash)
    with pytest.raises(RuntimeError, match="interrupted"):
        confirmation.confirm()
    with pytest.raises(FileExistsError):
        confirmation.confirm()
    assert len(calls) == 1


def test_historical_rehearsal_recipe_is_unchanged():
    baseline = RECIPES["ppo-rehearsal-v1"]
    changed = RECIPES["ppo-rehearsal-collision20-v2"]
    assert {k:v for k,v in changed.items() if k != "collision_penalty"} == baseline
    assert "collision_penalty" not in baseline
    assert changed["collision_penalty"] == -20
