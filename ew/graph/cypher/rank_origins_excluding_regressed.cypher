UNWIND $origins AS verified
MATCH (target:Policy {id:$policy})-[:USES_CONTRACT]->(contract:Contract)<-[:USES_CONTRACT]-(origin:Policy {id:verified.id})
UNWIND $criteria AS criterion
MATCH (origin)<-[:ASSESSED]-(ev:Evaluation)-[:ON_SUITE]->(suite:Suite {id:criterion.suite_id})
WHERE ev.id IN verified.evaluations AND suite.role='validation' AND ev.complete_suite=true
  AND ev.artifact_hash=origin.artifact_hash AND ev.suite_fingerprint=suite.fingerprint
WITH origin, count(DISTINCT suite.id) AS suite_count,
     sum(CASE WHEN ev.success_rate < criterion.min_success OR ev.collision_rate > criterion.max_collision THEN 1 ELSE 0 END) AS failed_suites,
     min(criterion.max_collision-ev.collision_rate) AS collision_clearance
WHERE suite_count=$suite_count
MATCH path=(origin)-[:DERIVED_FROM*0..8]->(ancestor:Policy)
WITH origin, failed_suites, collision_clearance, ancestor, length(path) AS hops,
     [n IN nodes(path) | n.id] AS lineage_path
WHERE hops<=$max_hops
OPTIONAL MATCH (ancestor)-[reg:REGRESSED_AGAINST]-(other:Policy)
OPTIONAL MATCH (decision:Decision)-[:HAS_OUTCOME]->(outcome:DecisionOutcome)-[:ASSESSED]->(child:Policy)
WHERE outcome.release_verdict=$blocked_verdict AND (child=ancestor OR (decision)-[:SELECTED]->(ancestor))
OPTIONAL MATCH (ancestor)-[:DERIVED_FROM]->(beyond:Policy)
WHERE hops=$max_hops
WITH origin, failed_suites, collision_clearance,
     collect(DISTINCT CASE WHEN reg IS NULL THEN null ELSE {ancestor_id:ancestor.id, reason:'REGRESSED_AGAINST', outcome_id:reg.outcome_id, other_policy:other.id, path:lineage_path} END) AS edge_reasons,
     collect(DISTINCT CASE WHEN outcome IS NULL THEN null ELSE {ancestor_id:ancestor.id, reason:'not_released_regression', outcome_id:outcome.id, path:lineage_path} END) AS outcome_reasons,
     collect(DISTINCT beyond.id) AS unexamined_ancestors,
     collect(DISTINCT CASE WHEN beyond IS NULL THEN null ELSE {reason:'unexamined, excluded', outcome_id:null, path:lineage_path+[beyond.id]} END) AS unexamined_paths
WITH origin, failed_suites, collision_clearance, edge_reasons+outcome_reasons AS reasons, unexamined_ancestors, unexamined_paths
RETURN origin.id AS origin_id, failed_suites, collision_clearance, reasons, unexamined_ancestors, unexamined_paths,
       size(reasons)>0 OR size(unexamined_ancestors)>0 AS excluded
ORDER BY excluded, failed_suites, collision_clearance DESC, origin_id
