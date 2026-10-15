"""Studio backend (FastAPI). Every number it serves comes from a record, artifact, job file or live query.

Run:  uvicorn ew.api:app --port 8000
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent_tools as T
from . import artifacts, jobs, records, rl, service, whatif
from .contract import CONTRACT_V1
from .graph import db
from .graph import queries as Q
from .scenarios import FAMILIES, PROTECTED_ROLES, SUITES, with_controls

app = FastAPI(title="EmbodiWeave Studio")
WEB = Path(__file__).resolve().parent.parent / "web"
STATIC_MODE = os.environ.get("EW_STATIC", "0") == "1"


@app.exception_handler(db.GraphUnavailable)
async def graph_down(_, exc):
    return JSONResponse(status_code=503, content={"error": "graph_unavailable", "detail": str(exc),
                                                  "note": "Graph-dependent decisions are stopped. Recorded evidence remains viewable."})


def _worker_alive() -> dict:
    running = [j for j in jobs.all_jobs() if j["state"] == "running"]
    hb = (artifacts.ROOT / "jobs" / "worker.heartbeat")
    alive = hb.exists() and time.time() - hb.stat().st_mtime < 10
    return {"alive": alive, "running": [j["id"] for j in running]}


@app.get("/api/status")
def status():
    up = db.ping()
    return {"graph": {"up": up, "revision": db.revision() if up else None, "name": db.GRAPH},
            "worker": _worker_alive(), "deployed_policy": T.DEPLOYED_POLICY,
            "contract": CONTRACT_V1.contract_id, "world": "simulated", "server_time": time.time()}


@app.get("/api/catalog")
def catalog():
    """Policy lineage from FalkorDB plus manifest facts from the artifact store."""
    rows = Q.run("policy_lineage_graph", {}).dicts()
    out = []
    for r in rows:
        m = artifacts.load_manifest(r["id"])
        out.append({**r, "artifact_hash": m["artifact_hash"], "consumed_steps": m["consumed_steps"], "seed": m["seed"],
                    "created_at": m["created_at"], "run_id": m.get("run_id"), "weight_delta_l2": m["weight_delta_l2"],
                    "run_kind": next((x["run_kind"] for x in records.all_of("run") if x.get("child_policy_id") == r["id"]), None)})
    return sorted(out, key=lambda x: x["created_at"])


@app.get("/api/decisions")
def decisions():
    return [{k: d.get(k) for k in ("id", "recorded_at", "mode", "action", "selected", "rule_version", "graph_revision",
                                   "explanation", "graph")} | {"budget": d["request"]["budget"]}
            for d in records.all_of("decision")]


@app.get("/api/decisions/{did}")
def decision(did: str):
    if not records.exists("decision", did):
        raise HTTPException(404)
    d = records.read("decision", did)
    launched = [r for r in records.all_of("run") if r.get("decision_id") == did]
    trials = [t for t in records.all_of("trial") if t.get("decision_id") == did]
    return {**d, "launched_runs": launched, "launched_trials": trials}


@app.get("/api/evaluations")
def evaluations(policy: str | None = None, suite: str | None = None):
    out = []
    for e in records.all_of("evaluation"):
        if e["suite_role"] in PROTECTED_ROLES:
            continue  # the studio never shows final-test outcomes outside the results report
        if policy and e["policy_id"] != policy:
            continue
        if suite and e["suite_id"] != suite:
            continue
        out.append({k: e.get(k) for k in ("id", "policy_id", "artifact_hash", "suite_id", "summary", "recorded_at",
                                          "purpose", "custom_family", "family_id")}
                   | {"has_replay": (service.REPLAYS / f"{e['id']}.json").exists()})
    return out


@app.get("/api/replay/{eid}")
def replay(eid: str):
    p = service.REPLAYS / f"{eid}.json"
    if not p.exists():
        raise HTTPException(404, "no replay stored for this evaluation")
    return FileResponse(p, media_type="application/json")


@app.get("/api/trials")
def trials():
    return records.all_of("trial")


@app.get("/api/evidence/{rid}")
def evidence(rid: str):
    """Look up any record id (evaluation, trial, run, decision, promotion, policy)."""
    for kind in ("evaluation", "trial", "run", "decision", "promotion", "agent_trace"):
        if records.exists(kind, rid):
            r = records.read(kind, rid)
            if kind == "evaluation":
                r = {k: v for k, v in r.items() if k != "episodes"} | {"episode_outcomes": [e["outcome"] for e in r["episodes"]]}
            return {"kind": kind, "record": r}
    if artifacts.policy_dir(rid).exists():
        return {"kind": "policy", "record": artifacts.load_manifest(rid)}
    raise HTTPException(404)


@app.get("/api/subgraph/{did}")
def subgraph(did: str):
    """Nodes and edges around a decision, read live from FalkorDB (graph name from the decision)."""
    d = records.read("decision", did)
    g = d.get("graph") or db.GRAPH
    if g != db.GRAPH:
        raise HTTPException(410, "What-if graph copies are dropped after use; showing the recorded decision only")
    cy = """
