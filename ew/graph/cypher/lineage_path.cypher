MATCH (source:Policy {id:$from_policy}), (target:Policy {id:$to_policy})
CALL algo.SPpaths({sourceNode:source, targetNode:target,
                  relTypes:['DERIVED_FROM'], weightProp:'weight', maxLen:8, pathCount:1})
YIELD path, pathWeight
RETURN [n IN nodes(path) | n.id] AS path, pathWeight
LIMIT 1
