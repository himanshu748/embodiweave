"""Bounded, parameterized read templates. All run through GRAPH.RO_QUERY.

Each call returns a QueryResult that carries the template name, exact Cypher, parameters, returned
rows, the record ids they reference and the graph revision, so a decision can cite exactly what it
was based on. No template can read final-test outcomes: those are never ingested into the decision
graph, and suite filters additionally require role = 'validation'.
"""
from __future__ import annotations

from pathlib import Path

from dataclasses import asdict, dataclass, field

from . import db

TEMPLATES = {
    "mcp_lineage_path": (Path(__file__).parent / "cypher/lineage_path.cypher").read_text(),
    "mcp_resolve_policy": "MATCH (p:Policy {id:$policy}) RETURN p.id AS policy_id LIMIT 1",
    "mcp_origins_excluding_regressed": (Path(__file__).parent / "cypher/rank_origins_excluding_regressed.cypher").read_text(),
    "mcp_evidence_record": """
MATCH (n {id:$id}) WHERE $kind IN labels(n)
OPTIONAL MATCH (n)-[:ON_SUITE]->(s:Suite)
WITH n,s WHERE $kind <> 'Evaluation' OR (s.role='validation' AND s.id IN $suites)
RETURN properties(n) AS record LIMIT 1""",
    "mcp_decision_outcomes": """
MATCH (target:Policy {id:$policy})-[:USES_CONTRACT]->(contract:Contract)<-[:USES_CONTRACT]-(origin:Policy)
MATCH (d:Decision)-[:SELECTED]->(origin), (d)-[:LAUNCHED]->(run:Run)-[:PRODUCED]->(child:Policy)
MATCH (d)-[:HAS_OUTCOME]->(o:DecisionOutcome)-[:ASSESSED]->(child)
MATCH (child)-[comparison:COMPARED_AGAINST {outcome_id:o.id}]->(origin)
MATCH (o)-[:BASED_ON]->(ev:Evaluation)-[:ON_SUITE]->(suite:Suite)
WHERE comparison.parent_hash=origin.artifact_hash AND comparison.child_hash=child.artifact_hash
  AND suite.role='validation' AND suite.id IN $suites
  AND ev.complete_suite=true AND ev.suite_fingerprint=suite.fingerprint
RETURN d.id AS decision_id, origin.id AS origin_id, run.id AS run_id, child.id AS child_id,
       properties(o) AS outcome, collect(DISTINCT ev.id) AS evaluation_ids
ORDER BY decision_id DESC LIMIT 40""",
    "mcp_regression_degree": """
MATCH (target:Policy {id:$policy})-[:USES_CONTRACT]->(contract:Contract)<-[:USES_CONTRACT]-(origin:Policy)
WHERE origin.id IN $origins
OPTIONAL MATCH (child:Policy)-[edge:COMPARED_AGAINST]->(origin)
WHERE edge.parent_hash=origin.artifact_hash AND edge.child_hash=child.artifact_hash
RETURN origin.id AS origin_id, count(edge) AS observed_children,
       CASE WHEN count(edge)=0 THEN null ELSE sum(edge.weight) END AS weighted_regression_degree,
       collect(child.id) AS children
ORDER BY weighted_regression_degree DESC, origin_id LIMIT 100""",

    "mcp_policy": """
MATCH (p:Policy {id:$policy})-[:USES_CONTRACT]->(c:Contract)-[:FOR_ROBOT]->(r:Robot)
RETURN p.id AS policy_id, p.artifact_hash AS artifact_hash, p.status AS status,
       c.id AS contract_id, r.id AS robot_id LIMIT 1""",
    "mcp_diagnosis": """
MATCH (p:Policy {id:$policy})<-[:ASSESSED]-(e:Evaluation)-[:ON_SUITE]->(s:Suite)
WHERE s.role = 'validation' AND s.id IN $suites AND e.complete_suite = true
  AND e.artifact_hash = p.artifact_hash AND e.suite_fingerprint = s.fingerprint
OPTIONAL MATCH (f:Failure)-[:OBSERVED_IN]->(e)
RETURN p.id AS policy_id, e.id AS evaluation_id, s.id AS suite_id, e.episodes AS episodes,
       e.success_rate AS success_rate, e.collision_rate AS collision_rate,
       f.id AS failure_id, f.hit AS hit, f.count AS count ORDER BY suite_id, evaluation_id LIMIT 200""",
    "mcp_lineage": """
MATCH path=(p:Policy {id:$policy})-[:DERIVED_FROM*1..8]->(a:Policy)
WHERE length(path) <= $max_hops
RETURN a.id AS ancestor_id, a.artifact_hash AS artifact_hash, length(path) AS hops,
       [n IN nodes(path) | n.id] AS path ORDER BY hops, ancestor_id LIMIT 100""",
    "mcp_nearest_passing_ancestor": """
MATCH (p:Policy {id:$policy})-[:USES_CONTRACT]->(c:Contract)<-[:USES_CONTRACT]-(a:Policy)
WITH p,a,shortestPath((p)-[:DERIVED_FROM*1..8]->(a)) AS path
WHERE path IS NOT NULL AND length(path) <= $max_hops AND a.status = 'completed'
MATCH (a)<-[:ASSESSED]-(e:Evaluation)-[:ON_SUITE]->(s:Suite {id:$suite})
WHERE s.role = 'validation' AND e.complete_suite = true AND e.artifact_hash = a.artifact_hash
  AND e.suite_fingerprint = s.fingerprint AND e.success_rate >= $min_success
  AND e.collision_rate <= $max_collision
RETURN a.id AS ancestor_id, a.artifact_hash AS artifact_hash, length(path) AS hops,
       [n IN nodes(path) | n.id] AS path, e.id AS evaluation_id,
       e.success_rate AS success_rate, e.collision_rate AS collision_rate
ORDER BY hops, collision_rate, ancestor_id LIMIT 20""",
    "mcp_decision": """
MATCH (d:Decision {id:$decision}) RETURN properties(d) AS decision LIMIT 1""",
    "mujoco_transfer": """
MATCH (p:Policy)<-[:ASSESSED]-(e:Evaluation)-[:ON_SUITE]->(s:Suite)
WHERE s.role = 'sim2sim' AND s.physics = 'mujoco'
  AND e.artifact_hash = p.artifact_hash AND e.complete_suite = true
  AND e.suite_fingerprint = s.fingerprint
OPTIONAL MATCH (p)-[:DERIVED_FROM*1..8]->(ancestor:Policy)
RETURN p.id AS policy_id, p.artifact_hash AS artifact_hash, s.id AS suite_id,
       e.id AS evaluation_id, e.episodes AS episodes, e.success_rate AS success_rate,
       e.collision_rate AS collision_rate, e.timeout_rate AS timeout_rate,
       collect(DISTINCT ancestor.id) AS lineage
ORDER BY suite_id, policy_id LIMIT 100""",

    "search_lineage": """
MATCH (d:Decision {rule_version:$rule})-[:SELECTED]->(parent:Policy)
MATCH (d)-[:LAUNCHED]->(r:Run)-[:PRODUCED]->(child:Policy)
MATCH (t:Trial)-[:VIA_RUN]->(r)
MATCH (gate:Promotion)-[:FOR]->(child)
MATCH (d)-[:BASED_ON]->(e:Evaluation)-[:ON_SUITE]->(s:Suite)
WHERE s.role = 'validation' AND (e)-[:ASSESSED]->(parent) AND e.artifact_hash = parent.artifact_hash
RETURN d.id AS decision, parent.id AS origin, t.intervention AS intervention,
       s.id AS evidence_suite, e.success_rate AS origin_success, e.collision_rate AS origin_collisions,
       child.id AS candidate, gate.verdict AS verdict, d.explanation AS rationale
ORDER BY decision, evidence_suite LIMIT 100""",

    "study_origins": """
MATCH (d:Decision {rule_version:$rule})-[rank:CONSIDERED]->(option:Policy)
MATCH (d)-[:SELECTED]->(origin:Policy)
MATCH (d)-[:LAUNCHED]->(r:Run)-[:PRODUCED]->(child:Policy)
MATCH (t:Trial)-[:VIA_RUN]->(r)
MATCH (gate:Promotion)-[:FOR]->(child)
WHERE gate.artifact_hash = child.artifact_hash
RETURN d.id AS decision, d.rule_version AS rule, d.graph_revision AS decision_revision,
       option.id AS option, option.recipe AS option_recipe, rank.rank AS rank, rank.key AS ranking_key,
       origin.id AS origin, r.id AS run, t.id AS trial, t.intervention AS intervention,
       child.id AS candidate, child.artifact_hash AS artifact_hash,
       gate.id AS promotion, gate.verdict AS verdict, d.explanation AS rationale
ORDER BY decision, rank LIMIT 100""",

    "physics_lineage": """
MATCH (d:Decision)-[:SELECTED]->(parent:Policy)
MATCH (d)-[:LAUNCHED]->(r:Run)-[:PRODUCED]->(child:Policy)
MATCH (t:Trial)-[:VIA_RUN]->(r)
MATCH (gate:Promotion)-[:FOR]->(child)
MATCH (d)-[:BASED_ON]->(e:Evaluation)-[:ON_SUITE]->(s:Suite)
WHERE d.rule_version IN ['physics-adapt-v1','physics-followup-v1']
  AND s.role = 'validation' AND (e)-[:ASSESSED]->(parent) AND e.artifact_hash = parent.artifact_hash
RETURN d.id AS decision, parent.id AS origin, t.intervention AS intervention,
       s.id AS evidence_suite, e.success_rate AS origin_success, e.collision_rate AS origin_collisions,
       child.id AS candidate, gate.verdict AS verdict, d.explanation AS rationale
ORDER BY decision, evidence_suite LIMIT 100""",

    "search_validation": """
MATCH (p:Policy)-[:USES_CONTRACT]->(:Contract {id:$contract})
MATCH (e:Evaluation)-[:ASSESSED]->(p)
MATCH (e)-[:ON_SUITE]->(s:Suite)
WHERE p.status = 'completed' AND s.role = 'validation' AND s.id IN $suites
  AND e.complete_suite = true AND e.artifact_hash = p.artifact_hash AND e.suite_fingerprint = s.fingerprint
RETURN p.id AS policy_id, p.artifact_hash AS artifact_hash, s.id AS suite_id,
       e.id AS evaluation_id, e.success_rate AS success_rate, e.collision_rate AS collision_rate,
       e.timeout_rate AS timeout_rate, e.at AS at
ORDER BY policy_id, suite_id, at LIMIT 2000""",

    "search_history": """
MATCH (t:Trial)-[:UNDER_CONTRACT]->(:Contract {id:$contract})
WHERE t.search_rule = $rule AND t.measured = true AND coalesce(t.hypothetical, false) = false
OPTIONAL MATCH (t)-[:PRODUCED]->(p:Policy)
OPTIONAL MATCH (g:Promotion)-[:FOR]->(p)
RETURN t.id AS trial_id, t.intervention AS intervention, t.status AS status,
       p.id AS child_id, g.verdict AS verdict ORDER BY trial_id LIMIT 200""",

    "mission_requirements": """
MATCH (m:Mission {id:$mission})-[:REQUIRES*1..6]->(c:Competency)
OPTIONAL MATCH (s:Suite)-[:EVALUATES]->(c) WHERE s.role = 'validation'
RETURN DISTINCT c.id AS competency, s.id AS suite_id
ORDER BY competency""",

    "candidate_eligibility": """
MATCH (tc:Contract {id:$contract})-[:FOR_ROBOT]->(tr:Robot {id:$robot})
MATCH (p:Policy)-[:USES_CONTRACT]->(pc:Contract)-[:FOR_ROBOT]->(pr:Robot)
OPTIONAL MATCH (run:Run)-[:PRODUCED]->(p)
RETURN p.id AS policy_id, p.artifact_hash AS artifact_hash, p.status AS status, p.created_at AS created_at,
       run.kind AS run_kind, pc.id AS contract_id, pr.id AS robot_id,
       pc.id = tc.id AS contract_match, pr.id = tr.id AS robot_match,
       [k IN ['ray_order','n_rays','history','history_reset','dt_s','action_map','normalization'] WHERE pc[k] <> tc[k]] AS differing_fields
ORDER BY created_at
LIMIT 200""",

    "candidate_ancestry": """
UNWIND $ids AS pid
MATCH (p:Policy {id:pid})
MATCH path = (p)-[:DERIVED_FROM*0..8]->(a:Policy)
OPTIONAL MATCH (run:Run)-[:PRODUCED]->(a)
OPTIONAL MATCH (run)-[:TRAINED_ON]->(f:Family)
RETURN pid AS policy_id, length(path) AS depth, a.id AS ancestor_id, a.artifact_hash AS ancestor_hash,
       run.id AS run_id, run.kind AS run_kind, f.name AS trained_on, run.consumed AS steps
ORDER BY policy_id, depth""",

    "matched_validation": """
MATCH (s:Suite {id:$suite}) WHERE s.role = 'validation'
UNWIND $ids AS pid
MATCH (p:Policy {id:pid})
OPTIONAL MATCH (e:Evaluation)-[:ASSESSED]->(p)
WHERE (e)-[:ON_SUITE]->(s) AND e.artifact_hash = p.artifact_hash AND e.complete_suite = true AND e.suite_fingerprint = s.fingerprint
RETURN pid AS policy_id, p.artifact_hash AS artifact_hash, e.id AS evaluation_id,
       e.success_rate AS success_rate, e.collision_rate AS collision_rate, e.timeout_rate AS timeout_rate,
       e.episodes AS episodes, e.at AS at
ORDER BY policy_id, at""",

    "relevant_trials": """
UNWIND $ids AS pid
MATCH (p:Policy {id:pid})
OPTIONAL MATCH (t:Trial)-[:FROM_PARENT]->(p)
WHERE t.threshold_id = $threshold AND t.recipe = $recipe AND t.budget = $budget
  AND (t)-[:TARGETS]->(:Family {id:$family})
  AND (t)-[:UNDER_CONTRACT]->(:Contract {id:$contract})
OPTIONAL MATCH (t)-[:PRODUCED]->(child:Policy)
RETURN pid AS policy_id, t.id AS trial_id, t.status AS status, t.threshold_reached AS reached,
       t.steps_to_threshold AS steps_to_threshold, t.consumed AS consumed, t.budget AS budget,
       t.seed AS seed, child.id AS child_id, coalesce(t.hypothetical, false) AS hypothetical
ORDER BY policy_id, trial_id""",

    "scratch_trials": """
MATCH (o:Origin {id:'scratch'})
OPTIONAL MATCH (t:Trial)-[:FROM_ORIGIN]->(o)
WHERE t.threshold_id = $threshold AND t.recipe = $recipe AND t.budget = $budget
  AND (t)-[:TARGETS]->(:Family {id:$family})
  AND (t)-[:UNDER_CONTRACT]->(:Contract {id:$contract})
RETURN t.id AS trial_id, t.status AS status, t.threshold_reached AS reached,
       t.steps_to_threshold AS steps_to_threshold, t.consumed AS consumed, t.seed AS seed,
       coalesce(t.hypothetical, false) AS hypothetical
ORDER BY trial_id""",

    "trial_outcomes": """
UNWIND $trial_ids AS tid
MATCH (t:Trial {id:tid})-[:PRODUCED]->(c:Policy)
MATCH (s:Suite {id:$suite}) WHERE s.role = 'validation'
OPTIONAL MATCH (e:Evaluation)-[:ASSESSED]->(c)
WHERE (e)-[:ON_SUITE]->(s) AND e.artifact_hash = c.artifact_hash AND e.complete_suite = true AND e.suite_fingerprint = s.fingerprint
RETURN tid AS trial_id, c.id AS child_id, e.id AS evaluation_id, e.success_rate AS success_rate,
       e.collision_rate AS collision_rate, e.at AS at
ORDER BY trial_id, at""",

    "non_applicable_trials": """
UNWIND $ids AS pid
MATCH (t:Trial)-[:FROM_PARENT]->(p:Policy {id:pid})
MATCH (t)-[:TARGETS]->(f:Family)
WHERE NOT (f.id = $family AND t.threshold_id = $threshold AND t.recipe = $recipe AND t.budget = $budget)
RETURN pid AS policy_id, t.id AS trial_id, f.name AS target, t.budget AS budget, t.threshold_reached AS reached""",

    "failure_inspection": """
MATCH (e:Evaluation {id:$evaluation})-[:ASSESSED]->(p:Policy)
MATCH (e)-[:ON_SUITE]->(s:Suite)
OPTIONAL MATCH (f:Failure)-[:OBSERVED_IN]->(e)
OPTIONAL MATCH (h:Hypothesis)-[:ABOUT]->(f)
OPTIONAL MATCH (h)-[:SUGGESTS]->(c:Competency)
RETURN p.id AS policy_id, s.id AS suite_id, e.success_rate AS success_rate, e.collision_rate AS collision_rate,
       f.id AS failure_id, f.outcome AS outcome, f.hit AS hit, f.count AS count, f.episodes AS episodes,
       h.id AS hypothesis_id, h.text AS hypothesis, c.id AS suggests_competency""",

    "promotion_evidence": """
MATCH (p:Policy {id:$policy})
UNWIND $suites AS sid
MATCH (s:Suite {id:sid}) WHERE s.role = 'validation'
OPTIONAL MATCH (e:Evaluation)-[:ASSESSED]->(p)
WHERE (e)-[:ON_SUITE]->(s) AND e.artifact_hash = $hash AND e.complete_suite = true AND e.suite_fingerprint = s.fingerprint
RETURN sid AS suite_id, p.artifact_hash AS policy_hash, e.id AS evaluation_id, e.artifact_hash AS evaluated_hash,
       e.success_rate AS success_rate, e.collision_rate AS collision_rate, e.episodes AS episodes, e.at AS at
ORDER BY suite_id, at""",

    "decision_provenance": """
MATCH (d:Decision {id:$decision})
OPTIONAL MATCH (d)-[c:CONSIDERED]->(p:Policy)
OPTIONAL MATCH (d)-[:SELECTED]->(sel:Policy)
OPTIONAL MATCH (d)-[:LAUNCHED]->(r:Run)-[:PRODUCED]->(child:Policy)
OPTIONAL MATCH (t:Trial)-[:VIA_RUN]->(r)
RETURN d.id AS decision_id, d.rule_version AS rule, d.graph_revision AS revision, d.action AS action,
       sel.id AS selected, collect(DISTINCT [p.id, c.rank]) AS considered, r.id AS run_id, child.id AS child_id,
       t.threshold_reached AS reached, t.steps_to_threshold AS steps_to_threshold""",

    "policy_lineage_graph": """
MATCH (p:Policy)
OPTIONAL MATCH (p)-[:DERIVED_FROM]->(q:Policy)
OPTIONAL MATCH (p)-[:USES_CONTRACT]->(c:Contract)
RETURN p.id AS id, p.status AS status, p.family AS family, q.id AS parent, c.id AS contract""",
}


@dataclass
class QueryResult:
    template: str
    cypher: str
    params: dict
    header: list
    rows: list
    graph: str
    graph_revision: int
    ms: float
    record_ids: list = field(default_factory=list)

    def dicts(self) -> list[dict]:
        return [dict(zip(self.header, r)) for r in self.rows]

    def to_log(self) -> dict:
        return asdict(self)


_ID_COLS = {"policy_id", "evaluation_id", "trial_id", "child_id", "ancestor_id", "run_id", "failure_id",
            "hypothesis_id", "decision_id", "competency", "suite_id", "selected"}


def run(template: str, params: dict, graph_name: str | None = None) -> QueryResult:
    if template not in TEMPLATES:
        raise KeyError(f"unknown read template {template}")
    cy = TEMPLATES[template].strip()
    header, rows, ms = db.ro(cy, params, graph_name)
    hdr = [h[1] if isinstance(h, (list, tuple)) else h for h in header]
    hdr = [h.decode() if isinstance(h, bytes) else h for h in hdr]
    ids = sorted({str(v) for r in rows for h, v in zip(hdr, r) if h in _ID_COLS and v is not None})
    return QueryResult(template, cy, params, hdr, rows, graph_name or db.GRAPH, db.revision(graph_name), ms, ids)
