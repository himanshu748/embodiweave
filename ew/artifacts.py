"""Artifact store: immutable checkpoint directories identified by content hash.

Layout: artifacts/policies/<policy_id>/{model.zip, vecnormalize.pkl, manifest.json}
A policy directory is written once (to a temp dir, then renamed) and made read-only.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from pathlib import Path

ROOT = Path(os.environ.get("EW_ARTIFACTS", Path(__file__).resolve().parent.parent / "artifacts"))
POLICIES = ROOT / "policies"
RUNS = ROOT / "runs"
EVALS = ROOT / "evals"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_hash(policy_dir: Path) -> str:
    """Hash over model weights and normalization stats (the parts that define behaviour)."""
    h = hashlib.sha256()
    for name in ("model.zip", "vecnormalize.pkl"):
        h.update(name.encode())
        h.update(sha256_file(policy_dir / name).encode())
    return h.hexdigest()


def policy_dir(policy_id: str) -> Path:
    return POLICIES / policy_id


def write_policy(policy_id: str, tmp_dir: Path, manifest: dict) -> dict:
    dest = policy_dir(policy_id)
    if dest.exists():
        raise FileExistsError(f"policy {policy_id} already exists; checkpoints are immutable")
    manifest = dict(manifest)
    manifest["policy_id"] = policy_id
    manifest["artifact_hash"] = artifact_hash(tmp_dir)
    manifest["files"] = {n: sha256_file(tmp_dir / n) for n in ("model.zip", "vecnormalize.pkl")}
    (tmp_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp_dir), str(dest))
    for f in dest.iterdir():
        f.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return manifest


def load_manifest(policy_id: str) -> dict:
    return json.loads((policy_dir(policy_id) / "manifest.json").read_text())


def verify_policy(policy_id: str, expected_hash: str | None = None) -> str:
    """Recompute the artifact hash; raise if files are missing or the hash does not match."""
    d = policy_dir(policy_id)
    for n in ("model.zip", "vecnormalize.pkl", "manifest.json"):
        if not (d / n).exists():
            raise FileNotFoundError(f"{policy_id}: missing {n}")
    h = artifact_hash(d)
    m = load_manifest(policy_id)
    if h != m["artifact_hash"]:
        raise ValueError(f"{policy_id}: artifact hash mismatch vs manifest")
    if expected_hash and h != expected_hash:
        raise ValueError(f"{policy_id}: artifact hash {h[:12]} != expected {expected_hash[:12]}")
    return h