MATCH (d:Decision {id:$d})-[r]->(x)
OPTIONAL MATCH (x)-[:DERIVED_FROM]->(par:Policy)
OPTIONAL MATCH (e:Evaluation)-[:ASSESSED]->(x) WHERE (e)-[:ON_SUITE]->(:Suite {id:$suite}) AND e.artifact_hash = x.artifact_hash
OPTIONAL MATCH (t:Trial)-[:FROM_PARENT|FROM_ORIGIN]->(x)
OPTIONAL MATCH (x)-[:USES_CONTRACT]->(c:Contract)
RETURN type(r) AS rel, labels(x)[0] AS xl, x.id AS xid, par.id AS parent, e.id AS eval, e.success_rate AS sr,
       t.id AS trial, t.threshold_reached AS reached, t.budget AS tb, c.id AS contract"""
    _, rows, ms = db.ro(cy.strip(), {"d": did, "suite": d["suite_id"]})
    hide = {r["policy_id"] for r in d["rejected"] if all(x.startswith("outside requested catalog") for x in r["reasons"])}
    nodes, edges = {did: {"id": did, "label": "Decision"}}, set()

    def put(n):
        nodes[n["id"]] = {**nodes.get(n["id"], {}), **{k: v for k, v in n.items() if v is not None}}

    for rel, xl, xid, par, ev, sr, tr, reached, tb, c in rows:
        if xid in hide:
            continue
        put({"id": xid, "label": xl})
        edges.add((did, xid, rel))
        if par:
            put({"id": par, "label": "Policy"})
            edges.add((xid, par, "DERIVED_FROM"))
        if ev:
            put({"id": ev, "label": "Evaluation", "success_rate": sr})
            edges.add((ev, xid, "ASSESSED"))
        if tr:
            put({"id": tr, "label": "Trial", "reached": reached, "budget": tb})
            edges.add((tr, xid, "FROM_ORIGIN" if xl == "Origin" else "FROM_PARENT"))
        if c:
            put({"id": c, "label": "Contract"})
            edges.add((xid, c, "USES_CONTRACT"))
    return {"nodes": list(nodes.values()), "edges": [{"from": a, "to": b, "type": t} for a, b, t in sorted(edges)],
            "hidden_outside_catalog": sorted(hide),
            "cypher": cy.strip(), "ms": ms, "graph_revision": db.revision()}


class DecideReq(BaseModel):
    budget: int = 150_000


@app.post("/api/decide")
def decide(r: DecideReq):
    if r.budget not in T.ALLOWED_BUDGETS:
        raise HTTPException(400, f"budget must be one of {T.ALLOWED_BUDGETS}")
    req = {**service.target_request(budget=r.budget), "candidate_run_kinds": ["library"]}
    return service.record_decision(req, mode="deterministic")


class TrainReq(BaseModel):
    decision_id: str
    seed: int = 7


@app.post("/api/train")
def train(r: TrainReq):
    out = T.start_training(decision_id=r.decision_id, seed=r.seed)
    if "error" in out:
        raise HTTPException(409, out["error"])
    return out


@app.post("/api/evaluate_candidates/{did}")
def eval_candidates(did: str):
    return T.evaluate_candidates(decision_id=did)


class EvalReq(BaseModel):
    policy_id: str
    suite_id: str


@app.post("/api/evaluate")
def evaluate(r: EvalReq):
    out = T.evaluate_checkpoint(policy_id=r.policy_id, suite_id=r.suite_id)
    if "error" in out:
        raise HTTPException(403, out["error"])
    return out


class ScenarioReq(BaseModel):
    policy_id: str
    base_family: str = "static_crossing"
    n_static: int | None = None
    mover_speed: float | None = None
    mover_radius: float | None = None
    episodes: int = 4
    seed: int = 4242


@app.post("/api/scenario_eval")
def scenario_eval(r: ScenarioReq):
    """Live evaluation of a saved checkpoint on a user-configured scenario (not a validation suite)."""
    if r.base_family not in FAMILIES:
        raise HTTPException(400, "unknown family")
    if not 1 <= r.episodes <= 8:
        raise HTTPException(400, "episodes must be 1..8")
    try:
        fam = with_controls(FAMILIES[r.base_family], r.n_static, r.mover_speed, r.mover_radius)
    except ValueError as e:
        raise HTTPException(400, str(e))
    seeds = list(range(r.seed, r.seed + r.episodes))
    ev = rl.evaluate_policy(r.policy_id, fam, seeds, record=True)
    rid = records.new_id("scen")
    service.REPLAYS.mkdir(parents=True, exist_ok=True)
    rec = records.write("evaluation", {
        "id": rid, "policy_id": r.policy_id, "artifact_hash": ev["artifact_hash"], "suite_id": "custom",
        "suite_role": "scenario", "suite_version": "-", "family_id": fam.fid(), "custom_family": True,
        "family_params": json.loads(json.dumps(fam.__dict__, default=list)), "seeds": seeds,
        "contract_id": ev["contract_id"], "summary": ev["summary"],
        "episodes": [{k: v for k, v in e.items() if k not in ("trace", "layout")} for e in ev["episodes"]],
        "purpose": "studio scenario control (not a validation suite; not used for decisions)", "wall_s": ev["wall_s"]})
    (service.REPLAYS / f"{rid}.json").write_text(json.dumps({
        "evaluation_id": rid, "policy_id": r.policy_id, "artifact_hash": ev["artifact_hash"], "suite_id": "custom",
        "family": rec["family_params"], "episodes": [{"seed": s, "layout": e["layout"], "trace": e["trace"],
                                                      "outcome": e["outcome"], "hit": e.get("hit"), "steps": e["steps"]}
                                                     for s, e in zip(seeds, ev["episodes"])]}))
    return {"evaluation_id": rid, "summary": ev["summary"], "family": rec["family_params"], "wall_s": ev["wall_s"]}


@app.get("/api/jobs")
def list_jobs():
    return [{k: j.get(k) for k in ("id", "kind", "state", "progress", "result", "error", "consumed_steps", "params",
                                   "submitted_at", "started_at", "finished_at", "requested_by")} for j in jobs.all_jobs()][::-1]


@app.post("/api/jobs/{jid}/cancel")
def cancel(jid: str):
    return T.cancel_job(job_id=jid)


@app.post("/api/promote/{pid}")
def promote(pid: str):
    return T.request_promotion(policy_id=pid)


@app.get("/api/promotions")
def promotions():
    return records.all_of("promotion")


@app.post("/api/export/{pid}")
def export(pid: str):
    b = service.export_bundle(pid)
    return {**{k: b[k] for k in ("policy_id", "artifact_hash", "sha256", "bytes")}, "download": f"/api/download/{Path(b['path']).name}"}


@app.get("/api/download/{name}")
def download(name: str):
    p = (artifacts.ROOT / "exports" / name).resolve()
    if p.parent != (artifacts.ROOT / "exports").resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, filename=name)


class WhatIfReq(BaseModel):
    budget: int = 150_000
    hypothetical_trials: list[dict] = []      # {"parent_id": str, "reached": bool, "steps_to_threshold": int|null}
    contract_overrides: list[str] = []        # policy ids to pretend use the mirrored contract


@app.post("/api/whatif")
def what_if(r: WhatIfReq):
    if len(r.hypothetical_trials) > 6 or len(r.contract_overrides) > 3:
        raise HTTPException(400, "too many interventions")
    req = {**service.target_request(budget=r.budget), "candidate_run_kinds": ["library"]}
    before = whatif.fingerprint()
    g = whatif.create()
    try:
        for h in r.hypothetical_trials:
            whatif.add_hypothetical_trial(g, h["parent_id"], req["target_family_id"], req["contract"], req["threshold_id"],
                                          req["recipe"], req["budget"], bool(h["reached"]), h.get("steps_to_threshold"))
        for pid in r.contract_overrides:
            whatif.set_hypothetical_contract(g, pid, "ew-contract-1m:6fad9cbfe838")
        d = service.record_decision(req, mode="what-if", graph=g)
    finally:
        whatif.drop(g)
    after = whatif.fingerprint()
    return {"decision": d, "production_unchanged": before == after, "production_revision": after["revision"],
            "interventions": r.model_dump()}


@app.get("/api/agent_traces")
def agent_traces():
    return [{"id": t["id"], "mode": t["mode"], "recorded_at": t["recorded_at"], "wall_s": t["wall_s"],
             "n_calls": len(t.get("calls") or [x for x in t.get("transcript", []) if "tool" in x])}
            for t in records.all_of("agent_trace")]


@app.get("/api/agent_traces/{tid}")
def agent_trace(tid: str):
    t = records.read("agent_trace", tid)
    p = T.TRACES / f"{tid}.jsonl"
    server_log = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
    return {**t, "server_log": server_log}


@app.get("/api/results")
def results():
    """Every reported experiment, normalized to arms -> per-seed rows. Final-test numbers appear only here."""
    out = []
    for name in ("experiment.json", "experiment2.json", "experiment3.json"):
        p = artifacts.ROOT / "results" / name
        if not p.exists():
            continue
        r = json.loads(p.read_text())
        runs = r.get("runs") or r.get("phase_b") or {}
        arms = []
        for arm, parent in r["arms"].items():
            rows = runs.get("null" if parent is None else parent, [])
            n = len(rows) or 1
            arms.append({"arm": arm, "parent": parent, "n": len(rows), "reached": sum(bool(x["reached"]) for x in rows),
                         "test_success": round(sum(x["final_test"]["success_rate"] for x in rows) / n, 4),
                         "test_collision": round(sum(x["final_test"]["collision_rate"] for x in rows) / n, 4),
                         "rows": [{k: x[k] for k in ("seed", "reached", "steps_to_threshold", "final_val", "final_test", "wall_s")}
                                  for x in rows]})
        out.append({"protocol": r["protocol"], "arms": arms, "costs": r.get("costs", {}),
                    "graph_decision": r.get("decision_graph"), "graph_explanation": r.get("graph_explanation")})
    return {"experiments": out} if out else {"status": "not_run"}


if WEB.exists():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
