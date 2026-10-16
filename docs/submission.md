# EmbodiWeave

I built EmbodiWeave to answer two recurring robotics questions: which checkpoint
should I retrain, and has the saved result earned deployment?

FalkorDB connects checkpoints to semantic sensor/action contracts, training
origins, adaptation trials, complete evaluations, object-level failures and gate
verdicts. Parameterized Cypher rules out incompatible artifacts and returns the
evidence for ranking origins and choosing interventions. Each Decision records
its queries, returned records and graph revision before training. Planning stops
when FalkorDB is unavailable. Final-test outcomes stay outside the decision graph.

Judges can launch real CPU PPO from the live webpage, watch simulator states in
2D or 3D, inspect 180 validation episodes and download a checksummed checkpoint.
A recorded walkthrough covers busy trainers and overloaded model providers.

The earlier rehearsal lineage passed validation but failed its held-out target
limit: 13 collisions in 100 episodes. I retained that result. In a separately
preregistered study, the graph selected that parent for 600,064 additional PPO
steps with a stronger training-only collision penalty. The saved candidate
passed all four unchanged validation suites. Its hash was frozen before one
fresh, four-family confirmation: target collisions were 8/100 against a 10% limit,
and all four families passed. It is now the 2D demo policy.

Unchanged 2D weights still had 6/40 target collisions in MuJoCo. Separate mixed-domain adaptation produced two children passing all eight development checks. The strongest had 2/40 target collisions, but crossing remained at its 15% limit. It missed the preregistered extra clearance, so physics confirmation stays unopened. A separately registered longer run regressed; its rejection remains visible.

Next are independent training seeds and stronger crossing behaviour. This is a simulated research prototype, not a hardware-safety or training-efficiency claim.
