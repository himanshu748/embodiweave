"""Preregistered validation-only continuation. Never accesses held-out outcomes.

The old search stopped as specified. This is a distinct, user-authorized study;
historical validation and confirmation records are immutable. Selection requires
the unchanged gate plus two episodes of collision clearance on every suite.
That clearance is an experiment stopping rule, not a change to promo-1.
"""
import hashlib
import json
import math
from pathlib import Path

from . import artifacts, records, service
from .contract import CONTRACT_V1
from .criteria import THRESHOLDS, meets
from .graph import db, ingest, queries as Q
from .search import CRITERIA, SUITES, rank_candidates

RULE = "robustness-v2"
SEED, BUDGET, MAX_TRIALS = 19, 600_000, 3
RECIPES = {"collision": "ppo-rehearsal-collision20-v2",
           "learning_rate": "ppo-rehearsal-collision20-lr-v2",
           "entropy": "ppo-rehearsal-collision20-entropy-v2"}
PROTOCOL_PATH = Path(__file__).resolve().parents[1] / "evidence/robustness-v2/protocol.json"


def protocol_hash():
    return hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()


def with_clearance(ranking):
    for candidate in ranking:
        deficit = 0
        for c in CRITERIA:
            e = candidate["validation"][c["suite_id"]]
            # Canonical suites are frozen: target 60, retained 40 each.
            from .scenarios import SUITES as DEFINITIONS
            n = len(DEFINITIONS[c["suite_id"]].seeds)
            collisions = round(e["collision_rate"] * n)
            allowed = math.floor(c["max_collision"] * n + 1e-8)
            deficit += max(0, collisions - max(0, allowed - 2))
        candidate["clearance_deficit"] = deficit
        candidate["sort_key"] = [4-candidate["passed"], deficit, *candidate["sort_key"][1:]]
    ranking.sort(key=lambda r: r["sort_key"])
    for i, candidate in enumerate(ranking, 1):
        candidate["rank"] = i
    return ranking


def plan(graph=None):
    protocol = json.loads(PROTOCOL_PATH.read_text())
    if (protocol["rule"], protocol["seed"], protocol["budget_steps"], protocol["max_trials"]) != (RULE, SEED, BUDGET, MAX_TRIALS):
        raise ValueError("Protocol does not match the registered study")
    candidates = Q.run("search_validation", {"contract": CONTRACT_V1.contract_id, "suites": SUITES}, graph)
    history = Q.run("search_history", {"contract": CONTRACT_V1.contract_id, "rule": RULE}, graph)
    ranking = with_clearance(rank_candidates(candidates.dicts()))
    if not ranking:
        raise ValueError("No exact-artifact complete-validation origin")
    attempts = history.dicts()
    # Never restart selection after confirmation or a frozen selection.
    if (artifacts.ROOT / "robustness-v2-selected.json").exists():
        raise PermissionError("Selection is frozen; no further training in this study")
    if len(attempts) >= MAX_TRIALS:
        raise ValueError("Registered trial budget exhausted")
    best = ranking[0]
    tried = {r["intervention"] for r in attempts}
    if attempts and best["passed"] == 4 and best["clearance_deficit"] == 0:
        raise ValueError("Selection criterion reached; freeze the candidate")
    # First isolate the collision-cost change. Further choices depend only on
    # complete canonical validation: collision deficits prefer a lower rate;
    # goal failures with collision clearance prefer exploration.
    order = (["collision", "learning_rate", "entropy"] if best["clearance_deficit"]
             else ["collision", "entropy", "learning_rate"])
    intervention = next(x for x in order if x not in tried)
    failures = [Q.run("failure_inspection", {"evaluation": e["evaluation_id"]}, graph)
                for e in best["validation"].values()]
    decision = records.write("decision", {
        "rule_version": RULE, "mode": "deterministic", "graph_revision": candidates.graph_revision,
        "graph": graph or db.GRAPH, "action": "train_from_parent", "selected": best["policy_id"],
        "request": service.target_request(BUDGET, RECIPES[intervention]), "intervention": intervention,
        "seed": SEED, "ranking": ranking, "rejected": [], "protocol_sha256": protocol_hash(),
        "evidence_trial_ids": [t["trial_id"] for t in attempts],
        "evidence_eval_ids": [e["evaluation_id"] for c in ranking for e in c["validation"].values()],
        "queries": [candidates.to_log(), history.to_log(), *[f.to_log() for f in failures]],
        "explanation": f"Canonical validation ranks {best['policy_id']} first: {best['passed']}/4 suites, "
                       f"collision-clearance deficit {best['clearance_deficit']} episodes. "
                       f"Choose {intervention}; fixed seed {SEED}, {BUDGET} requested additional steps. "
                       "No held-out or MuJoCo outcomes enter this decision.",
    })
    ingest.decision(decision, graph)
    db.bump_revision(f"robustness decision {decision['id']}", graph)
    return decision


def run_next(graph=None, on_progress=None):
    d = plan(graph)
    pid = records.new_id("robust")
    parent_hash = artifacts.verify_policy(d["selected"])
    out = service.train_run(pid, family="static_crossing", budget_steps=BUDGET, seed=SEED,
                            parent_id=d["selected"], recipe=d["request"]["recipe"], run_kind=RULE,
                            purpose=d["explanation"], decision_id=d["id"], graph=graph, on_progress=on_progress)
    artifacts.verify_policy(d["selected"], parent_hash)
    evaluations = [service.evaluate(pid, s, purpose=f"{RULE}:{d['id']}", save_replay=True, graph=graph) for s in SUITES]
    target = next(e for e in evaluations if e["suite_id"] == "val-target-v1")
    reached = meets(target["summary"], THRESHOLDS["thr-target-1"])
    trial = records.write("trial", {
        "parent_id": d["selected"], "parent_artifact_hash": parent_hash, "child_policy_id": pid,
        "child_artifact_hash": out["manifest"]["artifact_hash"], "run_id": out["run"]["id"],
        "target_family": "static_crossing", "target_family_id": d["request"]["target_family_id"],
        "suite_id": "val-target-v1", "contract_id": CONTRACT_V1.contract_id, "recipe": d["request"]["recipe"],
        "threshold_id": "thr-target-1", "threshold": THRESHOLDS["thr-target-1"], "seed": SEED,
        "budget_steps": BUDGET, "consumed_steps": out["run"]["consumed_steps"], "validation_every": None,
        "schedule": [{"steps": out["run"]["consumed_steps"], "suite_id": target["suite_id"], **target["summary"]}],
        "status": out["run"]["status"], "threshold_reached": reached,
        "steps_to_threshold": out["run"]["consumed_steps"] if reached else None,
        "final_evaluation_id": target["id"], "decision_id": d["id"], "search_rule": RULE,
        "intervention": d["intervention"], "protocol_sha256": protocol_hash(),
    })
    ingest.trial(trial, graph)
    db.bump_revision(f"robustness trial {trial['id']}", graph)
    gate = service.promote(pid, graph=graph)
    return {"decision_id": d["id"], "trial": trial, "promotion": gate,
            "evaluations": [{k: e[k] for k in ("id", "suite_id", "summary")} for e in evaluations]}
