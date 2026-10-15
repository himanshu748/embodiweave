"""Transfer measurements remain visible but can never satisfy promo-1."""
import hashlib
import json
import pytest

from ew.graph import db, ingest, queries, transfer
from ew.scenarios import FAMILIES


@pytest.fixture
def transfer_fixture(tmp_path):
    g = "ew_test_transfer_boundary"
    db.delete_graph(g)
    ingest.init_world(g)
    db.rw("CREATE (:Policy {id:'transfer-policy', artifact_hash:'unchanged', status:'completed'})", graph_name=g)
    p = {"role": "sim2sim", "physics": "mujoco", "suites": [{"id": "sim2sim-unit", "family": "open", "seeds": [5100000]}]}
    ph = hashlib.sha256(json.dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    e = {"id": "transfer-eval", "protocol_hash": ph, "suite_id": "sim2sim-unit", "policy_id": "transfer-policy",
         "artifact_hash": "unchanged", "suite_fingerprint": "unit-fingerprint", "contract_id": "unit-contract",
         "episodes": [{"seed": 5100000, "outcome": "collision", "hit": "mover"}],
         "summary": {"episodes": 1, "success": 0, "collision": 1, "timeout": 0,
                     "success_rate": 0., "collision_rate": 1., "timeout_rate": 0.}}
    for name, value in [("protocol.json", p), ("unit.json", e), ("summary.json", {"results": []})]:
        (tmp_path / name).write_text(json.dumps(value))
    (tmp_path / "checksums.json").write_text(json.dumps({f.name: transfer.sha(f) for f in tmp_path.glob("*.json")}))
    yield tmp_path, g
    db.delete_graph(g)


def test_ingest_is_idempotent_queryable_and_excluded_from_gate(transfer_fixture):
    root, g = transfer_fixture
    assert transfer.ingest(root, g) == 1
    assert transfer.ingest(root, g) == 1
    result = queries.run("mujoco_transfer", {}, g).dicts()
    assert len(result) == 1 and result[0]["collision_rate"] == 1
    assert queries.run("promotion_evidence", {"policy": "transfer-policy", "hash": "unchanged", "suites": ["sim2sim-unit"]}, g).rows == []
    assert db.ro("MATCH (f:Failure)-[:OBSERVED_IN]->(:Evaluation {id:'transfer-eval'}) RETURN f.count", graph_name=g)[1] == [[1]]
    assert db.ro("MATCH (:Threshold)-[:MEASURED_ON]->(:Suite {id:'sim2sim-unit'}) RETURN count(*)", graph_name=g)[1] == [[0]]


def test_tampered_or_unsigned_evidence_fails_before_ingestion(transfer_fixture):
    root, g = transfer_fixture
    (root / "unsigned.json").write_text("{}")
    with pytest.raises(ValueError, match="Unsigned"):
        transfer.ingest(root, g)
    (root / "unsigned.json").unlink()
    (root / "unit.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        transfer.ingest(root, g)
