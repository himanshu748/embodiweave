# Validation diagnosis and search protocol

## Starting evidence

Queried FalkorDB on 2026-10-15, using complete validation records for
`scratch~a7ee2c-s7`, artifact `556ec083bc8589363d034745bac670bf7e0afb17fedf138ea0fd8b8797066baa`.
No final-test outcomes were used for diagnosis or model selection.

| Validation suite | Success | Collisions | Timeouts | Measured failure records |
|---|---:|---:|---:|---|
| Target, 60 episodes | 52/60 | 8/60 | 0/60 | 6 mover, 2 static collisions |
| Open, 40 episodes | 29/40 | 0/40 | 11/40 | 11 timeouts |
| Static, 40 episodes | 38/40 | 1/40 | 1/40 | 1 static collision, 1 timeout |
| Crossing, 40 episodes | 29/40 | 7/40 | 4/40 | 7 mover collisions, 4 timeouts |

Evidence IDs: `eval-20261015060452-d0c201`, `eval-20261015060459-f5f025`,
`eval-20261015060501-50061b`, `eval-20261015060504-ae284d`.
These are 180 episodes in total. The unchanged promo-1 gate accepts only static.
The target allows at most 6 collisions in its 60 episodes; the recorded candidate has 8.

```cypher
MATCH (p:Policy {id:$policy})<-[:ASSESSED]-(e:Evaluation)-[:ON_SUITE]->(s:Suite)
WHERE s.role = 'validation' AND e.complete_suite = true
  AND e.artifact_hash = p.artifact_hash AND e.suite_fingerprint = s.fingerprint
OPTIONAL MATCH (f:Failure)-[:OBSERVED_IN]->(e)
RETURN s.id, e.id, e.success_rate, e.collision_rate, e.timeout_rate,
       f.outcome, f.hit, f.count
```

## Interpretation, not established causes

Moving obstacles account for most collisions. A higher training-only collision
penalty or more experience may help. Open-arena failures are timeouts, so collision
penalties alone could make that failure worse. Rehearsing earlier tasks is a
reasonable alternative to target-only fine-tuning. These are hypotheses, not causal findings.

The evaluation path freezes observation normalization and disables reward normalization.
No normalization defect was found in that path. A real implementation issue was found in
warm starts: `PPO.load` kept parent hyperparameters even when the requested recipe changed.
The loader now explicitly applies the recorded optimizer settings; a real load/train/reload
test checks the optimizer learning rate. Existing ppo-r1 settings remain the same.

## Preregistered search-v1

Written before the first search-v1 trial. Every attempt uses seed 7 and 300,000
additional requested steps (rounded to full PPO rollouts), the same contract and dynamics.
No seed search. One new training recipe intervention per attempt. The parent is selected
again from measured graph evidence, so comparisons are adaptive, not controlled causal estimates.

FalkorDB supplies compatible completed checkpoints, their exact-artifact complete validation,
failure records and previously attempted interventions. The authored planner ranks candidates
by failed-suite count, worst deficit, total deficit, summed success-minus-collision, then ID.
The ranking is selection logic; it does not modify the promotion gate.

The first intervention is a longer budget with ppo-r1. After that, retained-task failures
prioritize rehearsal; excess collisions prioritize a doubled training-only collision penalty.
Remaining options are entropy 0.005 and learning rate 0.0001. Each option runs at most once
under search-v1. Rehearsal cycles open, static, crossing and target families at episode
boundaries. It generates new training layouts, never validation layouts.

Each decision stores the live Cypher, returned evidence, graph revision and reason **before**
training. Each saved candidate receives all four canonical validation suites (180 episodes),
a separate unchanged promo-1 verdict and a checksummed export. Rejected candidates remain.
Stop selection on the first complete validation pass. The user authorized one final evaluation
only after that pass; final results remain outside the decision graph.

Run one attempt with:

```sh
PYTHONPATH=. python -m scripts.search_validation
```

Use an isolated artifact directory and graph for development. Import the measured records
and artifacts into the hosted demo only after hash verification. Do not use this trusted
operator command as an unrestricted public endpoint.

## Measured outcome; selection stopped

| Attempt | Additional actual steps | Target success / collision | Open | Static | Crossing | promo-1 |
|---|---:|---|---|---|---|---|
| Longer ppo-r1 | 301,056 | 55/60 / 5/60 | 33/40 / 0/40 | 37/40 / 2/40 | 34/40 / 4/40 | Rejected, 3/4 |
| Rehearsal | 301,056 | 57/60 / 3/60 | 40/40 / 0/40 | 39/40 / 1/40 | 34/40 / 6/40 | Promoted, 4/4 |

Cells show successes / collisions, with each fraction using that suite's episode count.
The graph chose `scratch~10715f-s7` for the first attempt. It had the same validation
metrics as `scratch~a7ee2c-s7`; the frozen ranking broke that tie by policy ID.
After the first attempt improved to three passing suites, the graph selected that
child as the next origin. Its open-arena failures triggered rehearsal. That is a
validation-driven, authored heuristic. It does not prove the intervention caused
the improvement, and it does not demonstrate that a graph beats a relational store.

The rehearsal checkpoint passed all four unchanged validation checks. Crossing
collisions were exactly 6/40, at the 15% limit, so that pass had no collision margin.
The complete lineage consumed 753,664 training steps including its 151,552-step root.

One fresh held-out target confirmation then measured **86/100 successes, 13/100
collisions, 1/100 timeout**. Collisions included 1 wall, 6 static and 6 movers.
It failed the 10% target collision limit. No further model selection or tuning
was performed. Held-out retained-task evaluation remains untested. The baseline
and first rejection remain visible; the deployed policy remains unchanged.

The validation pass is real and the held-out failure is real. With adaptive selection
on these validation suites, the gap is consistent with limited generalization;
these data do not establish its cause. A next study needs independently preregistered
training seeds and a fresh, sealed test protocol, rather than repeated use of this test.

See [`evidence/search-v1/summary.json`](../evidence/search-v1/summary.json) for exact
decision, trial, evaluation, promotion and bundle IDs; `checksums.json` binds the
new evidence records and unchanged suite/threshold source. Each bundle includes
the exact captured training source, all validation episodes and its decision queries.
