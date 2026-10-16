"""One preregistered paired test of family rehearsal, with fresh development seeds."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import zipfile

from . import artifacts, records, service
from .contract import CONTRACT_V1
from .graph import db, ingest, queries as Q
from .recipes import RECIPES
from .scenarios import FAMILIES, SUITES, Suite
from .search import CRITERIA, SUITES as CANONICAL, rank_candidates

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/rehearsal-recovery-v1"


def protocol():
    return json.loads((OUT / "protocol.json").read_text())


def development_suites(p):
    competency = {"open": "reach_goal", "static": "avoid_static", "crossing": "yield_dynamic",
                  "static_crossing": "static_crossing_mission"}
    return [Suite(s["id"], "1", "validation", FAMILIES[s["family"]],
                  tuple(range(s["seed_base"], s["seed_base"] + s["episodes"])), competency[s["family"]])
            for s in p["development"]]


def comparison(parent, control, child):
    """Stricter development stopping rule; does not run or redefine promo-1."""
    limits = {SUITES[c["suite_id"]].family.name: c for c in CRITERIA}
    for measurements in (parent, control, child):
        if set(measurements) != set(limits):
            raise ValueError("All four complete development families are required")
        for family, row in measurements.items():
            if row["episodes"] != parent[family]["episodes"] or row["episodes"] <= 0:
                raise ValueError("Paired episode counts must match")
            if any(row[o] < 0 for o in ("success", "collision", "timeout")) or sum(
                    row[o] for o in ("success", "collision", "timeout")) != row["episodes"]:
                raise ValueError("Every episode must have exactly one outcome")
    checks = []
    for family, row in child.items():
        c = limits[family]
        n = row["episodes"]
        checks.append({"family": family,
                       "reference_requirements_met": row["success"] / n >= c["min_success"]
                       and row["collision"] / n <= c["max_collision"],
                       "no_regression": all(row["collision"] <= other[family]["collision"]
                                            and row["success"] >= other[family]["success"]
                                            for other in (parent, control))})
    strict = all(sum(v["collision"] for v in child.values()) < sum(v["collision"] for v in other.values())
                 for other in (parent, control))
    accepted = all(c["reference_requirements_met"] and c["no_regression"] for c in checks) and strict
    return {"accepted_for_further_study": accepted, "checks": checks,
            "fewer_total_collisions_than_parent_and_control": strict,
            "promo_1": "not evaluated", "confirmation": "not opened", "deployment_changed": False}


def save(name, value):
    path = OUT / name
    with path.open("x") as f:
        json.dump(value, f, indent=2, default=str)
        f.write("\n")


def measure(pid, suites, graph):
    from . import rl
    study = protocol()["study"]
    rows = {}
    for suite in suites:
        result = rl.evaluate_policy(pid, suite.family, suite.seeds, record=True,
                                    expected_hash=artifacts.verify_policy(pid))
        rec = records.write("evaluation", {"policy_id": pid, "artifact_hash": result["artifact_hash"],
            "contract_id": result["contract_id"], "suite_id": suite.suite_id, "suite_role": suite.role,
            "suite_version": suite.version, "family_id": suite.family.fid(), "custom_family": False,
            "seeds": list(suite.seeds), "summary": result["summary"], "wall_s": result["wall_s"],
            "episodes": [{k: v for k, v in ep.items() if k not in ("trace", "layout")}
                         for ep in result["episodes"]], "purpose": study + " development only"})
        ingest.evaluation(rec, graph)
        db.bump_revision("development evaluation " + rec["id"], graph)
        episodes = rec["episodes"]
        rows[suite.family.name] = {"evaluation_id": rec["id"], "episodes": len(episodes),
                                  **{o: sum(e["outcome"] == o for e in episodes)
                                     for o in ("success", "collision", "timeout")}, "summary": rec["summary"]}
        save(f"{pid}-{suite.family.name}.json", rec)
        with gzip.open(OUT / (rec["id"] + "-replay.json.gz"), "wt") as f:
            json.dump({"evaluation_id": rec["id"], "artifact_hash": result["artifact_hash"],
                       "seeds": list(suite.seeds), "episodes": result["episodes"]}, f)
        print(json.dumps({"measured": pid, "family": suite.family.name, **rows[suite.family.name]}), flush=True)
    return rows


def run(catalog):
    p = protocol()
    digest = artifacts.sha256_file(OUT / "protocol.json")
    if artifacts.ROOT.resolve() in (catalog.resolve(), (ROOT / "artifacts").resolve(), Path("/data")):
        raise PermissionError("Use a new isolated EW_ARTIFACTS directory")
    if (p["training_seed"], p["requested_steps_per_arm"]) != (31, 60000) or (
            p["max_training_runs"] != len(p["arms"]) or len(p["arms"]) not in (1, 2)):
        raise ValueError("Registered training budget changed")
    # Spend the study before graph writes, model execution or any measurements.
    save("started.json", {"protocol_sha256": digest})
    if p["study_graph"] in db._conn().connection.execute_command("GRAPH.LIST"):
        raise FileExistsError("Study graph already exists; no retry is authorized")
    artifacts.POLICIES.mkdir(parents=True, exist_ok=True)
    for source in (catalog / "policies").iterdir():
        if source.is_dir():
            (artifacts.POLICIES / source.name).symlink_to(source.resolve(), target_is_directory=True)
    q = Q.run("search_validation", {"contract": CONTRACT_V1.contract_id, "suites": CANONICAL}, p["source_graph"])
    ranking = rank_candidates(q.dicts())
    if not ranking:
        raise ValueError("No verifiable complete-validation origin")
    parent = ranking[0]["policy_id"]
    parent_hash = artifacts.verify_policy(parent)
    if p.get("control_id"):
        control = artifacts.load_manifest(p["control_id"])
        if (control["parent_id"], control["seed"], control["budget_steps"], control["recipe"]) != (
                parent, 31, 60000, "ppo-rehearsal-v1"):
            raise ValueError("The saved paired control does not match the preregistered design")
    save("parent-selection.json", {"queries": [q.to_log()], "ranking": ranking,
                                   "selected": parent, "artifact_hash": parent_hash, "protocol_sha256": digest})
    graph = p["study_graph"]
    db.copy_graph(p["source_graph"], graph)
    suites = development_suites(p)
    for suite in suites:
        if suite.suite_id in SUITES:
            raise ValueError("Development suite already registered")
        SUITES[suite.suite_id] = suite
    ingest.init_world(graph)
    measurements = {"parent": measure(parent, suites, graph)}
    if p.get("control_id"):
        measurements["control"] = measure(p["control_id"], suites, graph)
    outcomes = []
    for arm in p["arms"]:
        pid = p.get("policy_prefix", "recovery-v1") + "-" + arm["id"]
        decision = records.write("decision", {"rule_version": p["study"], "mode": "deterministic_controlled_study",
            "graph_revision": db.revision(graph), "action": "train_from_parent", "selected": parent,
            "request": service.target_request(p["requested_steps_per_arm"], arm["recipe"]),
            "ranking": ranking, "rejected": [], "queries": [q.to_log()], "protocol_sha256": digest,
            "explanation": "Graph-ranked origin; paired, preregistered development intervention. No LLM decision claimed."})
        ingest.decision(decision, graph)
        save(arm["id"] + "-decision.json", decision)
        result = service.train_run(pid, family="static_crossing", budget_steps=p["requested_steps_per_arm"],
            seed=p["training_seed"], parent_id=parent, recipe=arm["recipe"], run_kind=p["study"],
            decision_id=decision["id"], purpose="Paired rehearsal development trial, no confirmation or release", graph=graph,
            on_progress=lambda value: print(json.dumps({"arm": arm["id"], "progress": value}), flush=True))
        artifacts.verify_policy(parent, parent_hash)
        ingest.decision_launched(decision["id"], result["run"]["id"], graph)
        save(arm["id"] + "-run.json", result)
        measurements[arm["id"]] = measure(pid, suites, graph)
        trial = records.write("trial", {"parent_id": parent, "parent_artifact_hash": parent_hash,
            "child_policy_id": pid, "child_artifact_hash": result["manifest"]["artifact_hash"],
            "run_id": result["run"]["id"], "decision_id": decision["id"], "target_family": "static_crossing",
            "target_family_id": FAMILIES["static_crossing"].fid(), "suite_id": suites[0].suite_id,
            "contract_id": CONTRACT_V1.contract_id, "recipe": arm["recipe"], "threshold_id": "thr-target-1",
            "threshold_reached": None, "steps_to_threshold": None, "schedule": [], "status": "completed",
            "budget_steps": p["requested_steps_per_arm"], "consumed_steps": result["run"]["consumed_steps"],
            "seed": p["training_seed"], "search_rule": p["study"], "intervention": arm["id"],
            "development_only": True, "threshold_note": "Canonical threshold was not evaluated."})
        ingest.trial(trial, graph)
        save(arm["id"] + "-trial.json", trial)
        outcomes.append({"arm": arm["id"], "policy_id": pid, "artifact_hash": result["manifest"]["artifact_hash"],
                         "consumed_steps": result["run"]["consumed_steps"], "trial_id": trial["id"]})
    verdict = comparison(measurements["parent"], measurements["control" if p.get("control_id") else "target_only"],
                         measurements[p.get("intervention_arm", "rehearsal")])
    save("summary.json", {"study": p["study"], "protocol_sha256": digest, "origin": parent,
                         "arms": outcomes, "measurements": measurements, "verdict": verdict})
    for arm in outcomes:
        with zipfile.ZipFile(OUT / (arm["policy_id"] + "-evidence.zip"), "x", zipfile.ZIP_DEFLATED) as z:
            for f in artifacts.policy_dir(arm["policy_id"]).iterdir():
                z.write(f, "policy/" + f.name)
            for f in sorted(OUT.glob("*.json")):
                z.write(f, "evidence/" + f.name)
            for f in sorted(OUT.glob(arm["policy_id"] + "-*.json")):
                rec = json.loads(f.read_text())
                if rec.get("kind") == "evaluation":
                    replay = OUT / (rec["id"] + "-replay.json.gz")
                    z.write(replay, "evidence/" + replay.name)
            for folder in (ROOT / "ew", ROOT / "sim"):
                for f in sorted(folder.rglob("*.py")):
                    z.write(f, "source/" + str(f.relative_to(ROOT)))
            z.write(ROOT / "requirements.lock", "source/requirements.lock")
    save("checksums.json", {str(f.relative_to(ROOT)): artifacts.sha256_file(f)
                           for f in sorted(OUT.iterdir()) if f.is_file()})
    print(json.dumps(verdict), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--study", choices=["rehearsal-recovery-v1", "collision-recovery-v1"],
                        default="rehearsal-recovery-v1")
    args = parser.parse_args()
    OUT = ROOT / "evidence" / args.study
    run(args.catalog)
