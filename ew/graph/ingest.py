"""Trusted graph writes. Idempotent MERGE on stable record ids; every call bumps the graph revision.

Only this module (called by trusted backend services) writes to the decision graph. MCP tools
can request bounded trusted actions; they cannot issue raw writes. Final-test evaluations never enter the decision
graph, so no planner query can see them.
"""
from __future__ import annotations

import json

from .. import records
from ..contract import CONTRACTS, CONTRACT_V1
from ..criteria import PROMOTION, THRESHOLDS
from ..scenarios import FAMILIES, PROTECTED_ROLES, SUITES
from ..validation import complete_evaluation, suite_fingerprint
from . import db

COMPETENCIES = {
    "reach_goal": [],
    "avoid_static": ["reach_goal"],
    "yield_dynamic": ["reach_goal"],
    "static_crossing_mission": ["avoid_static", "yield_dynamic"],
}

HYPOTHESES = [
    {"id": "hyp-mover-yield", "about_hit": "mover", "suggests": "yield_dynamic",
     "text": "Collisions with the moving obstacle MAY indicate weak yielding to dynamic obstacles. "
             "Authored hypothesis, not a measured cause."},
    {"id": "hyp-static-avoid", "about_hit": "static", "suggests": "avoid_static",
     "text": "Collisions with static obstacles MAY indicate weak static avoidance. Authored hypothesis."},
]


def init_world(g: str | None = None) -> int:
    """Authored configuration: robot, contracts, competencies, mission, families, suites, criteria."""
    for c in CONTRACTS.values():
        r = c.robot
        db.rw("MERGE (r:Robot {id:$id}) SET r.body=$body, r.radius_m=$rad, r.v_max=$v, r.w_max=$w, r.authored=true",
              {"id": r.name, "body": r.body, "rad": r.radius_m, "v": r.v_max_mps, "w": r.w_max_radps}, g)
        db.rw("MERGE (c:Contract {id:$id}) SET c.version=$ver, c.obs_dim=$od, c.n_rays=$nr, c.ray_order=$ro, "
              "c.history=$h, c.history_reset=$hr, c.dt_s=$dt, c.action_map=$am, c.normalization=$nm, "
              "c.wrappers=$wr, c.spec=$spec, c.authored=true "
              "WITH c MATCH (r:Robot {id:$rid}) MERGE (c)-[:FOR_ROBOT]->(r)",
              {"id": c.contract_id, "ver": c.version, "od": c.obs_dim, "nr": c.n_rays, "ro": c.ray_order,
               "h": c.history, "hr": c.history_reset, "dt": c.dt_s, "am": c.action_map, "nm": c.normalization,
               "wr": list(c.wrappers), "spec": json.dumps(c.describe(), default=list), "rid": r.name}, g)
    for cid, reqs in COMPETENCIES.items():
        db.rw("MERGE (:Competency {id:$id})", {"id": cid}, g)
    for cid, reqs in COMPETENCIES.items():
        for q in reqs:
            db.rw("MATCH (a:Competency {id:$a}), (b:Competency {id:$b}) MERGE (a)-[:REQUIRES {mandatory:true}]->(b)",
                  {"a": cid, "b": q}, g)
    for pid, p in PROMOTION.items():
        db.rw("MERGE (m:Mission {id:$m}) SET m.robot=$r, m.promotion_rule=$pid, m.authored=true "
              "WITH m MATCH (c:Competency {id:'static_crossing_mission'}) MERGE (m)-[:REQUIRES {mandatory:true}]->(c)",
              {"m": p["mission"], "r": CONTRACT_V1.robot.name, "pid": pid}, g)
    for f in FAMILIES.values():
        db.rw("MERGE (f:Family {id:$id}) SET f.name=$n, f.n_static=$ns, f.mover=$mv, f.mover_speed=$ms, "
              "f.mover_radius=$mr, f.max_steps=$mx, f.authored=true",
              {"id": f.fid(), "n": f.name, "ns": f.n_static, "mv": f.mover, "ms": list(f.mover_speed),
               "mr": f.mover_radius, "mx": f.max_steps}, g)
    for s in SUITES.values():
        db.rw("MERGE (s:Suite {id:$id}) SET s.version=$v, s.role=$role, s.episodes=$n, s.fingerprint=$fp, s.authored=true "
              "WITH s MATCH (f:Family {id:$fid}), (c:Competency {id:$c}) "
              "MERGE (s)-[:DRAWS_FROM]->(f) MERGE (s)-[:EVALUATES]->(c)",
              {"id": s.suite_id, "v": s.version, "role": s.role, "n": len(s.seeds), "fid": s.family.fid(),
               "c": s.competency, "fp": suite_fingerprint(s)}, g)
    for tid, t in THRESHOLDS.items():
        db.rw("MERGE (t:Threshold {id:$id}) SET t.min_success=$ms, t.max_collision=$mc, t.authored=true "
              "WITH t MATCH (s:Suite {id:$s}) MERGE (t)-[:MEASURED_ON]->(s)",
              {"id": tid, "ms": t["min_success"], "mc": t["max_collision"], "s": t["suite_id"]}, g)
    db.rw("MERGE (o:Origin {id:'scratch'}) SET o.meaning = 'no parent weights, fresh normalization', o.authored = true", None, g)
    for h in HYPOTHESES:
        db.rw("MERGE (h:Hypothesis {id:$id}) SET h.text=$t, h.about_hit=$a, h.authored=true, h.measured=false "
              "WITH h MATCH (c:Competency {id:$c}) MERGE (h)-[:SUGGESTS]->(c)",
              {"id": h["id"], "t": h["text"], "a": h["about_hit"], "c": h["suggests"]}, g)
    for q in ("CREATE INDEX FOR (p:Policy) ON (p.id)", "CREATE INDEX FOR (e:Evaluation) ON (e.id)",
              "CREATE INDEX FOR (t:Trial) ON (t.id)", "CREATE INDEX FOR (r:Run) ON (r.id)"):
        try:
            db.rw(q, None, g)
        except Exception as e:
            if "already indexed" not in str(e):
                raise
    return db.bump_revision("init_world", g)


