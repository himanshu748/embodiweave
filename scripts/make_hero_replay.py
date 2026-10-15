"""Extract one real recorded episode pair for the landing-page hero: the deployed policy and the agent's
new checkpoint on the same val-target-v1 seed. Output is a trimmed copy of the stored replays, not a re-render."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEFORE, AFTER, EPISODE = "eval-20261015040917-9c0df8", "eval-20261015060452-d0c201", 32


def pick(eid: str) -> dict:
    rep = json.loads((ROOT / "artifacts" / "replays" / f"{eid}.json").read_text())
    ep = rep["episodes"][EPISODE]
    return {"evaluation_id": eid, "policy_id": rep["policy_id"], "suite_id": rep["suite_id"], "seed": ep["seed"],
            "layout": ep["layout"], "outcome": ep["trace"][-1]["outcome"],
            "robot": [[round(v, 3) for v in s["robot"]] for s in ep["trace"]],
            "movers": [[[round(v, 3) for v in m[:2]] for m in s["movers"]] for s in ep["trace"]]}


before, after = pick(BEFORE), pick(AFTER)
assert before["seed"] == after["seed"]
out = ROOT / "web" / "hero-replay.json"
out.write_text(json.dumps({"source": "artifacts/replays (recorded simulator states)", "before": before, "after": after}))
print(out, out.stat().st_size, before["outcome"], after["outcome"], file=sys.stderr)
