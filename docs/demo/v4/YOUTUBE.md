# YouTube upload notes — v4

YOUTUBE_URL: YOUTUBE_URL

## Title

MCP agent launches robot training: 4/4 gates | EmbodiWeave x FalkorDB

## Description

I built an agent that reads a robot's training history in FalkorDB, decides which checkpoint to retrain, launches PPO training, and records whether the saved result meets a fixed gate.

The first line states the measured win: the workflow completed and all four validation gates passed. The first 15 seconds show the real public MCP run: GPT-4.1 Mini chooses graph tools, proposes an origin and calls start_training. A deterministic guardrail validates the proposal before the worker starts. The completed run trained 61,440 steps and evaluated 180 validation episodes.

All four fixed gates passed. But target collisions rose from 2/60 to 3/60 and crossing collisions from 0/40 to 1/40 against the chosen parent. I kept that regression visible. This run did not replace the demo policy, and it does not establish a safety improvement.

### How FalkorDB is used

- Policies, training runs, trials, evaluations, failures, contracts and decisions are connected by their actual provenance edges.
- MCP tools use GRAPH.RO_QUERY to read exact-artifact validation, compatible contracts and candidate origins.
- FalkorDB's native shortestPath returns the nearest passing ancestor along DERIVED_FROM lineage. The agent considers that output alongside candidate validation; it chose a different eligible origin.
- Before training, a Decision saves the model, tool calls, Cypher, parameters, returned records, chosen origin, guardrail verdict and graph revision. Planning stops if the graph is unavailable.

The final section reuses the separate MuJoCo-v2 transfer study: the confirmed 2D checkpoint had 6/40 target collisions in MuJoCo without retraining. This is a sim-to-sim test, not MuJoCo training or a physical safety certificate. Earlier held-out results stay unchanged.

Live demo: https://embodiweave.52.202.25.181.sslip.io
Repository: https://github.com/himanshu748/embodiweave
Source run: https://github.com/himanshu748/embodiweave/tree/main/evidence/mcp-agent-v2
Film evidence: https://github.com/himanshu748/embodiweave/tree/main/evidence/film-v4

Narration: Deepgram Aura-2. Captions: Deepgram Nova-3.
Voice: aura-2-thalia-en; 110.08 seconds of narration. Word timings and request receipts are saved. Two unchanged clips retain their original receipts.
Music: “Cipher” by Kevin MacLeod (incompetech.com), CC BY 3.0, https://creativecommons.org/licenses/by/3.0/
Track: https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3
Edited excerpt, normalized and mixed about 18 dB below narration.
Fonts: Space Grotesk and IBM Plex Mono, SIL Open Font License; licences in docs/demo/assets/.

Robot motion is saved policy output from real simulators. Graph layout, titles, camera framing, cursor movement and evidence highlights are editorial graphics. Browser shots replay completed run evidence; waiting time is removed. AI tools assisted the implementation, writing and edit. No AI-generated robot footage is used.

## Chapters

00:00 Agent acts through MCP; four gates passed
00:15 FalkorDB provenance graph
00:25 Native lineage shortest path
00:36 Contract and guardrail
00:47 Decision before action
00:58 Real PPO, saved replay and fixed gate
01:16 Honest parent-to-child regression
01:28 Frozen earlier studies
01:38 Separate MuJoCo transfer and credits

## Tags

FalkorDB, Graph Hacks, WeMakeDevs, MCP, robotics, PPO, reinforcement learning, graph database, knowledge graph, AI agents, Cypher, MuJoCo, sim-to-sim, explainable AI, EmbodiWeave

## Upload checklist

Upload `embodiweave-demo-v4.mp4` and `thumbnail.png`; attach `embodiweave-demo-v4.srt`. Replace YOUTUBE_URL after upload. Keep the v3 link as backup. Review the full spoken track, mobile captions and regression table before submitting the form.
