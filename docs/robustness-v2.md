# Robustness study v2

## Why another study

Search-v1 stopped after its validation pass. Its disclosed held-out failure and
MuJoCo-v1 results remain unchanged. On 2026-10-16 the user requested substantive
improvements and authorized one new confirmation after validation. A separate
protocol was committed before training, with new confirmation seeds and a fixed
training budget. This does not turn the old test into unseen evidence.

## Preregistered selection

- Fixed training seed 19, at most three attempts, 600,000 requested steps each.
- Start by retaining cyclic rehearsal and doubling the training-only terminal
  collision penalty from -10 to -20. The evaluation reward is unchanged.
- FalkorDB returns compatible checkpoints, exact-artifact complete canonical
  validation, failure records and previously tried interventions.
- Rank failed-suite count first, then the deficit from two episodes of collision
  clearance on every suite, then the original validation deficit ranking.
- Stop on the first new 4/4 pass with that clearance. This is a stricter study
  stopping rule, not a modification of promo-1. No seed sweep.
- Freeze the selected artifact hash before one fresh confirmation batch of
  100 episodes per family. An exclusive marker is created before inference;
  interruption cannot grant a retry. Confirmation never enters the decision graph.
- Run a separate post-selection MuJoCo transfer study. No retraining or further
  selection follows either confirmation or transfer outcomes.

Protocol: [`evidence/robustness-v2/protocol.json`](../evidence/robustness-v2/protocol.json).

## One measured attempt, then selection stopped

FalkorDB selected `search-20261015185749-4a6581`. Its crossing validation had
6/40 collisions, exactly the 15% limit. Decision `deci-20261016140226-d320a0`
recorded its queries and ranking before training. Trial `tria-20261016140422-f68ea3`
produced `robust-20261016140226-352fd7` after **600,064 actual PPO steps**.

Artifact hash: `b027851f2ffe5595de6742a3df2b5be419a95aa92c8d34c87d8e459aeaaa85b4`.

| Suite | Validation goals | Validation collisions | Collision limit | Fresh confirmation goals | Confirmation collisions | Confirmation timeouts |
|---|---:|---:|---:|---:|---:|---:|
| Target | 57/60 | 2/60 | 10% | 92/100 | 8/100 | 0/100 |
| Open | 40/40 | 0/40 | 5% | 100/100 | 0/100 | 0/100 |
| Static | 39/40 | 1/40 | 10% | 93/100 | 4/100 | 3/100 |
| Crossing | 40/40 | 0/40 | 15% | 95/100 | 5/100 | 0/100 |

All four canonical validation checks passed. All four fresh confirmation
families met the original success floors and collision maxima. The confirmation
is a separate measurement, not another promotion rule. There was no training
after confirmation. The AWS 2D demo now uses this checkpoint; the historical
baseline and rejected runs remain accessible.

## Physical transfer remains incomplete

Fresh MuJoCo-v2 seeds differ from v1. Each checkpoint runs the same 40 seeds per
family without retraining. Cells are **goals / collisions / timeouts**, not percentages.

| Suite | Historical P-static-b | Confirmed 2D checkpoint | Collision reference limit |
|---|---:|---:|---:|
| Open | 40 / 0 / 0 | 40 / 0 / 0 | 5% |
| Static | 18 / 10 / 12 | 38 / 1 / 1 | 10% |
| Crossing | 19 / 21 / 0 | 36 / 4 / 0 | 15% |
| Target | 14 / 21 / 5 | 32 / 6 / 2 | 10% |

The new checkpoint has fewer paired target collisions than P-static-b, but
**6/40 is 15%, above the 10% reference limit**. It is confirmed for the 2D
simulator, not certified for physics or hardware. No dynamics, sensor mapping,
friction, suite or threshold was fitted to these outcomes. MuJoCo-v2 lives in
separate sim2sim graph suites. Confirmation stays outside the graph.

The new training seed and additional budget also differ from search-v1, so this
adaptive comparison does not isolate a causal effect of the collision penalty.
One training seed and small transfer suites do not establish general safety or
an efficiency advantage. A future physics-adaptation study needs its own
training/validation protocol and a new independently authorized confirmation;
this study's confirmation is spent.

## Reproduce and inspect

```sh
PYTHONPATH=. python -m scripts.robustness_validation
PYTHONPATH=. python -m scripts.robustness_confirmation freeze
PYTHONPATH=. python -m scripts.robustness_confirmation confirm
PYTHONPATH=. python -m scripts.robustness_transfer
```

Use an isolated `EW_ARTIFACTS` directory and `EW_GRAPH` with the committed parent
artifacts and validation records. Existing selection/confirmation markers prevent
rerunning the spent study. For evaluation of the saved policy, use its checksummed
export bundle instead of restarting training or reopening confirmation seeds.

[All records and checksums](../evidence/robustness-v2/) · [MuJoCo trajectories](../evidence/mujoco-v2/).
