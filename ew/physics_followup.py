"""One preregistered longer run after the three-trial physics study stopped."""
import json
import os
from . import artifacts, records, service
from .criteria import meets, THRESHOLDS
from .graph import db, ingest
from .physics_study import ROOT, RULE as ORIGINAL, SEED, CANONICAL, study_hash, reads, ranking, evaluate_development

RULE="physics-followup-v1"
PROTOCOL=ROOT/"evidence/physics-followup-v1/protocol.json"


def run(on_progress=None):
    if (artifacts.ROOT/"physics-adapt-v1-selected.json").exists():raise PermissionError("Selection is frozen")
    original=[t for t in records.all_of("trial") if t.get("search_rule")==ORIGINAL]
    if len(original)!=3:raise PermissionError("Original three-trial study must be complete")
    p=json.loads(PROTOCOL.read_text())
    if p["validation_protocol_sha256"]!=study_hash():raise ValueError("Validation protocol changed")
    if p["budget_steps"]!=600000 or p["max_trials"]!=1 or p["recipe"]!="ppo-mixed-mujoco-lr-v1" or p["seed"]!=SEED:
        raise ValueError("Follow-up protocol does not verify")
    queries=reads();ranked=ranking(queries);best=ranked[0]
    original_ids={t["child_policy_id"] for t in original}
    if best["policy_id"] not in original_ids:raise PermissionError("Expected an original physics child")
    if any(r["policy_id"] in original_ids and r["passed"]==8 and r["clearance_deficit"]==0 for r in ranked):
        raise PermissionError("An original candidate already met selection; do not extend")
    parent=artifacts.load_manifest(best["policy_id"])
    if parent["recipe"]!=p["recipe"]:raise PermissionError("Longer training must retain the parent's recipe")
    fingerprint=artifacts.sha256_file(PROTOCOL)
    marker=artifacts.ROOT/"physics-followup-v1-started.json"
    fd=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o444)
    with os.fdopen(fd,"w") as f:json.dump({"protocol_sha256":fingerprint,"parent_id":best["policy_id"],"parent_hash":artifacts.verify_policy(best["policy_id"])},f,indent=2)
    d=records.write("decision",{"rule_version":RULE,"mode":"deterministic","graph":db.GRAPH,
        "graph_revision":queries[0].graph_revision,"action":"train_from_parent","selected":best["policy_id"],
        "request":service.target_request(p["budget_steps"],p["recipe"]),"seed":SEED,"intervention":"longer_training",
        "ranking":ranked,"rejected":[],"queries":[q.to_log() for q in queries],
        "evidence_eval_ids":[e["evaluation_id"] for r in ranked for e in r["validation"].values()],
        "evidence_trial_ids":[t["id"] for t in original],"protocol_sha256":fingerprint,
        "explanation":f"The original three-trial study stopped without clearance. Live graph ranking selects {best['policy_id']} with {best['passed']}/8 suites and clearance deficit {best['clearance_deficit']}. One separately preregistered 600000-step continuation retains its exact recipe and seed. No confirmation has been opened."})
    ingest.decision(d);db.bump_revision("physics follow-up decision")
    pid=records.new_id("physics");parent_hash=artifacts.verify_policy(best["policy_id"])
    out=service.train_run(pid,family="static_crossing",budget_steps=p["budget_steps"],seed=SEED,parent_id=best["policy_id"],
        recipe=p["recipe"],run_kind=RULE,purpose=d["explanation"],decision_id=d["id"],on_progress=on_progress)
    artifacts.verify_policy(best["policy_id"],parent_hash)
    evaluations=[service.evaluate(pid,s,purpose=RULE,save_replay=True) for s in CANONICAL]
    evaluate_development(pid)
    target=next(e for e in evaluations if e["suite_id"]=="val-target-v1")
    reached=meets(target["summary"],THRESHOLDS["thr-target-1"])
    t=records.write("trial",{"parent_id":best["policy_id"],"parent_artifact_hash":parent_hash,"child_policy_id":pid,
        "child_artifact_hash":out["manifest"]["artifact_hash"],"run_id":out["run"]["id"],"target_family":"static_crossing",
        "target_family_id":d["request"]["target_family_id"],"suite_id":"val-target-v1","contract_id":parent["contract_id"],
        "recipe":p["recipe"],"threshold_id":"thr-target-1","threshold":THRESHOLDS["thr-target-1"],"seed":SEED,
        "budget_steps":p["budget_steps"],"consumed_steps":out["run"]["consumed_steps"],"validation_every":None,
        "schedule":[{"steps":out["run"]["consumed_steps"],"suite_id":"val-target-v1",**target["summary"]}],
        "status":out["run"]["status"],"threshold_reached":reached,"steps_to_threshold":out["run"]["consumed_steps"] if reached else None,
        "final_evaluation_id":target["id"],"decision_id":d["id"],"search_rule":RULE,"intervention":"longer_training","protocol_sha256":fingerprint})
    ingest.trial(t);gate=service.promote(pid);db.bump_revision("physics follow-up trial")
    return {"trial":t,"promotion":gate,"ranking":ranking(reads())}


if __name__=="__main__":
    print(json.dumps(run(lambda p:print(json.dumps({"progress":p}),flush=True)),indent=2))
