"""Hosted read-only mode and the landing page's live graph endpoints."""
from fastapi.testclient import TestClient

from ew import api, records
from ew.graph import db, ingest


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
    imported = records.write("decision", {"mode":"deterministic", "graph":"source-validation-graph",
        "rule_version":"search-v1", "graph_revision":1, "action":"train_from_scratch", "selected":None,
        "request":{"target_family_id":"static_crossing"}, "ranking":[], "rejected":[]})
    ingest.decision(imported)
    sub = c.get(f"/api/subgraph/{imported['id']}")
    assert sub.status_code == 200 and any(n["label"] == "Decision" for n in sub.json()["nodes"])
    monkeypatch.setattr(api, "STATIC_MODE", False)
    assert c.post("/api/train", json={}).status_code != 403
    db.delete_graph("ew_test")
