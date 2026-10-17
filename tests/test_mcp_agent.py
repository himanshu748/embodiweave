"""Synthetic fixtures test governance; they are never published as run evidence."""
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx2
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ew import api, artifacts, judge_agent as J, judge_mcp, mcp_client as C, mcp_domain as D, records
from ew.contract import CONTRACT_V1, CONTRACT_MIRRORED
from ew.graph import db, ingest
from ew.scenarios import SUITES
from ew.select import inspect_training_origins, validate_proposed_origin


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "ROOT", tmp_path)
    monkeypatch.setattr(records, "RECORDS", tmp_path / "records")
    monkeypatch.setattr(db, "GRAPH", "ew_test_domain_mcp")
    monkeypatch.setattr(D.agent_tools, "DEPLOYED_POLICY", "target")
    db.delete_graph(db.GRAPH)
    ingest.init_world()
    manifests = {}
    for pid, parent in [("root", None), ("mid", "root"), ("target", "mid"),
                        ("incomplete", None), ("mirror", None), ("stale", None)]:
        contract = CONTRACT_MIRRORED if pid == "mirror" else CONTRACT_V1
        m = dict(policy_id=pid, artifact_hash="fixture-"+pid, created_at="2026-10-16", status="completed",
                 family="open", consumed_steps=0, seed=1, recipe="fixture", parent_id=parent, contract_id=contract.contract_id)
        manifests[pid] = m
        ingest.policy(m)
    monkeypatch.setattr(artifacts, "load_manifest", lambda pid: manifests[pid])
    def verify(pid, expected=None):
        h = manifests[pid]["artifact_hash"]
        if pid == "stale" or (expected is not None and expected != h):
            raise ValueError("Test artifact mismatch")
        return h
    monkeypatch.setattr(artifacts, "verify_policy", verify)
    for pid, m in manifests.items():
        for sid in D.SUITES[:1] if pid == "incomplete" else D.SUITES:
            suite = SUITES[sid]
            success = pid in ("root", "mirror", "stale")
            outcome = "success" if success else "timeout"
            ev = records.write("evaluation", dict(id=pid+"-"+sid, policy_id=pid, artifact_hash=m["artifact_hash"],
                suite_id=sid, suite_role=suite.role, suite_version=suite.version, family_id=suite.family.fid(),
                seeds=list(suite.seeds), contract_id=m["contract_id"],
                episodes=[{"outcome": outcome} for _ in suite.seeds],
                summary=dict(episodes=len(suite.seeds), success_rate=float(success), collision_rate=0.0,
                             timeout_rate=float(not success), mean_success_steps=1 if success else None)))
            ingest.evaluation(ev)
    yield manifests
    db.delete_graph(db.GRAPH)


def test_shortest_path_algorithm_is_bounded_and_filters_invalid_evidence(world):
    r = D.nearest_passing_ancestor("target")
    assert r["nearest"]["ancestor_id"] == "root" and r["nearest"]["hops"] == 2
    assert r["nearest"]["path"] == ["target", "mid", "root"]
    assert D.nearest_passing_ancestor("target", max_hops=1)["nearest"] is None
    for kwargs in ({"max_hops": 9}, {"max_hops": True}, {"suite_id": "test-target-v1"}):
        with pytest.raises(ValueError):
            D.nearest_passing_ancestor("target", **kwargs)
    db.rw("MATCH (e:Evaluation {id:'root-val-target-v1'}) SET e.artifact_hash='stale'")
    assert D.nearest_passing_ancestor("target")["nearest"] is None


def test_guardrail_checks_completeness_semantics_hash_and_budget_not_rank(world):
    result = inspect_training_origins("target", 60000)
    assert result["ranking"][0]["policy_id"] == "root"
    assert validate_proposed_origin("target", "target", 60000)["verdict"] == "allowed"
    for pid in ("mirror", "incomplete", "stale", "unknown"):
        assert validate_proposed_origin("target", pid, 60000)["verdict"] == "vetoed"
    assert validate_proposed_origin("target", "root", 900000)["verdict"] == "vetoed"


