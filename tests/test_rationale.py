"""Read-only display verification; saved decisions are fixtures, never rewritten."""
import copy
import hashlib
from pathlib import Path
from ew.rationale import accepts, checked, recorded_v4_review, session_display


def answer(rows=None):
    return {'selected_origin':'robust-known', 'results':[{'origin_ranking': rows if rows is not None else [
        {'origin_id':'robust-known','failed_suites':0,'collision_clearance':0.05,'excluded':False,'reasons':[]}]}]}


def test_identifiers_must_be_returned_in_this_turn():
    verdict=accepts('Policy ID invented. Run ID run-fake; decision deci-fake and outcome-deci-fake.',answer())
    assert not verdict['accepted']
    assert {'invented','run-fake','deci-fake','outcome-deci-fake'} <= set(verdict['invented_ids'])
    assert not accepts('Checkpoint fabricated has no collisions.',answer())['accepted']
    assert accepts('Origin robust-known has collision clearance 0.05.',answer())['accepted']
    poisoned={'results':[{'queries':[{'params':{'policy':'robust-fake'}}]}]}
    assert not accepts('robust-fake',poisoned)['accepted']


def test_comparison_requires_a_measured_number_in_same_sentence():
    for word in ('safest','safer','safe','guaranteed','best'):
        assert 'unsupported comparison' in accepts(f'{word}.',answer())['reasons']
        assert accepts(f'{word}, collision clearance 0.05.',answer())['accepted']
        assert not accepts(f'0.05 clearance. This is {word}.',answer())['accepted']
        assert not accepts(f'The {word} uses 999.',answer())['accepted']


def test_empty_or_excluded_ranking_cannot_claim_improvement():
    for rows in ([],[{'origin_id':'robust-known','excluded':True,'failed_suites':0,'collision_clearance':0.05,
                      'reasons':[{'reason':'REGRESSED_AGAINST','outcome_id':'outcome-deci-known'}]}]):
        result=checked('robust-known improves collisions by 0.05.', answer(rows))
        assert not result['accepted'] and 'improves' not in result['text']
        assert 'model sentence rejected:' in result['note']
    result=checked('It improves impact.',answer([{'origin_id':'robust-known','excluded':True,'failed_suites':0,
        'collision_clearance':0.05,'reasons':[{'reason':'REGRESSED_AGAINST','outcome_id':'outcome-deci-known'}]}]))
    assert 'REGRESSED_AGAINST' in result['text'] and 'outcome-deci-known' in result['text']


def test_recorded_v4_safest_rationale_is_replaced_without_editing_fixture():
    path=Path(__file__).resolve().parents[1]/'evidence/mcp-agent-v4/decision.json'
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    result=recorded_v4_review()
    assert not result['accepted'] and result['reasons']==['unsupported comparison']
    assert 'safest' not in result['text'] and 'robust-20261016140226-352fd7' in result['text']
    assert 'failed suites 0' in result['text'] and 'collision clearance' in result['text']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before


def test_public_display_checks_proposal_and_final_without_mutating_receipt():
    session={'calls':[{'tool':'rank_origins_excluding_regressed','args':{},'result':answer()['results'][0]},
        {'tool':'start_training','args':{'origin_id':'robust-known','reason':'This is safest.'},'result':{}}],
        'model_rationale':'robust-invented is best.', 'answer':'Measured MCP evidence.', 'answer_source':'compiled_mcp_evidence'}
    original=copy.deepcopy(session)
    display=session_display(session)
    assert session==original
    assert 'safest' not in display['calls'][1]['args']['reason']
    assert all(not x['accepted'] for x in display['rationale_checks'])
    assert 'robust-invented' not in display['display_rationale']
