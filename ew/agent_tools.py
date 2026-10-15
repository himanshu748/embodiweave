"""The bounded tool surface the runtime agent may use (exposed over MCP by ew.mcp_server).

No shell, no file paths, no URLs, no arbitrary Cypher, no graph writes. Reads go through named
templates on GRAPH.RO_QUERY. Actions go through trusted services that revalidate everything.
Every call is appended to a per-session JSONL trace with inputs, outputs and graph revision.
"""
from __future__ import annotations

import json
import os
import time

from . import artifacts, jobs, records, service
from .graph import db
from .graph import queries as Q
from .scenarios import PROTECTED_ROLES, SUITES

DEPLOYED_POLICY = os.environ.get("EW_DEPLOYED_POLICY", "P-static-b")
ALLOWED_BUDGETS = (60_000, 150_000)
AGENT_TEMPLATES = {"mission_requirements", "candidate_eligibility", "candidate_ancestry", "matched_validation",
                   "relevant_trials", "non_applicable_trials", "failure_inspection", "promotion_evidence",
                   "decision_provenance", "policy_lineage_graph"}
TRACES = artifacts.ROOT / "agent_traces"
SESSION = os.environ.get("EW_AGENT_SESSION", "adhoc")
MODE = os.environ.get("EW_AGENT_MODE", "llm-agent")  # llm-agent | deterministic


def _trace(tool: str, args: dict, out, err: str | None = None):
    TRACES.mkdir(parents=True, exist_ok=True)
    try:
        rev = db.revision()
    except Exception:  # noqa: BLE001
        rev = None
    with open(TRACES / f"{SESSION}.jsonl", "a") as f:
        f.write(json.dumps({"t": time.time(), "session": SESSION, "mode": MODE, "tool": tool, "args": args,
                            "graph_revision": rev, "error": err, "result": out}, default=str) + "\n")


def tool(fn):
    def wrapped(**kw):
        try:
            out = fn(**kw)
            _trace(fn.__name__, kw, out)
            return out
        except Exception as e:  # noqa: BLE001
            msg = f"{e.__class__.__name__}: {e}"
            _trace(fn.__name__, kw, None, msg)
            return {"error": msg}
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    return wrapped


def _compact_decision(d: dict) -> dict:
    return {"decision_id": d["id"], "action": d["action"], "selected": d["selected"], "rule": d["rule_version"],
            "graph_revision": d["graph_revision"], "explanation": d["explanation"],
            "needs_evaluation": d.get("needs_evaluation"),
            "rejected": d["rejected"],
            "ranking": [{k: c[k] for k in ("rank", "policy_id", "p_reach", "p_basis", "n_completed", "n_reached",
                                           "n_not_reached_within_budget", "validation", "median_steps_to_threshold")}
                        for c in d.get("ranking", [])],
            "queries": [{"template": q["template"], "params": q["params"], "returned_ids": q["record_ids"]}
                        for q in d["queries"]]}


@tool
def inspect_mission() -> dict:
    """Mission requirements (directed prerequisite closure), the deployed policy and its latest measured target evaluation."""
    req = Q.run("mission_requirements", {"mission": "static_crossing"})
    evs = [e for e in records.all_of("evaluation") if e["policy_id"] == DEPLOYED_POLICY and e["suite_id"] == "val-target-v1"]
    latest = evs[-1] if evs else None
    fail = Q.run("failure_inspection", {"evaluation": latest["id"]}).dicts() if latest else []
    return {"mission": "static_crossing", "robot": "ew-unicycle-r20", "requirements": req.dicts(),
            "deployed_policy": DEPLOYED_POLICY,
            "deployed_target_evaluation": {"evaluation_id": latest["id"], "summary": latest["summary"]} if latest else None,
            "failure_evidence": fail, "graph_revision": req.graph_revision,
            "note": "Failure rows are measured; hypothesis rows are authored and unverified."}


@tool
def query_graph(template: str, params: dict) -> dict:
    """Run one named read-only Cypher template (GRAPH.RO_QUERY). See AGENT_TEMPLATES for the allowed names."""
    template = template.split("(")[0].strip()  # models often echo the "name(params)" form from the tool description
    if template not in AGENT_TEMPLATES:
        raise PermissionError(f"template {template} not allowed; use one of {sorted(AGENT_TEMPLATES)}")
    for k, v in params.items():
        if not isinstance(v, (str, int, float, bool, list)):
            raise ValueError(f"param {k} has unsupported type")
    if "suite" in params and SUITES.get(params["suite"]) and SUITES[params["suite"]].role in PROTECTED_ROLES:
        raise PermissionError("final-test suites are not available to the agent")
    r = Q.run(template, params)
    return {"template": template, "rows": r.dicts()[:100], "row_count": len(r.rows), "graph_revision": r.graph_revision,
            "cypher": r.cypher}


@tool
def propose_adaptation(budget: int = 150_000) -> dict:
    """Apply the frozen selection rule (select.RULE_VERSION: reuse a parent or train from scratch) to current FalkorDB evidence and record a decision."""
    if budget not in ALLOWED_BUDGETS:
        raise ValueError(f"budget must be one of {ALLOWED_BUDGETS}")
    req = {**service.target_request(budget=budget), "candidate_run_kinds": ["library"]}
    d = service.record_decision(req, mode=MODE, agent_trace_id=SESSION)
    return _compact_decision(d)


