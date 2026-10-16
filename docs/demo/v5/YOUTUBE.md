# YouTube upload notes — v5

YOUTUBE_URL: https://youtu.be/IfFo4cicShk

## Title

EmbodiWeave: an MCP agent retrains a robot, FalkorDB keeps the evidence

## Description

I built an agent that reads a robot's training history in FalkorDB, chooses a checkpoint, launches PPO training and records the result against a fixed gate.

The completed public MCP run used GPT-4.1 Mini, trained 61,440 steps and passed all four gates over 180 validation episodes. But target collisions rose from 2/60 to 3/60 and crossing collisions from 0/40 to 1/40 against its parent. The child did not ship. This run does not establish a safety improvement.

I connected that comparison back to the graph. The one preregistered follow-up attempt read both prior outcomes and a weighted graph ranking, then exceeded the bounded model context before choosing an origin or training. At the time of this recording, I did not retry. No change in origin choice or planning advantage was established.

The separate shipped checkpoint passed four unchanged validation suites and fresh confirmation: target 8/100 collisions against a 10% limit. The success replay is a recorded validation episode from that checkpoint; it is not the 100-episode confirmation batch. Earlier held-out and MuJoCo limitations remain in the README.

### How FalkorDB is used

- Policies connect to training runs, evaluations, failures, contracts and Decisions through recorded provenance.
- MCP tools use GRAPH.RO_QUERY for exact-artifact validation, compatible origins and prior connected child outcomes.
- Native shortestPath exposes passing ancestry. A native Cypher weighted-degree ranking sums measured positive collision-rate deltas on child-to-parent regression edges; the follow-up agent actually read both outputs.
- A Decision stores model, tool calls, Cypher, parameters, records and guardrail verdict before training. The outcome links the child and evaluations back to that Decision. Planning stops without FalkorDB.

Live demo: https://embodiweave.52.202.25.181.sslip.io/
Repository: https://github.com/himanshu748/embodiweave
Completed run: https://github.com/himanshu748/embodiweave/tree/main/evidence/mcp-agent-v2
Stopped follow-up: https://github.com/himanshu748/embodiweave/tree/main/evidence/mcp-agent-v3
Film evidence: https://github.com/himanshu748/embodiweave/tree/main/evidence/film-v5

Narration: Deepgram Aura-2. Captions: Deepgram Nova-3.
Voice: aura-2-thalia-en; 114.64 seconds of narration. Unchanged clips retain their original receipts.
Music: “Cipher” by Kevin MacLeod (incompetech.com), CC BY 3.0, https://creativecommons.org/licenses/by/3.0/
Track: https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3
Edited excerpt mixed about 18 dB below narration.
Fonts: Space Grotesk and IBM Plex Mono, SIL Open Font License.

Robot motion comes from saved policy-driven simulator traces. Titles, graph layout, framing and highlights are editorial graphics. AI tools assisted implementation, writing and editing. No AI-generated robot footage or physical-robot safety claim.

## Chapters

00:00 A failure needs its history
00:10 A complete MCP run: four gates passed
00:25 FalkorDB connects the evidence
00:33 A shortest path through real lineage
00:42 The guardrail can veto the agent
00:52 The Decision precedes the action
01:01 Real PPO, then saved-policy evaluation
01:09 Four suites. The same fixed gate.
01:19 Target and crossing regressed
01:30 The next agent read the regression
01:38 The shipped checkpoint passed fresh confirmation
01:48 Every action is a node you can query

## Tags

FalkorDB, Graph Hacks, WeMakeDevs, MCP, robotics, PPO, reinforcement learning, graph database, AI agents, Cypher, EmbodiWeave

## Upload verified

Uploaded unlisted on October 16, 2026 with this title, description, thumbnail and the original English SRT. Playback was verified at 1920×1080 with English captions. [Upload receipt](../../../evidence/film-v5/upload/receipt.json). The film remains 118.10 seconds; YouTube reports a 118.121-second playback container. V4 and all earlier media are unchanged. No submission was made.