def policy(m: dict, g: str | None = None) -> None:
    db.rw("MERGE (p:Policy {id:$id}) SET p.artifact_hash=$h, p.created_at=$ca, p.status=$st, p.family=$fam, "
          "p.consumed_steps=$cs, p.seed=$seed, p.recipe=$rec "
          "WITH p MATCH (c:Contract {id:$cid}) MERGE (p)-[:USES_CONTRACT]->(c)",
          {"id": m["policy_id"], "h": m["artifact_hash"], "ca": m["created_at"], "st": m["status"],
           "fam": m["family"], "cs": m["consumed_steps"], "seed": m["seed"], "rec": m["recipe"],
           "cid": m["contract_id"]}, g)
    if m.get("parent_id"):
        db.rw("MATCH (p:Policy {id:$id}), (q:Policy {id:$pid}) MERGE (p)-[:DERIVED_FROM]->(q)",
              {"id": m["policy_id"], "pid": m["parent_id"]}, g)


def run(r: dict, g: str | None = None) -> None:
    db.rw("MERGE (r:Run {id:$id}) SET r.kind=$k, r.recipe=$rec, r.seed=$seed, r.budget=$b, r.consumed=$c, "
          "r.status=$st, r.wall_s=$w, r.purpose=$pur "
          "MERGE (f:Family {id:$fid}) ON CREATE SET f.name=$fname, f.authored=true MERGE (r)-[:TRAINED_ON]->(f)",
          {"id": r["id"], "k": r["run_kind"], "rec": r["recipe"], "seed": r["seed"], "b": r["budget_steps"],
           "c": r["consumed_steps"], "st": r["status"], "w": r["wall_s"], "pur": r.get("purpose", ""),
           "fid": r["family_id"], "fname": r["family"]}, g)
    if r.get("child_policy_id"):
        db.rw("MATCH (r:Run {id:$id}), (p:Policy {id:$pid}) MERGE (r)-[:PRODUCED]->(p)",
              {"id": r["id"], "pid": r["child_policy_id"]}, g)
    if r.get("parent_id"):
        db.rw("MATCH (r:Run {id:$id}), (p:Policy {id:$pid}) MERGE (r)-[:STARTED_FROM]->(p)",
              {"id": r["id"], "pid": r["parent_id"]}, g)
    if r.get("decision_id"):
        decision_launched(r["decision_id"], r["id"], g)


