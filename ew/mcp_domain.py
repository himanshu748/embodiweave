"""Domain reads and consent-scoped actions, shared by real MCP transports.

Capabilities exist only inside the API process. They never reach a model, tool
arguments, a receipt, or the PPO environment. Anonymous MCP clients can read;
public training needs the existing page consent and quota mechanism.
"""
from __future__ import annotations

import json
import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import agent_tools, artifacts, public_training, records, service
from .graph import db, ingest, queries as Q
from .search import CRITERIA, SUITES
from .select import inspect_training_origins, validate_proposed_origin


@dataclass
class Workflow:
    session_id: str
    owner: str
    training_consent: bool = False
    training_requested: bool = False
    target: str = field(default_factory=lambda: agent_tools.DEPLOYED_POLICY)
    mode: str = "llm"
    model: str | None = None
    transport: str = "streamable-http"
    calls: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    training_session_id: str | None = None
    created_at: float = field(default_factory=time.time)
    lock: threading.RLock = field(default_factory=threading.RLock)


_contexts: dict[str, Workflow] = {}
_context_lock = threading.Lock()


def register(workflow):
    with _context_lock:
        for key in [k for k, v in _contexts.items() if time.time()-v.created_at > 600]:
            del _contexts[key]
        capability = secrets.token_hex(32)
        _contexts[capability] = workflow
        return capability


def lookup(capability):
    with _context_lock:
        workflow = _contexts.get(capability)
    return workflow if workflow and time.time()-workflow.created_at <= 600 else None


def revoke(capability):
    with _context_lock:
        _contexts.pop(capability, None)


def query(name, params):
    q = Q.run(name, params)
    return {**q.to_log(), "rows": q.dicts(), "row_count": len(q.rows), "returned_ids": q.record_ids}


def policy(policy_id):
    q = query("mcp_policy", {"policy": policy_id})
    if not q["rows"]:
        raise ValueError("Unknown policy. Use a checkpoint ID from the graph.")
    return q


def diagnose_policy(policy_id):
    p = policy(policy_id)
    q = query("mcp_diagnosis", {"policy": policy_id, "suites": SUITES})
    return {"policy": p["rows"][0], "validation_and_failures": q["rows"], "queries": [p, q],
            "notice": "Canonical validation evidence only. No new evaluation was run."}


def explain_decision(decision_id):
    q = query("mcp_decision", {"decision": decision_id})
    if not q["rows"]:
        raise ValueError("Unknown decision")
    return {"decision": q["rows"][0]["decision"], "queries": [q]}


def lineage(policy_id, max_hops=8):
    if type(max_hops) is not int or not 1 <= max_hops <= 8:
        raise ValueError("Choose between one and eight lineage hops")
    p = policy(policy_id)
    q = query("mcp_lineage", {"policy": policy_id, "max_hops": max_hops})
    return {"ancestors": q["rows"], "queries": [p, q]}


def find_training_origins(target_policy):
    result = inspect_training_origins(target_policy, 60000)
    candidates = [{"policy_id": c["policy_id"], "rank": c["rank"], "passed": c["passed"],
                   "recipe": c["recipe"], "training_domain": c["training_domain"],
                   "validation": [{"suite": suite, "success": e["success_rate"], "collisions": e["collision_rate"],
                                   "evaluation_id": e["evaluation_id"]} for suite, e in c["validation"].items()]}
                  for c in result["ranking"]]
    return {**{k: v for k, v in result.items() if k != "ranking"}, "candidates": candidates,
            "notice": "The model may propose any eligible origin. Rank is the authored fallback order, not an instruction to the model."}


def nearest_passing_ancestor(policy_id, suite_id="val-target-v1", max_hops=8):
    if suite_id not in SUITES:
        raise ValueError("Only the four canonical validation suites are available")
    if type(max_hops) is not int or not 1 <= max_hops <= 8:
        raise ValueError("Choose between one and eight lineage hops")
    p = policy(policy_id)
    c = next(c for c in CRITERIA if c["suite_id"] == suite_id)
    q = query("mcp_nearest_passing_ancestor", {"policy": policy_id, "suite": suite_id,
              "max_hops": max_hops, "min_success": c["min_success"], "max_collision": c["max_collision"]})
    return {"algorithm": "FalkorDB shortestPath, minimum unweighted DERIVED_FROM hops",
            "nearest": q["rows"][0] if q["rows"] else None, "passing_ancestors": q["rows"], "queries": [p, q],
            "notice": "A passing ancestor is a recovery option. Graph distance is not evidence that extra PPO improves safety."}


def check_gate(policy_id):
    policy(policy_id)
    result = service.promotion_preview(policy_id)
    return {**result, "preview": True, "deployment_changed": False}


