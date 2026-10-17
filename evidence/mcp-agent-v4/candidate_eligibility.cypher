MATCH (tc:Contract {id:$contract})-[:FOR_ROBOT]->(tr:Robot {id:$robot})
MATCH (p:Policy)-[:USES_CONTRACT]->(pc:Contract)-[:FOR_ROBOT]->(pr:Robot)
OPTIONAL MATCH (run:Run)-[:PRODUCED]->(p)
RETURN p.id AS policy_id, p.artifact_hash AS artifact_hash, p.status AS status, p.created_at AS created_at,
       run.kind AS run_kind, pc.id AS contract_id, pr.id AS robot_id,
       pc.id = tc.id AS contract_match, pr.id = tr.id AS robot_match,
       [k IN ['ray_order','n_rays','history','history_reset','dt_s','action_map','normalization'] WHERE pc[k] <> tc[k]] AS differing_fields
ORDER BY created_at
LIMIT 200
