# Combined film: v5 with narrated v4 agent follow-up

YOUTUBE_URL: https://youtu.be/XVHaa5T7tiU

Uploaded unlisted on October 17, 2026. Verified 1920×1080 playback and the uploaded English captions, including the narrated ending. YouTube reports a 138.121-second playback container. [Upload receipt](../../../evidence/film-v5-v4-narrated/youtube-upload.json). Original v5 upload unchanged.

## Title

EmbodiWeave: the graph changes the origin, the regression blocks release

## Description

I built an agent that reads a robot's training history in FalkorDB, chooses a checkpoint, launches PPO training and records the result against a fixed gate.

This cut preserves the original v5 film and adds the recorded v4 agent follow-up at 01:58. The earlier film's account of the stopped v3 attempt describes the state at that recording. The later v3-retry and v4 records remain available below.

In v4, a parameterized graph query excludes origins with connected regression evidence. The agent chooses robust-20261016140226-352fd7 instead of physics-20261016150004-25da9c. It consumes 61,440 PPO steps and completes 180 validation episodes. The child passes all four unchanged gates, but target collisions rise from 2/60 to 4/60 and crossing collisions from 0/40 to 1/40 against its parent. The parent comparison blocks release. The deployed policy stays unchanged.

The exclusion rule was authored and required by the protocol. A changed origin is not proof of learning, improvement or a planning advantage.

The separate shipped checkpoint passed four unchanged validation suites and fresh confirmation: target 8/100 collisions against a 10% limit. The success replay is a recorded validation episode, not the confirmation batch. Earlier failures and MuJoCo limitations remain in the README.

How FalkorDB is used:
- Policies connect to runs, evaluations, failures, contracts, Decisions and DecisionOutcomes.
- MCP read tools use GRAPH.RO_QUERY to retrieve exact-artifact evidence and compatible origins.
- Native shortestPath exposes passing ancestry; the v4 exclusion query traces connected regression outcomes before ranking surviving origins.
- The Decision records tool calls, Cypher, parameters and returned evidence before training. The measured outcome is written back to the graph. Planning stops without FalkorDB.

Live demo: https://embodiweave.52.202.25.181.sslip.io/
Repository: https://github.com/himanshu748/embodiweave
V4 agent evidence: https://github.com/himanshu748/embodiweave/tree/207f451fcae4b8d9e441e17804b191924a45f138/evidence/mcp-agent-v4
V3-retry evidence: https://github.com/himanshu748/embodiweave/tree/207f451fcae4b8d9e441e17804b191924a45f138/evidence/mcp-agent-v3-retry
Original v5 backup: https://youtu.be/IfFo4cicShk

Narration: Deepgram Aura-2 (Thalia). Captions: Deepgram Nova-3.
Music in the original v5 segment: “Cipher” by Kevin MacLeod (incompetech.com), CC BY 3.0, https://creativecommons.org/licenses/by/3.0/
Track: https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3
Fonts: Space Grotesk and IBM Plex Mono, SIL Open Font License.

Robot motion comes from saved policy-driven simulator traces. Titles, graph layout, framing and highlights are editorial. AI tools assisted implementation, writing and editing. No AI-generated robot footage or physical-robot safety claim.

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
01:58 V4 follow-up: a different origin, still not released

## Thumbnail

Use the existing `docs/demo/v5/thumbnail.png`, unchanged.

## Captions

Use `docs/demo/v5-v4/embodiweave-demo-v5-with-v4-narrated.srt` after generation.

## Tags

FalkorDB, Graph Hacks, WeMakeDevs, MCP, robotics, PPO, reinforcement learning, graph database, AI agents, Cypher, EmbodiWeave
