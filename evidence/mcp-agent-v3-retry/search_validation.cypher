MATCH (p:Policy)-[:USES_CONTRACT]->(:Contract {id:$contract})
MATCH (e:Evaluation)-[:ASSESSED]->(p)
MATCH (e)-[:ON_SUITE]->(s:Suite)
WHERE p.status = 'completed' AND s.role = 'validation' AND s.id IN $suites
  AND e.complete_suite = true AND e.artifact_hash = p.artifact_hash AND e.suite_fingerprint = s.fingerprint
RETURN p.id AS policy_id, p.artifact_hash AS artifact_hash, s.id AS suite_id,
       e.id AS evaluation_id, e.success_rate AS success_rate, e.collision_rate AS collision_rate,
       e.timeout_rate AS timeout_rate, e.at AS at
ORDER BY policy_id, suite_id, at LIMIT 2000
