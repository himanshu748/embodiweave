import numpy as np
import pytest

from ew import artifacts, rl, service
from ew.contract import CONTRACT_V1
from ew.env import EmbodiNavEnv
from ew.graph import db, ingest
from ew.search import rank_candidates, SUITES


def test_warm_start_applies_recorded_optimizer_recipe():
    # A real load/learn/save verifies the new recipe reaches the optimizer,
    # rather than only appearing in the manifest.
    rl.train("recipe-parent", family="open", budget_steps=2048, seed=17)
    out = rl.train("recipe-child", family="open", budget_steps=2048, seed=17,
                   parent_id="recipe-parent", recipe="ppo-lr-v1")
    model, vn, _, manifest, _ = rl.load_policy("recipe-child")
    assert model.learning_rate == 1e-4
    assert model.policy.optimizer.param_groups[0]["lr"] == 1e-4
    assert out["manifest"]["recipe_params"]["learning_rate"] == 1e-4
    assert manifest["weight_delta_l2"] > 0
    vn.close()


def test_shaping_never_changes_observations_or_dynamics_or_evaluation_reward():
    plain = EmbodiNavEnv("open")
    shaped = rl.TrainingEnv("open", CONTRACT_V1, {"collision_penalty": -20.0})
    layout = {"start": [0.21, 5.0, np.pi], "goal": [8.5, 5.0], "statics": [], "movers": []}
    np.testing.assert_array_equal(plain.reset(options={"layout": layout})[0],
                                  shaped.reset(options={"layout": layout})[0])
    a, b = plain.step([1, 0]), shaped.step([1, 0])
    np.testing.assert_array_equal(a[0], b[0])
    assert a[2:] == b[2:]
    assert a[4]["outcome"] == "collision" and b[1] == pytest.approx(a[1] - 10)
    assert EmbodiNavEnv("open").family.name == "open"


def test_search_excludes_partial_evidence_and_verifies_exact_artifact(monkeypatch):
    monkeypatch.setattr(artifacts, "verify_policy", lambda pid, h: h)
    rows = [{"policy_id": pid, "artifact_hash": "hash", "suite_id": s,
             "success_rate": success, "collision_rate": 0.0, "timeout_rate": 1-success}
            for pid, success, suites in [("partial", 1.0, SUITES[:1]), ("all-pass", 1.0, SUITES),
                                         ("all-fail", 0.0, SUITES)] for s in suites]
    assert [x["policy_id"] for x in rank_candidates(rows)] == ["all-pass", "all-fail"]
    assert rank_candidates(rows)[0]["passed"] == 4


def test_search_fails_closed_when_graph_is_down(monkeypatch):
    from ew import search
    def unavailable(*args, **kwargs):
        raise db.GraphUnavailable("offline")
    monkeypatch.setattr(search.Q, "run", unavailable)
    with pytest.raises(db.GraphUnavailable):
        search.plan()


def test_promotion_implementation_thresholds_and_suites_are_unchanged():
    import ast
    import hashlib
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    proof = json.loads((root / "evidence/search-v1/gate-unchanged.json").read_text())["exact_source_matches"]
    text = (root / "ew/service.py").read_text()
    functions = {n.name: ast.get_source_segment(text, n) for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
    for name, digest in proof.items():
        content = (root / name).read_bytes() if name.endswith(".py") else functions[name].encode()
        assert hashlib.sha256(content).hexdigest() == digest
