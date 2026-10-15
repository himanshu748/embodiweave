"""Validation-only experiment planner, search-v1, authored before its first trial.

FalkorDB supplies eligibility, complete per-artifact validation, failures and tried
interventions. The following priorities are human-authored heuristics, not an LLM
discovery or a statistical proof of the best intervention. No gate code is changed.
"""
from . import artifacts, records, service
from .contract import CONTRACT_V1
from .criteria import PROMOTION, THRESHOLDS, meets
from .graph import db, ingest, queries as Q

RULE = "search-v1"
CRITERIA = [PROMOTION["promo-1"]["target"], *PROMOTION["promo-1"]["retained"]]
SUITES = [c["suite_id"] for c in CRITERIA]
# Fixed seed, equal extra training budgets, no seed search. One recipe change per attempt.
SEED, BUDGET = 7, 300_000
INTERVENTIONS = {
    "longer": ("ppo-r1", "Continue training the best complete-validation checkpoint."),
    "rehearsal": ("ppo-rehearsal-v1", "Rehearse all four authored training families to address retained-task failures."),
    "collision": ("ppo-collision20-v1", "Double the training-only terminal collision penalty."),
    "entropy": ("ppo-entropy-v1", "Add exploration entropy 0.005 during training."),
    "learning_rate": ("ppo-lr-v1", "Lower the optimizer learning rate to 0.0001."),
}


def rank_candidates(rows):
    latest = {}
    for r in rows:
        latest.setdefault(r["policy_id"], {})[r["suite_id"]] = r
    ranking = []
    for pid, ev in latest.items():
        if set(ev) != set(SUITES):
            continue
        try:
            artifacts.verify_policy(pid, next(iter(ev.values()))["artifact_hash"])
        except (OSError, ValueError):
            continue
        passed, deficits, scores = 0, [], []
        for c in CRITERIA:
            x = ev[c["suite_id"]]
            passed += x["success_rate"] >= c["min_success"] and x["collision_rate"] <= c["max_collision"]
            deficits.append(max(0, c["min_success"] - x["success_rate"]) +
                            max(0, x["collision_rate"] - c["max_collision"]))
            scores.append(x["success_rate"] - x["collision_rate"])
        # First reduce failed-suite count, then the worst deficit, then total deficit.
        key = [4 - passed, round(max(deficits), 4), round(sum(deficits), 4), -round(sum(scores), 4), pid]
        ranking.append({"policy_id": pid, "passed": passed, "sort_key": key, "validation": ev})
    ranking.sort(key=lambda r: r["sort_key"])
    for i, c in enumerate(ranking):
        c["rank"] = i + 1
    return ranking


def plan(graph=None):
    params = {"contract": CONTRACT_V1.contract_id, "suites": SUITES}
    candidates = Q.run("search_validation", params, graph)
    history = Q.run("search_history", {"contract": CONTRACT_V1.contract_id, "rule": RULE}, graph)
    ranking = rank_candidates(candidates.dicts())
    if not ranking:
        raise ValueError("No compatible checkpoint has complete evidence on all four validation suites")
    best = ranking[0]
    if best["passed"] == 4:
        raise ValueError("A validation pass exists; stop model selection")
    tried = {r["intervention"] for r in history.dicts()}
    ev = best["validation"]
    retained_failed = any(not (ev[c["suite_id"]]["success_rate"] >= c["min_success"] and
                               ev[c["suite_id"]]["collision_rate"] <= c["max_collision"]) for c in CRITERIA[1:])
    collisions = any(ev[c["suite_id"]]["collision_rate"] > c["max_collision"] for c in CRITERIA)
    # Budget is the initial control; subsequent order depends on observed failure type.
    order = ["longer"] + (["rehearsal"] if retained_failed else []) + (["collision"] if collisions else [])
    order += ["entropy", "learning_rate", "rehearsal", "collision"]
    intervention = next((x for x in order if x not in tried), None)
    if intervention is None:
        raise ValueError("search-v1 exhausted; publish negative results or author a new preregistered protocol")
    recipe, explanation = INTERVENTIONS[intervention]
    failures = [Q.run("failure_inspection", {"evaluation": x["evaluation_id"]}, graph) for x in ev.values()]
    decision = records.write("decision", {
        "rule_version": RULE, "mode": "deterministic", "graph_revision": candidates.graph_revision,
        "graph": graph or db.GRAPH, "action": "train_from_parent", "selected": best["policy_id"],
        "request": service.target_request(BUDGET, recipe), "intervention": intervention, "seed": SEED,
        "ranking": ranking, "rejected": [], "evidence_trial_ids": [r["trial_id"] for r in history.dicts()],
        "evidence_eval_ids": [e["evaluation_id"] for c in ranking for e in c["validation"].values()],
        "queries": [candidates.to_log(), history.to_log(), *[f.to_log() for f in failures]],
        "explanation": f"{best['policy_id']} ranks first across all four validation suites ({best['passed']}/4 pass). "
                       f"{explanation} Retained failure={retained_failed}; excess collisions={collisions}; "
                       f"previously tried={sorted(tried)}. Fixed seed {SEED}, {BUDGET} additional steps.",
    })
    ingest.decision(decision, graph)
    db.bump_revision(f"search decision {decision['id']}", graph)
    return decision


def run_next(graph=None, on_progress=None):
    """One measured attempt. Always validate the saved artifact on all 180 episodes."""
    d = plan(graph)
    pid = records.new_id("search")
    parent = d["selected"]
    parent_hash = artifacts.verify_policy(parent)
    out = service.train_run(pid, family="static_crossing", budget_steps=BUDGET, seed=SEED,
                            parent_id=parent, recipe=d["request"]["recipe"], run_kind="validation_search",
                            purpose=d["explanation"], decision_id=d["id"], graph=graph, on_progress=on_progress)
    artifacts.verify_policy(parent, parent_hash)
    evaluations = [service.evaluate(pid, s, purpose=f"{RULE}:{d['id']}", save_replay=True, graph=graph) for s in SUITES]
    target = next(e for e in evaluations if e["suite_id"] == "val-target-v1")
    reached = meets(target["summary"], THRESHOLDS["thr-target-1"])
    steps = out["run"]["consumed_steps"]
    trial = records.write("trial", {
        "parent_id": parent, "parent_artifact_hash": parent_hash, "child_policy_id": pid,
        "child_artifact_hash": out["manifest"]["artifact_hash"], "run_id": out["run"]["id"],
        "target_family": "static_crossing", "target_family_id": d["request"]["target_family_id"],
        "suite_id": "val-target-v1", "contract_id": CONTRACT_V1.contract_id, "recipe": d["request"]["recipe"],
        "threshold_id": "thr-target-1", "threshold": THRESHOLDS["thr-target-1"],
        "seed": SEED, "budget_steps": BUDGET, "consumed_steps": steps, "validation_every": None,
        "schedule": [{"steps": steps, "suite_id": "val-target-v1", **target["summary"]}],
        "status": out["run"]["status"], "threshold_reached": reached,
        "steps_to_threshold": steps if reached else None, "final_evaluation_id": target["id"],
        "decision_id": d["id"], "search_rule": RULE, "intervention": d["intervention"],
    })
    ingest.trial(trial, graph)
    db.bump_revision(f"search trial {trial['id']}", graph)
    promotion = service.promote(pid, graph=graph)  # unchanged promo-1 implementation
    bundle = service.export_bundle(pid)
    return {"decision_id": d["id"], "trial": trial, "promotion": promotion,
            "evaluations": [{k: e[k] for k in ("id", "suite_id", "summary")} for e in evaluations], "bundle": bundle}
