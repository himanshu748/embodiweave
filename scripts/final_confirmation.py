"""One-shot held-out confirmation, callable only after an existing validation pass.

Existing final suites were spent by exp-1/2/3. This separate, preregistered
100-episode target confirmation neither edits those suites nor joins the planner.
The marker is created before inference, so interruption does not allow a retry.
"""
import hashlib
import json
import os
from pathlib import Path

from ew import artifacts, records, rl, service
from ew.contract import CONTRACT_V1
from ew.provenance import source_snapshot
from ew.scenarios import FAMILIES, SUITES

POLICY = "search-20261015185749-4a6581"
EXPECTED = "b7e2fcc958695920db1970a4abdb40c65788a76f35e756bf6332729a8e3ba565"
SUITE_ID = "confirmation-target-search-v1"
SEEDS = tuple(range(4_100_000, 4_100_100))


def main():
    gate = service.promotion_preview(POLICY)
    if gate["verdict"] != "promoted":
        raise PermissionError("Requires a complete promo-1 validation pass before final access")
    artifacts.verify_policy(POLICY, EXPECTED)
    assert not set(SEEDS).intersection(s for suite in SUITES.values() for s in suite.seeds)
    protocol = {"suite_id": SUITE_ID, "role": "final_test", "family_id": FAMILIES["static_crossing"].fid(),
                "seeds": list(SEEDS), "episodes": len(SEEDS), "policy_id": POLICY, "artifact_hash": EXPECTED,
                "validation_gate": gate, "source": source_snapshot(),
                "authorization": "User allowed one final evaluation after a validation pass on 2026-10-15",
                "selection_stopped": True}
    marker = artifacts.ROOT / "final-confirmation-started.json"
    fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    with os.fdopen(fd, "w") as f:
        json.dump(protocol, f, indent=2)
    result = rl.evaluate_policy(POLICY, FAMILIES["static_crossing"], SEEDS, record=True, expected_hash=EXPECTED)
    rec = records.write("evaluation", {"policy_id": POLICY, "artifact_hash": EXPECTED,
        "suite_id": SUITE_ID, "suite_role": "final_test", "suite_version": "search-v1-confirmation-1",
        "family_id": FAMILIES["static_crossing"].fid(), "contract_id": CONTRACT_V1.contract_id,
        "seeds": list(SEEDS), "summary": result["summary"], "wall_s": result["wall_s"],
        "episodes": [{k:v for k,v in e.items() if k not in ("trace","layout")} for e in result["episodes"]],
        "purpose": "One final target confirmation after model selection stopped; never ingested into FalkorDB",
        "protocol_sha256": hashlib.sha256(marker.read_bytes()).hexdigest()})
    replay = service.REPLAYS / f"{rec['id']}.json"
    replay.parent.mkdir(parents=True, exist_ok=True)
    replay.write_text(json.dumps(result, indent=1))
    print(json.dumps({"evaluation":rec, "protocol":str(marker), "replay":str(replay)},indent=2))


if __name__ == "__main__":
    main()
