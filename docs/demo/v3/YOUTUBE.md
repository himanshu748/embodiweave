# EmbodiWeave v3 upload notes

YOUTUBE_URL

## Title

EmbodiWeave: FalkorDB chose the checkpoint. Fresh tests checked it.

## Description

I built EmbodiWeave to make robot training decisions auditable. FalkorDB connects exact checkpoint artifacts, semantic sensor/action contracts, training origins, trials, evaluations, failures and decisions.

The earlier rehearsal checkpoint passed validation but failed its held-out target test with 13 collisions in 100 episodes. I kept that evidence. In a separate preregistered study, FalkorDB supplied the validation evidence for choosing that parent and a stronger training-only collision penalty. After 600,064 additional PPO steps, the saved candidate passed all four unchanged validation suites.

I froze its hash before one fresh four-family confirmation. Target results were 92 goals, 8 collisions and no timeouts in 100 episodes, under the unchanged 10% collision limit. All four confirmation families passed their original requirements. The current 2D demo uses this checkpoint.

MuJoCo remains harder. The same 2D-trained checkpoint, unchanged and without physics retraining, collided in 6/40 target episodes and 4/40 crossing episodes. Target transfer still exceeds the 10% reference limit. Real physics footage and complete failures remain visible. This is a simulated research prototype, not a physical safety certificate.

Live demo: https://embodiweave.52.202.25.181.sslip.io
Current evidence: https://embodiweave.52.202.25.181.sslip.io/robustness.html
Repository: https://github.com/himanshu748/embodiweave
Protocol: https://github.com/himanshu748/embodiweave/blob/main/docs/robustness-v2.md

### How FalkorDB is used

- Connects checkpoint artifacts, contracts, runs, trials, evaluations, failures and decisions through typed provenance relationships.
- Matches complete validation to an exact artifact hash and rules out incompatible sensor/action contracts.
- Supplies evidence for authored origin/intervention ranking. Decisions preserve Cypher, parameters and returned records before training.
- Makes planning stop when unavailable. MuJoCo has separate sim2sim suites; confirmation outcomes stay outside the planning graph.

Narration: Deepgram Aura-2. Captions: Deepgram Nova-3. Voice: aura-2-thalia-en. Scenes 1-8 and 12 reuse the original Deepgram recordings; scenes 9-11 have new requests and word-timed transcripts. Raw transcripts and caption corrections are retained.

Music: “Cipher” by Kevin MacLeod (incompetech.com), licensed under Creative Commons Attribution 3.0: https://creativecommons.org/licenses/by/3.0/
Source: https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3
Changes: excerpt, fades, loudness normalization and music mixed about 18 dB below narration. No endorsement implied.

Robot motion is real checkpoint-driven MuJoCo simulation. Titles, graph layouts, highlighting, camera work and sensor overlays are editorial graphics. No keyframed or AI-generated robot footage. Codex and Claude assisted with code, experiments and production; no outcome was fabricated.

## Chapters

00:00 A test is not a guarantee
00:06 Which checkpoint? Safe to ship?
00:14 The history is a graph
00:24 Diagnose the exact artifact
00:34 Same shape. Different meaning.
00:43 The decision is evidence too
00:53 No graph. No plan.
00:59 Two measured training attempts
01:10 The graph chose a stronger collision cost.
01:24 Frozen first. Confirmed once.
01:36 New physics still exposed a gap.
01:49 Robot training decisions you can audit.

## Tags

EmbodiWeave, FalkorDB, GraphHacks, robotics, PPO, reinforcement learning, MuJoCo, sim-to-sim transfer, Cypher, knowledge graph, AI agents, Deepgram, hackathon

## Upload

Use `embodiweave-demo-v3.mp4`, `thumbnail.png` and `embodiweave-demo-v3.srt`. The film has burned-in captions. Keep the music attribution. Replace YOUTUBE_URL after upload. V2 and V1 remain available as fallback films.
