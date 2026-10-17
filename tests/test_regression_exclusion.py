"""Exercise the real read-only Cypher against a frozen production projection."""
import json
from pathlib import Path
from collections import defaultdict
import pytest
from ew import mcp_domain as D, agent_context as C
from ew.graph import db

SNAPSHOT = Path(__file__).resolve().parents[1] / 'evidence/mcp-agent-v4/graph-snapshot.json'
TARGET = 'robust-20261016140226-352fd7'
OLD = 'physics-20261016150004-25da9c'

@pytest.fixture
def snapshot(monkeypatch):
    data = json.loads(SNAPSHOT.read_text())
    monkeypatch.setattr(db, 'GRAPH', 'ew_test_v4_snapshot')
    db.delete_graph(db.GRAPH)
    labels = defaultdict(list)
    for n in data['nodes']: labels[n['label']].append(n['properties'])
    for label, props in labels.items():
        assert label in {'Robot','Policy','Evaluation','Suite','Contract','Decision','DecisionOutcome'}
        db.rw(f'UNWIND $rows AS props CREATE (n:{label}) SET n=props', {'rows':props})
    types = defaultdict(list)
    for e in data['edges']: types[e['type']].append(e)
    for kind, edges in types.items():
        assert kind in {'USES_CONTRACT','FOR_ROBOT','DERIVED_FROM','ASSESSED','ON_SUITE','HAS_OUTCOME','SELECTED','REGRESSED_AGAINST'}
        db.rw(f'UNWIND $rows AS e MATCH (a {{id:e.source}}),(b {{id:e.target}}) CREATE (a)-[r:{kind}]->(b) SET r=e.properties', {'rows':edges})
    monkeypatch.setattr(D, 'inspect_training_origins', lambda target,budget: data['verified_eligibility'])
    yield data
    db.delete_graph(db.GRAPH)

def test_saved_graph_excludes_regression_and_orders_survivors(snapshot):
    revision = db.revision()
    result = D.rank_origins_excluding_regressed(TARGET)
    rows = result['origin_ranking']
    assert len(rows) == len(snapshot['verified_eligibility']['ranking'])
    old = next(r for r in rows if r['origin_id']==OLD)
    assert old['excluded']
    assert {'REGRESSED_AGAINST','not_released_regression'} <= {r['reason'] for r in old['reasons']}
    assert 'outcome-deci-20261016175734-1b2724' in {r['outcome_id'] for r in old['reasons']}
    survivors = [r for r in rows if not r['excluded']]
    assert survivors and OLD not in [r['origin_id'] for r in survivors]
    assert survivors == sorted(survivors,key=lambda r:(r['failed_suites'],-r['collision_clearance'],r['origin_id']))
    assert db.revision()==revision
    assert len(C.encode(C.summarize('rank_origins_excluding_regressed',result)).encode()) <= C.TOOL_TEXT_BUDGET
    # Control changes only the isolated fixture; receipts and production graph stay intact.
    db.rw('MATCH ()-[r:REGRESSED_AGAINST]->() DELETE r')
    still = D.rank_origins_excluding_regressed(TARGET)['origin_ranking']
    assert next(r for r in still if r['origin_id']==OLD)['excluded']
    db.rw('MATCH (o:DecisionOutcome) DETACH DELETE o')
    control = D.rank_origins_excluding_regressed(TARGET)['origin_ranking']
    assert not next(r for r in control if r['origin_id']==OLD)['excluded']

def test_transitive_lineage_depth_and_parameter_bounds(snapshot):
    # Attach the target to a known excluded origin only in this isolated test graph.
    db.rw('MATCH (a:Policy {id:$a}), (b:Policy {id:$b}) CREATE (a)-[:DERIVED_FROM]->(b)', {'a':TARGET,'b':OLD})
    row = next(r for r in D.rank_origins_excluding_regressed(TARGET)['origin_ranking'] if r['origin_id']==TARGET)
    assert row['excluded'] and any(r['ancestor_id']==OLD for r in row['reasons'])
    for hops in (0,9,True,'8'):
        with pytest.raises(ValueError): D.rank_origins_excluding_regressed(TARGET,hops)
    row = next(r for r in D.rank_origins_excluding_regressed(TARGET,1)['origin_ranking'] if r['origin_id']==TARGET)
    assert row['excluded'] and row['unexamined_ancestors']
