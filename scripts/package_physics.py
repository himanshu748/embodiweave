"""Publish the separate physics study, including rejected children and raw traces."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from ew import artifacts, records, service
from ew.physics_study import OUT, ROOT, RULE, protocol, study_hash, reads, ranking
from ew.search import CRITERIA
from scripts.package_search import copy_once


def publish():
    destination = ROOT / "artifacts"
    trials = [t for t in records.all_of("trial") if t.get("search_rule") in (RULE,"physics-followup-v1")]
    pids = {t["child_policy_id"] for t in trials}
    dids = {t["decision_id"] for t in trials}
    selection_reads=reads()
    ranked={r["policy_id"]:r for r in ranking(selection_reads)}
    paths, attempts = [], []
    for kind in ("trial", "run", "evaluation", "decision", "promotion"):
        for rec in records.all_of(kind):
            # Parent diagnostics are new evidence too. Confirmation is never a graph record.
            physical = kind == "evaluation" and rec.get("suite_version") == RULE
            if not physical and rec.get("child_policy_id", rec.get("policy_id")) not in pids and not (kind == "decision" and rec["id"] in dids):
                continue
            target = destination / "records" / kind / f"{rec['id']}.json"
            copy_once(records.RECORDS / kind / target.name, target); paths.append(target)
            replay = service.REPLAYS / target.name
            if kind == "evaluation" and replay.exists():
                out = destination / "replays" / target.name
                copy_once(replay, out); paths.append(out)
    criteria = dict(zip(("static_crossing", "open", "static", "crossing"), CRITERIA))
    def measured(folder):
        result = json.loads((folder / "summary.json").read_text())["results"]
        for r in result:
            c = criteria[r["family"]]
            r["min_success"], r["max_collision"] = c["min_success"], c["max_collision"]
            r["pass"] = r["summary"]["success_rate"] >= c["min_success"] and r["summary"]["collision_rate"] <= c["max_collision"]
        return result
    for trial in trials:
        pid = trial["child_policy_id"]
        manifest = artifacts.load_manifest(pid)
        archive = artifacts.ROOT / "source_archives" / (manifest["source"]["source_hash"] + ".zip")
        with zipfile.ZipFile(archive) as z:
            assert set(z.namelist()) == set(manifest["source"]["files"])
            assert all(hashlib.sha256(z.read(n)).hexdigest() == h for n,h in manifest["source"]["files"].items())
        target = destination / "source_archives" / archive.name
        copy_once(archive, target); paths.append(target)
        for f in artifacts.policy_dir(pid).iterdir():
            target = destination / "policies" / pid / f.name
            copy_once(f, target); paths.append(target)
        base = service.export_bundle(pid)
        bundle = destination / "exports" / f"{pid}-{manifest['artifact_hash'][:12]}-physics-repro-v1.zip"
        if not bundle.exists():
            with zipfile.ZipFile(base["path"]) as src, zipfile.ZipFile(bundle,"w",zipfile.ZIP_DEFLATED) as z:
                for n in src.namelist():
                    if n != "checksums.json": z.writestr(n,src.read(n))
                z.write(OUT / "protocol.json", "study-protocol.json")
                folder = OUT / "development" / pid
                for f in sorted(folder.rglob("*")):
                    if f.is_file(): z.write(f, "physics-development/" + str(f.relative_to(folder)))
                z.writestr("REPRODUCE-PHYSICS.md", "# Reproduce physics development\n\nInstall requirements.lock then requirements-mujoco.txt. Extract this bundle and run:\n\n```sh\nPYTHONPATH=source .venv/bin/python reproduce_physics.py\n```\n\nThis replays the published development seeds only. No confirmation rerun is included. Training used both 2D and MuJoCo, with training source captured separately in training-source.zip. No real-world safety claim.\n")
                z.writestr("reproduce_physics.py", "import os,json,shutil\nfrom pathlib import Path\np=json.load(open('physics-development/protocol.json'))\npid=p['policies']['candidate']['id']\nos.environ['EW_ARTIFACTS']=str(Path('reproduction-artifacts').resolve())\nd=Path(os.environ['EW_ARTIFACTS'])/'policies'/pid\nd.mkdir(parents=True,exist_ok=True)\nfor n in ('model.zip','vecnormalize.pkl','manifest.json'):shutil.copyfile(Path('policy')/n,d/n)\nfrom sim.mujoco.evaluate import run\nrun(p,Path('reproduced-development'))\n")
                # Confirmation may be appended only to the selected release bundle below.
                z.writestr("checksums.json",json.dumps({n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()},indent=2))
        with zipfile.ZipFile(bundle) as z:
            assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in json.loads(z.read("checksums.json")).items())
        paths.append(bundle)
        gate = next(g for g in records.all_of("promotion") if g["policy_id"] == pid)
        attempts.append({"policy_id":pid,"study":trial["search_rule"],"artifact_hash":manifest["artifact_hash"],"parent_id":trial["parent_id"],
            "trial_id":trial["id"],"decision_id":trial["decision_id"],"recipe":trial["recipe"],
            "requested_steps":trial["budget_steps"],"actual_steps":trial["consumed_steps"],"seed":trial["seed"],
            "canonical_checks":gate["checks"],"canonical_verdict":gate["verdict"],
            "validation_suites_passed":ranked[pid]["passed"],"physics_clearance_deficit":ranked[pid]["clearance_deficit"],
            "selection_eligible":ranked[pid]["passed"]==8 and ranked[pid]["clearance_deficit"]==0,
            "physics_development":measured(OUT/"development"/pid),
            "bundle_url":"api/download/"+bundle.name,"bundle_sha256":artifacts.sha256_file(bundle)})
    selected = json.loads((OUT/"selected.json").read_text()) if (OUT/"selected.json").exists() else None
    confirmation = measured(OUT/"confirmation") if (OUT/"confirmation/summary.json").exists() else None
    if selected:
        for name in ("physics-adapt-v1-selected.json","physics-adapt-v1-confirmation-started.json"):
            if (artifacts.ROOT/name).exists():
                target=destination/name;copy_once(artifacts.ROOT/name,target);paths.append(target)
    confirmation_bundle = None
    if selected and confirmation:
        attempt=next(a for a in attempts if a["policy_id"]==selected["policy_id"])
        base=destination/"exports"/Path(attempt["bundle_url"]).name
        target=base.with_name(base.name.replace("physics-repro-v1","physics-confirmation-v1"))
        if not target.exists():
            with zipfile.ZipFile(base) as src, zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
                for n in src.namelist():
                    if n!="checksums.json":z.writestr(n,src.read(n))
                z.write(OUT/"selected.json","frozen-selection.json")
                z.write(artifacts.ROOT/"physics-adapt-v1-confirmation-started.json","confirmation-started.json")
                for f in sorted((OUT/"confirmation").rglob("*")):
                    if f.is_file():z.write(f,"physics-confirmation/"+str(f.relative_to(OUT/"confirmation")))
                z.writestr("checksums.json",json.dumps({n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()},indent=2))
        with zipfile.ZipFile(target) as z:
            assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in json.loads(z.read("checksums.json")).items())
        paths.append(target)
        confirmation_bundle={"url":"api/download/"+target.name,"sha256":artifacts.sha256_file(target)}
    summary={"study":RULE,"protocol_sha256":study_hash(),"training_domains":["2D","MuJoCo"],
        "validation_query_receipts":[q.to_log() for q in selection_reads],
        "attempts":attempts,"selected_policy":selected["policy_id"] if selected else None,
        "physics_confirmation":confirmation,"physics_confirmation_pass":all(r["pass"] for r in confirmation) if confirmation else None,
        "confirmation_bundle":confirmation_bundle,
        "notice":"Separate mixed-domain adaptation. Earlier unchanged transfer and 2D confirmation stay frozen. Physics confirmation never enters planning; no new 2D held-out evaluation was authorized."}
    for target in (OUT/"summary.json",ROOT/"web/media/physics-evidence.json"):
        target.write_text(json.dumps(summary,indent=2)+"\n");paths.append(target)
    paths += [f for f in OUT.rglob("*") if f.is_file() and f != OUT/"checksums.json"]
    paths += [f for f in (ROOT/"evidence/physics-followup-v1").glob("*.json")]
    (OUT/"checksums.json").write_text(json.dumps({str(p.relative_to(ROOT)):artifacts.sha256_file(p) for p in sorted(set(paths))},indent=2)+"\n")
    print(json.dumps({"attempts":len(attempts),"selected":summary["selected_policy"],"physics_confirmation_pass":summary["physics_confirmation_pass"]}))


if __name__ == "__main__":publish()