def evaluation(e: dict, g: str | None = None) -> None:
    if SUITES[e["suite_id"]].role in PROTECTED_ROLES:
        raise PermissionError("final-test evaluations are never written to the decision graph")
    s = e["summary"]
    from ..artifacts import load_manifest
    complete = complete_evaluation(e, load_manifest(e["policy_id"])["contract_id"])
    db.rw("MERGE (e:Evaluation {id:$id}) SET e.artifact_hash=$h, e.success_rate=$sr, e.collision_rate=$cr, "
          "e.timeout_rate=$tr, e.episodes=$n, e.mean_success_steps=$ms, e.contract_id=$cid, e.at=$at, "
          "e.measured=true, e.complete_suite=$complete, e.suite_fingerprint=$fp "
          "WITH e MATCH (p:Policy {id:$pid}), (s:Suite {id:$sid}) MERGE (e)-[:ASSESSED]->(p) MERGE (e)-[:ON_SUITE]->(s)",
          {"id": e["id"], "h": e["artifact_hash"], "sr": s["success_rate"], "cr": s["collision_rate"],
           "tr": s["timeout_rate"], "n": s["episodes"], "ms": s["mean_success_steps"], "cid": e["contract_id"],
           "at": e["recorded_at"], "pid": e["policy_id"], "sid": e["suite_id"],
           "complete": complete, "fp": suite_fingerprint(SUITES[e["suite_id"]]) if complete else ""}, g)
    # Measured failure evidence, grouped by outcome/object, with episode indices into the eval record.
    for i_hit in ("mover", "static", "wall"):
        idx = [i for i, ep in enumerate(e["episodes"]) if ep["outcome"] == "collision" and ep.get("hit") == i_hit]
        if idx:
            fid = f"{e['id']}:collision:{i_hit}"
            db.rw("MERGE (f:Failure {id:$id}) SET f.outcome='collision', f.hit=$hit, f.count=$n, f.episodes=$idx, "
                  "f.measured=true WITH f MATCH (e:Evaluation {id:$eid}) MERGE (f)-[:OBSERVED_IN]->(e) "
                  "WITH f OPTIONAL MATCH (h:Hypothesis {about_hit:$hit}) FOREACH (_ IN CASE WHEN h IS NULL THEN [] ELSE [1] END | MERGE (h)-[:ABOUT]->(f))",
                  {"id": fid, "hit": i_hit, "n": len(idx), "idx": idx[:50], "eid": e["id"]}, g)
    idx = [i for i, ep in enumerate(e["episodes"]) if ep["outcome"] == "timeout"]
    if idx:
        db.rw("MERGE (f:Failure {id:$id}) SET f.outcome='timeout', f.count=$n, f.episodes=$idx, f.measured=true "
              "WITH f MATCH (e:Evaluation {id:$eid}) MERGE (f)-[:OBSERVED_IN]->(e)",
              {"id": f"{e['id']}:timeout", "n": len(idx), "idx": idx[:50], "eid": e["id"]}, g)


