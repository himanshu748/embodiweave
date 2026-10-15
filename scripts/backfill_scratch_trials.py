"""Write conditioned scratch Trial records for the exp-1 scratch comparison runs (ew-select-2 needs them).

The runs, their validation schedules and final validation evaluations were measured during exp-1 and are
already immutable records. This only derives Trial records from them; nothing is re-run or re-measured.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ew import artifacts, records, service  # noqa: E402
from ew.criteria import THRESHOLDS  # noqa: E402
from ew.graph import db, ingest  # noqa: E402
from ew.scenarios import FAMILIES  # noqa: E402


def main():
    exp = json.loads((artifacts.ROOT / "results" / "experiment.json").read_text())
    thr = THRESHOLDS[exp["protocol"]["threshold_id"]]
    fam = FAMILIES[exp["protocol"]["target_family"]]
    for x in exp["phase_b"]["null"]:
        tid = f"trial-exp1-scratch-s{x['seed']}"
        if records.exists("trial", tid):
            print("exists", tid)
            continue
        run = records.read("run", x["run_id"])
        assert run["parent_id"] is None and run["family_id"] == fam.fid()
        sched = run["validation_schedule"]
        stt = service.steps_to_threshold(sched, thr)
        m = artifacts.load_manifest(x["child"])
        t = records.write("trial", {
            "id": tid, "parent_id": None, "parent_artifact_hash": None, "child_policy_id": x["child"],
            "child_artifact_hash": m["artifact_hash"], "run_id": run["id"], "target_family": fam.name,
            "target_family_id": fam.fid(), "suite_id": thr["suite_id"], "contract_id": m["contract_id"],
            "recipe": run["recipe"], "threshold_id": exp["protocol"]["threshold_id"], "threshold": thr,
            "seed": x["seed"], "budget_steps": exp["protocol"]["budget"], "consumed_steps": run["consumed_steps"],
            "validation_every": sched[1]["steps"] - sched[0]["steps"] if len(sched) > 1 else None,
            "schedule": sched, "status": run["status"], "threshold_reached": stt is not None,
            "steps_to_threshold": stt, "final_evaluation_id": x["final_val_id"], "decision_id": None,
            "note": f"derived after the fact from exp-1 comparison run {run['id']} (measured {run.get('recorded_at')}); "
                    "no new training or evaluation"})
        ingest.trial(t)
        db.bump_revision(f"backfilled scratch trial {tid}")
        print("wrote", tid, "reached" if stt else "not reached", stt)


if __name__ == "__main__":
    main()
