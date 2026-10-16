"""Hosted read-only mode and the landing page's live graph endpoints."""
from fastapi.testclient import TestClient

from ew import api, records
from ew.graph import db, ingest, queries


def test_hosted_mode_refuses_training_but_serves_live_reads(monkeypatch):
    db.delete_graph("ew_test")
    ingest.init_world()
    c = TestClient(api.app)
    monkeypatch.setattr(api, "STATIC_MODE", True)
    for path in ("/api/train", "/api/evaluate", "/api/promote/P-x", "/api/export/P-x", "/api/scenario_eval"):
        r = c.post(path, json={})
        assert r.status_code == 403 and r.json()["error"] == "hosted_demo_readonly", path
    o = c.get("/api/live/overview").json()
    assert o["via"] == "GRAPH.RO_QUERY" and o["node_total"] > 0
    assert sum(n["n"] for n in o["nodes"]) == o["node_total"]
    # this artifacts directory holds no featured agent run: say so instead of inventing rows
    assert c.get("/api/live/query/transfer").status_code == 404
    assert c.get("/api/live/featured").status_code == 404
    lineage = c.get("/api/search/lineage").json()
    assert lineage["via"] == "GRAPH.RO_QUERY" and lineage["rows"] == []
    assert lineage["params"] == {"rule": "search-v1"}
    current = c.get("/api/robustness/lineage").json()
    assert current["origins"]["params"] == {"rule": "robustness-v2"}
    assert current["origins"]["rows"] == []
    imported = records.write("decision", {"mode":"deterministic", "graph":"source-validation-graph",
        "rule_version":"search-v1", "graph_revision":1, "action":"train_from_scratch", "selected":None,
        "request":{"target_family_id":"static_crossing"}, "ranking":[], "rejected":[]})
    ingest.decision(imported)
    sub = c.get(f"/api/subgraph/{imported['id']}")
    assert sub.status_code == 200 and any(n["label"] == "Decision" for n in sub.json()["nodes"])
    monkeypatch.setattr(api, "STATIC_MODE", False)
    assert c.post("/api/train", json={}).status_code != 403
    db.delete_graph("ew_test")


def test_stored_origin_ranking_preserves_decision_revision_and_exact_gate_hash():
    graph = "ew_test_origins"
    db.delete_graph(graph)
    try:
        db.rw("CREATE (d:Decision {id:'d',rule_version:'robustness-v2',graph_revision:3,explanation:'recorded reason'}), "
              "(p:Policy {id:'parent'}), (other:Policy {id:'other'}), "
              "(r:Run {id:'run'}), (c:Policy {id:'child',artifact_hash:'exact'}), "
              "(t:Trial {id:'trial',intervention:'collision'}), "
              "(g:Promotion {id:'gate',artifact_hash:'exact',verdict:'promoted'}), "
              "(d)-[:SELECTED]->(p), (d)-[:LAUNCHED]->(r), (r)-[:PRODUCED]->(c), "
              "(t)-[:VIA_RUN]->(r), (g)-[:FOR]->(c), "
              "(d)-[:CONSIDERED {rank:2,key:'[1,1]'}]->(other), "
              "(d)-[:CONSIDERED {rank:1,key:'[0,2]'}]->(p)", graph_name=graph)
        result = queries.run("study_origins", {"rule": "robustness-v2"}, graph)
        rows = result.dicts()
        assert [r["option"] for r in rows] == ["parent", "other"]
        assert [r["ranking_key"] for r in rows] == ["[0,2]", "[1,1]"]
        assert all(r["decision_revision"] == 3 and r["artifact_hash"] == "exact" for r in rows)
        assert all(r["run"] == "run" and r["trial"] == "trial" and r["promotion"] == "gate" for r in rows)
        assert queries.run("study_origins", {"rule": "another-study"}, graph).rows == []
        db.rw("MATCH (g:Promotion) SET g.artifact_hash='stale'", graph_name=graph)
        assert queries.run("study_origins", {"rule": "robustness-v2"}, graph).rows == []
    finally:
        db.delete_graph(graph)
