"""Freeze a validation-selected checkpoint; run one fresh four-suite confirmation.

The marker is exclusive and written before inference. Never ingests confirmation
outcomes into the decision graph. Existing final suites and results are untouched.
"""
import argparse
import hashlib
import json
import os

from ew import artifacts, records, rl, service
from ew.contract import CONTRACT_V1
from ew.graph import queries as Q
from ew.robustness import PROTOCOL_PATH, RULE, SUITES, protocol_hash, rank_candidates, with_clearance
from ew.scenarios import FAMILIES, SUITES as DEFINITIONS


def freeze():
    from ew.contract import CONTRACT_V1
    q = Q.run("search_validation", {"contract": CONTRACT_V1.contract_id, "suites": SUITES})
    best = with_clearance(rank_candidates(q.dicts()))[0]
    if best["passed"] != 4 or best["clearance_deficit"] != 0:
        raise PermissionError("Requires all four validation suites plus the registered collision clearance")
    trials = [t for t in records.all_of("trial") if t.get("search_rule") == RULE]
    if best["policy_id"] not in {t["child_policy_id"] for t in trials}:
        raise PermissionError("Selection must be a measured new candidate in this study")
    gate = service.promotion_preview(best["policy_id"])
    if gate["verdict"] != "promoted":
        raise PermissionError("Unchanged promo-1 gate did not pass")
    rec = {"policy_id": best["policy_id"], "artifact_hash": artifacts.verify_policy(best["policy_id"]),
           "protocol_sha256": protocol_hash(), "selection_stopped": True, "validation_gate": gate,
           "ranking": best, "selection_query": q.to_log()}
    path = artifacts.ROOT / "robustness-v2-selected.json"
    with path.open("x") as f:
        json.dump(rec, f, indent=2)
    return rec


def confirm():
    selected = json.loads((artifacts.ROOT / "robustness-v2-selected.json").read_text())
    if selected["protocol_sha256"] != protocol_hash() or not selected["selection_stopped"]:
        raise PermissionError("Frozen selection does not match the preregistration")
    pid, expected = selected["policy_id"], selected["artifact_hash"]
    artifacts.verify_policy(pid, expected)
    gate = service.promotion_preview(pid)
    if gate["verdict"] != "promoted":
        raise PermissionError("Validation pass no longer verifies")
    p = json.loads(PROTOCOL_PATH.read_text())
    marker = artifacts.ROOT / "robustness-v2-confirmation-started.json"
    # Across every family, none of these seeds can overlap a canonical suite.
    reserved = {s for suite in DEFINITIONS.values() for s in suite.seeds}
    seeds = [s for suite in p["confirmation"]["suites"] for s in suite["seeds"]]
    if len(set(seeds)) != len(seeds) or set(seeds) & reserved:
        raise ValueError("Confirmation seeds overlap another registered suite")
    # A crash is not permission to inspect partially completed outcomes and retry.
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, "w") as f:
        json.dump({"selected": selected, "protocol": p, "confirmation_batch": "one authorized batch"}, f, indent=2)
    results = []
    for suite in p["confirmation"]["suites"]:
        measured = rl.evaluate_policy(pid, FAMILIES[suite["family"]], suite["seeds"], record=True, expected_hash=expected)
        rec = records.write("evaluation", {"policy_id": pid, "artifact_hash": expected,
            "suite_id": suite["id"], "suite_role": "final_test", "suite_version": RULE,
            "family_id": FAMILIES[suite["family"]].fid(), "contract_id": CONTRACT_V1.contract_id,
            "seeds": suite["seeds"], "summary": measured["summary"], "wall_s": measured["wall_s"],
            "episodes": [{k:v for k,v in e.items() if k not in ("trace", "layout")} for e in measured["episodes"]],
            "purpose": "One new authorized post-selection confirmation batch; excluded from planning graph",
            "protocol_sha256": protocol_hash(), "marker_sha256": hashlib.sha256(marker.read_bytes()).hexdigest()})
        service.REPLAYS.mkdir(parents=True, exist_ok=True)
        with (service.REPLAYS / f"{rec['id']}.json").open("x") as f:
            json.dump(measured, f)
        results.append({"id": rec["id"], "family": suite["family"], "summary": rec["summary"]})
    path = artifacts.ROOT / "robustness-v2-confirmation.json"
    with path.open("x") as f:
        json.dump({"policy_id": pid, "artifact_hash": expected, "results": results}, f, indent=2)
    return json.loads(path.read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "confirm"])
    args = parser.parse_args()
    print(json.dumps(freeze() if args.action == "freeze" else confirm(), indent=2))
