"""Append-only evidence records persisted outside the graph.

Every measured fact (run, evaluation, transfer trial, decision, promotion) is written once as
JSON under artifacts/records/<kind>/<id>.json using O_EXCL, so a record can never be silently
overwritten. FalkorDB is rebuilt from these files by ew.graph.ingest; the graph is the operational
decision store, these files are the durable source of truth for recovery.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from .artifacts import ROOT

RECORDS = ROOT / "records"
KINDS = ("run", "evaluation", "trial", "decision", "promotion", "job", "agent_trace")


def new_id(prefix: str) -> str:
    return f"{prefix}-{time.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"


def write(kind: str, rec: dict) -> dict:
    assert kind in KINDS, kind
    rec = dict(rec)
    rec.setdefault("id", new_id(kind[:4]))
    rec.setdefault("recorded_at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    rec["kind"] = kind
    d = RECORDS / kind
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{rec['id']}.json"
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, "w") as f:
        json.dump(rec, f, indent=1, sort_keys=True, default=str)
    return rec


def read(kind: str, rid: str) -> dict:
    return json.loads((RECORDS / kind / f"{rid}.json").read_text())


def all_of(kind: str) -> list[dict]:
    d = RECORDS / kind
    if not d.exists():
        return []
    out = [json.loads(p.read_text()) for p in d.glob("*.json")]
    return sorted(out, key=lambda r: (r.get("recorded_at", ""), r["id"]))


def exists(kind: str, rid: str) -> bool:
    return (RECORDS / kind / f"{rid}.json").exists()