def reads(workflow):
    for tool, args in [("diagnose_policy", {"policy_id": "target"}),
                       ("find_training_origins", {"target_policy": "target"}),
                       ("nearest_passing_ancestor", {"policy_id": "target"})]:
        assert "error" not in D.dispatch(tool, args, workflow)


def test_veto_is_recorded_before_any_worker_and_choice_is_not_overridden(world, monkeypatch):
    launched = []
    def start(*args, **kwargs):
        d = records.read("decision", kwargs["agent_decision_id"])
        assert d["guardrail"]["verdict"] == "allowed" and d["selected"] == "target"
        assert d["model"] == "fixture-model" and any("shortestPath" in q["cypher"] for q in d["queries"])
        launched.append(kwargs)
        return {"id": "ppo-"+"1"*32, "state": "queued"}
    monkeypatch.setattr(D.public_training, "start", start)
    flow = D.Workflow("test-session", "private-owner", True, True, target="target", model="fixture-model")
    reads(flow)
    rejected = D.dispatch("start_training", {"origin_id": "mirror", "budget": 60000, "reason": "root is the measured passing ancestor"}, flow)
    assert rejected["guardrail"]["verdict"] == "vetoed" and not launched
    allowed = D.dispatch("start_training", {"origin_id": "target", "budget": 60000,
                         "reason": "root is the passing ancestor; target is complete and I choose it for this fixture"}, flow)
    assert allowed["training_session_id"] and launched[0]["origin_id"] == "target" and launched[0]["seed"] == 29
    D.dispatch("start_training", {"origin_id": "target", "budget": 60000, "reason": "root again"}, flow)
    assert len(launched) == 1
    node = D.explain_decision(flow.decisions[-1])["decision"]
    assert node["guardrail_verdict"] == "allowed" and node["model"] == "fixture-model"
    assert "private-owner" not in json.dumps(node)


def test_missing_consent_algorithm_or_algorithm_citation_stops_launch(world, monkeypatch):
    monkeypatch.setattr(D.public_training, "start", lambda *a, **k: pytest.fail("Worker must not launch"))
    assert "error" in D.dispatch("start_training", {"origin_id": "root", "budget": 60000, "reason": "Read-only test"})
    flow = D.Workflow("test", "owner", True, True, target="target")
    veto = D.dispatch("start_training", {"origin_id": "root", "budget": 60000, "reason": "No graph algorithm read yet"}, flow)
    assert veto["guardrail"]["verdict"] == "vetoed"
    reads(flow)
    veto = D.dispatch("start_training", {"origin_id": "target", "budget": 60000, "reason": "Evidence but missing the identifier"}, flow)
    assert any("ancestor ID" in why for why in veto["guardrail"]["reasons"])


def test_real_sdk_stdio_discovery_and_algorithm(world):
    async def run():
        env = {k: v for k, v in os.environ.items() if k not in ("OPENROUTER_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY")}
        env.update(EW_GRAPH=db.GRAPH, EW_FALKOR_PORT=str(db.PORT))
        async with stdio_client(StdioServerParameters(command=sys.executable, args=["-m", "ew.mcp_server"], env=env)) as streams:
            async with ClientSession(*streams) as client:
                await client.initialize()
                tools = await client.list_tools()
                assert len(tools.tools) == 11
                r = C.unpack(await client.call_tool("nearest_passing_ancestor", {"policy_id": "target"}))
                assert r["nearest"]["hops"] == 2
    asyncio.run(run())


