"""Build the small checkpoint library with real PPO runs. Library cost is accounted separately."""
import json, time
from ew import service
from ew.contract import CONTRACT_MIRRORED, CONTRACT_V1
from ew.graph import ingest, db
from ew.scenarios import FAMILIES, with_controls

db.delete_graph(db.GRAPH)
print("graph revision after init:", ingest.init_world())
t0 = time.time()
plan = [
    ("P-open-a", None, "open", 120_000, 101, CONTRACT_V1, "reach-goal base policy"),
    ("P-static-a", "P-open-a", "static", 150_000, 102, None, "static avoidance fine-tune"),
    ("P-cross-a", "P-open-a", "crossing", 150_000, 103, None, "crossing-obstacle fine-tune"),
    ("P-mirror", None, "crossing", 200_000, 105, CONTRACT_MIRRORED, "same shape, mirrored ray order (other robot stack)"),
    ("P-static-b", "P-static-a", with_controls(FAMILIES["static"], n_static=4), 100_000, 104, None, "denser static fine-tune (latest)"),
]
cost = []
for pid, parent, fam, steps, seed, contract, why in plan:
    out = service.train_run(pid, family=fam, budget_steps=steps, seed=seed, parent_id=parent,
                            contract=contract, run_kind="library", purpose=why)
    r = out["run"]; cost.append({"policy": pid, "steps": r["consumed_steps"], "wall_s": r["wall_s"]})
    print(pid, r["consumed_steps"], r["wall_s"], out["manifest"]["artifact_hash"][:12], flush=True)
# natural validation history (each on suites relevant to how it was trained)
evals = {"P-open-a": ["val-open-v1"], "P-static-a": ["val-open-v1", "val-static-v1"],
         "P-cross-a": ["val-open-v1", "val-crossing-v1"], "P-mirror": ["val-crossing-v1"],
         "P-static-b": ["val-open-v1", "val-static-v1"]}
for pid, suites in evals.items():
    for s in suites:
        e = service.evaluate(pid, s, purpose="library-history", save_replay=True)
        cost.append({"eval": e["id"], "policy": pid, "suite": s, "wall_s": e["wall_s"]})
        print(pid, s, e["summary"], flush=True)
# one earlier transfer measurement on a DIFFERENT target (crossing), to exercise trial conditioning
tr = service.transfer_trial(parent_id="P-static-a", child_id="P-static-a~cross-t1", target_family="crossing",
                            threshold_id="thr-target-1", budget_steps=60_000, seed=201,
                            run_kind="transfer_measurement", purpose="prior trial on crossing target")
print("trial", tr["trial"]["id"], tr["trial"]["threshold_reached"], tr["trial"]["steps_to_threshold"])
cost.append({"trial": tr["trial"]["id"], "steps": tr["trial"]["consumed_steps"], "wall_s": tr["run"]["wall_s"]})
print(json.dumps({"library_cost": cost, "total_wall_s": round(time.time() - t0, 1),
                  "graph_revision": db.revision()}, indent=1))
