"""Independent, preregistered mixed-physics adaptation. No final data in planning."""
import hashlib
import json
import math
from pathlib import Path

from . import artifacts, records, service
from .contract import CONTRACT_V1
from .criteria import meets, THRESHOLDS
from .graph import db, ingest, queries as Q
from .search import CRITERIA, SUITES as CANONICAL, rank_candidates
from .scenarios import SUITES, FAMILIES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/physics-adapt-v1"
RULE, SEED, BUDGET, MAX_TRIALS = "physics-adapt-v1", 23, 300_000, 3
RECIPES = {"mixed_physics": "ppo-mixed-mujoco-v1", "collision": "ppo-mixed-mujoco-collision40-v1", "learning_rate": "ppo-mixed-mujoco-lr-v1"}


def protocol(): return json.loads((OUT / "protocol.json").read_text())
def fingerprint(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def study_hash(): return artifacts.sha256_file(OUT / "protocol.json")
def physical_ids(): return [s["id"] for s in protocol()["development"]]


def measurement_protocol(pid, phase):
    p = protocol()
    for name, expected in p["frozen_physics_sources"].items():
        if artifacts.sha256_file(ROOT / name) != expected:
            raise ValueError("Registered physics or sensor source changed")
    m = artifacts.load_manifest(pid)
    return {"version": RULE, "role": "validation" if phase == "development" else "final_test", "physics": "mujoco",
        "mujoco": p["mujoco"], "contract_id": CONTRACT_V1.contract_id, "deterministic_policy": True,
        "training": False, "policy_training_domains": ["2D", "MuJoCo"] if m["recipe_params"].get("physics") else ["2D"],
        "policies": {"candidate": {"id": pid, "artifact_hash": artifacts.verify_policy(pid)}},
        "suites": p[phase], "sources": p["frozen_physics_sources"], "study_protocol_sha256": study_hash(),
        "selection": "Development validation only" if phase == "development" else "One authorized confirmation after selection stopped",
        "record_prefix": "pva1" if phase == "development" else "pft1"}


def ingest_development(pid, graph=None):
    folder = OUT / "development" / pid
    p = json.loads((folder / "protocol.json").read_text())
    if p != measurement_protocol(pid, "development"):
        raise ValueError("Development protocol does not verify")
    checksums = json.loads((folder / "checksums.json").read_text())
    actual = {str(f.relative_to(folder)) for f in folder.rglob("*") if f.is_file() and f.name != "checksums.json"}
    if set(checksums) != actual: raise ValueError("Unsigned physics evidence")
    for name, expected in checksums.items():
        file=(folder/name).resolve()
        if not file.is_relative_to(folder.resolve()) or artifacts.sha256_file(file)!=expected: raise ValueError("Physics evidence checksum mismatch")
    for suite in p["suites"]:
        e=json.loads((folder/f"candidate-{suite['family']}.json").read_text());summary=e["summary"]
        if e["role"]!="validation" or e["protocol_hash"]!=fingerprint(p) or [ep["seed"] for ep in e["episodes"]]!=suite["seeds"]:
            raise ValueError("Incomplete or protected physics evidence")
        for outcome in ("success","collision","timeout"):
            if sum(ep["outcome"]==outcome for ep in e["episodes"])!=summary[outcome]: raise ValueError("Physics counts disagree")
        if not records.exists("evaluation", e["id"]):
            records.write("evaluation", {"id":e["id"],"policy_id":pid,"artifact_hash":e["artifact_hash"],
                "suite_id":suite["id"],"suite_role":"validation","suite_version":RULE,
                "family_id":FAMILIES[suite["family"]].fid(),"contract_id":CONTRACT_V1.contract_id,
                "seeds":suite["seeds"],"summary":summary,"episodes":e["episodes"],"physics":"mujoco",
                "protocol_sha256":study_hash(),"purpose":"Physics development validation, never confirmation",
                "source_evidence":str(folder.relative_to(ROOT)),"wall_s":e["wall_s"]})
        elif records.read("evaluation",e["id"])["summary"] != summary:
            raise ValueError("Persisted physics record disagrees with verified evidence")
        # Stable suite fingerprint independent of which checkpoint is assessed.
        sf=fingerprint({"study":study_hash(),"suite":suite})
        db.rw("MERGE (s:Suite {id:$id}) SET s.role='validation', s.physics='mujoco', s.fingerprint=$fp, s.episodes=$n "
              "WITH s MATCH (f:Family {id:$family}) MERGE (s)-[:DRAWS_FROM]->(f)",
              {"id":suite["id"],"fp":sf,"n":len(suite["seeds"]),"family":FAMILIES[suite["family"]].fid()},graph)
        db.rw("MATCH (p:Policy {id:$p}) WHERE p.artifact_hash=$hash WITH p MERGE (e:Evaluation {id:$id}) "
              "SET e.artifact_hash=$hash, e.complete_suite=true, e.suite_fingerprint=$fp, e.physics='mujoco', "
              "e.success_rate=$sr, e.collision_rate=$cr, e.timeout_rate=$tr, e.episodes=$n, e.measured=true, e.at=$at "
              "WITH e,p MATCH (s:Suite {id:$s}) MERGE (e)-[:ASSESSED]->(p) MERGE (e)-[:ON_SUITE]->(s)",
              {"id":e["id"],"p":pid,"hash":e["artifact_hash"],"fp":sf,"s":suite["id"],"sr":summary["success_rate"],
               "cr":summary["collision_rate"],"tr":summary["timeout_rate"],"n":summary["episodes"],"at":RULE},graph)
        for hit in ("wall","static","mover"):
            seeds=[ep["seed"] for ep in e["episodes"] if ep["outcome"]=="collision" and ep["hit"]==hit]
            if seeds: db.rw("MERGE (f:Failure {id:$id}) SET f.outcome='collision', f.hit=$hit, f.count=$n, f.seeds=$seeds, f.measured=true "
                "WITH f MATCH (e:Evaluation {id:$e}) MERGE (f)-[:OBSERVED_IN]->(e)",
                {"id":e["id"]+":collision:"+hit,"hit":hit,"n":len(seeds),"seeds":seeds,"e":e["id"]},graph)
    db.bump_revision(f"physics development {pid}",graph)


def evaluate_development(pid, graph=None):
    import mujoco
    if mujoco.__version__ != protocol()["mujoco"]: raise ValueError("MuJoCo runtime differs from preregistration")
    from sim.mujoco.evaluate import run
    run(measurement_protocol(pid,"development"), OUT/"development"/pid)
    ingest_development(pid, graph)


def reads(graph=None):
    return [Q.run("search_validation", {"contract":CONTRACT_V1.contract_id,"suites":suites},graph) for suites in (CANONICAL,physical_ids())]


def ranking(queries):
    joined={}
    for q in queries:
        for r in q.dicts():joined.setdefault(r["policy_id"],{})[r["suite_id"]]=r
    specs=[(c["suite_id"],c,len(SUITES[c["suite_id"]].seeds),False) for c in CRITERIA]
    byfamily=dict(zip(("static_crossing","open","static","crossing"),CRITERIA))
    specs += [(s["id"],byfamily[s["family"]],len(s["seeds"]),True) for s in protocol()["development"]]
    result=[]
    for pid,ev in joined.items():
        if set(ev)!={s[0] for s in specs}:continue
        artifacts.verify_policy(pid,next(iter(ev.values()))["artifact_hash"])
        failed,clearance,deficits,score=0,0,[],0.
        for sid,c,n,physical in specs:
            e=ev[sid];failed+=not(e["success_rate"]>=c["min_success"] and e["collision_rate"]<=c["max_collision"])
            deficits.append(max(0,c["min_success"]-e["success_rate"])+max(0,e["collision_rate"]-c["max_collision"]))
            if physical:clearance+=max(0,round(e["collision_rate"]*n)-max(0,math.floor(c["max_collision"]*n+1e-8)-1))
            score+=e["success_rate"]-e["collision_rate"]
        result.append({"policy_id":pid,"passed":8-failed,"clearance_deficit":clearance,"validation":ev,
                       "sort_key":[failed,clearance,round(max(deficits),4),round(sum(deficits),4),-round(score,4),pid]})
    result.sort(key=lambda r:r["sort_key"])
    for i,r in enumerate(result,1):r["rank"]=i
    return result


def initialize(graph=None):
    q=Q.run("search_validation",{"contract":CONTRACT_V1.contract_id,"suites":CANONICAL},graph)
    candidates=rank_candidates(q.dicts())[:2]
    path=OUT/"initial-parent-selection.json"
    if path.exists():
        frozen=json.loads(path.read_text());candidates=frozen["parents"]
    else:
        path.write_text(json.dumps({"protocol_sha256":study_hash(),"query":q.to_log(),"parents":candidates},indent=2)+"\n")
    for c in candidates:evaluate_development(c["policy_id"],graph)


def run_next(graph=None,on_progress=None):
    if (artifacts.ROOT/"physics-adapt-v1-selected.json").exists():raise PermissionError("Physics selection is frozen")
    queries=reads(graph);ranked=ranking(queries)
    history=Q.run("search_history",{"contract":CONTRACT_V1.contract_id,"rule":RULE},graph)
    attempts=history.dicts()
    if len(attempts)>=MAX_TRIALS:raise ValueError("Registered physics trial budget exhausted")
    new={t["child_id"] for t in attempts}
    eligible=[r for r in ranked if r["policy_id"] in new and r["passed"]==8 and not r["clearance_deficit"]]
    if eligible:raise ValueError("New candidate meets the stopping rule; freeze selection")
    best=ranked[0];tried={t["intervention"] for t in attempts}
    order=["mixed_physics","collision","learning_rate"] if best["clearance_deficit"] else ["mixed_physics","learning_rate","collision"]
    change=next(x for x in order if x not in tried)
    d=records.write("decision",{"rule_version":RULE,"mode":"deterministic","graph":graph or db.GRAPH,
        "graph_revision":queries[0].graph_revision,"action":"train_from_parent","selected":best["policy_id"],
        "request":service.target_request(BUDGET,RECIPES[change]),"seed":SEED,"intervention":change,
        "ranking":ranked,"rejected":[],"queries":[*[q.to_log() for q in queries],history.to_log()],
        "evidence_eval_ids":[e["evaluation_id"] for r in ranked for e in r["validation"].values()],
        "evidence_trial_ids":[t["trial_id"] for t in attempts],"protocol_sha256":study_hash(),
        "explanation":f"Graph ranking selects {best['policy_id']} with {best['passed']}/8 suites and physics clearance deficit {best['clearance_deficit']}. "
                      f"Choose {change}; 4 MuJoCo and 4 kinematic training environments, fixed seed {SEED}, {BUDGET} requested steps. No confirmation evidence is queried."})
    ingest.decision(d,graph);db.bump_revision(f"physics decision {d['id']}",graph)
    pid=records.new_id("physics");parent_hash=artifacts.verify_policy(best["policy_id"])
    out=service.train_run(pid,family="static_crossing",budget_steps=BUDGET,seed=SEED,parent_id=best["policy_id"],
        recipe=RECIPES[change],run_kind=RULE,purpose=d["explanation"],decision_id=d["id"],graph=graph,on_progress=on_progress)
    artifacts.verify_policy(best["policy_id"],parent_hash)
    ev=[service.evaluate(pid,s,purpose=RULE,save_replay=True,graph=graph) for s in CANONICAL]
    evaluate_development(pid,graph)
    target=next(e for e in ev if e["suite_id"]=="val-target-v1");reached=meets(target["summary"],THRESHOLDS["thr-target-1"])
    t=records.write("trial",{"parent_id":best["policy_id"],"parent_artifact_hash":parent_hash,"child_policy_id":pid,
        "child_artifact_hash":out["manifest"]["artifact_hash"],"run_id":out["run"]["id"],"target_family":"static_crossing",
        "target_family_id":d["request"]["target_family_id"],"suite_id":"val-target-v1","contract_id":CONTRACT_V1.contract_id,
        "recipe":RECIPES[change],"threshold_id":"thr-target-1","threshold":THRESHOLDS["thr-target-1"],"seed":SEED,
        "budget_steps":BUDGET,"consumed_steps":out["run"]["consumed_steps"],"validation_every":None,
        "schedule":[{"steps":out["run"]["consumed_steps"],"suite_id":"val-target-v1",**target["summary"]}],
        "status":out["run"]["status"],"threshold_reached":reached,"steps_to_threshold":out["run"]["consumed_steps"] if reached else None,
        "final_evaluation_id":target["id"],"decision_id":d["id"],"search_rule":RULE,"intervention":change,"protocol_sha256":study_hash()})
    ingest.trial(t,graph);gate=service.promote(pid,graph=graph);db.bump_revision(f"physics trial {t['id']}",graph)
    return {"trial":t,"promotion":gate,"ranking":ranking(reads(graph))}