def test_real_sdk_http_reads_and_unauthorized_action(world):
    async def run():
        async with api.lifespan(api.app):
            async with C.connect(url="http://testserver/mcp/", transport=httpx2.ASGITransport(api.app)) as (client, tools, initialized):
                assert len(tools) == 11 and initialized["serverInfo"]["name"] == "EmbodiWeave"
                assert C.unpack(await client.call_tool("lineage", {"policy_id": "target"}))["ancestors"]
                assert C.unpack(await client.call_tool("diagnose_policy", {"policy_id": "target"}))["validation_and_failures"]
                result = C.unpack(await client.call_tool("start_training", {"origin_id": "root", "reason": "Unauthorized action must stop"}))
                assert "read-only" in result["error"]
                for args in ({"policy_id": "target", "max_hops": 20}, {"policy_id": "target", "max_hops": True}):
                    assert "error" in C.unpack(await client.call_tool("lineage", args))
    asyncio.run(run())
    assert not records.all_of("decision")


@pytest.mark.parametrize("provider_down", [False, True])
def test_live_agent_uses_discovered_mcp_tools_and_labels_fallback(world, monkeypatch, provider_down):
    monkeypatch.setenv("EW_PUBLIC_AGENT", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-provider")
    real_thread = J.threading.Thread
    monkeypatch.setattr(J.threading, "Thread", lambda **kwargs: SimpleNamespace(start=lambda: None))
    monkeypatch.setattr(D.public_training, "start", lambda *a, **kw: {"id": "ppo-"+"2"*32, "state": "queued"})
    counter = 0
    def completion(messages, config, remaining):
        nonlocal counter
        counter += 1
        assert {t["function"]["name"] for t in config["tools"]} == set(D.READS) | {"start_training"}
        if provider_down:
            raise J.ProviderFailure("fixture provider down")
        if counter == 1:
            requests = [("diagnose_policy", {"policy_id": "target"}), ("find_training_origins", {"target_policy": "target"}),
                        ("nearest_passing_ancestor", {"policy_id": "target"})]
        elif counter == 2:
            requests = [("start_training", {"origin_id": "target", "budget": 60000, "reason": "root is two hops away and passes; I choose the complete target fixture to continue training"})]
        else:
            return {"model": J.FREE_NVIDIA_MODELS[0], "choices": [{"message": {"content": "Invented statement: the new child passed with zero collisions."}}]}
        return {"model": J.FREE_NVIDIA_MODELS[0], "choices": [{"message": {"tool_calls": [
            {"id": str(counter)+str(i), "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
            for i, (name, args) in enumerate(requests)]}}]}
    monkeypatch.setattr(J, "_completion", completion)
    original = C.connect
    @asynccontextmanager
    async def local(capability):
        async with original(capability, "http://testserver/mcp/", httpx2.ASGITransport(api.app)) as connection:
            yield connection
    monkeypatch.setattr(C, "connect", local)
    s = J.start("Choose an origin and train once", True, J.visitor(None), training_consent=True, training_requested=True)
    monkeypatch.setattr(J.threading, "Thread", real_thread)
    private = json.loads(J._path(s["id"]).read_text())
    async def run():
        async with api.lifespan(api.app):
            await judge_mcp.investigate(private)
    asyncio.run(run())
    saved = json.loads(J._path(s["id"]).read_text())
    assert saved["state"] == "completed" and saved["transport"] == "mcp-streamable-http"
    assert saved["training_started"] and all(call["transport"] == "mcp" for call in saved["calls"])
    decision = records.read("decision", saved["decision_ids"][-1])
    assert decision["mode"] == ("deterministic_fallback" if provider_down else "llm")
    assert decision["selected"] == ("root" if provider_down else "target")
    assert decision["model"] == (None if provider_down else J.FREE_NVIDIA_MODELS[0])
    if not provider_down:
        assert "Invented statement" not in saved["answer"] and "zero collisions" not in saved["answer"]
        assert "pending run" in saved["answer"]
    assert any(call["tool"] == "nearest_passing_ancestor" for call in decision["mcp_tool_calls"])
    assert "test-only-provider" not in json.dumps(decision)


def test_weighted_degree_preserves_unknown_and_ignores_stale_hash(world):
    q = D.rank_regression_origins("target")
    assert all(r['observed_children'] == 0 and r['weighted_regression_degree'] is None for r in q['ranking'])
    db.rw("MATCH (c:Policy {id:'target'}), (p:Policy {id:'root'}) "
          "CREATE (c)-[:COMPARED_AGAINST {weight:0.05, child_hash:'fixture-target', parent_hash:'fixture-root'}]->(p)")
    row = next(r for r in D.rank_regression_origins('target')['ranking'] if r['origin_id']=='root')
    assert row['observed_children'] == 1 and row['weighted_regression_degree'] == .05
    db.rw("MATCH (c:Policy {id:'target'}) SET c.artifact_hash='changed'")
    row = next(r for r in D.rank_regression_origins('target')['ranking'] if r['origin_id']=='root')
    assert row['observed_children'] == 0 and row['weighted_regression_degree'] is None


def test_outcome_is_immutable_connected_and_replayable(world):
    from ew.decision_outcomes import record_outcome
    # Exact fixture parent has success in every episode; child times out.
    world['target']['parent_id'] = 'root'
    ranking = inspect_training_origins('target', 60000)['ranking']
    d = records.write('decision', dict(id='decision-outcome-test', rule_version='fixture', mode='fixture',
        request={'target_family_id':'fixture'}, ranking=ranking, rejected=[], action='train_from_parent',
        selected='root', graph_revision=db.revision()))
    ingest.decision(d)
    run = records.write('run', dict(id='outcome-run', decision_id=d['id'], parent_id='root', child_policy_id='target',
        status='completed', run_kind='fixture', recipe='fixture', seed=1, budget_steps=60000, consumed_steps=61440,
        wall_s=0, family_id='fixture', family='fixture'))
    ingest.run(run)
    ids = ['target-'+sid for sid in D.SUITES]
    gate = {'id':'gate-fixture', 'policy_id':'target', 'artifact_hash':'fixture-target', 'evaluation_ids':ids, 'verdict':'rejected'}
    out = record_outcome(d['id'], run['id'], 'target', ids, gate)
    assert out['regressed'] and not out['deployment_changed'] and out['release_verdict']=='not_released_regression'
    assert record_outcome(d['id'], run['id'], 'target', ids, gate) == out
    rows = D.get_decision_outcomes('target')['outcomes']
    assert len(rows)==1 and rows[0]['decision_id']==d['id'] and len(rows[0]['evaluation_ids'])==8
    assert len(rows[0]['outcome']['suites'])==4
    assert D.explain_decision(d['id'])['decision']['selected']=='root'
    assert records.read('decision', d['id']) == d
    with pytest.raises(ValueError):
        record_outcome(d['id'], run['id'], 'target', ids[:3], gate)
    with pytest.raises(ValueError):
        record_outcome(d['id'], run['id'], 'target', ids, {**gate, 'artifact_hash':'wrong'})
    # Restoring the persisted outcome restores graph edges without touching the original Decision.
    db.rw("MATCH (o:DecisionOutcome) DETACH DELETE o")
    ingest.decision_outcome(records.read('decision_outcome', out['id']))
    assert len(D.get_decision_outcomes('target')['outcomes'])==1


def test_v3_requires_outcome_reads_before_launch(world, monkeypatch):
    monkeypatch.setattr(D.public_training, 'start', lambda *a, **k: pytest.fail('must veto'))
    flow = D.Workflow('v3-test', 'owner', True, True, target='target', study_id='agent-mcp-v3')
    reads(flow)
    veto = D.dispatch('start_training', {'origin_id':'root','budget':60000,
                        'reason':'root is the ancestor but no prior outcomes were read'}, flow)
    assert 'Read prior outcomes' in ';'.join(veto['guardrail']['reasons'])


def test_saved_outcome_tool_results_fit_bounded_model_context():
    # Offline serialization regression test; never calls a provider or trainer.
    from pathlib import Path
    receipt = json.loads((Path(__file__).parents[1]/'evidence/mcp-agent-v3/agent-receipt.json').read_text())
    ids = {c['policy_id'] for call in receipt['calls'] if call['tool']=='find_training_origins'
           for c in call['result']['candidates']}
    for call in receipt['calls']:
        if call['tool']=='rank_regression_origins':
            call['result']['ranking']=[r for r in call['result']['ranking'] if r['origin_id'] in ids]
    payload=sum(len(judge_mcp.model_result(c['result']).encode()) for c in receipt['calls'])
    schemas=len(json.dumps(receipt['mcp_tools']).encode())
    assert payload+schemas < 26000  # Leaves 6000 bytes for prompt, question, call wrappers.


def test_current_full_graph_tool_text_and_history_are_bounded():
    from pathlib import Path
    from ew import agent_context as AC
    from ew.mcp_server import create_server
    receipt=json.loads((Path(__file__).parents[1]/'evidence/mcp-agent-v3-retry/context-inputs.json').read_text())
    actual_tools=asyncio.run(create_server().list_tools())
    tools=[{'type':'function','function':{'name':t.name,'description':t.description,'parameters':t.input_schema}} for t in actual_tools]
    messages=[{'role':'system','content':'x'*4500},{'role':'user','content':'x'*800}]
    prior='outcome-deci-20261016121309-c0c93f'
    for i,c in enumerate(receipt['calls']):
        summary=AC.summarize(c['tool'],c['result'])
        text=AC.encode(summary)
        assert len(text.encode()) <= AC.TOOL_TEXT_BUDGET
        if c['tool']=='get_decision_outcomes':
            assert prior in text and summary['outcomes'][0]['suites'][0]['collision_delta']==1
        if c['tool']=='find_training_origins':
            assert summary['total_candidates']==len(c['result']['candidates'])
            assert summary['omitted_candidates']>0 and summary['candidates']
        messages += [{'role':'assistant','tool_calls':[{'id':str(i),'type':'function',
            'function':{'name':c['tool'],'arguments':json.dumps(c['args'])}}]},
            {'role':'tool','tool_call_id':str(i),'content':text}]
    # Repeated investigation history cannot accumulate without a cap.
    for i in range(30):
        messages += [{'role':'assistant','content':'Follow-up '+str(i),'tool_calls':[{'id':'extra'+str(i),
            'type':'function','function':{'name':'check_gate','arguments':'{}'}}]},
            {'role':'tool','tool_call_id':'extra'+str(i),'content':'x'*AC.TOOL_TEXT_BUDGET}]
    bounded,receipt=AC.bound_history(messages,tools)
    assert receipt['dropped_exchange_groups']>0
    assert receipt['tool_text_token_upper_bound']<=12000
    assert receipt['serialized_messages_and_tools_bytes']<28000
    assert prior in json.dumps(bounded)
    call_ids={c['id'] for m in bounded for c in m.get('tool_calls',[])}
    assert {m['tool_call_id'] for m in bounded if m['role']=='tool'}==call_ids


def test_large_graph_rows_and_strings_never_defeat_tool_bound():
    from ew import agent_context as AC
    source=json.loads((__import__('pathlib').Path(__file__).parents[1]/'evidence/mcp-agent-v3-retry/context-inputs.json').read_text())
    for c in source['calls']:
        result=c['result']
        for key in ('candidates','outcomes','ranking','ancestors','validation_and_failures'):
            if key in result:result[key]=result[key]*100
        assert len(AC.encode(AC.summarize(c['tool'],result)).encode())<=2000
    assert len(AC.encode(AC.summarize('get_evidence_record',{'record':{'id':'x','explanation':'🧪'*10000}})).encode())<=2000


def test_record_id_lookup_is_read_only_and_excludes_protected_evaluations(world):
    assert D.get_evidence_record('Policy','root')['record']['artifact_hash']=='fixture-root'
    assert D.get_evidence_record('Evaluation','root-val-target-v1')['record']['episodes']==60
    for kind,record in [('Secret','x'),('Evaluation','test-target-v1')]:
        with pytest.raises(ValueError):D.get_evidence_record(kind,record)
    flow=D.Workflow('bounded-read','owner',target='target')
    result=D.dispatch('diagnose_policy',{'policy_id':'target'},flow)
    assert result['bounded_tool_summary'] and 'queries' not in result
    assert flow.calls[-1]['result']['queries']  # Complete evidence remains in the Decision source.


def test_retry_guard_requires_explicit_prior_outcome_citation(world,monkeypatch):
    monkeypatch.setattr(D.public_training,'start',lambda *a,**k:pytest.fail('must veto'))
    flow=D.Workflow('retry-veto','owner',True,True,target='target',study_id='v3-retry')
    reads(flow)
    D.dispatch('get_decision_outcomes',{'target_policy':'target'},flow)
    D.dispatch('rank_regression_origins',{'target_policy':'target'},flow)
    result=D.dispatch('start_training',{'origin_id':'root','budget':60000,
                'reason':'root is the passing ancestor, but this fixture has no cited prior outcome'},flow)
    assert result['guardrail']['verdict']=='vetoed'
    assert any('outcome ID' in s for s in result['guardrail']['reasons'])


@pytest.mark.parametrize("study", ["v3-retry", "agent-mcp-v4"])
def test_retry_cannot_start_a_second_attempt(world,monkeypatch,study):
    # This fixture tests attempt reuse, independently of the real study deadline.
    monkeypatch.setattr(J.time, 'time', lambda: 1792173000.0)
    monkeypatch.setenv('EW_AGENT_STUDY',study)
    monkeypatch.setattr(J,'configuration',lambda:{'enabled':True,'provider':'fixture','model':'fixture'})
    monkeypatch.setattr(J.threading,'Thread',lambda **kw:SimpleNamespace(start=lambda:None))
    first=J.start('Choose once with recorded outcome',True,'one',True,True)
    stored=json.loads(J._path(first['id']).read_text());stored['state']='failed';J._path(first['id']).write_text(json.dumps(stored))
    with pytest.raises(J.Limited,match='already been used'):
        J.start('Choose once with recorded outcome',True,'two',True,True)


def test_v4_fresh_exclusion_veto_and_single_proposal(world, monkeypatch):
    monkeypatch.setattr(D.public_training, 'start', lambda *a,**k: pytest.fail('Excluded origin must not train'))
    flow=D.Workflow('v4-fixture','owner',True,True,target='target',study_id='agent-mcp-v4')
    reads(flow)
    prior='outcome-deci-20261016121309-c0c93f'
    flow.calls += [dict(tool='get_decision_outcomes',args={'target_policy':'target'},
                       result={'outcomes':[{'outcome':{'id':prior}}]}),
                   dict(tool='rank_regression_origins',args={'target_policy':'target'},result={})]
    # Agent saw a clean ranking; new evidence arrives before proposal.
    D.dispatch('rank_origins_excluding_regressed',{'target_policy':'target'},flow)
    db.rw("MATCH (a:Policy {id:'target'}),(b:Policy {id:'root'}) CREATE (a)-[:REGRESSED_AGAINST {outcome_id:$o}]->(b)",{'o':prior})
    saved=[]
    def record(workflow,guard,origin,budget,reason):
        saved.append(guard); workflow.decisions.append('fixture-v4-veto')
        return {'id':'fixture-v4-veto','guardrail':guard}
    monkeypatch.setattr(D,'_record',record)
    reason=f'root is the shortestPath ancestor. regression-lineage-exclusion-v1 cites {prior}.'
    result=D.dispatch('start_training',{'origin_id':'root','budget':60000,'reason':reason},flow)
    assert not result['training_started'] and saved[0]['verdict']=='vetoed'
    assert any('fresh graph' in s for s in saved[0]['reasons'])
    assert any('REGRESSED_AGAINST' in q['cypher'] for q in saved[0]['queries'])
    again=D.dispatch('start_training',{'origin_id':'root','budget':60000,'reason':reason},flow)
    assert 'sole v4 proposal' in again['error'] and len(saved)==1