def trial(t: dict, g: str | None = None) -> None:
    db.rw("MERGE (t:Trial {id:$id}) SET t.status=$st, t.threshold_id=$thr, t.threshold_reached=$reached, "
          "t.steps_to_threshold=$stt, t.budget=$b, t.consumed=$c, t.seed=$seed, t.recipe=$rec, "
          "t.schedule=$sched, t.measured=true, t.at=$at "
          "WITH t MATCH (f:Family {id:$fid}), (s:Suite {id:$sid}), (c:Contract {id:$cid}) "
          "MERGE (t)-[:TARGETS]->(f) MERGE (t)-[:VALIDATED_ON]->(s) MERGE (t)-[:UNDER_CONTRACT]->(c)",
          {"id": t["id"], "st": t["status"], "thr": t["threshold_id"], "reached": t["threshold_reached"],
           "stt": t["steps_to_threshold"], "b": t["budget_steps"], "c": t["consumed_steps"], "seed": t["seed"],
           "rec": t["recipe"], "sched": json.dumps(t["schedule"]), "at": t["recorded_at"],
           "pid": t["parent_id"], "fid": t["target_family_id"], "sid": t["suite_id"], "cid": t["contract_id"]}, g)
    if t.get("parent_id"):
        db.rw("MATCH (t:Trial {id:$id}), (p:Policy {id:$pid}) MERGE (t)-[:FROM_PARENT]->(p)", {"id": t["id"], "pid": t["parent_id"]}, g)
    else:
        db.rw("MATCH (t:Trial {id:$id}) MERGE (o:Origin {id:'scratch'}) MERGE (t)-[:FROM_ORIGIN]->(o)", {"id": t["id"]}, g)
    if t.get("child_policy_id"):
        db.rw("MATCH (t:Trial {id:$id}), (p:Policy {id:$cp}) MERGE (t)-[:PRODUCED]->(p)",
              {"id": t["id"], "cp": t["child_policy_id"]}, g)
    if t.get("run_id"):
        db.rw("MATCH (t:Trial {id:$id}), (r:Run {id:$r}) MERGE (t)-[:VIA_RUN]->(r)", {"id": t["id"], "r": t["run_id"]}, g)
    if t.get("search_rule"):
        db.rw("MATCH (t:Trial {id:$id}) SET t.search_rule=$rule, t.intervention=$intervention",
              {"id": t["id"], "rule": t["search_rule"], "intervention": t["intervention"]}, g)


def decision(d: dict, g: str | None = None) -> None:
    db.rw("MERGE (d:Decision {id:$id}) SET d.rule_version=$rv, d.graph_revision=$rev, d.action=$act, "
          "d.selected=$sel, d.mode=$mode, d.target_family=$tf, d.at=$at, d.explanation=$ex",
          {"id": d["id"], "rv": d["rule_version"], "rev": d["graph_revision"], "act": d["action"],
           "sel": d.get("selected") or "", "mode": d["mode"], "tf": d["request"]["target_family_id"],
           "at": d["recorded_at"], "ex": d.get("explanation", "")}, g)
    if d.get("rule_version") == "agent-mcp-v1":
        db.rw("MATCH (d:Decision {id:$id}) SET d.model=$model, d.transport=$transport, "
              "d.proposed_origin=$origin, d.guardrail_verdict=$verdict, d.guardrail=$guardrail, "
              "d.mcp_tool_calls=$calls, d.query_receipts=$queries, d.candidates=$candidates, "
              "d.study_id=$study, d.protocol_sha256=$protocol",
              {"id": d["id"], "model": d.get("model") or ("none (deterministic fallback)" if d["mode"] == "deterministic_fallback" else "unknown (external MCP client)"),
               "transport": d["transport"], "origin": d.get("proposed_origin") or "",
               "verdict": d["guardrail"]["verdict"], "guardrail": json.dumps(d["guardrail"]),
               "calls": json.dumps(d["mcp_tool_calls"]), "queries": json.dumps(d["queries"]),
               "candidates": json.dumps(d["ranking"]), "study": d.get("study_id", "agent-mcp-v1"),
               "protocol": d.get("protocol_sha256", "")}, g)
    for c in d["ranking"]:
        db.rw("MATCH (d:Decision {id:$id}), (p:Policy {id:$pid}) MERGE (d)-[r:CONSIDERED]->(p) "
              "SET r.rank=$rank, r.key=$key", {"id": d["id"], "pid": c["policy_id"], "rank": c["rank"],
                                               "key": json.dumps(c["sort_key"])}, g)
    for c in d["rejected"]:
        db.rw("MATCH (d:Decision {id:$id}), (p:Policy {id:$pid}) MERGE (d)-[r:REJECTED]->(p) SET r.reason=$why",
              {"id": d["id"], "pid": c["policy_id"], "why": "; ".join(c["reasons"])}, g)
    if d.get("selected"):
        db.rw("MATCH (d:Decision {id:$id}), (p:Policy {id:$pid}) MERGE (d)-[:SELECTED]->(p)",
              {"id": d["id"], "pid": d["selected"]}, g)
    elif d["action"] == "train_from_scratch":
        db.rw("MATCH (d:Decision {id:$id}) MERGE (o:Origin {id:'scratch'}) MERGE (d)-[:SELECTED]->(o)", {"id": d["id"]}, g)
    for tid in d.get("evidence_trial_ids", []):
        db.rw("MATCH (d:Decision {id:$id}), (t:Trial {id:$t}) MERGE (d)-[:BASED_ON]->(t)", {"id": d["id"], "t": tid}, g)
    for eid in d.get("evidence_eval_ids", []):
        db.rw("MATCH (d:Decision {id:$id}), (e:Evaluation {id:$e}) MERGE (d)-[:BASED_ON]->(e)", {"id": d["id"], "e": eid}, g)


