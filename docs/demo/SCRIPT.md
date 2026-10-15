# EmbodiWeave demo v2: final script

119.23 seconds, 1080p30. Narration: Deepgram Aura-2 Thalia. Captions: Deepgram Nova-3.

This is a replay of measured evidence, not a newly launched training run. Robot motion is recorded MuJoCo simulation with unchanged 2D-trained checkpoints.

## 00:00:00.000 to 00:00:06.900: A test is not a guarantee

This robot passed its open-arena test. Watch what happens when a pedestrian crosses.

Visual: `physics-hook`. Speech 5.40 s; scene 6.90 s.

## 00:00:06.900 to 00:00:14.600: Which checkpoint? Safe to ship?

I built EmbodiWeave to answer two questions: which robot checkpoint should I retrain, and is the result safe to ship?

Visual: `problem`. Speech 7.20 s; scene 7.70 s.

## 00:00:14.600 to 00:00:24.633: The history is a graph

Falkor-D-B connects policies, training runs, trials, evaluations, failures and decisions. The links preserve what produced what.

Visual: `graph`. Speech 9.52 s; scene 10.03 s.

## 00:00:24.633 to 00:00:34.233: Diagnose the exact artifact

First, the agent queries failed validation suites, matching the exact artifact hash. A look-alike checkpoint cannot substitute for measured evidence.

Visual: `diagnose`. Speech 9.08 s; scene 9.60 s.

## 00:00:34.233 to 00:00:43.333: Same shape. Different meaning.

Matching tensor shapes are not enough. Falkor-D-B links sensor and action contracts, so incompatible starting points are excluded.

Visual: `contracts`. Speech 8.60 s; scene 9.10 s.

## 00:00:43.333 to 00:00:53.967: The decision is evidence too

The planner ranks eligible origins by failed suites and deficits. Before training, its decision records the Cypher, parameters and returned evidence in Falkor-D-B.

Visual: `decision`. Speech 10.12 s; scene 10.63 s.

## 00:00:53.967 to 00:00:59.933: No graph. No plan.

If Falkor-D-B is unavailable, planning stops. There is no silent fallback.

Visual: `closed`. Speech 5.44 s; scene 5.97 s.

## 00:00:59.933 to 00:01:10.767: Two measured training attempts

Longer training came first. A retained-task failure then led to rehearsal across training families. Each attempt added about three hundred thousand P-P-O steps.

Visual: `learning`. Speech 10.32 s; scene 10.83 s.

## 00:01:10.767 to 00:01:22.667: Same gate. Every candidate.

The original passed one of four suites. Longer training passed three. Rehearsal passed all four. The collision limits stayed at ten, five, ten and fifteen percent.

Visual: `gate`. Speech 11.40 s; scene 11.90 s.

## 00:01:22.667 to 00:01:34.333: I report it anyway.

One held-out target test recorded thirteen collisions across one hundred episodes. The limit was ten percent. I report it anyway. Production stays unchanged.

Visual: `heldout`. Speech 11.16 s; scene 11.67 s.

## 00:01:34.333 to 00:01:51.567: New physics. Unchanged checkpoints.

Finally, I transferred the same two-dimensional-trained checkpoints into MuJoCo physics. On forty fresh target episodes, the deployed policy collided 24 times. The rehearsal checkpoint collided 3 times. Crossing still had eight collisions. No retraining.

Visual: `transfer`. Speech 16.72 s; scene 17.23 s.

## 00:01:51.567 to 00:01:59.233: Robot training decisions you can audit.

The graph and checksummed evidence make these results inspectable. EmbodiWeave. Built on Falkor-D-B.

Visual: `close`. Speech 6.16 s; scene 7.67 s.

## Changes from the supplied draft

- The opening refers specifically to the old open-arena test, which P-static-b passed, rather than implying it passed every old suite.
- Original scratch passed one of four validation suites, not three. Longer training passed three; rehearsal passed four.
- Removed the unsupported statement about what most teams use. The script stays in first person.
- The held-out line says “thirteen collisions across one hundred episodes” for clearer transcription.
- MuJoCo target collisions are 24/40 deployed and 3/40 rehearsal; the original is 4/40 on screen. Crossing rehearsal failures, 8/40, are explicitly spoken and shown.
- The closing cites both the graph and checksummed evidence. Held-out outcomes are deliberately outside the planning graph.
- Shortened wording throughout to fit the narration. Speech is not sped up: the edit follows the generated scene WAVs, with reading beats rounded to 30fps frames.
- Caption spelling “cipher” is corrected to the query language name “Cypher”; word timings are unchanged.

## What is footage and what is graphics

Scenes 1 and 11 render real recorded MuJoCo joint states and scripted pedestrian states. Cameras, rays, fading trails and slow playback are editorial overlays. Scene 3 and part of scene 6 visualize real FalkorDB nodes and edges in an editorial layout; the query text and returned rows are real reads. Scene 8 uses recorded PPO training-progress samples. The remaining scenes are explanatory titles or tables backed by recorded evidence. The fail-closed scene is a title card describing a tested behavior, not footage of a live outage. No physical robot was filmed.
