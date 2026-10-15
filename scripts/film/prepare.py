"""Build the film's factual inputs from recorded evidence and real FalkorDB reads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ew.graph import db, queries as Q

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence/film"


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")


def main():
    transfer = json.loads((ROOT / "evidence/mujoco-v1/summary.json").read_text())
    target = {r["label"]: r["summary"] for r in transfer["results"] if r["family"] == "static_crossing"}
    n = target["deployed"]["episodes"]
    physics = (f"On forty fresh target episodes, the deployed policy collided {target['deployed']['collision']} times. "
               f"The rehearsal checkpoint collided {target['rehearsal']['collision']} times. Crossing still had eight collisions. No retraining.")
    scenes = [
        ("A test is not a guarantee", "This robot passed its open-arena test. Watch what happens when a pedestrian crosses.", "physics-hook"),
        ("Which checkpoint? Safe to ship?", "I built EmbodiWeave to answer two questions: which robot checkpoint should I retrain, and is the result safe to ship?", "problem"),
        ("The history is a graph", "Falkor-D-B connects policies, training runs, trials, evaluations, failures and decisions. The links preserve what produced what.", "graph"),
        ("Diagnose the exact artifact", "First, the agent queries failed validation suites, matching the exact artifact hash. A look-alike checkpoint cannot substitute for measured evidence.", "diagnose"),
        ("Same shape. Different meaning.", "Matching tensor shapes are not enough. Falkor-D-B links sensor and action contracts, so incompatible starting points are excluded.", "contracts"),
        ("The decision is evidence too", "The planner ranks eligible origins by failed suites and deficits. Before training, its decision records the Cypher, parameters and returned evidence in Falkor-D-B.", "decision"),
        ("No graph. No plan.", "If Falkor-D-B is unavailable, planning stops. There is no silent fallback.", "closed"),
        ("Two measured training attempts", "Longer training came first. A retained-task failure then led to rehearsal across training families. Each attempt added about three hundred thousand P-P-O steps.", "learning"),
        ("Same gate. Every candidate.", "The original passed one of four suites. Longer training passed three. Rehearsal passed all four. The collision limits stayed at ten, five, ten and fifteen percent.", "gate"),
        ("I report it anyway.", "One held-out target test recorded thirteen collisions across one hundred episodes. The limit was ten percent. I report it anyway. Production stays unchanged.", "heldout"),
        ("New physics. Unchanged checkpoints.", "Finally, I transferred the same two-dimensional-trained checkpoints into MuJoCo physics. " + physics, "transfer"),
        ("Robot training decisions you can audit.", "The graph and checksummed evidence make these results inspectable. EmbodiWeave. Built on Falkor-D-B.", "close"),
    ]
    write("scenes.json", [{"id": i+1, "title": title, "narration": narration, "visual": visual}
                         for i, (title, narration, visual) in enumerate(scenes)])
    # Freeze the edited film's source evidence, not new training or a new decision.
    query_logs = {
        "lineage": Q.run("search_lineage", {"rule": "search-v1"}).to_log(),
        "transfer": Q.run("mujoco_transfer", {}).to_log(),
    }
    diagnosis = """MATCH (p:Policy {id:$policy})<-[:ASSESSED]-(e:Evaluation)-[:ON_SUITE]->(s:Suite)
WHERE s.role = 'validation' AND e.complete_suite = true
  AND e.artifact_hash = p.artifact_hash AND e.suite_fingerprint = s.fingerprint
