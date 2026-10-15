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


@pytest.mark.parametrize('fails_target', [False, True])
def test_gate_can_approve_complete_evidence_and_reject_a_failed_suite(monkeypatch, fails_target):
    """Unit fixtures only: prove the gate is conditional, without publishing invented runs."""
    from types import SimpleNamespace
    from ew import artifacts, records, service
    from ew.graph import queries
    from ew.scenarios import SUITES
    suites = ['val-target-v1', 'val-open-v1', 'val-static-v1', 'val-crossing-v1']
    evs, rows = {}, []
    for sid in suites:
        suite = SUITES[sid]
        failed = fails_target and sid == 'val-target-v1'
        ev = {'policy_id':'unit-checkpoint','artifact_hash':'unit-hash','suite_id':sid,
              'suite_version':suite.version,'suite_role':suite.role,'family_id':suite.family.fid(),
              'contract_id':CONTRACT_V1.contract_id,'seeds':list(suite.seeds),
              'episodes':[{'outcome':'collision' if failed else 'success'} for _ in suite.seeds],
              'summary':{'episodes':len(suite.seeds),'success_rate':0.0 if failed else 1.0,
                         'collision_rate':1.0 if failed else 0.0,'timeout_rate':0.0}}
        eid='unit-'+sid;evs[eid]=ev
        rows.append({'suite_id':sid,'evaluation_id':eid,'policy_hash':'unit-hash'})
    monkeypatch.setattr(artifacts,'verify_policy',lambda *a:'unit-hash')
    monkeypatch.setattr(artifacts,'load_manifest',lambda *a:{'contract_id':CONTRACT_V1.contract_id,'status':'completed'})
    monkeypatch.setattr(records,'exists',lambda kind,eid:eid in evs)
    monkeypatch.setattr(records,'read',lambda kind,eid:evs[eid])
    monkeypatch.setattr(queries,'run',lambda *a:SimpleNamespace(dicts=lambda:rows,to_log=lambda:{}))
    result=service.promotion_preview('unit-checkpoint')
    assert result['verdict']==('rejected' if fails_target else 'promoted')
    assert len(result['checks'])==4 and not result['missing']
