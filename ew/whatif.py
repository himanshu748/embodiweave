"""Isolated What-if graph copies (GRAPH.COPY). Production evidence is never modified.

Interventions are written only to a graph named ew_whatif_<id>, are flagged hypothetical=true /
measured=false, and decisions made there carry mode='what-if'. They cannot launch training.
"""
from __future__ import annotations

import uuid

from . import records
from .graph import db

PREFIX = "ew_whatif_"


def fingerprint(graph_name: str | None = None) -> dict:
    _, rows, _ = db.ro("MATCH (n) RETURN labels(n)[0] AS l, count(n) AS c ORDER BY l", graph_name=graph_name)
    _, trows, _ = db.ro("MATCH (t:Trial) RETURN t.id, t.threshold_reached, t.steps_to_threshold ORDER BY t.id", graph_name=graph_name)
    _, erows, _ = db.ro("MATCH (p:Policy)-[:USES_CONTRACT]->(c:Contract) RETURN p.id, c.id ORDER BY p.id", graph_name=graph_name)
    return {"revision": db.revision(graph_name), "counts": {r[0]: r[1] for r in rows},
            "trials": [list(r) for r in trows], "contracts": [list(r) for r in erows]}


def create() -> str:
    name = PREFIX + uuid.uuid4().hex[:8]
    db.copy_graph(db.GRAPH, name)
    db.rw("MATCH (m:Meta {id:'meta'}) SET m.whatif = true, m.copied_from_revision = m.revision", graph_name=name)
    return name


def _guard(graph_name: str):
    if not graph_name.startswith(PREFIX):
        raise PermissionError("What-if interventions are only allowed on isolated ew_whatif_* copies")


def add_hypothetical_trial(graph_name: str, parent_id: str, target_family_id: str, contract_id: str,
                           threshold_id: str, recipe: str, budget: int, reached: bool,
                           steps_to_threshold: int | None = None) -> str:
    _guard(graph_name)
    tid = "hyp-trial-" + uuid.uuid4().hex[:6]
    db.rw("MATCH (p:Policy {id:$pid}), (f:Family {id:$fid}), (c:Contract {id:$cid}) "
          "CREATE (t:Trial {id:$id, status:'completed', threshold_id:$thr, recipe:$rec, budget:$b, consumed:$b, "
          "threshold_reached:$r, steps_to_threshold:$stt, hypothetical:true, measured:false}) "
          "CREATE (t)-[:FROM_PARENT]->(p), (t)-[:TARGETS]->(f), (t)-[:UNDER_CONTRACT]->(c)",
          {"pid": parent_id, "fid": target_family_id, "cid": contract_id, "id": tid, "thr": threshold_id,
           "rec": recipe, "b": budget, "r": reached, "stt": steps_to_threshold if reached else None}, graph_name)
    db.bump_revision(f"what-if hypothetical trial {tid}", graph_name)
    return tid


def set_hypothetical_contract(graph_name: str, policy_id: str, contract_id: str) -> None:
    """Pretend a checkpoint was built under another contract (a compatibility-fact intervention)."""
    _guard(graph_name)
    db.rw("MATCH (p:Policy {id:$pid})-[u:USES_CONTRACT]->() DELETE u", {"pid": policy_id}, graph_name)
    db.rw("MATCH (p:Policy {id:$pid}), (c:Contract {id:$cid}) CREATE (p)-[:USES_CONTRACT {hypothetical:true}]->(c)",
          {"pid": policy_id, "cid": contract_id}, graph_name)
    db.bump_revision(f"what-if contract {policy_id}->{contract_id}", graph_name)


def drop(graph_name: str) -> None:
    _guard(graph_name)
    db.delete_graph(graph_name)
