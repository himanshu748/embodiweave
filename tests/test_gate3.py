import json
import threading

import pytest

from ew import agent_tools as T
from ew import artifacts, jobs, records, service, whatif
from ew.graph import db, ingest

TINY = 2048


@pytest.fixture(scope="module")
def world():
    db.delete_graph("ew_test")
    ingest.init_world()
    for pid, fam, seed, parent in [("G-a", "open", 1, None), ("G-b", "static", 2, "G-a")]:
        if not artifacts.policy_dir(pid).exists():
            service.train_run(pid, family=fam, budget_steps=TINY, seed=seed, parent_id=parent)
        else:
            m = artifacts.load_manifest(pid)
            ingest.policy(m)
    yield
    db.delete_graph("ew_test")


def _trial_params(seed, budget=TINY, parent="G-a"):
    return {"parent_id": parent, "child_id": f"{parent}~job-s{seed}", "trial_id": f"trial-job-s{seed}",
            "target_family": "static_crossing", "threshold_id": "thr-target-1", "budget": budget, "seed": seed,
            "recipe": "ppo-r1", "decision_id": None}


def test_idempotent_submit_and_quota(world, monkeypatch):
    j1, c1 = jobs.submit("transfer_trial", _trial_params(11))
    j2, c2 = jobs.submit("transfer_trial", _trial_params(11))
    assert c1 and not c2 and j1["id"] == j2["id"]
    with pytest.raises(jobs.QuotaExceeded):
        jobs.submit("transfer_trial", _trial_params(12, budget=jobs.MAX_JOB_STEPS + 1))
    monkeypatch.setattr(jobs, "STEP_QUOTA", jobs.steps_used() + 10)
    with pytest.raises(jobs.QuotaExceeded):
        jobs.submit("transfer_trial", _trial_params(13))
    jobs.cancel(j1["id"])
    assert jobs.get(j1["id"])["state"] == "cancelled"


def test_worker_runs_trial_and_cancel_records_cancelled(world):
    j, _ = jobs.submit("transfer_trial", _trial_params(21, budget=8 * TINY))
    (jobs.JOBS / f"{j['id']}.cancel").write_text("1")
    # mark as running by worker: work_once picks the oldest queued job
    while True:
        done = jobs.work_once()
        if done is None or done["id"] == j["id"]:
            break
    j = jobs.get(j["id"])
    assert j["state"] == "cancelled"
    t = records.read("trial", "trial-job-s21")
    assert t["status"] == "cancelled" and t["consumed_steps"] < 8 * TINY
    assert artifacts.load_manifest("G-a~job-s21")["status"] == "cancelled"
    d = service.record_decision({**service.target_request(budget=TINY)})
    assert "G-a~job-s21" in {r["policy_id"] for r in d["rejected"]}


def test_restart_recovery_marks_interrupted(world):
    j, _ = jobs.submit("transfer_trial", _trial_params(31))
    j = jobs.get(j["id"])
    j.update(state="running", worker_pid=999_999, progress={"steps": 1234})
    jobs._save(j)
    rec = jobs.recover()
    assert j["id"] in rec
    j = jobs.get(j["id"])
    assert j["state"] == "interrupted" and j["consumed_steps"] == 1234
    t = records.read("trial", "trial-job-s31")
    assert t["status"] == "interrupted" and t["child_policy_id"] is None and t["steps_to_threshold"] is None
    assert not artifacts.policy_dir("G-a~job-s31").exists()


def test_promotion_requires_exact_artifact_evidence(world):
    p = service.promote("G-b")
    assert p["verdict"] == "insufficient_evidence" and len(p["missing"]) == 4
    # evidence on the PARENT does not count for the child
    service.evaluate("G-a", "val-target-v1")
    assert "val-target-v1" in service.promote("G-b")["missing"]
    # a forged evaluation with another hash is ignored by the evidence query
    forged = records.write("evaluation", {"policy_id": "G-b", "artifact_hash": "0" * 64, "suite_id": "val-target-v1",
                                          "suite_role": "validation", "contract_id": "x", "seeds": [],
                                          "summary": {"success_rate": 1.0, "collision_rate": 0.0, "timeout_rate": 0.0,
                                                      "episodes": 60, "mean_success_steps": 50}, "episodes": []})
    ingest.evaluation(forged)
    assert "val-target-v1" in service.promote("G-b")["missing"]
    for s in ("val-target-v1", "val-open-v1", "val-static-v1", "val-crossing-v1"):
        service.evaluate("G-b", s)
    p = service.promote("G-b")
    assert p["verdict"] == "rejected" and not p["missing"]
    assert all(c["evaluation_id"] != forged["id"] for c in p["checks"])


def test_agent_tool_guards(world):
    assert "error" in T.query_graph(template="raw", params={"q": "MATCH (n) DETACH DELETE n"})
    assert "PermissionError" in T.evaluate_checkpoint(policy_id="G-a", suite_id="test-target-v1")["error"]
    assert "budget" in T.propose_adaptation(budget=999_999)["error"]
    g = whatif.create()
    try:
        dw = service.record_decision(service.target_request(budget=TINY), mode="what-if", graph=g)
        assert "what-if" in T.start_training(decision_id=dw["id"], seed=1)["error"]
    finally:
        whatif.drop(g)
    lines = (T.TRACES / f"{T.SESSION}.jsonl").read_text().strip().splitlines()
    assert json.loads(lines[-1])["tool"] == "start_training" and json.loads(lines[-1])["error"]


def test_smoke_evaluations_cannot_rank_or_promote(world):
    service.train_run("G-smoke", family="open", budget_steps=TINY, seed=91)
    for suite in ("val-target-v1", "val-open-v1", "val-static-v1", "val-crossing-v1"):
        service.evaluate("G-smoke", suite, n_episodes=1)
    assert "G-smoke" in service.record_decision(service.target_request(budget=TINY))["needs_evaluation"]
    assert service.promote("G-smoke")["verdict"] == "insufficient_evidence"
    # This test's child is outside the normal library catalog for subsequent decisions.
    db.rw("MATCH (r:Run)-[:PRODUCED]->(p:Policy {id:'G-smoke'}) SET r.kind='smoke-test'")


def test_stale_decision_refused(world):
    req = {**service.target_request(budget=TINY), "candidate_run_kinds": ["library"]}
    d = service.record_decision(req)
    if d["action"] != "train_from_parent":
        for pid in d["needs_evaluation"]:
            service.evaluate(pid, "val-target-v1")
        d = service.record_decision(req)
    # new measured evidence: three failed trials for the selected parent make it lose its place
    sel = d["selected"]
    for s in (41, 42, 43):
        service.transfer_trial(parent_id=sel, child_id=f"{sel}~stale-{s}", target_family="static_crossing",
                               threshold_id="thr-target-1", budget_steps=TINY, seed=s)
    out = T.start_training(decision_id=d["id"], seed=5)
    assert "stale decision" in out.get("error", "")


def test_recovery_preserves_already_recorded_trial(world, monkeypatch):
    params = dict(parent_id="G-a", child_id="G-a~crash-s98", target_family="static_crossing",
                  threshold_id="thr-target-1", budget=TINY, seed=98, recipe="ppo-r1",
                  trial_id="trial-already-recorded")
    job, _ = jobs.submit("transfer_trial", params)
    job.update(state="running", worker_pid=999999999, progress={"steps":8})
    jobs._save(job)
    records.write("trial", {"id":params["trial_id"], "status":"failed", "note":"retained original"})
    jobs.recover()
    assert records.read("trial",params["trial_id"])["note"] == "retained original"
    assert jobs.get(job["id"])["state"] == "interrupted"
