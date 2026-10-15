"""ew-select-2: scratch as an explicit option backed by its own conditioned trials."""
import pytest

from ew import agent_tools, jobs, records, service, whatif
from ew.graph import db, ingest

TINY = 2048


@pytest.fixture(scope="module")
def world2():
    db.delete_graph("ew_test")
    ingest.init_world()
    service.train_run("V-a", family="open", budget_steps=TINY, seed=1)
    service.evaluate("V-a", "val-target-v1")
    yield
    db.delete_graph("ew_test")


def req():
    return {**service.target_request(budget=TINY), "candidate_run_kinds": ["library"]}


def test_scratch_trial_links_origin_and_is_counted(world2):
    t = service.transfer_trial(parent_id=None, child_id="scratch~v2-s4", target_family="static_crossing",
                               threshold_id="thr-target-1", budget_steps=TINY, seed=4)["trial"]
    assert t["parent_id"] is None and t["threshold_reached"] is False and t["steps_to_threshold"] is None
    rows = db.ro("MATCH (t:Trial {id:$id})-[:FROM_ORIGIN]->(o:Origin) RETURN o.id", {"id": t["id"]})[1]
    assert rows == [["scratch"]]
    d = service.record_decision(req(), rule="ew-select-2")
    so = d["scratch_option"]
    assert d["rule_version"] == "ew-select-2" and so["n_completed"] == 1 and so["n_reached"] == 0
    assert so["p_reach"] == pytest.approx(1 / 3, abs=1e-3)
    # parent has only the prior (0.5), scratch 1/3: reuse is kept
    assert d["action"] == "train_from_parent" and d["selected"] == "V-a"
    assert t["id"] in d["evidence_trial_ids"]


def test_v1_ignores_scratch_option(world2):
    d = service.record_decision(req(), rule="ew-select-1")
    assert d["rule_version"] == "ew-select-1" and d.get("scratch_option") is None
    assert not any(q["template"] == "scratch_trials" for q in d["queries"])


def test_whatif_scratch_evidence_flips_to_scratch_and_cannot_launch(world2):
    r = req()
    base = whatif.fingerprint()
    g = whatif.create()
    try:
        for _ in range(3):
            whatif.add_hypothetical_trial(g, None, r["target_family_id"], r["contract"], r["threshold_id"],
                                          r["recipe"], r["budget"], reached=True, steps_to_threshold=TINY)
        dw = service.record_decision(r, mode="what-if", graph=g, rule="ew-select-2")
        assert dw["action"] == "train_from_scratch" and dw["selected"] is None
        assert "WHAT-IF" in dw["scratch_option"]["p_basis"]
        assert whatif.fingerprint() == base
        out = agent_tools.start_training(decision_id=dw["id"], seed=3)  # tools return errors, never raise
        assert out["error"].startswith("PermissionError")
    finally:
        whatif.drop(g)
    assert db.ro("MATCH (d:Decision {id:$id}) RETURN d.id", {"id": dw["id"]})[1] == []


def test_scratch_decision_launches_parentless_job(world2):
    r = req()
    # two more measured scratch failures would not help; instead fail the parent twice so the prior wins
    for s in (5, 6):
        service.transfer_trial(parent_id="V-a", child_id=f"V-a~v2-s{s}", target_family="static_crossing",
                               threshold_id="thr-target-1", budget_steps=TINY, seed=s)
    d = service.record_decision(r, rule="ew-select-2")
    # parent 1/4 = 0.25 < scratch 1/3
    assert d["action"] == "train_from_scratch", d["explanation"]
    rows = db.ro("MATCH (d:Decision {id:$id})-[:SELECTED]->(o:Origin) RETURN o.id", {"id": d["id"]})[1]
    assert rows == [["scratch"]]
    out = agent_tools.start_training(decision_id=d["id"], seed=9)
    assert "error" not in out, out
    j = jobs.get(out["job_id"])
    assert out["parent"] is None and j["params"]["parent_id"] is None and out["child_policy_id"].startswith("scratch~")
    jobs.cancel(out["job_id"])


def test_v3_uses_trial_child_validation_on_ties(world2):
    """At this point V-a has 0/2 (p=0.25) and scratch 0/1 (p=1/3): scratch wins on p_reach under v3 too.
    Add one more failed scratch trial so both sit at 0.25; the tie is then broken by measured child scores."""
    service.transfer_trial(parent_id=None, child_id="scratch~v3-s8", target_family="static_crossing",
                           threshold_id="thr-target-1", budget_steps=TINY, seed=8)
    d = service.record_decision(req(), rule="ew-select-3")
    so = d["scratch_option"]
    va = {c["policy_id"]: c for c in d["ranking"]}["V-a"]
    assert so["p_reach"] == va["p_reach"] == 0.25
    assert so["n_trial_child_scores"] == 2 and va["n_trial_child_scores"] == 2
    assert any(q["template"] == "trial_outcomes" for q in d["queries"])
    winner = "scratch" if so["trial_child_score"] > va["trial_child_score"] else "V-a"
    if so["trial_child_score"] != va["trial_child_score"]:
        assert d["option_order"][0] == winner and "trial-child validation" in d["explanation"]
        assert (d["action"] == "train_from_scratch") == (winner == "scratch")
