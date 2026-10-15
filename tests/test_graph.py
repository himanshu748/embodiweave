import numpy as np
import pytest

from ew import artifacts, records, rl, service, whatif
from ew.contract import CONTRACT_MIRRORED, CONTRACT_V1
from ew.graph import db, ingest, queries
from ew.scenarios import SUITES

TINY = 2048


@pytest.fixture(scope="module")
def world():
    db.delete_graph("ew_test")
    ingest.init_world()
    service.train_run("T-a", family="open", budget_steps=TINY, seed=1)
    service.train_run("T-b", family="static", budget_steps=TINY, seed=2, parent_id="T-a")
    service.train_run("T-m", family="open", budget_steps=TINY, seed=3, contract=CONTRACT_MIRRORED)
    yield
    db.delete_graph("ew_test")


def req():
    return {**service.target_request(budget=TINY), "candidate_run_kinds": ["library"]}


def test_ro_query_rejects_write(world):
    with pytest.raises(Exception, match="read-only"):
        db.ro("MATCH (p:Policy) SET p.status = 'hacked'")
    assert db.ro("MATCH (p:Policy {id:'T-a'}) RETURN p.status")[1][0][0] == "completed"


def test_reload_normalization_and_weights(world):
    m = artifacts.load_manifest("T-a")
    assert m["weight_delta_l2"] > 0
    model, vn, contract, man, h = rl.load_policy("T-a")
    assert h == m["artifact_hash"] and not vn.training and vn.obs_rms.count > TINY * 0.9
    assert contract.contract_id == CONTRACT_V1.contract_id
    e1 = rl.evaluate_policy("T-a", SUITES["val-open-v1"].family, SUITES["val-open-v1"].seeds[:3])
    e2 = rl.evaluate_policy("T-a", SUITES["val-open-v1"].family, SUITES["val-open-v1"].seeds[:3])
    assert e1["episodes"] == e2["episodes"]


def test_parent_immutable_and_distinct_child(world):
    h_before = artifacts.verify_policy("T-a")
    assert artifacts.load_manifest("T-b")["parent_id"] == "T-a"
    assert artifacts.verify_policy("T-a") == h_before
    with pytest.raises(FileExistsError):
        service.train_run("T-a", family="open", budget_steps=TINY, seed=9)
    assert artifacts.load_manifest("T-b")["artifact_hash"] != h_before


def test_mission_prerequisite_closure(world):
    r = queries.run("mission_requirements", {"mission": "static_crossing"})
    comps = {d["competency"] for d in r.dicts()}
    assert comps == {"reach_goal", "avoid_static", "yield_dynamic", "static_crossing_mission"}


def test_compat_rejects_same_shape(world):
    assert CONTRACT_MIRRORED.obs_dim == CONTRACT_V1.obs_dim
    d = service.record_decision(req())
    rej = {r["policy_id"]: r["reasons"] for r in d["rejected"]}
    assert "T-m" in rej and "ray_order" in rej["T-m"][0]


def test_missing_validation_requires_evaluation_then_ranks_all(world):
    d = service.record_decision(req())
    assert d["action"] == "evaluate_candidates" and set(d["needs_evaluation"]) == {"T-a", "T-b"}
    for pid in d["needs_evaluation"]:
        service.evaluate(pid, "val-target-v1")
    d2 = service.record_decision(req())
    assert d2["action"] == "train_from_parent"
    assert {c["policy_id"] for c in d2["ranking"]} == {"T-a", "T-b"}
    assert all(q["graph_revision"] >= 1 for q in d2["queries"])
    assert d2["queries"][0]["cypher"].startswith("MATCH")


def test_failed_trial_recorded_without_invented_steps(world):
    d = service.record_decision(req())
    sel = d["selected"]
    t = service.transfer_trial(parent_id=sel, child_id=f"{sel}~t1", target_family="static_crossing",
                               threshold_id="thr-target-1", budget_steps=TINY, seed=5, decision_id=d["id"])["trial"]
    assert t["threshold_reached"] is False and t["steps_to_threshold"] is None
    assert t["consumed_steps"] >= TINY and records.read("trial", t["id"]) == t
    d2 = service.record_decision(req())
    c = {x["policy_id"]: x for x in d2["ranking"]}[sel]
    assert c["n_not_reached_within_budget"] == 1 and c["p_reach"] == pytest.approx(1 / 3, abs=1e-3)
    prov = queries.run("decision_provenance", {"decision": d["id"]}).dicts()[0]
    assert prov["run_id"] == t["run_id"] and prov["child_id"] == f"{sel}~t1" and prov["reached"] is False
    with pytest.raises(FileExistsError):
        records.write("trial", t)


