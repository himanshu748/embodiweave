"""Trusted operator for the new physics study; protected confirmation runs once."""
import argparse
import json
import os

from ew import artifacts, records, service
from ew.physics_study import OUT, RULE, protocol, study_hash, initialize, run_next, ranking, reads, measurement_protocol


def freeze():
    trials=[t for t in records.all_of("trial") if t.get("search_rule") in (RULE,"physics-followup-v1")]
    queries=reads()
    ranked={r["policy_id"]:r for r in ranking(queries)}
    selected=next((ranked[t["child_policy_id"]] for t in trials if t["child_policy_id"] in ranked and
        ranked[t["child_policy_id"]]["passed"]==8 and ranked[t["child_policy_id"]]["clearance_deficit"]==0),None)
    if selected is None:raise PermissionError("No new candidate passed the registered eight-suite stopping rule")
    pid=selected["policy_id"]
    gate=service.promotion_preview(pid)
    if gate["verdict"]!="promoted":raise PermissionError("Canonical gate did not pass")
    rec={"policy_id":pid,"artifact_hash":artifacts.verify_policy(pid),"selection_stopped":True,
         "training_domains":["2D","MuJoCo"],"protocol_sha256":study_hash(),"validation_gate":gate,"ranking":selected,
         "selection_queries":[q.to_log() for q in queries]}
    trial=next(t for t in trials if t["child_policy_id"]==pid)
    training_protocol=OUT/"protocol.json" if trial["search_rule"]==RULE else OUT.parent/"physics-followup-v1/protocol.json"
    if artifacts.sha256_file(training_protocol)!=trial["protocol_sha256"]:raise PermissionError("Training protocol does not verify")
    rec["training_study"]=trial["search_rule"]
    rec["training_protocol_sha256"]=trial["protocol_sha256"]
    with (artifacts.ROOT/"physics-adapt-v1-selected.json").open("x") as f:json.dump(rec,f,indent=2)
    with (OUT/"selected.json").open("x") as f:json.dump(rec,f,indent=2)
    return rec


def confirm():
    from sim.mujoco.evaluate import run
    selected=json.loads((artifacts.ROOT/"physics-adapt-v1-selected.json").read_text())
    if not selected["selection_stopped"] or selected["protocol_sha256"]!=study_hash():raise PermissionError("Selection not frozen")
    pid=selected["policy_id"];artifacts.verify_policy(pid,selected["artifact_hash"])
    if service.promotion_preview(pid)["verdict"]!="promoted":raise PermissionError("Canonical gate does not verify")
    p=measurement_protocol(pid,"confirmation")
    marker=artifacts.ROOT/"physics-adapt-v1-confirmation-started.json"
    fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o444)
    with os.fdopen(fd,"w")as f:json.dump({"selection":selected,"measurement_protocol":p},f,indent=2)
    # Never ingested into FalkorDB. A crash spends the authorization, too.
    run(p,OUT/"confirmation")
    return json.loads((OUT/"confirmation/summary.json").read_text())


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=["initialize","train","freeze","confirm"])
    args=parser.parse_args()
    if args.action=="initialize":initialize()
    elif args.action=="train":print(json.dumps(run_next(on_progress=lambda p:print(json.dumps({"progress":p}),flush=True)),indent=2),flush=True)
    else:print(json.dumps(freeze() if args.action=="freeze" else confirm(),indent=2),flush=True)
