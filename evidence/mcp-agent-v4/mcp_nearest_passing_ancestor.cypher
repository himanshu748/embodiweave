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
ORDER BY hops, collision_rate, ancestor_id LIMIT 20