RETURN s.id AS suite, e.id AS evaluation, e.success_rate AS success, e.collision_rate AS collisions
ORDER BY suite"""
    header, rows, ms = db.ro(diagnosis, {"policy": "search-20261015185536-6720c9"})
    query_logs["diagnosis"] = {"cypher": diagnosis, "params": {"policy": "search-20261015185536-6720c9"},
                                "header": [h[1] for h in header], "rows": rows, "ms": ms}
    query_logs["contracts"] = Q.run("candidate_eligibility", {"contract": "ew-contract-1:2f013b6f4849", "robot": "ew-unicycle-r20"}).to_log()
    write("queries.json", query_logs)
    # Use real IDs/properties/edges. Layout and highlight motion are editorial.
    ids = ["P-static-b", "scratch~10715f-s7", "scratch~a7ee2c-s7", "search-20261015185536-6720c9",
           "search-20261015185749-4a6581", "ew-contract-1:2f013b6f4849",
           "deci-20261015185536-da13c7", "deci-20261015185749-420707",
           "run-20261015185536-140d3e", "run-20261015185749-177cb3",
           "tria-20261015185709-8932b2", "tria-20261015185835-ce926e",
           "prom-20261015185709-2941eb", "prom-20261015185835-ec1f6d"]
    _, evaluations, _ = db.ro("MATCH (e:Evaluation)-[:ASSESSED]->(p:Policy) MATCH (e)-[:ON_SUITE]->(s:Suite) "
                              "WHERE p.id IN $ids AND s.id='val-target-v1' RETURN e.id", {"ids": ids})
    ids.extend(r[0] for r in evaluations)
    _, failures, _ = db.ro("MATCH (f:Failure)-[:OBSERVED_IN]->(e:Evaluation) WHERE e.id IN $ids AND f.hit='mover' RETURN f.id", {"ids": ids})
    ids.extend(r[0] for r in failures)
    node_query = "MATCH (n) WHERE n.id IN $ids RETURN n.id, labels(n), properties(n) ORDER BY n.id"
    edge_query = "MATCH (a)-[r]->(b) WHERE a.id IN $ids AND b.id IN $ids RETURN a.id, type(r), b.id ORDER BY a.id,type(r),b.id"
    _, nodes, _ = db.ro(node_query, {"ids": ids})
    _, edges, _ = db.ro(edge_query, {"ids": ids})
    write("graph-records.json", {"graph": db.GRAPH, "revision": db.revision(), "node_cypher": node_query,
                                "edge_cypher": edge_query, "params": {"ids": ids}, "nodes": nodes, "edges": edges})
    progress = []
    for i, label in [(1, "longer"), (2, "rehearsal")]:
        source = ROOT.parent / f"search-trial-{i}.log"
        if not source.exists():
            frozen = json.loads((OUT / 'learning-progress.json').read_text())
            progress.append(next(r for r in frozen if r['attempt'] == label))
            continue
        data = [json.loads(line)["progress"] for line in source.read_text().splitlines() if line.startswith('{"progress":')]
        progress.append({"attempt": label, "source_log_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                         "samples": data, "meaning": "Recent training success over at most 200 episodes, not validation performance"})
    write("learning-progress.json", progress)
    deployed = json.loads((ROOT / "evidence/mujoco-v1/deployed-static_crossing.json").read_text())
    selected = json.loads((ROOT / "evidence/mujoco-v1/rehearsal-static_crossing.json").read_text())
    candidates = [(a, b) for a, b in zip(deployed["episodes"], selected["episodes"])
                  if a["outcome"] == "collision" and a["hit"] == "mover"]
    if not candidates:
        deployed = json.loads((ROOT / "evidence/mujoco-v1/deployed-crossing.json").read_text())
        selected = json.loads((ROOT / "evidence/mujoco-v1/rehearsal-crossing.json").read_text())
        candidates = [(a, b) for a, b in zip(deployed["episodes"], selected["episodes"])
                      if a["outcome"] == "collision" and a["hit"] == "mover"]
    if not candidates:
        raise RuntimeError("No deployed pedestrian collision was measured. Change the film's hook honestly; do not manufacture one.")
    pair = sorted(candidates, key=lambda pair: (pair[1]["outcome"] != "success", pair[0]["seconds"], pair[0]["seed"]))[0]
    write("filmed-pair.json", {"suite": deployed["suite_id"], "seed": pair[0]["seed"],
                              "deployed": pair[0], "rehearsal": pair[1],
                              "selection": "Earliest deployed pedestrian collision among paired rehearsal successes, for a readable short replay. Selected illustrative episode; full aggregates are reported."})
    print(json.dumps({"words": sum(len(s["narration"].split()) for s in json.loads((OUT/"scenes.json").read_text())), "filmed_seed": pair[0]["seed"]}))


if __name__ == "__main__":
    main()
