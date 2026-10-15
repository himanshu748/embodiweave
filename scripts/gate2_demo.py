"""Gate 2: real FalkorDB-backed parent selection on the target mission."""
import json, sys
from ew import service
from ew.graph import db
from ew.scenarios import SUITES

def show(d):
    print(f"\n### decision {d['id']} rev={d['graph_revision']} action={d['action']} selected={d['selected']}")
    print("   ", d["explanation"])
    for r in d["rejected"]:
        print("    rejected", r["policy_id"], r["reasons"])
    for c in d.get("ranking", []):
        print(f"    #{c['rank']} {c['policy_id']:22s} p={c['p_reach']:.3f} ({c['p_basis']}) val={c['validation']['score']:+.3f} "
              f"succ={c['validation']['success_rate']:.2f} coll={c['validation']['collision_rate']:.2f}")

req = service.target_request(budget=60_000)
d1 = service.record_decision(req); show(d1)
for pid in d1.get("needs_evaluation", []):
    e = service.evaluate(pid, "val-target-v1", purpose=f"matched-validation for {d1['id']}", save_replay=True)
    print("   eval", pid, e["id"], e["summary"])
d2 = service.record_decision(req); show(d2)
if d2["action"] == "train_from_parent" and "--trial" in sys.argv:
    seed = int(sys.argv[sys.argv.index("--trial") + 1])
    t = service.transfer_trial(parent_id=d2["selected"], child_id=f"{d2['selected']}~tgt-s{seed}",
                               target_family="static_crossing", threshold_id="thr-target-1", budget_steps=60_000,
                               seed=seed, decision_id=d2["id"], purpose="decision-launched transfer trial")
    tr = t["trial"]
    print(f"\n   trial {tr['id']} reached={tr['threshold_reached']} steps_to_threshold={tr['steps_to_threshold']} "
          f"consumed={tr['consumed_steps']} schedule={[(p['steps'], p['success_rate'], p['collision_rate']) for p in tr['schedule']]}")
    d3 = service.record_decision(req); show(d3)
print("\ngraph revision", db.revision())
