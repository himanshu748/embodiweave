"""Bind an export to its actual source, including an uncommitted working tree."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def source_snapshot():
    files = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted((ROOT / "ew").rglob("*.py"))}
    commit = os.environ.get("RENDER_GIT_COMMIT")
    dirty = None
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--", "ew", "requirements.lock"],
                                            cwd=ROOT, stderr=subprocess.DEVNULL, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return {"commit": commit, "dirty": dirty, "files": files,
            "source_hash": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
