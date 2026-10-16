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
ORDER BY decision_id DESC LIMIT 40
