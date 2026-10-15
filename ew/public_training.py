"""Bounded public PPO workflow; one disposable CPU subprocess, no model credentials.

The API stays torch-free. Only trusted code chooses paths, recipe, suites and budget.
Receipts/quotas are ephemeral on free Render. Never run multiple API workers.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import artifacts, jobs
from .agent_sessions import _save
from .recipes import reserved_steps

BUDGET, MAX_SECONDS, DAILY_RUNS, VISITOR_HOURLY = 60000, 480, 16, 4
ALLOWED_BUDGETS = (4096, 60000, 150000)
SUITES = ("val-target-v1", "val-open-v1", "val-static-v1", "val-crossing-v1")
ACTIVE = {"queued", "running", "cancelling"}
_processes: dict[str, subprocess.Popen] = {}


class Limited(RuntimeError):
    pass


def configuration():
    enabled = importlib.util.find_spec("torch") is not None and importlib.util.find_spec("stable_baselines3") is not None
    return {"enabled": enabled, "budget": BUDGET, "budgets": list(ALLOWED_BUDGETS), "max_seconds": MAX_SECONDS, "daily_runs": DAILY_RUNS,
            "visitor_hourly": VISITOR_HOURLY, "suites": list(SUITES), "ephemeral": os.environ.get("EW_PERSISTENT_ARTIFACTS") != "1",
            "reason": None if enabled else "CPU training is not installed on this service."}


def _root():
    p = artifacts.ROOT / "public_training"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _path(sid):
    if not re.fullmatch(r"ppo-[0-9a-f]{32}", sid):
        raise FileNotFoundError("Unknown PPO trial")
    return _root() / (sid + ".json")


def _frame_path(sid):
    _path(sid)
    root = _root() / "frames"
    root.mkdir(exist_ok=True)
    return root / (sid + ".json")


def owner(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _public(s):
    return {k: v for k, v in s.items() if k not in ("owner", "pid")}


def _read(sid):
    p = _path(sid)
    s = json.loads(p.read_text())
    if s["state"] in ACTIVE and sid not in _processes:
        s.update(state="interrupted", detail="The service restarted. This trial did not complete; start a new one.", finished_at=time.time())
        _save(p, s)
    return s


def status(sid, token):
    s = _read(sid)
    if not token or not secrets.compare_digest(s["owner"], owner(token)):
        raise FileNotFoundError("Unknown PPO trial")
    return _public(s)


def cancel(sid, token):
    status(sid, token)
    with jobs._lock("public-ppo-state"):
        s = _read(sid)
        if s["state"] in ACTIVE:
            (_root() / (sid + ".cancel")).touch()
            s.update(state="cancelling", detail="Cancellation requested. The worker will stop; no final gate will be claimed.")
            _save(_path(sid), s)
    return _public(s)


def _worker_env():
    # Explicit allowlist: model, cloud and Render API credentials cannot reach PPO.
    allowed = {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "PYTHONPATH", "EW_ARTIFACTS", "EW_GRAPH",
               "EW_FALKOR_HOST", "EW_FALKOR_PORT", "EW_GIT_COMMIT", "RENDER_GIT_COMMIT", "SYSTEMROOT"}
    return {**{k: v for k, v in os.environ.items() if k in allowed},
            "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MALLOC_ARENA_MAX": "2"}


def start(token, seed=7, consent=False, *, owner_hash=None, budget=BUDGET):
    if consent is not True:
        raise PermissionError("Confirm that you want to start training.")
    if type(seed) is not int or not 0 <= seed < 100000:
        raise ValueError("Seed must be an integer from 0 to 99999.")
    if type(budget) is not int or budget not in ALLOWED_BUDGETS:
        raise ValueError("Choose 4096, 60000 or 150000 training steps.")
    if not configuration()["enabled"]:
        raise PermissionError(configuration()["reason"])
    identity, now = owner_hash or owner(token), time.time()
    with jobs._lock("public-ppo"):
        sessions = [_read(p.stem) for p in _root().glob("ppo-*.json")]
        for s in sessions:
            if s["state"] in ACTIVE:
                if s["owner"] == identity:
                    return _public(s)
                raise Limited("Another judge's PPO trial is running. Try again after it finishes (at most eight minutes).")
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        if sum(s["day"] == day for s in sessions) >= DAILY_RUNS:
            raise Limited("Today's shared training allowance is used. Recorded evidence and live graph queries remain available.")
        if sum(s["owner"] == identity and now - s["started_at"] < 3600 for s in sessions) >= VISITOR_HOURLY:
            raise Limited("This browser has used four training runs this hour. Download an existing trial or return later.")
        sid = "ppo-" + secrets.token_hex(16)
        s = {"id": sid, "owner": identity, "day": day, "started_at": now, "state": "queued", "phase": "select",
             "seed": seed, "budget": budget, "reserved_steps": reserved_steps(budget), "consumed_steps": 0, "evaluations": [], "gate": None,
             "detail": "Choosing a starting policy from FalkorDB.", "cancel_requested": False}
        _save(_path(sid), s)
        try:
            with open(_root() / (sid + ".log"), "w") as log:
                proc = subprocess.Popen([sys.executable, "-m", "ew.public_training", "worker", sid],
                                        env=_worker_env(), stdin=subprocess.DEVNULL, stdout=log,
                                        stderr=log, close_fds=True)
        except Exception:
            s.update(state="failed", detail="The CPU worker could not start.", finished_at=time.time())
            _save(_path(sid), s)
            raise RuntimeError(s["detail"]) from None
        _processes[sid] = proc
        threading.Thread(target=_watch, args=(sid, proc), daemon=True).start()
        return _public(s)


def _watch(sid, proc):
    try:
        try:
            code = proc.wait(timeout=MAX_SECONDS)
            terminal, detail = "failed", f"The CPU worker exited before completion (code {code}). No completed gate is claimed."
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            terminal, detail = "timed_out", "The eight-minute CPU limit was reached. No completed gate is claimed."
        with jobs._lock("public-ppo-state"):
            s = json.loads(_path(sid).read_text())
            if s["state"] in ACTIVE:
                s.update(state=terminal, detail=detail, finished_at=time.time())
                _save(_path(sid), s)
    finally:
        _processes.pop(sid, None)


def _update(sid, **values):
    with jobs._lock("public-ppo-state"):
        s = json.loads(_path(sid).read_text())
        s.update(values)
        _save(_path(sid), s)
        return s


def bundle(sid, token):
    s = status(sid, token)
    if s["state"] != "completed" or not s.get("bundle"):
        raise FileNotFoundError("Complete the trial before downloading its checkpoint.")
    name = s["bundle"]["filename"]
    if Path(name).name != name:
        raise FileNotFoundError("Invalid bundle")
    return artifacts.ROOT / "exports" / name


def frames(sid, token, after=0):
    s = status(sid, token)
    path = _frame_path(sid)
    data = json.loads(path.read_text()) if path.exists() else {"latest": 0, "frames": []}
    return {**data, "frames": [f for f in data["frames"] if f["seq"] > after], "finished": s["state"] not in ACTIVE}


def _worker(sid):
    from . import records, service
    from .criteria import THRESHOLDS, meets
    from .graph import db, ingest
    from .scenarios import FAMILIES
    from .select import decide

    s = json.loads(_path(sid).read_text())
    from .live_frames import FrameWriter
    writer = FrameWriter(_frame_path(sid))
    budget = s["budget"]
    stop = lambda: (_root() / (sid + ".cancel")).exists()
    try:
        if stop():
            raise InterruptedError()
        req = {**service.target_request(budget=budget), "candidate_run_kinds": ["library"]}
        d = service.record_decision(req)
        if d["action"] not in ("train_from_parent", "train_from_scratch"):
            raise ValueError("The selection rule did not authorize training.")
        fresh = decide(req)
        if (fresh["action"], fresh["selected"]) != (d["action"], d["selected"]):
            raise ValueError("Graph evidence changed during selection. Start a new trial.")
        parent = d["selected"]
        parent_hash = artifacts.verify_policy(parent) if parent else None
        child = "judge-" + sid[4:]
        _update(sid, state="running", phase="train", decision_id=d["id"], selection=d,
                parent_id=parent, policy_id=child, detail=f"Training the policy for {budget:,} steps. The view shows one of eight simulator environments.")
        out = service.train_run(child, family="static_crossing", budget_steps=budget, seed=s["seed"],
                                parent_id=parent, run_kind="judge_demo", decision_id=d["id"],
                                purpose="bounded public judge trial; not a benchmark", should_cancel=stop,
                                on_progress=lambda p: _update(sid, consumed_steps=p["steps"], train_progress=p),
                                on_frame=writer.observer("train"))
        run, m = out["run"], out["manifest"]
        _update(sid, consumed_steps=run["consumed_steps"], run_id=run["id"], artifact_hash=m["artifact_hash"],
                weight_delta_l2=m["weight_delta_l2"])
        if parent:
            artifacts.verify_policy(parent, parent_hash)
        if stop() or run["status"] != "completed":
            raise InterruptedError()
        evaluations = []
        for suite in SUITES:
            if stop():
                raise InterruptedError()
            _update(sid, phase="validate", detail=f"Evaluating saved checkpoint on {suite}; {len(evaluations)}/4 suites complete.")
            ev = service.evaluate(child, suite, expected_hash=m["artifact_hash"],
                                  purpose="bounded-public-trial:" + sid, save_replay=suite == SUITES[0], on_frame=writer.observer("validate", suite), should_cancel=stop)
            evaluations.append({k: ev[k] for k in ("id", "suite_id", "artifact_hash", "summary")})
            _update(sid, evaluations=evaluations)
        if stop():
            raise InterruptedError()
        writer.flush()
        thr = THRESHOLDS[req["threshold_id"]]
        target = evaluations[0]
        reached = meets(target["summary"], thr)
        trial = records.write("trial", {"parent_id": parent, "parent_artifact_hash": parent_hash,
            "child_policy_id": child, "child_artifact_hash": m["artifact_hash"], "run_id": run["id"],
            "target_family": "static_crossing", "target_family_id": FAMILIES["static_crossing"].fid(),
            "suite_id": SUITES[0], "contract_id": m["contract_id"], "recipe": "ppo-r1", "threshold_id": req["threshold_id"],
            "threshold": thr, "seed": s["seed"], "budget_steps": budget, "consumed_steps": run["consumed_steps"],
            "validation_every": None, "schedule": [{"steps": run["consumed_steps"], "suite_id": SUITES[0], **target["summary"]}],
            "status": "completed", "threshold_reached": reached, "steps_to_threshold": run["consumed_steps"] if reached else None,
            "final_evaluation_id": target["id"], "decision_id": d["id"]})
        ingest.trial(trial)
        db.bump_revision("public trial " + trial["id"])
        _update(sid, phase="gate", trial_id=trial["id"], detail="Checking the exact artifact against all four canonical suites.")
        gate = service.promote(child)
        exported = service.export_bundle(child)
        _update(sid, state="completed", phase="complete", gate=gate, replay_evaluation_id=target["id"],
                bundle={"filename": Path(exported["path"]).name, "sha256": exported["sha256"], "bytes": exported["bytes"]},
                graph_revision=db.revision(), finished_at=time.time(),
                detail="Training and all 180 test episodes finished. Your checkpoint and results are ready to download.")
    except InterruptedError:
        _update(sid, state="cancelled", phase="stopped", finished_at=time.time(), detail="Trial cancelled. Partial records may exist; no completed gate or export is claimed.")
    except Exception as exc:
        # No credentials in child environment; don't expose internals or arbitrary exception text.
        _update(sid, state="failed", phase="stopped", finished_at=time.time(),
                detail=f"The CPU workflow stopped ({type(exc).__name__}). No completed flow is claimed.")
        raise


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "worker":
        _path(sys.argv[2])
        with jobs._lock("public-ppo-execute"):
            _worker(sys.argv[2])
    else:
        raise SystemExit("Use the bounded public training API.")
