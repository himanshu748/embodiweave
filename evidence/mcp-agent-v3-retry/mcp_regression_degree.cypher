MATCH (target:Policy {id:$policy})-[:USES_CONTRACT]->(contract:Contract)<-[:USES_CONTRACT]-(origin:Policy)
WHERE origin.id IN $origins
OPTIONAL MATCH (child:Policy)-[edge:COMPARED_AGAINST]->(origin)
WHERE edge.parent_hash=origin.artifact_hash AND edge.child_hash=child.artifact_hash
RETURN origin.id AS origin_id, count(edge) AS observed_children,
       CASE WHEN count(edge)=0 THEN null ELSE sum(edge.weight) END AS weighted_regression_degree,
       collect(child.id) AS children
ORDER BY weighted_regression_degree DESC, origin_id LIMIT 100
