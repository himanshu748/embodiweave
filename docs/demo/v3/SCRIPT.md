# EmbodiWeave v3

116.67 seconds. Scenes 1-8 retain the recorded search-v1 history. Scenes 9-11 report robustness-v2. Narration: Deepgram Aura-2 Thalia. Captions: Deepgram Nova-3.

## 00:00:00,000 to 00:00:06,900: A test is not a guarantee

This robot passed its open-arena test. Watch what happens when a pedestrian crosses.

## 00:00:06,900 to 00:00:14,600: Which checkpoint? Safe to ship?

I built EmbodiWeave to answer two questions: which robot checkpoint should I retrain, and is the result safe to ship?

## 00:00:14,600 to 00:00:24,633: The history is a graph

Falkor-D-B connects policies, training runs, trials, evaluations, failures and decisions. The links preserve what produced what.

## 00:00:24,633 to 00:00:34,233: Diagnose the exact artifact

First, the agent queries failed validation suites, matching the exact artifact hash. A look-alike checkpoint cannot substitute for measured evidence.

## 00:00:34,233 to 00:00:43,333: Same shape. Different meaning.

Matching tensor shapes are not enough. Falkor-D-B links sensor and action contracts, so incompatible starting points are excluded.

## 00:00:43,333 to 00:00:53,967: The decision is evidence too

The planner ranks eligible origins by failed suites and deficits. Before training, its decision records the Cypher, parameters and returned evidence in Falkor-D-B.

## 00:00:53,967 to 00:00:59,933: No graph. No plan.

If Falkor-D-B is unavailable, planning stops. There is no silent fallback.

## 00:00:59,933 to 00:01:10,767: Two measured training attempts

Longer training came first. A retained-task failure then led to rehearsal across training families. Each attempt added about three hundred thousand P-P-O steps.

## 00:01:10,767 to 00:01:24,000: The graph chose a stronger collision cost.

Falkor-D-B chose the rehearsal checkpoint for six hundred thousand more P-P-O steps, with double the collision penalty. The saved candidate passed all four unchanged validation suites.

## 00:01:24,000 to 00:01:36,367: Frozen first. Confirmed once.

I froze its hash before a fresh confirmation batch. All four suites passed. Target collisions: eight in one hundred. The limit stayed ten percent. The earlier failure remains visible.

## 00:01:36,367 to 00:01:49,000: New physics still exposed a gap.

Physics still exposed a gap. The same checkpoint, without retraining in MuJoCo, collided six times in forty target episodes, and four times in crossing. This is no physical safety certificate.

## 00:01:49,000 to 00:01:56,667: Robot training decisions you can audit.

The graph and checksummed evidence make these results inspectable. EmbodiWeave. Built on Falkor-D-B.
