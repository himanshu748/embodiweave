MATCH (p:Policy {id:$policy})-[:USES_CONTRACT]->(c:Contract)-[:FOR_ROBOT]->(r:Robot)
RETURN p.id AS policy_id, p.artifact_hash AS artifact_hash, p.status AS status,
       c.id AS contract_id, r.id AS robot_id LIMIT 1
