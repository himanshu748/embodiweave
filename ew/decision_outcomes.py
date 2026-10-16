"""Append-only parent comparisons. Never changes promo-1 or releases a policy."""
from . import artifacts, records
from .graph import db, ingest
from .search import SUITES
from .validation import complete_evaluation, suite_fingerprint
from .scenarios import SUITES as DEFINITIONS


def record_outcome(decision_id, run_id, child_id, evaluation_ids, gate):
    did = records.read('decision', decision_id)
    run = records.read('run', run_id)
    parent_id = did['selected']
    if (run['decision_id'] != decision_id or run['parent_id'] != parent_id
            or run['child_policy_id'] != child_id or run['status'] != 'completed'):
        raise ValueError('Run does not match the recorded decision')
    parent = artifacts.load_manifest(parent_id)
    child = artifacts.load_manifest(child_id)
    for m in (parent, child):
        artifacts.verify_policy(m['policy_id'], m['artifact_hash'])
    if child['parent_id'] != parent_id or child['contract_id'] != parent['contract_id']:
        raise ValueError('Parent or sensor contract mismatch')
    selected = next(c for c in did['ranking'] if c['policy_id'] == parent_id)
    child_evals = [records.read('evaluation', eid) for eid in evaluation_ids]
    if len(child_evals) != 4 or {e['suite_id'] for e in child_evals} != set(SUITES):
        raise ValueError('Comparison needs four complete canonical suites')
    rows = []
    for ce in child_evals:
        sid = ce['suite_id']
        pe = records.read('evaluation', selected['validation'][sid]['evaluation_id'])
        for ev, m in ((ce, child), (pe, parent)):
            if (ev['policy_id'] != m['policy_id'] or ev['artifact_hash'] != m['artifact_hash']
                    or ev['suite_id'] != sid or not complete_evaluation(ev, m['contract_id'])):
                raise ValueError('Comparison evidence does not match exact artifacts and suites')
        pc = sum(e['outcome'] == 'collision' for e in pe['episodes'])
        cc = sum(e['outcome'] == 'collision' for e in ce['episodes'])
        pg = sum(e['outcome'] == 'success' for e in pe['episodes'])
        cg = sum(e['outcome'] == 'success' for e in ce['episodes'])
        n = len(ce['episodes'])
        rows.append(dict(suite_id=sid, suite_fingerprint=suite_fingerprint(DEFINITIONS[sid]),
            parent_evaluation_id=pe['id'], child_evaluation_id=ce['id'], episodes=n,
            parent_collisions=pc, child_collisions=cc, collision_delta=cc-pc,
            collision_rate_delta=(cc-pc)/n, parent_goals=pg, child_goals=cg, goal_delta=cg-pg))
    if (gate['policy_id'] != child_id or gate['artifact_hash'] != child['artifact_hash']
            or set(gate['evaluation_ids']) != set(evaluation_ids)):
        raise ValueError('Gate does not assess these child evaluations')
    regression = any(r['collision_delta'] > 0 or r['goal_delta'] < 0 for r in rows)
    # Stable ID makes replaying ingestion idempotent, without overwriting records.
    oid = 'outcome-' + decision_id
    data = dict(id=oid, decision_id=decision_id, run_id=run_id, parent_id=parent_id, child_id=child_id,
        parent_hash=parent['artifact_hash'], child_hash=child['artifact_hash'], contract_id=child['contract_id'],
        suites=rows, regressed=regression, gate_id=gate['id'], gate_verdict=gate['verdict'],
        weighted_regression=sum(max(0, r['collision_rate_delta']) for r in rows),
        release_verdict='not_released_regression' if regression else 'not_released_review_required',
        deployment_changed=False, comparison='same canonical validation seeds, one training seed; not causal advantage')
    if records.exists('decision_outcome', oid):
        saved = records.read('decision_outcome', oid)
        if any(saved[k] != v for k, v in data.items()):
            raise ValueError('A different outcome is already recorded')
    else:
        saved = records.write('decision_outcome', data)
    ingest.decision_outcome(saved)
    db.bump_revision('decision outcome ' + oid)
    return saved
