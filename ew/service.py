"""Trusted backend operations. These are the only code paths that write measured evidence.

They call real PPO training / evaluation, persist immutable records, then ingest into FalkorDB.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import artifacts, records, rl
from .contract import CONTRACT_V1, PolicyContract, get_contract
from .criteria import THRESHOLDS, meets
from .graph import db, ingest
from .scenarios import FAMILIES, PROTECTED_ROLES, SUITES, Family

REPLAYS = artifacts.ROOT / "replays"


def _fam(f) -> Family:
    return FAMILIES[f] if isinstance(f, str) else f


def train_run(policy_id: str, *, family, budget_steps: int, seed: int, parent_id: str | None = None,
              recipe: str = "ppo-r1", contract: PolicyContract | None = None, run_kind: str = "library",
              purpose: str = "", decision_id: str | None = None, run_id: str | None = None,
              validation_suite: str | None = None, on_progress=None, should_cancel=None, graph: str | None = None) -> dict:
    fam = _fam(family)
    run_id = run_id or records.new_id("run")
    val = SUITES[validation_suite] if validation_suite else None
    if val is not None and val.role in PROTECTED_ROLES:
        raise PermissionError("training may not validate against a protected final-test suite")
    t0 = time.time()
    res = rl.train(policy_id, family=fam, budget_steps=budget_steps, seed=seed, parent_id=parent_id,
                   recipe=recipe, contract=contract, on_progress=on_progress, should_cancel=should_cancel,
                   validation=val, run_id=run_id)
    m = res["manifest"]
    rec = records.write("run", {
        "id": run_id, "run_kind": run_kind, "purpose": purpose, "parent_id": parent_id,
        "child_policy_id": policy_id, "child_artifact_hash": m["artifact_hash"], "family": fam.name,
        "family_id": fam.fid(), "recipe": recipe, "seed": seed, "budget_steps": budget_steps,
        "consumed_steps": res["consumed_steps"], "status": res["status"], "wall_s": round(time.time() - t0, 2),
        "train_wall_s": round(res["wall_s"], 2), "train_episodes": res["train_episodes"],
        "weight_delta_l2": m["weight_delta_l2"], "contract_id": m["contract_id"], "decision_id": decision_id,
        "validation_schedule": res["validation_schedule"], "runtime": m["runtime"]})
    ingest.policy(m, graph)
    ingest.run(rec, graph)
    db.bump_revision(f"run {run_id}", graph)
    return {"run": rec, "manifest": m}


def evaluate(policy_id: str, suite_id: str, *, purpose: str = "", save_replay: bool = False,
             expected_hash: str | None = None, final_test_runner: bool = False, graph: str | None = None,
             family_override: Family | None = None, n_episodes: int | None = None) -> dict:
    """Reload the saved artifact and evaluate it on a fixed, versioned suite."""
    s = SUITES[suite_id]
    if s.role in PROTECTED_ROLES and not final_test_runner:
        raise PermissionError(f"{suite_id} is a protected final-test suite")
    fam = family_override or s.family
    seeds = s.seeds[:n_episodes] if n_episodes else s.seeds
    ev = rl.evaluate_policy(policy_id, fam, seeds, record=save_replay, expected_hash=expected_hash)
    episodes = [{k: v for k, v in ep.items() if k not in ("trace", "layout")} for ep in ev["episodes"]]
    rec = records.write("evaluation", {
        "policy_id": policy_id, "artifact_hash": ev["artifact_hash"], "suite_id": suite_id,
        "suite_role": s.role, "suite_version": s.version, "family_id": fam.fid(), "custom_family": family_override is not None,
        "seeds": list(seeds), "contract_id": ev["contract_id"], "summary": ev["summary"], "episodes": episodes,
        "purpose": purpose, "wall_s": ev["wall_s"]})
    if save_replay:
        REPLAYS.mkdir(parents=True, exist_ok=True)
        (REPLAYS / f"{rec['id']}.json").write_text(json.dumps({
            "evaluation_id": rec["id"], "policy_id": policy_id, "artifact_hash": ev["artifact_hash"],
            "suite_id": suite_id, "family": json.loads(json.dumps(fam.__dict__, default=list)),
            "episodes": [{"seed": sd, "layout": ep["layout"], "trace": ep["trace"], "outcome": ep["outcome"],
                          "hit": ep.get("hit"), "steps": ep["steps"]} for sd, ep in zip(seeds, ev["episodes"])]}))
    if s.role not in PROTECTED_ROLES and family_override is None:
        ingest.evaluation(rec, graph)
        db.bump_revision(f"evaluation {rec['id']}", graph)
    return rec


def steps_to_threshold(schedule: list, thr: dict):
    """First scheduled validation point meeting the threshold, else None (unknown, not reached)."""
    for pt in schedule:
        if meets(pt, thr):
            return pt["steps"]
    return None


def transfer_trial(*, parent_id: str | None, child_id: str, target_family: str, threshold_id: str,
                   budget_steps: int, seed: int, recipe: str = "ppo-r1", decision_id: str | None = None,
                   run_kind: str = "transfer_trial", purpose: str = "", on_progress=None, should_cancel=None,
                   graph: str | None = None, trial_id: str | None = None, run_id: str | None = None) -> dict:
    """Conditioned parent->target adaptation attempt. Always recorded, including non-success."""
    thr = THRESHOLDS[threshold_id]
    fam = _fam(target_family)
    contract = get_contract(artifacts.load_manifest(parent_id)["contract_id"]) if parent_id else CONTRACT_V1
    parent_hash = artifacts.verify_policy(parent_id) if parent_id else None
    out = train_run(child_id, family=fam, budget_steps=budget_steps, seed=seed, parent_id=parent_id,
                    recipe=recipe, contract=contract, run_kind=run_kind, purpose=purpose, decision_id=decision_id,
                    validation_suite=thr["suite_id"], on_progress=on_progress, should_cancel=should_cancel,
                    graph=graph, run_id=run_id)
    run, m = out["run"], out["manifest"]
    if parent_id:  # source checkpoint must be untouched
        artifacts.verify_policy(parent_id, parent_hash)
    sched = run["validation_schedule"]
    stt = steps_to_threshold(sched, thr)
    final_eval = evaluate(child_id, thr["suite_id"], purpose=f"trial-final:{run['id']}", save_replay=True, graph=graph)
    status = run["status"]
    reached = stt is not None
    t = records.write("trial", {
        "id": trial_id or records.new_id("trial"), "parent_id": parent_id, "parent_artifact_hash": parent_hash,
        "child_policy_id": child_id, "child_artifact_hash": m["artifact_hash"], "run_id": run["id"],
        "target_family": fam.name, "target_family_id": fam.fid(), "suite_id": thr["suite_id"],
        "contract_id": contract.contract_id, "recipe": recipe, "threshold_id": threshold_id, "threshold": thr,
        "seed": seed, "budget_steps": budget_steps, "consumed_steps": run["consumed_steps"],
        "validation_every": sched[1]["steps"] - sched[0]["steps"] if len(sched) > 1 else None,
        "schedule": sched, "status": status, "threshold_reached": reached,
        # None means: not reached within the observed budget; the true steps-to-threshold is unknown.
        "steps_to_threshold": stt, "final_evaluation_id": final_eval["id"], "decision_id": decision_id})
    if parent_id:
        ingest.trial(t, graph)
        db.bump_revision(f"trial {t['id']}", graph)
    return {"trial": t, "run": run, "final_evaluation": final_eval}


def target_request(budget: int = 60_000, recipe: str = "ppo-r1", threshold_id: str = "thr-target-1") -> dict:
    fam = FAMILIES["static_crossing"]
    return {"mission": "static_crossing", "robot": CONTRACT_V1.robot.name, "contract": CONTRACT_V1.contract_id,
            "target_family": fam.name, "target_family_id": fam.fid(), "threshold_id": threshold_id,
            "recipe": recipe, "budget": budget}


def record_decision(request: dict, *, mode: str = "deterministic", graph: str | None = None,
                    use_history: bool = True, agent_trace_id: str | None = None) -> dict:
    """Run the frozen selection rule on graph evidence and persist the decision.

    mode: 'llm-agent' (an LLM tool call asked for it), 'deterministic' (scripted), 'what-if' (isolated copy).
    What-if decisions are written only to their isolated graph copy and are flagged in the record.
    """
    from . import select
    d = select.decide(request, graph_name=graph, use_history=use_history)
    d["mode"] = mode
    d["agent_trace_id"] = agent_trace_id
    rec = records.write("decision", d)
    ingest.decision(rec, graph)
    db.bump_revision(f"decision {rec['id']}", graph)
    return rec


def promote(policy_id: str, rule: str = "promo-1", graph: str | None = None) -> dict:
    """Trusted promotion gate. Binds to the exact artifact hash; evidence must be on that hash."""
    from .criteria import PROMOTION
    from .graph import queries as Q
    pr = PROMOTION[rule]
    reasons, verdict = [], "promoted"
    h = artifacts.verify_policy(policy_id)  # files exist and match their manifest
    m = artifacts.load_manifest(policy_id)
    if m["contract_id"] != CONTRACT_V1.contract_id:
        reasons.append(f"contract {m['contract_id']} is not the mission contract")
    if m["status"] != "completed":
        reasons.append(f"checkpoint status {m['status']}")
    reqs = [pr["target"]] + pr["retained"]
    q = Q.run("promotion_evidence", {"policy": policy_id, "suites": [r["suite_id"] for r in reqs], "hash": h}, graph)
    rows = {}
    for r in q.dicts():
        if r["evaluation_id"]:
            rows[r["suite_id"]] = r  # newest wins (ordered by time)
        if r["policy_hash"] != h:
            reasons.append("graph artifact hash differs from files on disk")
    used, missing, checks = [], [], []
    for crit in reqs:
        r = rows.get(crit["suite_id"])
        if r is None:
            missing.append(crit["suite_id"])
            continue
        ok = r["success_rate"] >= crit["min_success"] and r["collision_rate"] <= crit["max_collision"]
        checks.append({"suite_id": crit["suite_id"], "evaluation_id": r["evaluation_id"], "success_rate": r["success_rate"],
                       "collision_rate": r["collision_rate"], "min_success": crit["min_success"],
                       "max_collision": crit["max_collision"], "pass": ok,
                       "role": "target" if crit is pr["target"] else "retained"})
        used.append(r["evaluation_id"])
        if not ok:
            reasons.append(f"{crit['suite_id']}: success {r['success_rate']:.2f} (min {crit['min_success']}), "
                           f"collision {r['collision_rate']:.2f} (max {crit['max_collision']})")
    if missing:
        verdict = "insufficient_evidence"
        reasons.append("no evaluation of this exact artifact on: " + ", ".join(missing))
    elif reasons:
        verdict = "rejected"
    rec = records.write("promotion", {"policy_id": policy_id, "artifact_hash": h, "rule": rule, "verdict": verdict,
                                      "reasons": reasons, "checks": checks, "missing": missing,
                                      "evaluation_ids": used, "query": q.to_log()})
    ingest.promotion(rec, graph)
    db.bump_revision(f"promotion {rec['id']}", graph)
    return rec


def export_bundle(policy_id: str) -> dict:
    """Zip the checkpoint with contract, records, lock file and checksums."""
    import hashlib
    import zipfile
    m = artifacts.load_manifest(policy_id)
    artifacts.verify_policy(policy_id, m["artifact_hash"])
    out_dir = artifacts.ROOT / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{policy_id}-{m['artifact_hash'][:12]}.zip"
    root = Path(__file__).resolve().parent.parent
    rel = {"runs": [r for r in records.all_of("run") if r.get("child_policy_id") == policy_id],
           "evaluations": [e for e in records.all_of("evaluation") if e["policy_id"] == policy_id],
           "trials": [t for t in records.all_of("trial") if policy_id in (t.get("child_policy_id"), t.get("parent_id"))],
           "promotions": [p for p in records.all_of("promotion") if p["policy_id"] == policy_id]}
    lineage, cur = [], m
    while cur:
        lineage.append({"policy_id": cur["policy_id"], "artifact_hash": cur["artifact_hash"], "family": cur["family"],
                        "steps": cur["consumed_steps"], "seed": cur["seed"]})
        cur = artifacts.load_manifest(cur["parent_id"]) if cur.get("parent_id") else None
    contract = get_contract(m["contract_id"]).describe()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        d = artifacts.policy_dir(policy_id)
        for n in ("model.zip", "vecnormalize.pkl", "manifest.json"):
            z.write(d / n, f"policy/{n}")
        z.writestr("contract.json", json.dumps(contract, indent=1, default=list))
        z.writestr("records.json", json.dumps(rel, indent=1, default=str))
        z.writestr("lineage.json", json.dumps(lineage, indent=1))
        lock = root / "requirements.lock"
        if lock.exists():
            z.write(lock, "requirements.lock")
        z.writestr("REPRODUCE.md", (
            f"# Reproduce {policy_id}\n\nartifact_hash (sha256 over model.zip + vecnormalize.pkl digests): {m['artifact_hash']}\n\n"
            "```\npip install -r requirements.lock\npython -m ew.cli evaluate --policy-dir policy --suite val-target-v1\n```\n"
            f"Training: recipe {m['recipe']} seed {m['seed']} steps {m['consumed_steps']} on family {m['family']} "
            f"from parent {m.get('parent_id') or 'scratch'}. Runtime: {json.dumps(m['runtime'])}.\n"
            "Bitwise identical retraining is not promised across hardware or package versions; evaluation of the\n"
            "saved artifact on the same suite seeds is deterministic on the same package set.\n"))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": str(path), "sha256": sha, "policy_id": policy_id, "artifact_hash": m["artifact_hash"],
            "lineage": lineage, "bytes": path.stat().st_size}
