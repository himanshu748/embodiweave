"""Publish the fixed search-v1 evidence index from immutable measured records.

Run with EW_ARTIFACTS pointing at the search store. This copies only new search
records to the checkout and verifies captured training source against Git.
"""
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from ew import artifacts, records, service
from ew.provenance import ROOT


def copy_once(src, dest):
    if dest.exists():
        if src.read_bytes() != dest.read_bytes():
            raise ValueError(f"Refusing to replace immutable evidence: {dest}")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)


def main():
    destination = ROOT / "artifacts"
    new_trials = [t for t in records.all_of("trial") if t.get("search_rule") == "search-v1"]
    if len(new_trials) != 2:
        raise ValueError("This report is frozen to the two measured search-v1 attempts")
    pids = {t["child_policy_id"] for t in new_trials}
    dids = {t["decision_id"] for t in new_trials}
    selected_records = {}
    for kind in ("trial", "run", "evaluation", "decision", "promotion"):
        selected_records[kind] = [r for r in records.all_of(kind) if
            r.get("child_policy_id", r.get("policy_id")) in pids or (kind == "decision" and r["id"] in dids)]
        for r in selected_records[kind]:
            out = destination / "records" / kind / f"{r['id']}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            copy_once(records.RECORDS / kind / out.name, out)
    for pid in sorted(pids):
        m = artifacts.load_manifest(pid)
        captured = m["source"]
        archive = artifacts.ROOT / "source_archives" / f"{captured['source_hash']}.zip"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                for name, digest in captured["files"].items():
                    content = subprocess.check_output(["git", "show", f"{captured['commit']}:{name}"], cwd=ROOT)
                    if hashlib.sha256(content).hexdigest() != digest:
                        raise ValueError("Training source differs from recorded commit")
                    z.writestr(name, content)
        for f in artifacts.policy_dir(pid).iterdir():
            copy_once(f, destination / "policies" / pid / f.name)
        # Use the already published archive on repeated packaging, preserving its bytes.
        published = destination / "source_archives" / archive.name
        if published.exists():
            shutil.copyfile(published, archive)
        else:
            copy_once(archive, published)
    for e in selected_records["evaluation"]:
        p = service.REPLAYS / f"{e['id']}.json"
        if p.exists():
            (destination / "replays").mkdir(exist_ok=True)
            copy_once(p, destination / "replays" / p.name)
    copy_once(artifacts.ROOT / "final-confirmation-started.json", destination / "final-confirmation-started.json")
    attempts = []
    for i, t in enumerate(new_trials, 1):
        pid = t["child_policy_id"]
        gate = next(p for p in selected_records["promotion"] if p["policy_id"] == pid)
        decision = records.read("decision", t["decision_id"])
        m = artifacts.load_manifest(pid)
        bundle = service.export_bundle(pid)
        with zipfile.ZipFile(bundle["path"]) as z:
            checksums = json.loads(z.read("checksums.json"))
            assert all(hashlib.sha256(z.read(n)).hexdigest() == h for n, h in checksums.items())
        out = destination / "exports" / Path(bundle["path"]).name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle["path"], out)
        attempts.append({"label": f"Attempt {i}: {t['intervention']}", "policy_id": pid,
            "display_explanation": ("The graph selected a compatible checkpoint with the best complete-validation ranking. More target training passed three suites, but open-arena success still missed its requirement." if i == 1 else
                "The graph selected the improved child. Its remaining open-arena failure triggered rehearsal of earlier training families; the saved checkpoint then passed all four validation suites."),
            "parent_id": t["parent_id"], "artifact_hash": m["artifact_hash"], "source": m["source"],
            "requested_steps": t["budget_steps"], "consumed_steps": t["consumed_steps"],
            "recipe": t["recipe"], "seed": t["seed"], "decision_id": decision["id"],
            "trial_id": t["id"], "explanation": decision["explanation"], "verdict": gate["verdict"],
            "promotion_id": gate["id"], "checks": gate["checks"],
            "bundle_url": f"api/download/{out.name}", "bundle_sha256": bundle["sha256"],
            "bundle_files_verified": len(checksums)})
    final = next(e for e in selected_records["evaluation"] if e["suite_role"] == "final_test")
    first_decision = records.read("decision", new_trials[0]["decision_id"])
    index = {"headline": "Passed all four validation suites. Held-out target collisions were 13%, above the 10% limit.",
        "origin": {"policy_id": first_decision["selected"], "passed": first_decision["ranking"][0]["passed"]},
        "selection_stopped": True, "attempts": attempts,
        "final_evaluation": {"record_id": final["id"], "metrics": final["summary"],
            "summary": "One held-out target evaluation after selection stopped: 86 goals, 13 collisions and 1 timeout in 100 episodes. Target collision limit failed. No further tuning was performed. Retained tasks were not evaluated on held-out seeds."}}
    for output in (ROOT / "web/media/search-evidence.json", ROOT / "evidence/search-v1/summary.json"):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(index, indent=2) + "\n")
    evidence = ROOT / "evidence/search-v1"
    files = [*evidence.glob("*.json"), *(destination / "records").glob("*/*.json")]
    # Checksums cover new evidence and the precise gate/suite source, without copying historical results.
    paths = [p for p in files if p.name != "checksums.json" and (p.parent == evidence or any(p.stem == r["id"] for rs in selected_records.values() for r in rs))]
    paths += [ROOT / "ew/criteria.py", ROOT / "ew/scenarios.py", ROOT / "scripts/final_confirmation.py"]
    (evidence / "checksums.json").write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2)+"\n")
    print(json.dumps({"attempts":len(attempts), "validation_gate":attempts[-1]["verdict"], "held_out":final["summary"]},indent=2))


if __name__ == "__main__":
    main()
