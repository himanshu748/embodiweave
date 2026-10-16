# EmbodiWeave: MCP action opening

This is the next-cut script, not a claim that v3 has been re-rendered. Keep all v3 exports as fallbacks. Use the genuine public [`agent-mcp-v2` receipt](../../../evidence/mcp-agent-v2/agent-receipt.json) and its [checkpoint bundle](../../../evidence/mcp-agent-v2/repro-v3.zip) for every new shot. Waiting time may be trimmed, with a visible “waiting time removed” label. Never imply a pending session has finished. The v1 deterministic fallback stays separately labelled.

Recorded source: GPT-4.1 Mini through OpenRouter/Azure, session `judge-ce0e904e4e79d0ca94d7e69240da52e6`; Decision `deci-20261016121309-c0c93f`; child `judge-a524ef1f3d677cd255354736e0cba609`. [Measured summary and all IDs](../../../evidence/mcp-agent-v2/summary.json).

## 00:00 to 00:20: The agent chooses tools and starts a real run

| Time | Actual screen evidence | Narration |
|---|---|---|
| 00:00 to 00:04 | SDK `tools/list` receipt, with the discovered domain schemas. Highlight `diagnose_policy`, `find_training_origins` and `nearest_passing_ancestor`. | “I let the agent read a robot's training history in Falkor-D-B, through M-C-P.” |
| 00:04 to 00:09 | Actual `tools/call` results: diagnosis, shortest-path nodes and eligible origins. Show the returned ancestor ID and hop count from the receipt. | “It traces a passing ancestor and compares the checkpoints it can actually use.” |
| 00:09 to 00:14 | Model-selected `start_training` arguments, including the saved origin and its reason. Do not replace these with the fallback's choice. | “Then it chooses an origin and calls the training tool.” |
| 00:14 to 00:20 | The new Decision, guardrail verdict, pending PPO session and its first real simulator frame. Show source `llm_mcp`. | “The guardrail checks its evidence before the robot starts learning. It can veto the agent.” |

No PPO explanation precedes this action. In this recording, the model chose `physics-20261016150004-25da9c` from 17 eligible origins. The shortest-path result was `robust-20261016140226-352fd7 → search-20261015185749-4a6581`, one hop. The chosen origin differs from the nearest ancestor; the model cited the path and compared the candidate's validation. It chose the authored rank-one candidate, and the guardrail allowed it. Do not imply the algorithm itself chose the origin.

## 00:20 to 00:32: The problem

“I built EmbodiWeave because retraining leaves two questions: which checkpoint should I start from, and did the new policy meet the checks? I want the reasons recorded with the result.”

Show the real Policy, Contract, Run, Trial, Evaluation, Failure and Decision nodes. Graph layout and highlighting are editorial; IDs and edges come from FalkorDB.

## 00:32 to 00:46: The algorithm

“This tool runs shortest-path traversal inside Falkor-D-B. It finds the nearest ancestor that passed this validation suite on the exact saved artifact. Distance gives the agent a recovery option. It doesn't predict safety.”

Show the actual Cypher, parameters, returned path and evaluation ID. Label it “Unweighted lineage shortest path”. Do not call it weighted search, community detection or a learned algorithm.

## 00:46 to 01:00: The guardrail

“The agent makes the proposal. The guardrail checks sensor and action semantics, artifact hashes, complete validation and the training budget. Before training starts, the Decision stores the model, tool calls, candidates and the evidence it read.”

Show this new Decision's actual fields. Keep historical deterministic experiments labelled separately. A test-only veto fixture is not public run evidence and must not appear as a real rejected training attempt.

## 01:00 to 01:20: The run

Show the new run's saved learning curve and actual requested versus consumed steps, followed by reload and validation. Use its real 2D simulator states, with the 3D rendering clearly labelled as the same simulator. Do not use MuJoCo footage to imply this public run trained in physics.

“The worker trained sixty-one thousand, four hundred forty steps from sixty thousand requested, then reloaded the checkpoint for all one hundred eighty validation episodes.” Fixed training seed: 29. End-to-end recording: 71.25 seconds; film waiting time is trimmed and labelled. This run trains in the original 2D simulator; its parent's mixed-domain history is not new MuJoCo training.

## 01:20 to 01:40: The verdict, whatever it is

Show all four suite results and the collision limits: target 10%, open 5%, static 10%, crossing 15%. Read the real gate verdict and exact-artifact metrics from the new bundle. Compare to the chosen origin on matched validation, and say plainly if a measure regressed. Do not say “safer” merely because a gate passed.

“The fixed gate passed all four suites. Target collisions were three in sixty; open, zero in forty; static and crossing, one in forty each. But the parent had two target collisions and no crossing collisions. These results do not establish a safety improvement. I kept the results, and the demo policy stayed unchanged.”

On-screen limits: 10%, 5%, 10%, 15%, respectively. [Gate and matched parent measurements](../../../evidence/mcp-agent-v2/README.md#fixed-gate-result). Keep this measured regression central; do not replace it with the earlier confirmation result.

## 01:40 to 01:50: Keep the earlier evidence

The earlier 13/100 held-out failure stays visible. Robustness-v2's separate confirmation remains 8/100 target collisions. Its unchanged-weight MuJoCo-v2 target transfer remains 6/40. No frozen suite or existing result is rerun for this film.

## 01:50 to 02:00: Close

“I can inspect what the agent saw, what it chose, and what training actually produced. EmbodiWeave. Built on Falkor-D-B.”

Show the repo, AWS demo and `/mcp/` endpoint. Keep the existing AI, narration and music credits if their recordings or track are reused. A new voice request needs its own receipt. Upload the finished recut only after the spoken claims match the saved evidence.
