"""Trusted operator command, never a public arbitrary-budget endpoint."""
import json
from ew.search import run_next

if __name__ == "__main__":
    result = run_next(on_progress=lambda p: print(json.dumps({"progress": p}), flush=True))
    print(json.dumps(result, indent=2), flush=True)
