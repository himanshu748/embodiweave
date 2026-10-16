MATCH (p:Policy {id:$policy})<-[:ASSESSED]-(e:Evaluation)-[:ON_SUITE]->(s:Suite)
WHERE s.role = 'validation' AND s.id IN $suites AND e.complete_suite = true
  AND e.artifact_hash = p.artifact_hash AND e.suite_fingerprint = s.fingerprint
OPTIONAL MATCH (f:Failure)-[:OBSERVED_IN]->(e)
RETURN p.id AS policy_id, e.id AS evaluation_id, s.id AS suite_id, e.episodes AS episodes,
       e.success_rate AS success_rate, e.collision_rate AS collision_rate,
       f.id AS failure_id, f.hit AS hit, f.count AS count ORDER BY suite_id, evaluation_id LIMIT 200
