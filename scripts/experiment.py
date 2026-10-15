"""Gate 5 experiment exp-1. The protocol is written to disk before any run starts.

Phase A  transfer measurement (cost reported separately): 2 trials per eligible library candidate.
Select   frozen rule ew-select-1 on the graph after phase A; nohist variant; latest; best matched validation.
Phase B  equal-budget adaptation for each distinct arm parent and scratch, paired seeds.
Final    frozen test-target-v1 on every phase B checkpoint, once, after phase B is complete.
"""
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROTOCOL = {
    "id": "exp-1", "frozen_at": None, "target_family": "static_crossing", "recipe": "ppo-r1", "budget": 150_000,
    "threshold_id": "thr-target-1", "validation_suite": "val-target-v1", "validation_points": 4,
    "final_test_suite": "test-target-v1", "selection_rule": "ew-select-1", "catalog": "library run kind only",
    "history_seeds": [501, 502], "comparison_seeds": [601, 602, 603],
    "arms": {"graph": "ew-select-1 on graph evidence after phase A",
             "graph_nohist": "ew-select-1-nohist (matched validation only; same rule otherwise)",
             "latest": "latest created_at among eligible library checkpoints",
             "best_val": "max (success_rate - collision_rate) on val-target-v1, ties by policy id",
             "scratch": "no parent weights, fresh VecNormalize"},
    "notes": "Identical (parent, seed) pairs are computed once and shared between arms that agree.",
}
WORKERS = 3


def _trial(args):
    parent, seed, tag, kind = args
    from ew import service
    child = f"{parent or 'scratch'}~{tag}-s{seed}"
    t0 = time.time()
    if parent is None:
        out = service.train_run(child, family="static_crossing", budget_steps=PROTOCOL["budget"], seed=seed,
                                run_kind=kind, purpose=f"exp-1 {tag} scratch", validation_suite="val-target-v1")
        from ew.criteria import THRESHOLDS
        sched = out["run"]["validation_schedule"]
        stt = service.steps_to_threshold(sched, THRESHOLDS["thr-target-1"])
        fe = service.evaluate(child, "val-target-v1", purpose=f"exp-1 {tag} final validation", save_replay=True)
        return {"parent": None, "seed": seed, "child": child, "schedule": sched, "steps_to_threshold": stt,
                "reached": stt is not None, "consumed": out["run"]["consumed_steps"], "wall_s": round(time.time() - t0, 1),
                "final_val": fe["summary"], "final_val_id": fe["id"], "trial_id": None, "run_id": out["run"]["id"]}
    r = service.transfer_trial(parent_id=parent, child_id=child, target_family="static_crossing",
                               threshold_id="thr-target-1", budget_steps=PROTOCOL["budget"], seed=seed,
                               run_kind=kind, purpose=f"exp-1 {tag}")
    t = r["trial"]
    return {"parent": parent, "seed": seed, "child": child, "schedule": t["schedule"],
            "steps_to_threshold": t["steps_to_threshold"], "reached": t["threshold_reached"],
            "consumed": t["consumed_steps"], "wall_s": round(time.time() - t0, 1),
            "final_val": r["final_evaluation"]["summary"], "final_val_id": r["final_evaluation"]["id"],
            "trial_id": t["id"], "run_id": t["run_id"]}


def _final(child):
    from ew import service
    e = service.evaluate(child, "test-target-v1", purpose="exp-1 frozen final test", final_test_runner=True, save_replay=True,
                         experiment_id="exp-1")
    return child, {"evaluation_id": e["id"], **e["summary"]}


def main():
    from ew import artifacts, records, service
    out_dir = artifacts.ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    PROTOCOL["frozen_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out_dir / "protocol.json").write_text(json.dumps(PROTOCOL, indent=1))
    req = {**service.target_request(budget=PROTOCOL["budget"]), "candidate_run_kinds": ["library"]}
    d0 = service.record_decision(req)
    eligible = sorted(c["policy_id"] for c in d0["ranking"])
    print("eligible:", eligible, "pre-phase-A choice:", d0["selected"], flush=True)

    t0 = time.time()
    with ProcessPoolExecutor(WORKERS) as ex:
        phase_a = list(ex.map(_trial, [(p, s, "hist", "transfer_measurement") for p in eligible for s in PROTOCOL["history_seeds"]]))
    phase_a_wall = time.time() - t0
    for x in phase_a:
        print("A", x["parent"], x["seed"], x["reached"], x["steps_to_threshold"], x["final_val"]["success_rate"], flush=True)

    d_graph = service.record_decision(req)
    d_nohist = service.record_decision(req, use_history=False)
    cat = {c["policy_id"]: c for c in d_graph["ranking"]}
    latest = max(eligible, key=lambda p: artifacts.load_manifest(p)["created_at"])
    best_val = sorted(eligible, key=lambda p: (-cat[p]["validation"]["score"], p))[0]
    arms = {"graph": d_graph["selected"], "graph_nohist": d_nohist["selected"], "latest": latest,
            "best_val": best_val, "scratch": None}
    print("arms:", arms, flush=True)

    parents = sorted({v for v in arms.values()}, key=lambda v: v or "")
    jobs_b = [(p, s, "cmp", "comparison") for p in parents for s in PROTOCOL["comparison_seeds"]]
    t1 = time.time()
    with ProcessPoolExecutor(WORKERS) as ex:
        phase_b = list(ex.map(_trial, jobs_b))
    phase_b_wall = time.time() - t1
    by_parent = {}
    for x in phase_b:
        by_parent.setdefault(x["parent"], []).append(x)

    with ProcessPoolExecutor(WORKERS) as ex:
        finals = dict(ex.map(_final, [x["child"] for x in phase_b]))
    for x in phase_b:
        x["final_test"] = finals[x["child"]]

    library_cost = [{"policy": r["child_policy_id"], "steps": r["consumed_steps"], "wall_s": r["wall_s"]}
                    for r in records.all_of("run") if r["run_kind"] == "library"]
    res = {"protocol": PROTOCOL, "decision_before_phase_a": d0["id"], "decision_graph": d_graph["id"],
           "decision_nohist": d_nohist["id"], "graph_revision_at_selection": d_graph["graph_revision"],
           "arms": arms, "eligible": eligible, "rejected": d_graph["rejected"],
           "ranking_graph": [{k: c[k] for k in ("rank", "policy_id", "p_reach", "p_basis", "validation", "n_completed", "n_reached")}
                             for c in d_graph["ranking"]],
           "phase_a": phase_a, "phase_b": by_parent,
           "costs": {"library_steps": sum(c["steps"] for c in library_cost), "library_wall_s": round(sum(c["wall_s"] for c in library_cost), 1),
                     "transfer_measurement_steps": sum(x["consumed"] for x in phase_a), "phase_a_wall_s": round(phase_a_wall, 1),
                     "comparison_steps_per_arm_seed": PROTOCOL["budget"], "phase_b_wall_s": round(phase_b_wall, 1)},
           "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (out_dir / "experiment.json").write_text(json.dumps(res, indent=1, default=str))
    for arm, p in arms.items():
        rows = by_parent[p]
        print(f"{arm:13s} {str(p):12s} " + " | ".join(
            f"s{x['seed']} reach={x['reached']} stt={x['steps_to_threshold']} val={x['final_val']['success_rate']:.2f}/"
            f"{x['final_val']['collision_rate']:.2f} test={x['final_test']['success_rate']:.2f}/{x['final_test']['collision_rate']:.2f}"
            for x in rows), flush=True)


if __name__ == "__main__":
    main()