def decision_launched(decision_id: str, run_id: str, g: str | None = None) -> None:
    db.rw("MATCH (d:Decision {id:$d}), (r:Run {id:$r}) MERGE (d)-[:LAUNCHED]->(r)", {"d": decision_id, "r": run_id}, g)


def promotion(p: dict, g: str | None = None) -> None:
    db.rw("MERGE (x:Promotion {id:$id}) SET x.verdict=$v, x.artifact_hash=$h, x.rule=$rule, x.reasons=$why, x.at=$at "
          "WITH x MATCH (p:Policy {id:$pid}) MERGE (x)-[:FOR]->(p)",
          {"id": p["id"], "v": p["verdict"], "h": p["artifact_hash"], "rule": p["rule"],
           "why": p["reasons"], "at": p["recorded_at"], "pid": p["policy_id"]}, g)
    for eid in p["evaluation_ids"]:
        db.rw("MATCH (x:Promotion {id:$id}), (e:Evaluation {id:$e}) MERGE (x)-[:USED_EVALUATION]->(e)",
              {"id": p["id"], "e": eid}, g)


def rebuild(g: str | None = None) -> int:
    """Rebuild the decision graph from persisted records (recovery only)."""
    db.delete_graph(g or db.GRAPH)
    init_world(g)
    from ..artifacts import POLICIES
    mans = [json.loads((d / "manifest.json").read_text()) for d in POLICIES.glob("*") if (d / "manifest.json").exists()]
    for m in sorted(mans, key=lambda m: m["created_at"]):
        if not m.get("scratch_probe"):
            policy(m, g)
    for m in mans:  # second pass for lineage edges whose parent sorted later
        if m.get("parent_id"):
            policy(m, g)
    for r in records.all_of("run"):
        run({**r, "decision_id": None}, g)
    for e in records.all_of("evaluation"):
        if e["suite_id"] in SUITES and SUITES[e["suite_id"]].role not in PROTECTED_ROLES and not e.get("custom_family"):
            evaluation(e, g)
    # Physics evaluations must exist before Decision BASED_ON edges are restored.
    from ..physics_study import OUT as physics_root, ingest_development
    if (physics_root / "protocol.json").exists():
        for folder in sorted((physics_root / "development").glob("*")):
            if (folder / "summary.json").exists() and (POLICIES / folder.name / "manifest.json").exists():
                ingest_development(folder.name, g)
    for t in records.all_of("trial"):
        trial(t, g)
    for d in records.all_of("decision"):
        if d["mode"] != "what-if":
            decision(d, g)
    for r in records.all_of("run"):
        run(r, g)
    for p in records.all_of("promotion"):
        promotion(p, g)
    from .transfer import DEFAULT_ROOT, ingest as transfer_ingest
    transfer_ingest(graph=g, strict=False)
    transfer_ingest(DEFAULT_ROOT.with_name("mujoco-v2"), graph=g, strict=False)
    return db.bump_revision("rebuild", g)
