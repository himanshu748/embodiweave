"""Publish measured robustness-v2 records without rewriting historical evidence."""
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from ew import artifacts, records, service
from ew.provenance import ROOT
from ew.robustness import CRITERIA, RULE, protocol_hash
from scripts.package_search import copy_once


def publish():
    trials = [t for t in records.all_of("trial") if t.get("search_rule") == RULE]
    pids = {t["child_policy_id"] for t in trials}
    dids = {t["decision_id"] for t in trials}
    paths = []
    destination = ROOT / "artifacts"
    for kind in ("trial", "run", "evaluation", "decision", "promotion"):
        for rec in records.all_of(kind):
            if rec.get("child_policy_id", rec.get("policy_id")) not in pids and not (kind == "decision" and rec["id"] in dids):
                continue
            target = destination / "records" / kind / f"{rec['id']}.json"
            copy_once(records.RECORDS / kind / target.name, target)
            paths.append(target)
            replay = service.REPLAYS / target.name
            if kind == "evaluation" and replay.exists():
                out = destination / "replays" / target.name
                copy_once(replay, out); paths.append(out)
    attempts = []
    for t in trials:
        pid = t["child_policy_id"]
        manifest = artifacts.load_manifest(pid)
        source = manifest["source"]
        archive = artifacts.ROOT / "source_archives" / f"{source['source_hash']}.zip"
        if not archive.exists():
            archive.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                for name, expected in source["files"].items():
                    content = subprocess.check_output(["git", "show", f"{source['commit']}:{name}"], cwd=ROOT)
                    if hashlib.sha256(content).hexdigest() != expected:
                        raise ValueError("Captured training source differs from its commit")
                    z.writestr(name, content)
        target = destination / "source_archives" / archive.name
        copy_once(archive, target); paths.append(target)
        for f in artifacts.policy_dir(pid).iterdir():
            target = destination / "policies" / pid / f.name
            copy_once(f, target); paths.append(target)
        gate = next(g for g in records.all_of("promotion") if g["policy_id"] == pid)
        bundle = service.export_bundle(pid)
        target = destination / "exports" / Path(bundle["path"]).name
        # First package creates the release bundle. Future packaging verifies and
        # retains it rather than re-exporting different ZIP timestamps.
        if not target.exists(): shutil.copyfile(bundle["path"], target)
        with zipfile.ZipFile(target) as z:
            checksums = json.loads(z.read("checksums.json"))
            assert all(hashlib.sha256(z.read(n)).hexdigest() == h for n,h in checksums.items())
        paths.append(target)
        attempts.append({"policy_id": pid, "artifact_hash": manifest["artifact_hash"],
            "parent_id": t["parent_id"], "decision_id": t["decision_id"], "trial_id": t["id"],
            "recipe": t["recipe"], "requested_steps": t["budget_steps"], "actual_steps": t["consumed_steps"],
            "seed": t["seed"], "checks": gate["checks"], "validation_verdict": gate["verdict"],
            "bundle_url": "api/download/"+target.name, "bundle_sha256": artifacts.sha256_file(target)})
    selected = json.loads((artifacts.ROOT / "robustness-v2-selected.json").read_text())
    confirmation = json.loads((artifacts.ROOT / "robustness-v2-confirmation.json").read_text())
    for name in ("robustness-v2-selected.json", "robustness-v2-confirmation-started.json", "robustness-v2-confirmation.json"):
        target = destination / name
        copy_once(artifacts.ROOT / name, target); paths.append(target)
    confirmation_pass = True
    family_criteria = dict(zip(("static_crossing", "open", "static", "crossing"), CRITERIA))
    for result in confirmation["results"]:
        c = family_criteria[result["family"]]
        result["min_success"], result["max_collision"] = c["min_success"], c["max_collision"]
        result["pass"] = (result["summary"]["success_rate"] >= c["min_success"] and
                          result["summary"]["collision_rate"] <= c["max_collision"])
        confirmation_pass &= result["pass"]
    transfer = json.loads((ROOT / "evidence/mujoco-v2/summary.json").read_text())
    selected_transfer = [r for r in transfer["results"] if r["policy_id"] == selected["policy_id"]]
    transfer_pass = len(selected_transfer) == 4 and all(
        r["summary"]["success_rate"] >= family_criteria[r["family"]]["min_success"] and
        r["summary"]["collision_rate"] <= family_criteria[r["family"]]["max_collision"] for r in selected_transfer)
    summary = {"study": RULE, "protocol_sha256": protocol_hash(), "attempts": attempts,
        "selected_policy": selected["policy_id"], "artifact_hash": selected["artifact_hash"],
        "selection_stopped": True, "confirmation": confirmation, "confirmation_pass": confirmation_pass,
        "transfer": transfer["results"], "transfer_meets_reference_limits": transfer_pass,
        "deployment_eligible": confirmation_pass,
        "deployment_scope": "2D simulator only. MuJoCo transfer has not cleared target collision requirements.",
        "notice": "New preregistered study. Existing search-v1 and MuJoCo-v1 results remain frozen. Confirmation never enters the planning graph."}
    for target in (ROOT / "evidence/robustness-v2/summary.json", ROOT / "web/media/robustness-evidence.json"):
        target.write_text(json.dumps(summary, indent=2)+"\n"); paths.append(target)
    paths += [p for p in (ROOT / "evidence/robustness-v2").glob("*.json") if p.name != "checksums.json"]
    paths += [ROOT / "ew/criteria.py", ROOT / "ew/scenarios.py"]
    (ROOT / "evidence/robustness-v2/checksums.json").write_text(json.dumps({str(p.relative_to(ROOT)):
        artifacts.sha256_file(p) for p in sorted(set(paths))}, indent=2)+"\n")
    print(json.dumps({"attempts": len(attempts), "selected": selected["policy_id"],
                      "confirmation_pass": confirmation_pass, "transfer_pass": transfer_pass}, indent=2))


if __name__ == "__main__":
    publish()
