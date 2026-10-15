# YouTube upload notes

YOUTUBE_URL

## Title

EmbodiWeave: FalkorDB chooses robot checkpoints, MuJoCo tests them

## Description

I built EmbodiWeave to make robot training decisions auditable. FalkorDB connects each exact checkpoint to its sensor/action contract, training origins, evaluations, failures and recorded decisions. The graph supplies the evidence for what to train next; a fixed validation gate checks the saved result.

The graph-selected rehearsal lineage passed 4/4 validation suites. Its one held-out target test still failed: 13 collisions in 100 episodes, above the 10% limit. I report that result and leave the deployed policy unchanged.

This film also shows a sim-to-sim transfer test: the same 2D-trained PPO checkpoints running unchanged in real MuJoCo contact physics. On 40 fresh target episodes, deployed / original / rehearsal collisions were 24 / 4 / 3. Rehearsal still collided in 8/40 crossing-only episodes. No MuJoCo retraining, no real-world safety claim, and no altered gate.

Live demo: https://embodiweave.52.202.25.181.sslip.io
Source and evidence: https://github.com/himanshu748/embodiweave
MuJoCo protocol: https://github.com/himanshu748/embodiweave/blob/main/docs/mujoco-transfer.md
Evidence: https://github.com/himanshu748/embodiweave/tree/main/evidence/mujoco-v1

### How FalkorDB is used

- Connects policies, runs, trials, evaluations, failures, contracts and decisions through typed provenance relationships.
- Matches complete validation to the exact artifact hash and rules out incompatible sensor/action contracts.
- Returns evidence for the deterministic planner's ranking; the recorded Decision preserves Cypher, parameters, returned records and graph revision before training.
- Makes planning fail closed when unavailable. MuJoCo transfer evidence has its own sim2sim role; held-out outcomes stay outside the planning graph.

Narration: Deepgram Aura-2. Captions: Deepgram Nova-3.
Voice: aura-2-thalia-en. Actual word-timed transcripts and request receipts are in the repository.

Music: “Cipher” by Kevin MacLeod (incompetech.com).
Licensed under Creative Commons Attribution 3.0: https://creativecommons.org/licenses/by/3.0/
Source: https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3
Changes: excerpt, fades, loudness normalization and narration mix. No endorsement implied.

Robot motion is real checkpoint-driven MuJoCo simulation. Graph layouts, titles, learning-curve plots, sensor overlays and camera moves are editorial graphics. No AI-generated robot footage. Claude and Codex assisted with implementation, auditing, experiments and film production; measured results were not fabricated.

## Chapters

00:00 A test is not a guarantee
00:06 Which checkpoint? Safe to ship?
00:14 The history is a graph
00:24 Diagnose the exact artifact
00:34 Same shape. Different meaning.
00:43 The decision is evidence too
00:53 No graph. No plan.
00:59 Two measured training attempts
01:10 Same gate. Every candidate.
01:22 I report it anyway.
01:34 New physics. Unchanged checkpoints.
01:51 Robot training decisions you can audit.

## Tags

EmbodiWeave, FalkorDB, GraphHacks, reinforcement learning, PPO, robotics, MuJoCo, sim-to-sim transfer, knowledge graph, Cypher, AI agents, Deepgram, Aura-2, Nova-3, hackathon

## Upload checklist

Upload `embodiweave-demo-v2.mp4` and `thumbnail.png`. The film already contains burned-in captions; also upload `embodiweave-demo-v2.srt` as the caption track. Keep the music attribution in the description. Replace YOUTUBE_URL after upload. The 720p site cut and narration-free version use the same scene timing; v1 stays available as a fallback.
