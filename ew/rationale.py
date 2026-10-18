"""Display-only checks against this investigation's returned evidence.

This is a conservative lexical check, not a semantic proof of safety or truth.
Historical decisions and receipts are never changed by this module.
"""
from __future__ import annotations

import copy
import json
import re

IDS = re.compile(r"(?<![\w-])(?:outcome-[\w~-]+|decision-[\w~-]+|judge-[\w~-]+|deci-[\w~-]+|run-[\w~-]+|ppo-[\w~-]+|P-[\w~.-]+|(?:robust|search|physics|rehearsal|scratch|collision|policy|checkpoint|origin)[~-][\w~.-]+)")
COMPARISON = re.compile(r"\b(?:safest|safer|safe|guaranteed|best)\b", re.I)
IMPACT = re.compile(r"\b(?:improv\w*|impact|reduc\w*|prevent\w*|safer|safest|safe|best|guaranteed)\b", re.I)
NUMBER = re.compile(r"(?<![\w-])\d+(?:\.\d+)?%?(?![\w-])")
METRICS = {'failed_suites', 'collision_clearance', 'collision_rate', 'success_rate', 'episodes',
           'collisions', 'success', 'parent_collisions', 'child_collisions', 'collision_delta',
           'goal_delta', 'hops', 'pathWeight', 'count', 'passed'}


def facts(answer):
    """Collect returned identifiers/measurements, never query parameters or model prose."""
    ids, numbers = set(), set()
    def walk(value, key=''):
        if isinstance(value, dict):
            for k, v in value.items():
                if k == 'queries' and isinstance(v,list):
                    for query in v: walk(query.get('rows',[]))
                elif k not in {'queries','params','cypher','reason','explanation','notice','error','question'}:
                    walk(v, k)
        elif isinstance(value, list):
            for v in value: walk(v, key)
        elif isinstance(value, str):
            if key == 'id' or key.endswith('_id') or key.endswith('_ids') or key in {'selected','proposed_origin','origin','candidate','decision','run','outcome','path','children','unexamined_ancestors'}:
                ids.add(value)
        elif type(value) in (int,float) and key in METRICS:
            numbers.add(format(value,'.12g'))
            if key in {'collision_rate','success_rate','collisions','success','collision_clearance'} and 0 <= value <= 1:
                numbers.add(format(value*100,'.12g')+'%')
    walk(answer.get('results', answer))
    return ids, numbers


def _rows(answer):
    for result in reversed(answer.get('results', [answer])):
        if 'origin_ranking' in result: return result['origin_ranking']
        if 'eligible_origins' in result:
            return [{**r,'excluded':False} for r in result['eligible_origins']] + [
                {**r,'excluded':True} for r in result.get('excluded_origins',[])]
        if 'candidates' in result:
            return [{'origin_id':r['policy_id'], 'excluded':False} for r in result['candidates']]
    return None


def accepts(sentence, answer):
    """Return an explicit acceptance verdict, invented IDs and rejection reasons."""
    ids, numbers = facts(answer)
    claimed = {x.rstrip('.,') for x in IDS.findall(sentence)}
    # Also check explicit ID declarations, including IDs outside today's naming convention.
    claimed.update(m.group(1).rstrip('.,') for m in re.finditer(
        r'\b(?:policy|checkpoint|run|decision|outcome)\s+(?:ID\s*[:=]?\s*)[`\"\']?([\w~.-]+)', sentence, re.I))
    ordinary = {'a','an','the','is','was','has','had','will','can','may','must','should','stays',
                'remains','passed','failed','selected','selection','choice','history','evidence',
                'training','budget','result','results','returned','id','not','and','or','that','this',
                'with','from','for','of','to','in','on','due','because','based','after','before','only','changes','changed','continues','starts'}
    for match in re.finditer(r'\b(?:policy|checkpoint|run|decision|outcome)\s+[`\"\']?([\w~.-]+)', sentence, re.I):
        candidate=match.group(1).rstrip('.,')
        if candidate.lower() not in ordinary: claimed.add(candidate)
    invented = sorted(claimed-ids)
    reasons = ['invented IDs: '+', '.join(invented)] if invented else []
    rows = _rows(answer)
    selected = answer.get('selected_origin')
    invalid_origin = rows is not None and (not any(not r.get('excluded',False) for r in rows) or
        (selected is not None and not any(r.get('origin_id')==selected and not r.get('excluded',False) for r in rows)))
    # Apply the number exception per sentence, not to a whole paragraph containing unrelated metrics.
    for part in re.split(r'(?<=[.!?])\s+|\n+', sentence):
        quoted = set(NUMBER.findall(IDS.sub('',part)))
        if COMPARISON.search(part) and not quoted.intersection(numbers):
            reasons.append('unsupported comparison')
        if invalid_origin and IMPACT.search(part):
            reasons.append('empty or excluded ranking cannot support impact or improvement')
    reasons = list(dict.fromkeys(reasons))
    return {'accepted':not reasons, 'reasons':reasons, 'invented_ids':invented}


