"""Gate 5 experiment exp-3. Protocol frozen to disk (and in git) before any run starts.

Question: after exp-2 exposed that ew-select-2 keeps reuse on a p_reach tie, does ew-select-3 (which breaks
that tie with measured trial-child validation) pick the arm that does best on a fresh final test?
exp-2 spent test-target-v2, so exp-3 uses test-target-v3 and new comparison seeds.
"""
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROTOCOL = {
    "id": "exp-3", "frozen_at": None, "target_family": "static_crossing", "recipe": "ppo-r1", "budget": 150_000,
    "threshold_id": "thr-target-1", "validation_suite": "val-target-v1", "validation_points": 4,
    "final_test_suite": "test-target-v3", "selection_rule": "ew-select-3", "catalog": "library run kind only",
    "comparison_seeds": [801, 802, 803],
    "arms": {"graph": "ew-select-3 on graph evidence at freeze time (parent or scratch)",
             "graph_v2": "ew-select-2 on the same graph, for contrast",
             "latest": "latest created_at among eligible library checkpoints",
             "best_val": "max (success_rate - collision_rate) on val-target-v1, ties by policy id",
             "scratch": "no parent weights, fresh VecNormalize"},
    "notes": "Identical (parent, seed) pairs are computed once and shared between arms that agree. "
             "Every run is recorded as a Trial and ingested, so the graph keeps learning after selection.",
}
WORKERS = 3


def _trial(args):
    parent, seed = args
    from ew import service
    child = f"{parent or 'scratch'}~x3-s{seed}"
    t0 = time.time()
    r = service.transfer_trial(parent_id=parent, child_id=child, target_family="static_crossing",
                               threshold_id="thr-target-1", budget_steps=PROTOCOL["budget"], seed=seed,
                               run_kind="comparison", purpose="exp-3 comparison", trial_id=f"trial-exp3-{parent or 'scratch'}-s{seed}")
    t = r["trial"]
    return {"parent": parent, "seed": seed, "child": child, "schedule": t["schedule"],
            "steps_to_threshold": t["steps_to_threshold"], "reached": t["threshold_reached"],
            "consumed": t["consumed_steps"], "wall_s": round(time.time() - t0, 1),
            "final_val": r["final_evaluation"]["summary"], "final_val_id": r["final_evaluation"]["id"],
            "trial_id": t["id"], "run_id": t["run_id"]}


def _final(child):
    from ew import service
    e = service.evaluate(child, PROTOCOL["final_test_suite"], purpose="exp-3 frozen final test",
                         final_test_runner=True, save_replay=True, experiment_id="exp-3")
    return child, {"evaluation_id": e["id"], **e["summary"]}


def main():
    from ew import artifacts, service
    out_dir = artifacts.ROOT / "results"
    if (out_dir / "experiment3.json").exists():
        raise SystemExit("exp-3 already reported; its final test is spent")
    PROTOCOL["frozen_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out_dir / "protocol3.json").write_text(json.dumps(PROTOCOL, indent=1))
    req = {**service.target_request(budget=PROTOCOL["budget"]), "candidate_run_kinds": ["library"]}
    d2 = service.record_decision(req, rule="ew-select-3")
    d1 = service.record_decision(req, rule="ew-select-2")
    cat = {c["policy_id"]: c for c in d2["ranking"]}
    eligible = sorted(cat)
    latest = max(eligible, key=lambda p: artifacts.load_manifest(p)["created_at"])
    best_val = sorted(eligible, key=lambda p: (-cat[p]["validation"]["score"], p))[0]
    arms = {"graph": d2["selected"], "graph_v2": d1["selected"], "latest": latest, "best_val": best_val, "scratch": None}
    print("graph decision:", d2["id"], d2["action"], d2["explanation"], flush=True)
    print("arms:", arms, flush=True)

    parents = sorted(set(arms.values()), key=lambda v: v or "")
    t1 = time.time()
    with ProcessPoolExecutor(WORKERS) as ex:
        runs = list(ex.map(_trial, [(p, s) for p in parents for s in PROTOCOL["comparison_seeds"]]))
    train_wall = time.time() - t1
    with ProcessPoolExecutor(WORKERS) as ex:
        finals = dict(ex.map(_final, [x["child"] for x in runs]))
    by_parent = {}
    for x in runs:
        x["final_test"] = finals[x["child"]]
        by_parent.setdefault(x["parent"], []).append(x)

    summary = {}
    for arm, p in arms.items():
        rows = by_parent[p]
        n = len(rows)
        summary[arm] = {"parent": p, "n_seeds": n,
                        "reached": sum(x["reached"] for x in rows),
                        "test_success_mean": round(sum(x["final_test"]["success_rate"] for x in rows) / n, 4),
                        "test_collision_mean": round(sum(x["final_test"]["collision_rate"] for x in rows) / n, 4),
                        "per_seed_test_success": {x["seed"]: x["final_test"]["success_rate"] for x in rows}}
    res = {"protocol": PROTOCOL, "decision_graph": d2["id"], "decision_graph_v2": d1["id"],
           "graph_action": d2["action"], "graph_explanation": d2["explanation"],
           "graph_revision_at_selection": d2["graph_revision"], "arms": arms, "eligible": eligible,
           "ranking_graph": [{k: c[k] for k in ("rank", "policy_id", "p_reach", "p_basis", "validation", "n_completed", "n_reached")}
                             for c in d2["ranking"]], "scratch_option": d2.get("scratch_option"),
           "runs": by_parent, "summary": summary,
           "costs": {"steps": sum(x["consumed"] for x in runs), "train_wall_s": round(train_wall, 1)},
           "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (out_dir / "experiment3.json").write_text(json.dumps(res, indent=1, default=str))
    for arm, s in summary.items():
        print(f"{arm:9s} {str(s['parent']):11s} reached {s['reached']}/{s['n_seeds']} test success {s['test_success_mean']:.3f} "
              f"collision {s['test_collision_mean']:.3f} per-seed {s['per_seed_test_success']}", flush=True)


if __name__ == "__main__":
    main()