def test_final_test_protected(world):
    with pytest.raises(PermissionError):
        service.evaluate("T-a", "test-target-v2")
    with pytest.raises(PermissionError, match="spent"):
        service.evaluate("T-a", "test-target-v1", final_test_runner=True, n_episodes=2)
    rec = service.evaluate("T-a", "test-target-v2", final_test_runner=True, n_episodes=2, experiment_id="exp-2")
    with pytest.raises(PermissionError):
        ingest.evaluation(rec)
    rows = db.ro("MATCH (e:Evaluation)-[:ON_SUITE]->(s:Suite {role:'final_test'}) RETURN count(e)")[1]
    assert rows[0][0] == 0
    with pytest.raises(PermissionError):
        service.train_run("T-x", family="open", budget_steps=TINY, seed=1, validation_suite="test-target-v1")


def test_whatif_isolated_and_changes_choice(world):
    r = req()
    d = service.record_decision(r)
    base = whatif.fingerprint()
    other = [c["policy_id"] for c in d["ranking"] if c["policy_id"] != d["selected"]][0]
    g = whatif.create()
    try:
        for _ in range(3):
            whatif.add_hypothetical_trial(g, other, r["target_family_id"], r["contract"], r["threshold_id"],
                                          r["recipe"], r["budget"], reached=True, steps_to_threshold=TINY)
        dw = service.record_decision(r, mode="what-if", graph=g)
        assert dw["selected"] == other and dw["mode"] == "what-if"
        assert "hypothetical" in {c["policy_id"]: c for c in dw["ranking"]}[other]["p_basis"]
        assert whatif.fingerprint() == base
        with pytest.raises(PermissionError):
            whatif.add_hypothetical_trial("ew_test", other, "f", "c", "t", "r", 1, True)
    finally:
        whatif.drop(g)


def test_outage_stops_decisions(world, monkeypatch):
    monkeypatch.setattr(db, "PORT", 6390)
    monkeypatch.setattr(db, "_db", None)
    with pytest.raises(db.GraphUnavailable):
        service.record_decision(req())
    monkeypatch.setattr(db, "_db", None)


def test_export_bundle_contains_reloadable_artifact(world):
    import zipfile
    out = service.export_bundle("T-b")
    with zipfile.ZipFile(out["path"]) as z:
        names = set(z.namelist())
        assert {"policy/model.zip", "policy/vecnormalize.pkl", "policy/manifest.json", "contract.json",
                "records.json", "lineage.json", "REPRODUCE.md"} <= names
        lineage = [x["policy_id"] for x in __import__("json").loads(z.read("lineage.json"))]
    assert lineage == ["T-b", "T-a"]


def test_export_reproduction_command_runs(world, tmp_path):
    import hashlib
    import json
    import os
    import subprocess
    import sys
    import zipfile
    out = service.export_bundle("T-b")
    with zipfile.ZipFile(out["path"]) as z:
        checksums = json.loads(z.read("checksums.json"))
        assert all(hashlib.sha256(z.read(name)).hexdigest() == digest for name, digest in checksums.items())
        assert json.loads(z.read("source.json"))["export_source"]["source_hash"]
        z.extractall(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(tmp_path / "source")}
    result = subprocess.run([sys.executable, "-m", "ew.cli", "evaluate", "--policy-dir", "policy",
        "--suite", "val-target-v1", "--episodes", "2"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    expected = rl.evaluate_policy("T-b", SUITES["val-target-v1"].family, SUITES["val-target-v1"].seeds[:2])
    assert actual["episodes"] == expected["episodes"] and actual["artifact_hash"] == expected["artifact_hash"]
    assert not actual["complete_suite"]