@tool
def evaluate_candidates(decision_id: str) -> dict:
    """Queue matched validation evaluations for every candidate a decision reported as missing evidence."""
    d = records.read("decision", decision_id)
    if d["mode"] == "what-if":
        raise PermissionError("what-if decisions cannot trigger jobs")
    out = []
    for pid in d.get("needs_evaluation") or []:
        j, created = jobs.submit("evaluate", {"policy_id": pid, "suite_id": d["suite_id"],
                                              "purpose": f"matched validation for {decision_id}"}, SESSION)
        out.append({"job_id": j["id"], "policy_id": pid, "created": created, "state": j["state"]})
    return {"jobs": out}


@tool
def start_training(decision_id: str, seed: int) -> dict:
    """Launch the PPO adaptation a recorded decision selected. Revalidated against the current graph before launch."""
    d = records.read("decision", decision_id)
    if d["mode"] == "what-if":
        raise PermissionError("what-if decisions cannot launch training")
    if d["action"] not in ("train_from_parent", "train_from_scratch"):
        raise ValueError(f"decision action is {d['action']}, not a training action")
    if not (0 <= int(seed) < 100_000):
        raise ValueError("seed out of range")
    fresh = __import__("ew.select", fromlist=["decide"]).decide(d["request"], rule=d["rule_version"].replace("-nohist", ""),
                                                                 use_history=not d["rule_version"].endswith("-nohist"))
    if (fresh["action"], fresh["selected"]) != (d["action"], d["selected"]):
        now = fresh["selected"] or fresh["action"]
        raise RuntimeError(f"stale decision: current evidence says {now}, not {d['selected'] or d['action']}; propose again")
    parent = d["selected"]
    if parent:
        artifacts.verify_policy(parent)
    child = f"{parent or 'scratch'}~{decision_id[-6:]}-s{seed}"
    params = {"parent_id": parent, "child_id": child, "trial_id": f"trial-{decision_id[-6:]}-s{seed}",
              "target_family": d["request"]["target_family"], "threshold_id": d["request"]["threshold_id"],
              "budget": d["request"]["budget"], "seed": int(seed), "recipe": d["request"]["recipe"],
              "decision_id": decision_id, "purpose": "agent-launched " + ("adaptation" if parent else "scratch training")}
    j, created = jobs.submit("transfer_trial", params, SESSION)
    return {"job_id": j["id"], "created": created, "state": j["state"], "parent": parent, "child_policy_id": child,
            "budget": params["budget"], "quota_used_steps": jobs.steps_used(), "quota_steps": jobs.STEP_QUOTA}


@tool
def job_status(job_id: str) -> dict:
    """Actual worker state of a job (from the worker's state file)."""
    j = jobs.get(job_id)
    return {k: j.get(k) for k in ("id", "kind", "state", "progress", "result", "error", "consumed_steps", "params")}


@tool
def wait_for_job(job_id: str, timeout_s: int = 180) -> dict:
    """Block until the job leaves queued/running or timeout_s (max 240) passes; returns job_status."""
    t_end = time.time() + min(int(timeout_s), 240)
    while time.time() < t_end:
        j = jobs.get(job_id)
        if j["state"] not in ("queued", "running"):
            break
        time.sleep(2)
    j = jobs.get(job_id)
    return {k: j.get(k) for k in ("id", "kind", "state", "progress", "result", "error", "consumed_steps")}


@tool
def cancel_job(job_id: str) -> dict:
    """Request cancellation. A running PPO job stops at the next step and records a cancelled trial."""
    j = jobs.cancel(job_id)
    return {"id": j["id"], "state": j["state"], "cancel_requested": j.get("cancel_requested", False)}


@tool
def evaluate_checkpoint(policy_id: str, suite_id: str) -> dict:
    """Queue an evaluation of a saved checkpoint on a validation suite (final-test suites are refused)."""
    s = SUITES.get(suite_id)
    if s is None or s.role in PROTECTED_ROLES:
        raise PermissionError(f"suite {suite_id} is not an allowed validation suite")
    artifacts.verify_policy(policy_id)
    j, created = jobs.submit("evaluate", {"policy_id": policy_id, "suite_id": suite_id, "purpose": "agent evaluation"}, SESSION)
    return {"job_id": j["id"], "created": created, "state": j["state"]}


@tool
def request_promotion(policy_id: str) -> dict:
    """Ask the trusted gate (promo-1) to promote or reject this exact artifact."""
    p = service.promote(policy_id)
    return {k: p[k] for k in ("id", "policy_id", "artifact_hash", "verdict", "reasons", "checks", "missing")}


@tool
def export_evidence(policy_id: str) -> dict:
    """Build the reproducibility bundle (weights, normalization, contract, records, lock, checksums)."""
    b = service.export_bundle(policy_id)
    return {k: b[k] for k in ("policy_id", "artifact_hash", "sha256", "bytes", "lineage")} | {"bundle": os.path.basename(b["path"])}


TOOLS = [inspect_mission, query_graph, propose_adaptation, evaluate_candidates, start_training, job_status,
         wait_for_job, cancel_job, evaluate_checkpoint, request_promotion, export_evidence]
