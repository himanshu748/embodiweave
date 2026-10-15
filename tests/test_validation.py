from copy import deepcopy

import pytest

from ew.contract import CONTRACT_V1
from ew.scenarios import SUITES
from ew.validation import complete_evaluation


def evidence():
    suite = SUITES["val-target-v1"]
    return {"suite_id": suite.suite_id, "suite_version": suite.version, "suite_role": suite.role,
            "seeds": list(suite.seeds), "family_id": suite.family.fid(), "contract_id": CONTRACT_V1.contract_id,
            "episodes": [{"outcome": "success"}] * len(suite.seeds),
            "summary": {"episodes": len(suite.seeds), "success_rate": 1.0, "collision_rate": 0.0, "timeout_rate": 0.0}}


def test_complete_suite_is_accepted():
    assert complete_evaluation(evidence(), CONTRACT_V1.contract_id)


@pytest.mark.parametrize("field,value", [("suite_version", "old"), ("suite_role", "final_test"),
    ("family_id", "wrong"), ("contract_id", "wrong"), ("seeds", [1300000]), ("episodes", [{"outcome": "success"}]),
    ("custom_family", True), ("summary", {"episodes": 60, "success_rate": 0.9, "collision_rate": 0.1, "timeout_rate": 0.0})])
def test_incomplete_or_mismatched_evidence_is_refused(field, value):
    record = deepcopy(evidence())
    record[field] = value
    assert not complete_evaluation(record, CONTRACT_V1.contract_id)