def _record(workflow, guard, origin_id, budget, reason, *, action="train_from_parent"):
    calls = list(workflow.calls)
    queries = [q for call in calls for q in call["result"].get("queries", [])] + guard["queries"]
    evaluation_ids = sorted({e["evaluation_id"] for r in guard["ranking"] for e in r["validation"].values()})
    did = records.new_id("deci")
    proposal = {"tool": "start_training", "args": {"origin_id": origin_id, "budget": budget, "reason": reason},
                "transport": "mcp", "result": {"guardrail_verdict": guard["verdict"], "decision_id": did}}
    d = records.write("decision", {"id": did, "rule_version": "agent-mcp-v1", "mode": workflow.mode,
        "model": workflow.model, "transport": workflow.transport, "agent_session_id": workflow.session_id,
        "graph": db.GRAPH, "graph_revision": guard["graph_revision"], "action": action,
        "selected": origin_id if guard["verdict"] == "allowed" else None, "proposed_origin": origin_id,
        "guardrail": {"rule": "agent-guardrail-v1", "verdict": guard["verdict"], "reasons": guard["reasons"]},
        "request": service.target_request(budget), "ranking": guard["ranking"], "rejected": guard["rejected"],
        "queries": queries, "mcp_tool_calls": calls + ([proposal] if action == "train_from_parent" else []), "evidence_eval_ids": evaluation_ids,
        "evidence_trial_ids": [], "explanation": reason,
        "protocol_sha256": hashlib.sha256((Path(__file__).resolve().parents[1] / "evidence/mcp-agent-v1/protocol.json").read_bytes()).hexdigest()})
    ingest.decision(d)
    db.bump_revision("MCP agent decision " + did)
    workflow.decisions.append(did)
    return d


def record_investigation(workflow):
    return _record(workflow, {"queries": [], "ranking": [], "rejected": [], "graph_revision": db.revision(),
        "verdict": "not_requested", "reasons": []}, None, 60000,
        "MCP investigation completed; no training origin chosen.", action="inspect")


def start_training(origin_id, budget, reason, workflow):
    if not workflow or not workflow.training_consent or not workflow.training_requested:
        raise PermissionError("Start an agent training request on the webpage and give training consent. This MCP connection is read-only.")
    with workflow.lock:
        if workflow.training_session_id:
            return {"training_session_id": workflow.training_session_id, "state": "already_launched", "decision_ids": workflow.decisions}
        guard = validate_proposed_origin(workflow.target, origin_id, budget)
        if type(budget) is not int or budget != 60000:
            guard["reasons"].append("Page consent authorizes exactly 60000 steps")
        reads = {c["tool"] for c in workflow.calls if not c["result"].get("error") and
                 c["args"].get("policy_id", c["args"].get("target_policy")) == workflow.target}
        if not {"diagnose_policy", "find_training_origins", "nearest_passing_ancestor"} <= reads:
            guard["reasons"].append("Read diagnosis, origins and the graph algorithm before proposing training")
        algorithms = [c["result"].get("nearest") for c in workflow.calls if c["tool"] == "nearest_passing_ancestor"
                      and c["args"].get("policy_id") == workflow.target and c["result"].get("nearest")]
        if algorithms and algorithms[-1]["ancestor_id"] not in reason:
            guard["reasons"].append("Cite the ancestor ID returned by the algorithm in your reason")
        if not 12 <= len(reason) <= 800:
            guard["reasons"].append("Give a reason of 12 to 800 characters, referring to the returned graph evidence")
        guard["verdict"] = "vetoed" if guard["reasons"] else "allowed"
        d = _record(workflow, guard, origin_id, budget, reason)
        if guard["verdict"] != "allowed":
            return {"decision_id": d["id"], "guardrail": d["guardrail"], "training_started": False}
        trial = public_training.start(None, seed=29, consent=True, owner_hash=workflow.owner, budget=budget,
                                      agent_decision_id=d["id"], origin_id=origin_id)
        workflow.training_session_id = trial["id"]
        return {"decision_id": d["id"], "guardrail": d["guardrail"], "training_session_id": trial["id"],
                "state": trial["state"], "origin_id": origin_id, "budget": budget, "seed": 29,
                "detail": "Real PPO queued. The trusted worker will evaluate 180 validation episodes and record the gate. Follow the training panel; this is not a completed result."}


READS = {name: globals()[name] for name in ("diagnose_policy", "explain_decision", "lineage", "find_training_origins", "nearest_passing_ancestor", "check_gate")}


def dispatch(name, args, workflow=None):
    start = time.time()
    try:
        result = start_training(**args, workflow=workflow) if name == "start_training" else READS[name](**args)
    except db.GraphUnavailable:
        result = {"error": "FalkorDB unavailable; planning stopped.", "graph_unavailable": True}
    except (PermissionError, ValueError, KeyError, OSError, public_training.Limited) as exc:
        result = {"error": str(exc) if isinstance(exc, (PermissionError, ValueError, public_training.Limited)) else "The requested evidence is unavailable."}
    if workflow:
        with workflow.lock:
            workflow.calls.append({"tool": name, "args": args, "result": result, "transport": "mcp",
                                   "t": start, "wall_ms": round((time.time()-start)*1000, 2)})
    return result
