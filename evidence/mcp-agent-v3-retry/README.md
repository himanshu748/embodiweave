# v3-retry — one registered outcome-aware run

[Protocol](protocol.json) was committed as `1a950ba` before the sole run. The earlier [v3 receipt](../mcp-agent-v3/agent-receipt.json) remains byte-for-byte unchanged.

GPT-4.1 Mini called `diagnose_policy`, `find_training_origins`, `nearest_passing_ancestor`, `get_decision_outcomes`, `rank_regression_origins`, then `start_training` over MCP. The [Decision](decision.json) cites `outcome-deci-20261016121309-c0c93f`, as explicitly required by the protocol and prompt. It describes the prior target and crossing regressions, but chooses the same origin as v2: `physics-20261016150004-25da9c`. Its stated intention to improve robustness is not a measured result.

The one run consumed 61,440 PPO steps (60,000 requested), seed 29, then completed 180 unchanged canonical validation episodes. All four promo-1 checks passed. The child again regressed against its parent and was not released.

| Suite | Child collisions | Parent collisions | Collision limit | Gate |
|---|---:|---:|---:|---|
| Target | 3/60 | 2/60 | 10% | Pass |
| Open | 0/40 | 0/40 | 5% | Pass |
| Static | 1/40 | 1/40 | 10% | Pass |
| Crossing | 1/40 | 0/40 | 15% | Pass |

The [connected outcome](outcome.json) is `outcome-deci-20261016175734-1b2724`, with release verdict `not_released_regression`. The current demo policy remains `robust-20261016140226-352fd7`. The registered process criteria were met; neither a different origin nor learning, planner advantage or improvement was established. No further retry was made, and no final tests were opened.

## Context repair

The old five tool results totaled 33,515 bytes, exceeding the application's 32,000-byte request cap even before messages and schemas. This was the local serialized-request guard, not an OpenRouter model context-window rejection. [Diagnosis and measured summaries](context-fix.json).

Model-facing tool summaries now have a 2,000 UTF-8-byte ceiling each, with 12,000 bytes across retained tool text, six exchange groups and a 28,000-byte whole-request limit. Byte counts conservatively bound byte-BPE text tokens; they are not tokenizer measurements. Whole call/response exchanges are retained or removed together. Full graph records remain available through the read-only `get_evidence_record` tool; full tool results are retained in the Decision audit. Omitted candidates are labelled, so the model's top-k view is a limitation. The three real requests peaked at 17,926 bytes.

## Receipts

- [Model wire calls and provider usage](agent-receipt.json)
- [Training and all validation summaries](training-receipt.json)
- [Full pre-training Decision](decision.json), [gate](gate.json), [outcome](outcome.json)
- [Read-only graph verification after completion](post-run-mcp.json)
- [Checkpoint, normalization and episode evidence bundle](repro-v3-retry.zip), [verified internal checksums](bundle-checksums.json)
- [Machine-readable summary](summary.json), [file checksums](checksums.json)
