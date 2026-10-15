# EmbodiWeave

Robot policies fail in specific situations, but choosing the next training run
often means searching scattered checkpoints and experiment logs. EmbodiWeave
connects that evidence so an agent can choose a training origin and explain why.

FalkorDB stores semantic sensor/action contracts, checkpoint lineage, adaptation
trials, complete evaluations, object-level failures and promotion verdicts.
Parameterized Cypher follows those relationships to reject incompatible artifacts,
rank training origins and identify the next untried intervention. Decisions record
the queries, returned evidence and graph revision before training. Planning stops
when FalkorDB is unavailable. Final-test results stay outside the decision graph.

The webpage lets judges run real CPU PPO, watch actual simulator states in 2D or
3D, evaluate the saved checkpoint on 180 validation episodes and download a
checksummed evidence bundle. A recorded walkthrough remains available when the
shared trainer or free model provider is busy.

Our new validation-only search ran two attempts at a fixed seed. Longer training
passed three of four suites but retained open-arena failures. The graph-driven
planner then selected that child and rehearsed earlier training families. That
lineage passed all four unchanged validation gates, including 95% target success
and 5% target collisions.

The single held-out target evaluation was weaker: 86% success, 13% collisions,
1% timeout. It failed the 10% collision limit. We stopped selection before that
test and did no further tuning. Rejections remain visible and production weights
are unchanged.

Next: preregister independent training seeds, improve dynamic-obstacle behavior,
and run a fresh sealed generalization study. This is a simulated research
prototype; it does not establish real robot safety or a training-efficiency advantage.
