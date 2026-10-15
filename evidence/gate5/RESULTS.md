# Gate 5 results: does the graph pick a better starting point?

All numbers below were measured in this container on 2026-10-15 and come from the files in this
folder (`experiment1.json`, `experiment2.json`, `experiment3.json`, their protocols and `exp*.out`).
Nothing is estimated or animated. Three training seeds per arm, so every difference here is
preliminary and no significance claim is made.

## Setup shared by all three experiments

- Target: `static_crossing` (2 static obstacles plus a crossing mover), contract `ew-contract-1`.
- Budget: 150,000 PPO steps per arm and seed, recipe `ppo-r1`, validation every 37.5k steps on
  `val-target-v1` (60 episodes).
- Threshold `thr-target-1`: validation success at least 0.80 and collision at most 0.10.
- Arms: the graph's choice, a contrast rule, latest library checkpoint, best matched validation
  checkpoint, and scratch. Arms that pick the same start share the same runs.
- Each experiment froze its protocol (on disk and in git) before training and used its own final-test
  suite exactly once. Final-test results are never ingested into the decision graph. A spent suite is
  refused by code (`ew/scenarios.py: SPENT_FINAL_TESTS`).

## exp-1 (rule ew-select-1, final test `test-target-v1`, seeds 601-603)

Phase A first measured 2 transfer trials per library checkpoint (8 trials, 1.21M steps, all failed to
reach the threshold). Then:

| Arm | Start | Reached | Mean test success | Mean test collision |
|---|---|---|---|---|
| graph (ew-select-1) | P-static-a | 0/3 | 0.333 | 0.42 |
| graph_nohist | P-static-b | 0/3 | 0.350 | 0.43 |
| latest | P-static-b | 0/3 | 0.350 | 0.43 |
| best_val | P-static-b | 0/3 | 0.350 | 0.43 |
| scratch | scratch | 1/3 (at 75k) | **0.763** | **0.17** |

Negative result: warm starts from this library plateau, and the graph rule only chose between parents,
so it could not recommend the arm that won. Its choice was no better than the simple baselines.

Diagnostic after exp-1 (`diag-*.json`, P-open-a parent, seed 601, validation only, single seed):
keeping or refitting normalization and resetting the value head change little (0.08 to 0.13 success at
150k). Resetting the policy log-std to 0 reaches 0.33. Parents keep their low exploration noise, which
is a likely cause of the plateau. This was not pursued further.

## exp-2 (rule ew-select-2, final test `test-target-v2`, seeds 701-703)

ew-select-2 adds "train from scratch" as an option with its own conditioned trials in the graph
(`(:Trial)-[:FROM_ORIGIN]->(:Origin {id:'scratch'})`). The exp-1 scratch runs were backfilled as Trial
records derived from their measured run records. Graph decision: scratch, p_reach 0.40 (1/3) against
the best parent at 0.25 (0/2).

| Arm | Start | Reached | Mean test success | Mean test collision | Per seed |
|---|---|---|---|---|---|
| graph (ew-select-2) | scratch | 0/3 | **0.713** | **0.18** | 0.77, 0.76, 0.61 |
| graph_v1 (ew-select-1) | P-cross-a | 0/3 | 0.093 | 0.44 | 0.11, 0.09, 0.08 |
| latest / best_val | P-static-b | 0/3 | 0.393 | 0.36 | 0.45, 0.36, 0.37 |
| scratch | scratch | 0/3 | 0.713 | 0.18 | same runs as graph |

The graph arm beat latest and best_val on every paired seed (+0.32, +0.40, +0.24 success).

## A flaw exp-2 exposed, and ew-select-3

After exp-2 was ingested, ew-select-2 tied scratch (1/6 reached, p 0.25) with P-open-a (0/2 reached,
p 0.25) and kept reuse, although scratch children scored about +0.57 on validation and P-open-a
children about -0.74. The binary reached/not-reached estimate threw that measured evidence away.
ew-select-3 ranks parents and scratch together and breaks p_reach ties with the mean matched validation
score of the checkpoints each option's trials produced (query template `trial_outcomes`). It was frozen
in git before exp-3.

## exp-3 (rule ew-select-3, final test `test-target-v3`, seeds 801-803)

| Arm | Start | Reached | Mean test success | Mean test collision | Per seed |
|---|---|---|---|---|---|
| graph (ew-select-3) | scratch | 1/3 | **0.700** | **0.18** | 0.65, 0.68, 0.77 |
| graph_v2 (ew-select-2) | P-open-a | 0/3 | 0.133 | 0.85 | 0.15, 0.15, 0.10 |
| latest / best_val | P-static-b | 0/3 | 0.370 | 0.45 | 0.39, 0.35, 0.37 |
| scratch | scratch | 1/3 | 0.700 | 0.18 | same runs as graph |

The graph arm beat latest and best_val on every paired seed (+0.26, +0.33, +0.40). The old rule would
have picked the worst arm.

## What this does and does not show

- The graph's value in exp-2 and exp-3 is recognising that reuse does not pay for this target and
  budget. It did not find a better parent; the graph arm and the scratch arm are the same runs.
- No arm met the full threshold on the final test: collision stayed around 0.18 against the 0.10 limit.
  Scratch reached the validation threshold in 2 of 9 runs. From-scratch learnability (Gate 1) reached
  0.93 at 400k, so 150k is a short budget for this mission.
- The rule changed twice after seeing results. Each change is documented in `ew/select.py`, committed
  before the next run, and judged on a fresh, previously unused final-test suite.
- Costs: library 725k steps; exp-1 transfer measurement 1.21M; exp-1 phase B, exp-2 and exp-3 about
  1.36M steps each (about 3.3 min wall each on 4 CPU cores with 3 parallel workers).
