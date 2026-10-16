"""Bind an export to its actual source, including an uncommitted working tree."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def source_snapshot():
    sources = [*sorted((ROOT / "ew").rglob("*.py")), *sorted((ROOT / "sim").rglob("*.py"))]
    files = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    commit = os.environ.get("EW_GIT_COMMIT") or os.environ.get("RENDER_GIT_COMMIT")
    dirty = None
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--", "ew", "sim", "requirements.lock"],
                                            cwd=ROOT, stderr=subprocess.DEVNULL, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return {"commit": commit, "dirty": dirty, "files": files,
            "source_hash": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
