"""Bounded job queue + single worker.

Jobs are small mutable state files (operational status); their outcomes are immutable records.
- One worker process, one job at a time (bounded concurrency).
- Hard per-job budget cap and a global step quota.
- Idempotent submission: same kind+params returns the existing job.
- Cancellation via a flag file checked inside the PPO callback.
- Restart recovery: jobs left 'running' by a dead worker become 'interrupted' and an
  interrupted trial record is written; nothing is marked complete without its artifact.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from . import artifacts, records

JOBS = artifacts.ROOT / "jobs"
MAX_JOB_STEPS = int(os.environ.get("EW_MAX_JOB_STEPS", "200000"))
STEP_QUOTA = int(os.environ.get("EW_STEP_QUOTA", "3000000"))
STATES = ("queued", "running", "completed", "failed", "cancelled", "interrupted")


class QuotaExceeded(RuntimeError):
    pass


def _p(job_id: str) -> Path:
    return JOBS / f"{job_id}.json"


def _save(job: dict) -> None:
    JOBS.mkdir(parents=True, exist_ok=True)
    tmp = _p(job["id"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(job, indent=1, default=str))
    os.replace(tmp, _p(job["id"]))


def get(job_id: str) -> dict:
    return json.loads(_p(job_id).read_text())


def all_jobs() -> list[dict]:
    if not JOBS.exists():
        return []
    return sorted((json.loads(p.read_text()) for p in JOBS.glob("*.json")), key=lambda j: j["submitted_at"])


def steps_used() -> int:
    tot = 0
    for j in all_jobs():
        if j["kind"] == "transfer_trial":
            tot += j.get("consumed_steps") or (j["params"]["budget"] if j["state"] in ("queued", "running") else 0)
    return tot


def idem_key(kind: str, params: dict) -> str:
    return hashlib.sha256(json.dumps([kind, params], sort_keys=True).encode()).hexdigest()[:16]


def submit(kind: str, params: dict, requested_by: str = "api") -> tuple[dict, bool]:
    """Returns (job, created). Duplicate submissions return the existing job (created=False)."""
    key = idem_key(kind, params)
    for j in all_jobs():
        if j["idem_key"] == key and j["state"] not in ("failed", "interrupted"):
            return j, False
    if kind == "transfer_trial":
        b = int(params["budget"])
        if b > MAX_JOB_STEPS:
            raise QuotaExceeded(f"budget {b} exceeds per-job cap {MAX_JOB_STEPS}")
        if steps_used() + b > STEP_QUOTA:
            raise QuotaExceeded(f"step quota {STEP_QUOTA} would be exceeded ({steps_used()} used)")
    job = {"id": records.new_id("job"), "kind": kind, "params": params, "idem_key": key, "state": "queued",
           "submitted_at": time.time(), "requested_by": requested_by, "progress": None, "result": None,
           "error": None, "consumed_steps": None}
    _save(job)
    return job, True


def cancel(job_id: str) -> dict:
    j = get(job_id)
    if j["state"] == "queued":
        j["state"] = "cancelled"
        j["error"] = "cancelled before start"
        _save(j)
    elif j["state"] == "running":
        (JOBS / f"{job_id}.cancel").write_text("1")
        j["cancel_requested"] = True
        _save(j)
    return j


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def recover() -> list[str]:
    """Mark jobs orphaned by a dead worker as interrupted and record the incomplete trial."""
    out = []
    for j in all_jobs():
        if j["state"] == "running" and not _pid_alive(j.get("worker_pid", -1)):
            j["state"] = "interrupted"
            j["error"] = "worker exited while job was running; partial output discarded"
            j["finished_at"] = time.time()
            if j["kind"] == "transfer_trial":
                j["consumed_steps"] = (j.get("progress") or {}).get("steps", 0)
                _record_incomplete_trial(j, "interrupted")
            _save(j)
            out.append(j["id"])
    return out


def _record_incomplete_trial(j: dict, status: str) -> None:
    from .criteria import THRESHOLDS
    from .graph import db, ingest
    from .scenarios import FAMILIES
    p = j["params"]
    thr = THRESHOLDS[p["threshold_id"]]
    fam = FAMILIES[p["target_family"]]
    m = artifacts.load_manifest(p["parent_id"])
    t = records.write("trial", {
        "id": j["params"]["trial_id"], "parent_id": p["parent_id"], "parent_artifact_hash": m["artifact_hash"],
        "child_policy_id": None, "child_artifact_hash": None, "run_id": None, "target_family": fam.name,
        "target_family_id": fam.fid(), "suite_id": thr["suite_id"], "contract_id": m["contract_id"],
        "recipe": p["recipe"], "threshold_id": p["threshold_id"], "threshold": thr, "seed": p["seed"],
        "budget_steps": p["budget"], "consumed_steps": j.get("consumed_steps") or 0, "validation_every": None,
        "schedule": (j.get("progress") or {}).get("schedule", []), "status": status, "threshold_reached": False,
        "steps_to_threshold": None, "final_evaluation_id": None, "decision_id": p.get("decision_id"),
        "note": "outcome unknown: run did not complete; no checkpoint, no threshold claim", "job_id": j["id"]})
    try:
        ingest.trial(t)
        db.bump_revision(f"{status} trial {t['id']}")
    except Exception:  # graph down: record persists and is ingested on rebuild
        pass


def _run(j: dict) -> None:
    from . import service
    p = j["params"]
    flag = JOBS / f"{j['id']}.cancel"

    def prog(info):
        j["progress"] = {**(j.get("progress") or {}), **info, "at": time.time()}
        _save(j)

    def should_cancel():
        return flag.exists()

    if j["kind"] == "transfer_trial":
        out = service.transfer_trial(parent_id=p["parent_id"], child_id=p["child_id"],
                                     target_family=p["target_family"], threshold_id=p["threshold_id"],
                                     budget_steps=p["budget"], seed=p["seed"], recipe=p["recipe"],
                                     decision_id=p.get("decision_id"), purpose=p.get("purpose", "agent job"),
                                     on_progress=prog, should_cancel=should_cancel, trial_id=p["trial_id"])
        t = out["trial"]
        j["consumed_steps"] = t["consumed_steps"]
        j["result"] = {"trial_id": t["id"], "run_id": t["run_id"], "child_policy_id": t["child_policy_id"],
                       "child_artifact_hash": t["child_artifact_hash"], "threshold_reached": t["threshold_reached"],
                       "steps_to_threshold": t["steps_to_threshold"], "trial_status": t["status"],
                       "final_evaluation_id": t["final_evaluation_id"], "schedule": t["schedule"]}
        j["state"] = "cancelled" if t["status"] == "cancelled" else "completed"
    elif j["kind"] == "evaluate":
        e = service.evaluate(p["policy_id"], p["suite_id"], purpose=p.get("purpose", "agent job"), save_replay=True)
        j["result"] = {"evaluation_id": e["id"], "summary": e["summary"], "artifact_hash": e["artifact_hash"]}
        j["state"] = "completed"
    else:
        raise ValueError(f"unknown job kind {j['kind']}")


def work_once() -> dict | None:
    queued = [j for j in all_jobs() if j["state"] == "queued"]
    if not queued:
        return None
    j = queued[0]
    j["state"], j["worker_pid"], j["started_at"] = "running", os.getpid(), time.time()
    _save(j)
    try:
        _run(j)
    except Exception as e:  # noqa: BLE001
        j["state"] = "failed"
        j["error"] = f"{e.__class__.__name__}: {e}"
        j["traceback"] = traceback.format_exc()[-2000:]
        if j["kind"] == "transfer_trial" and not records.exists("trial", j["params"]["trial_id"]):
            j["consumed_steps"] = (j.get("progress") or {}).get("steps", 0)
            _record_incomplete_trial(j, "failed")
    j["finished_at"] = time.time()
    _save(j)
    return j


def main() -> None:
    print("worker recovered:", recover(), flush=True)
    stop = {"v": False}
    signal.signal(signal.SIGTERM, lambda *a: stop.update(v=True))
    while not stop["v"]:
        if work_once() is None:
            time.sleep(1.0)


if __name__ == "__main__":
    sys.exit(main())
