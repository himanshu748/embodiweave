"""Evidence completeness independent of the graph's cached summaries."""
import hashlib
import json

from .scenarios import SUITES


def suite_fingerprint(suite):
    return hashlib.sha256(json.dumps(suite.to_record(), sort_keys=True).encode()).hexdigest()


def complete_evaluation(e, contract_id=None):
    """A smoke test is a measurement, but never a complete suite pass."""
    suite = SUITES.get(e.get("suite_id"))
    if suite is None or e.get("custom_family"):
        return False
    if (e.get("suite_version") != suite.version or e.get("suite_role") != suite.role
            or e.get("family_id") != suite.family.fid() or e.get("seeds") != list(suite.seeds)):
        return False
    if contract_id is not None and e.get("contract_id") != contract_id:
        return False
    episodes = e.get("episodes", [])
    summary = e.get("summary", {})
    n = len(suite.seeds)
    if not n or len(episodes) != n or summary.get("episodes") != n:
        return False
    for outcome, metric in (("success", "success_rate"), ("collision", "collision_rate"), ("timeout", "timeout_rate")):
        expected = round(sum(ep.get("outcome") == outcome for ep in episodes) / n, 4)
        if summary.get(metric) != expected:
            return False
    return all(ep.get("outcome") in ("success", "collision", "timeout") for ep in episodes)
