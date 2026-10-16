# Separate MuJoCo adaptation study

This study follows the frozen robustness-v2 release. It does not revise the earlier 2D confirmation or unchanged-weight transfer results. The new checkpoints are trained in **both 2D and MuJoCo**. They are not examples of unchanged 2D-to-physics transfer.

## Protocol

The study was registered before training in [protocol.json](../evidence/physics-adapt-v1/protocol.json). FalkorDB selected the two starting points from complete canonical validation, before the new physics development measurements. Those diagnostic measurements then became graph evidence for the registered ranking rule.

Every attempted child uses four real MuJoCo environments and four original kinematic environments, rehearsing all four task families. The seed is fixed at 23. Each attempt requests 300,000 PPO steps and consumes a whole rollout budget. The three registered interventions are domain mixing, a stronger training collision cost, and a lower learning rate. The graph chooses the highest ranked origin and the next untried intervention according to the preregistered rule. It does not invent the training algorithm.

Selection uses all 180 canonical validation episodes plus 160 physics development episodes. The original promotion thresholds and code are unchanged. In addition, selection requires one episode of collision clearance on each physics suite. This is a stopping rule, not a change to promo-1. The first new eligible child is frozen; training must then stop.

## Protected confirmation

The user authorized one new physics confirmation, only after validation selection ends. It comprises 100 fresh episodes per family, 400 total. An exclusive marker is created before inference; a crash also spends the authorization. The frozen policy hash and protocol must verify before opening it. No confirmation outcome is ingested into FalkorDB or queried by the planner. No new 2D held-out evaluation was authorized for this physics child.

The confirmed robustness-v2 parent remains the default 2D demo policy. A physics child's canonical 2D validation alone does not give it a fresh 2D confirmation.

## Evidence and reproduction

[evidence/physics-adapt-v1](../evidence/physics-adapt-v1/) contains parent selection, all development evaluations, seeded layouts, actual recorded joint states, model hashes and checksums. Each completed child has a `physics-repro-v1.zip` bundle with the policy, normalization statistics, captured training source, graph query receipts, per-episode development records and trajectories. `REPRODUCE-PHYSICS.md` explains how to rerun development measurement only. Confirmation is deliberately not an automated reproduction command.

A `Suite` node with role `validation` and physics `mujoco` identifies each development suite. Evaluations bind exact policy hashes and suite fingerprints; Failure nodes retain collision objects and seeds. Planning uses two exact-artifact reads, one for canonical suites and one for physics development. A Decision records both reads and the returned records before training.

```cypher
MATCH (d:Decision {rule_version:'physics-adapt-v1'})-[:SELECTED]->(origin:Policy)
MATCH (d)-[:LAUNCHED]->(r:Run)-[:PRODUCED]->(child:Policy)
MATCH (d)-[:BASED_ON]->(e:Evaluation)-[:ON_SUITE]->(s:Suite)
WHERE s.role='validation' AND (e)-[:ASSESSED]->(origin)
  AND e.artifact_hash=origin.artifact_hash
RETURN d.id, origin.id, child.id, s.id, s.physics,
       e.success_rate, e.collision_rate, d.explanation
ORDER BY d.id, s.id
```

## Limits

These are small simulated tasks with scripted pedestrians and a fixed sensor/action contract. Successful simulation results do not establish physical robot safety or generalize to arbitrary pedestrians, environments or sensor faults. MuJoCo uses the documented velocity-servo mobile base, not a validated hardware model. The [transfer mapping](mujoco-transfer.md) lists the remaining mismatches. No claimed pass removes those limits.
