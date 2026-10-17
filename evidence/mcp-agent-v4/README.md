# V4: the graph changed the eligible origins

The [protocol](protocol.json) was committed as `7b610c2` before the single attempt. Implementation and tests were green at `2735e99`. No second proposal, training attempt, fallback or final evaluation was made.

GPT-4.1 Mini called seven MCP tools: diagnosis, eligible origins, shortestPath, prior outcomes, weighted regression degree, the new regression-exclusion ranking, and `start_training`. The [Decision](decision.json) cites `outcome-deci-20261016121309-c0c93f` and the authored `regression-lineage-exclusion-v1` rule. The graph excluded the previous origin, `physics-20261016150004-25da9c`. The agent chose `robust-20261016140226-352fd7`, a different surviving origin. The citation and rule use were explicitly required by the protocol and prompt.

The [new tool result](rank_origins_excluding_regressed.json) retains the exact Cypher, parameters, graph revision, returned candidates and exclusion reasons. The [snapshot](graph-snapshot.json) is a read-only pre-run projection; tests modify only an isolated copy. Unknown support is not proof of safety. The raw model rationale calls its choice “safest”; that comparison is unsupported and is not a project claim. This is an authored eligibility rule, not evidence of autonomous learning or planner advantage.

## Measured result

60,000 requested steps, 61,440 consumed steps, seed 29, 180 unchanged canonical validation episodes. The fixed promo-1 gate passed all four suites. The separate parent comparison recorded a regression and did not release the child.

| Suite | Parent collisions | Child collisions | Limit | Gate |
|---|---:|---:|---:|---|
| Target | 2/60 | 4/60 | 10% | Pass |
| Open | 0/40 | 0/40 | 5% | Pass |
| Static | 1/40 | 1/40 | 10% | Pass |
| Crossing | 0/40 | 1/40 | 15% | Pass |

The [outcome](outcome.json) is `not_released_regression`. The process criteria were met; no improvement over the parent was established. The confirmed 8/100 checkpoint remains deployed. All earlier receipts and the v5 film are unchanged.

[Agent trace](agent-receipt.json) · [Training receipt](training-receipt.json) · [Gate](gate.json) · [Summary](summary.json) · [Checkpoint and episode bundle](repro-v4.zip) · [Verified bundle checksums](bundle-checksums.json)

[Post-run graph verification](post-run-mcp.json) · [Run file checksums](run-checksums.json)
