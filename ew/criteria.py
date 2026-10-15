"""Versioned thresholds and promotion gates. Frozen before any benchmark or final test run.

Chosen at Gate 1/2 from learnability probes on validation suites only (evidence/gate1). They were
not tuned against test-target-v1, which had not been evaluated when these were fixed.
"""
from __future__ import annotations

THRESHOLDS = {
    # Transfer-trial threshold: the adapted child is "at threshold" on the target validation suite.
    "thr-target-1": {"suite_id": "val-target-v1", "min_success": 0.80, "max_collision": 0.10},
}

PROMOTION = {
    # Mission static_crossing requires (AND) the target behaviour and three retained behaviours,
    # all measured on the SAME candidate artifact hash.
    "promo-1": {
        "mission": "static_crossing",
        "target": {"suite_id": "val-target-v1", "min_success": 0.80, "max_collision": 0.10},
        "retained": [
            {"suite_id": "val-open-v1", "min_success": 0.90, "max_collision": 0.05},
            {"suite_id": "val-static-v1", "min_success": 0.75, "max_collision": 0.10},
            {"suite_id": "val-crossing-v1", "min_success": 0.75, "max_collision": 0.15},
        ],
    }
}


def meets(summary: dict, crit: dict) -> bool:
    return summary["success_rate"] >= crit["min_success"] and summary["collision_rate"] <= crit["max_collision"]
