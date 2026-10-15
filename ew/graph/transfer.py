"""Verify and ingest immutable sim-to-sim evidence, never promotion evidence.

This module has no MuJoCo dependency: production serves recorded transfer results.
No Threshold, Trial, Decision or Promotion is created from transfer outcomes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import db
from ..scenarios import FAMILIES

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "evidence/mujoco-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest(root: Path = DEFAULT_ROOT, graph=None, *, strict=True):
    root = Path(root)
    if not (root / "summary.json").exists():
        return 0
    checksums = json.loads((root / "checksums.json").read_text())
    actual_files = {str(f.relative_to(root)) for f in root.rglob("*") if f.is_file() and f.name != "checksums.json"}
    if set(checksums) != actual_files:
        raise ValueError("Unsigned or missing transfer evidence file")
    for name, expected in checksums.items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()) or sha(target) != expected:
            raise ValueError("Transfer evidence checksum mismatch")
    p = json.loads((root / "protocol.json").read_text())
    ph = hashlib.sha256(json.dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if p["role"] != "sim2sim" or p["physics"] != "mujoco":
        raise ValueError("Transfer role must remain sim2sim")
    count = 0
    for path in sorted(root.glob("*.json")):
        e = json.loads(path.read_text())
        if not isinstance(e, dict) or "episodes" not in e or "summary" not in e:
            continue
        s = next(s for s in p["suites"] if s["id"] == e["suite_id"])
        if e["protocol_hash"] != ph or [ep["seed"] for ep in e["episodes"]] != s["seeds"]:
            raise ValueError("Incomplete or mismatched transfer suite")
        if e["summary"]["episodes"] != len(s["seeds"]):
            raise ValueError("Transfer episode count mismatch")
        for outcome in ("success", "collision", "timeout"):
            actual = sum(ep["outcome"] == outcome for ep in e["episodes"])
            if e["summary"][outcome] != actual or e["summary"][outcome+"_rate"] != actual/len(s["seeds"]):
                raise ValueError("Transfer summary does not reconcile")
        _, rows, _ = db.ro("MATCH (p:Policy {id:$p}) RETURN p.artifact_hash", {"p": e["policy_id"]}, graph)
        if not rows or rows[0][0] != e["artifact_hash"]:
            if strict: raise ValueError("Transfer policy is absent or its artifact differs")
            continue  # isolated test graph may intentionally contain only test artifacts
        db.rw("MERGE (s:Suite {id:$id}) SET s.role='sim2sim', s.physics='mujoco', s.version='1', "
              "s.episodes=$n, s.seeds=$seeds, s.fingerprint=$fp, s.protocol_hash=$ph "
              "WITH s MATCH (f:Family {id:$fid}) MERGE (s)-[:DRAWS_FROM]->(f)",
              {"id": s["id"], "n": len(s["seeds"]), "seeds": s["seeds"], "fp": e["suite_fingerprint"],
               "ph": ph, "fid": FAMILIES[s["family"]].fid()}, graph)
        summary = e["summary"]
        db.rw("MERGE (e:Evaluation {id:$id}) SET e.artifact_hash=$hash, e.success_rate=$sr, "
              "e.collision_rate=$cr, e.timeout_rate=$tr, e.episodes=$n, e.measured=true, "
              "e.complete_suite=true, e.suite_fingerprint=$fp, e.physics='mujoco', e.protocol_hash=$ph, "
              "e.contract_id=$contract, e.evidence=$path "
              "WITH e MATCH (p:Policy {id:$policy}), (s:Suite {id:$suite}) "
              "MERGE (e)-[:ASSESSED]->(p) MERGE (e)-[:ON_SUITE]->(s)",
              {"id": e["id"], "hash": e["artifact_hash"], "sr": summary["success_rate"],
               "cr": summary["collision_rate"], "tr": summary["timeout_rate"], "n": summary["episodes"],
               "fp": e["suite_fingerprint"], "ph": ph, "contract": e["contract_id"],
               "path": "evidence/mujoco-v1/"+path.name, "policy": e["policy_id"], "suite": s["id"]}, graph)
        for hit in ("wall", "static", "mover"):
            seeds = [ep["seed"] for ep in e["episodes"] if ep["outcome"] == "collision" and ep["hit"] == hit]
            if seeds:
                db.rw("MERGE (f:Failure {id:$id}) SET f.outcome='collision', f.hit=$hit, f.count=$n, "
                      "f.seeds=$seeds, f.measured=true, f.physics='mujoco' "
                      "WITH f MATCH (e:Evaluation {id:$eval}) MERGE (f)-[:OBSERVED_IN]->(e)",
                      {"id": e["id"]+":collision:"+hit, "hit": hit, "n": len(seeds), "seeds": seeds, "eval": e["id"]}, graph)
        count += 1
    if count: db.bump_revision(f"MuJoCo transfer: {count} recorded evaluations", graph)
    return count


if __name__ == "__main__":
    print(f"Ingested {ingest()} transfer evaluations")
