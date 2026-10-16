"""Trusted operator: one preregistered validation-only robustness attempt."""
import json
from ew.robustness import run_next

if __name__ == "__main__":
    print(json.dumps(run_next(on_progress=lambda p: print(json.dumps({"progress": p}), flush=True)), indent=2), flush=True)