def flat_sentence(answer):
    rows = _rows(answer)
    if rows is None:
        return 'No origin-ranking rows were returned. No impact or improvement is established.'
    if not rows:
        return 'The returned origin ranking is empty. No origin is established.'
    selected = answer.get('selected_origin')
    chosen = next((r for r in rows if r.get('origin_id')==selected), None)
    show = [chosen] if chosen else rows[:3]
    text=[]
    for row in show:
        fields=[f"Origin {row['origin_id']}"]
        if 'failed_suites' in row: fields.append(f"failed suites {row['failed_suites']}")
        if 'collision_clearance' in row: fields.append(f"collision clearance {row['collision_clearance']:.6g}")
        fields.append('excluded' if row.get('excluded') else 'eligible in the returned ranking')
        for reason in row.get('reasons',[]):
            fields.append(f"{reason['reason']} (outcome {reason.get('outcome_id') or 'not returned'})")
        if row.get('unexamined_ancestors'): fields.append('unexamined, excluded')
        text.append('; '.join(fields)+'.')
    return ' '.join(text)


def checked(sentence, answer):
    verdict=accepts(sentence, answer)
    return {**verdict, 'text':sentence if verdict['accepted'] else flat_sentence(answer),
            'note':None if verdict['accepted'] else 'model sentence rejected: '+'; '.join(verdict['reasons'])}


def session_display(session):
    """Sanitize a copy at the response boundary; retain the stored raw audit unchanged."""
    out=copy.deepcopy(session)
    results=[]
    checks=[]
    selected=None
    for call in out.get('calls',[]):
        args=call.get('args',{})
        if args.get('origin_id'): selected=args['origin_id']
        if isinstance(args.get('reason'),str):
            review=checked(args['reason'], {'results':results,'selected_origin':selected})
            args['reason']=review['text']
            call['rationale_check']=review
            checks.append(review)
        result=call.get('result',{})
        # Returned historical prose is display-checked too; full stored records remain available by ID.
        for key in ('decision','record'):
            node=result.get(key)
            if isinstance(node,dict) and isinstance(node.get('explanation'),str):
                review=checked(node['explanation'], {'results':results+[result], 'selected_origin':node.get('selected')})
                node['explanation']=review['text'];checks.append(review)
        results.append(result)
    if out.get('model_rationale'):
        review=checked(out.pop('model_rationale'), {'results':results,'selected_origin':selected})
        out['display_rationale']=review['text'];checks.append(review)
    elif out.get('answer') and out.get('answer_source') not in {'compiled_mcp_evidence','compiled_live_graph_evidence','deterministic_fallback'}:
        review=checked(out['answer'], {'results':results,'selected_origin':selected})
        out['answer']=review['text'];checks.append(review)
    out['rationale_checks']=checks
    return out


def recorded_v4_review():
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'evidence/mcp-agent-v4/decision.json'
    decision=json.loads(path.read_text())
    results=[c['result'] for c in decision['mcp_tool_calls'] if c['tool']!='start_training']
    return {**checked(decision['explanation'], {'results':results, 'selected_origin':decision['selected']}),
            'source':'evidence/mcp-agent-v4/decision.json', 'decision_id':decision['id'],
            'notice':'Display check of a saved rationale. No model call, training or evaluation; the receipt is unchanged.'}


def decision_display(decision):
    """Check historical model prose for Studio without modifying the source record."""
    out = copy.deepcopy(decision)
    if out.get('mode') not in {'llm', 'llm-agent'}:
        return out
    results = [call.get('result', {}) for call in out.get('mcp_tool_calls', [])
               if call.get('tool') != 'start_training']
    review = checked(out.get('explanation', ''),
                     {'results': results, 'selected_origin': out.get('selected')})
    out['explanation'] = review['text']
    out['rationale_check'] = review
    return out
