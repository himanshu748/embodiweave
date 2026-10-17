"""Bound model-facing MCP text while retaining full records in the audit log.

Budgets use UTF-8 bytes as a conservative upper bound on byte-BPE text tokens,
not a tokens-per-character estimate. Protocol framing and schemas have a separate
serialized-request ceiling. Unknown or omitted rows are explicitly marked.
"""
import json

TOOL_TEXT_BUDGET = 2000
ALL_TOOL_TEXT_BUDGET = 12000
REQUEST_BYTE_BUDGET = 28000
MAX_HISTORY_GROUPS = 6
REQUIRED_READS = {'diagnose_policy', 'find_training_origins', 'nearest_passing_ancestor',
                  'get_decision_outcomes', 'rank_regression_origins', 'rank_origins_excluding_regressed'}


def encode(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'), default=str)


def pick(value, keys):
    return {k: value[k] for k in keys if k in value}


def summarize(name, result):
    if result.get('bounded_tool_summary'):
        assert len(encode(result).encode()) <= TOOL_TEXT_BUDGET
        return result
    q = result.get('queries', [])
    out = {'bounded_tool_summary': True, 'tool': name,
           'graph_revision': max((x.get('graph_revision', 0) for x in q), default=0),
           'full_records': 'get_evidence_record(record_type, record_id); full query rows remain in the Decision audit'}
    if result.get('error'):
        out.update(pick(result, ['error', 'graph_unavailable']))
        out['error'] = str(out['error'])[:600]
    elif 'origin_ranking' in result:
        rows=result['origin_ranking']
        eligible=[r for r in rows if not r['excluded']]
        excluded=[r for r in rows if r['excluded']]
        out.update(rule=result['rule'], total_eligible=len(eligible), total_excluded=len(excluded),
            eligible_origins=[pick(r, ['origin_id','failed_suites','collision_clearance']) for r in eligible[:3]],
            excluded_origins=[{**pick(r,['origin_id','unexamined_ancestors']), 'reasons':r['reasons'][:2]} for r in excluded[:2]],
            notice='Top-k summary; full exclusions and Cypher retained in Decision audit. No observed regression is not safety.')
    elif 'candidates' in result:
        rows = result['candidates']
        out.update(total_candidates=len(rows), candidate_order='authored eligibility rank; not a safety prediction',
                   candidates=[{'policy_id': c['policy_id'], 'rank': c['rank'], 'passed': c['passed'],
                                'training_domain': c['training_domain'], 'validation': [
                                    pick(e, ['suite', 'success', 'collisions']) for e in c['validation']]} for c in rows[:4]],
                   rejected_count=len(result.get('rejected', [])))
    elif 'outcomes' in result:
        rows = result['outcomes']
        out.update(total_outcomes=len(rows), outcomes=[{
            **pick(r, ['decision_id', 'origin_id', 'child_id']),
            **pick(r['outcome'], ['id', 'regressed', 'gate_verdict', 'release_verdict']),
            'suites': [pick(s, ['suite_id', 'episodes', 'parent_collisions', 'child_collisions',
                                'collision_delta', 'goal_delta']) for s in r['outcome']['suites']]} for r in rows[:2]])
    elif 'ranking' in result:
        # Explicitly sort observed support before null; never call unknown zero risk.
        rows = sorted(result['ranking'], key=lambda r: (not bool(r['observed_children']),
                       -(r['weighted_regression_degree'] or 0), r['origin_id']))
        out.update(total_origins=len(rows), weight='sum of positive per-suite child-minus-parent collision-rate deltas',
                   unknown_means='no observations, not safer', ranking=[pick(r, ['origin_id', 'observed_children',
                                    'weighted_regression_degree']) for r in rows[:8]])
    elif 'validation_and_failures' in result:
        unique = {r['evaluation_id']: r for r in result['validation_and_failures']}
        out.update(policy=pick(result['policy'], ['policy_id', 'artifact_hash', 'contract_id']),
                   validation=[pick(r, ['suite_id', 'evaluation_id', 'episodes', 'success_rate', 'collision_rate'])
                               for r in list(unique.values())[:4]], total_evaluations=len(unique))
    elif 'nearest' in result:
        out.update(nearest=result['nearest'], algorithm=result['algorithm'])
    elif 'ancestors' in result:
        out.update(ancestors=result['ancestors'][:4], total_ancestors=len(result['ancestors']))
    elif 'decision' in result or 'record' in result:
        record = result.get('decision', result.get('record', {}))
        out['record_type'] = result.get('record_type', 'Decision')
        out['record'] = pick(record, ['id', 'policy_id', 'artifact_hash', 'selected', 'proposed_origin', 'model',
                     'mode', 'explanation', 'regressed', 'gate_verdict', 'release_verdict', 'suites', 'episodes',
                     'collision_rate', 'success_rate', 'contract_id', 'status'])
        if isinstance(out['record'].get('suites'), str):
            out['record']['suites'] = [pick(s, ['suite_id', 'episodes', 'parent_collisions', 'child_collisions',
                                                'collision_delta', 'goal_delta']) for s in json.loads(out['record']['suites'])]
    else:
        out.update(pick(result, ['decision_id', 'training_session_id', 'state', 'origin_id', 'budget', 'seed',
                      'guardrail', 'training_started', 'policy_id', 'artifact_hash', 'preview', 'verdict', 'checks',
                      'missing', 'deployment_changed']))
    # Reduce complete rows, never slice JSON or a metric. Full records stay queryable.
    for key in ['candidates', 'outcomes', 'ranking', 'ancestors', 'eligible_origins', 'excluded_origins']:
        while len(encode(out).encode()) > TOOL_TEXT_BUDGET and len(out.get(key, [])) > 1:
            out[key].pop()
    if 'candidates' in out:
        out['omitted_candidates'] = out['total_candidates']-len(out['candidates'])
        out['more'] = 'Use diagnose_policy(policy_id) for exact validation. Full eligible rows are retained in the audit.'
    if len(encode(out).encode()) > TOOL_TEXT_BUDGET:
        # Unusually large graph strings must not defeat the hard bound.
        out = {'bounded_tool_summary': True, 'tool': name, 'truncated': True,
               'notice': 'Record exceeds the text budget; full graph record remains queryable by ID.',
               'record_id': str(result.get('record', result.get('decision', {})).get('id', ''))[:160]}
    assert len(encode(out).encode()) <= TOOL_TEXT_BUDGET
    return out


def bound_history(messages, tools):
    """Drop whole old exchanges, retaining first required reads and latest group.

Tool call/response pairs stay valid. The full chronological trace is saved
separately; this function only bounds the provider's input.
"""
    fixed = messages[:2]
    groups = []
    for message in messages[2:]:
        if message['role'] == 'assistant' or not groups:
            groups.append([])
        groups[-1].append(message)
    pinned, seen = set(), set()
    for i, group in enumerate(groups):
        names = {c['function']['name'] for m in group for c in m.get('tool_calls', [])}
        new = (names & REQUIRED_READS)-seen
        if new:
            pinned.add(i); seen |= new
    keep = list(range(len(groups)))
    def selected():return fixed+[m for i in keep for m in groups[i]]
    def within():
        ms=selected()
        return (len(keep)<=MAX_HISTORY_GROUPS and
                sum(len(m.get('content', '').encode()) for m in ms if m['role']=='tool') <= ALL_TOOL_TEXT_BUDGET and
                len(json.dumps({'messages':ms,'tools':tools}).encode()) <= REQUEST_BYTE_BUDGET-800)
    while not within():
        removable=next((i for i in keep if i not in pinned and i != len(groups)-1), None)
        if removable is None:
            raise ValueError('Required evidence exceeds the bounded request; no model call was sent')
        keep.remove(removable)
    return selected(), {'dropped_exchange_groups':len(groups)-len(keep),
        'tool_text_token_upper_bound':sum(len(m.get('content','').encode()) for m in selected() if m['role']=='tool'),
        'serialized_messages_and_tools_bytes':len(json.dumps({'messages':selected(),'tools':tools}).encode())}
