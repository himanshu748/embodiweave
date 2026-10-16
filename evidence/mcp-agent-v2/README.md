# Public LLM and MCP action demonstration (v2)

**GPT-4.1 Mini selected real MCP tools and started training on the public AWS deployment.** This separate operational demonstration followed a free-provider quota failure in [v1](../mcp-agent-v1/). It was registered before execution; it was not a retry for a better gate result.

## What ran

- Agent session: `judge-ce0e904e4e79d0ca94d7e69240da52e6`; source `llm_mcp`, no deterministic fallback.
- MCP discovery plus four calls: `diagnose_policy`, `find_training_origins`, `nearest_passing_ancestor`, `start_training`.
- Native FalkorDB `shortestPath`: `robust-20261016140226-352fd7 → search-20261015185749-4a6581` (1 hop).
- The model chose `physics-20261016150004-25da9c` from 17 verified origins. It chose the authored rank-one candidate; tests separately prove the guardrail permits other eligible choices.
- Guardrail allowed Decision `deci-20261016121309-c0c93f`, written before Run `run-20261016121310-0bfccc`. Graph revision 10 within deployment `06ec5d437ec1b73870aed1836d78e7f7a3fb9eec`.
- 60000 requested / 61440 consumed PPO steps, seed 29, original 2D environment only. The parent has mixed 2D and MuJoCo history.
- End to end: 71.25 seconds from agent start to completed validation/export. Provider-reported inference cost: $0.0062364; the separate availability probe is in [provider-probe.json](provider-probe.json).

## Fixed gate result

| Suite | Child goals | Parent collisions | Child collisions | Collision limit | Result |
|---|---:|---:|---:|---:|---|
| val-target-v1 | 57/60 | 2/60 | 3/60 | 10% | Pass |
| val-open-v1 | 40/40 | 0/40 | 0/40 | 5% | Pass |
| val-static-v1 | 39/40 | 1/40 | 1/40 | 10% | Pass |
| val-crossing-v1 | 39/40 | 0/40 | 1/40 | 15% | Pass |

**Unchanged promo-1: 4/4 pass. Target and crossing collisions regressed relative to the chosen parent.** The example demonstrates auditable agent action, not an established safety improvement or an advantage over the deterministic planner. The model's suggestion that mixed-domain history might help robustness is its recorded rationale, not a measured causal finding.

No confirmation was performed, and this child did not replace the current demo policy. The prior frozen search, confirmation and physics studies are unchanged. The v1 and v2 action demonstrations use the same requested budget and fixed training seed; v2 is an operational reproduction with an actual model decision, not independent evidence of training reliability.

## Inspect the evidence

- [Agent receipt: actual MCP calls, model and provider usage](agent-receipt.json)
- [Decision: Cypher, parameters, candidates, origin, guardrail and protocol hash](decision.json)
- [Native algorithm output](algorithm.json) and [exact Cypher](nearest-passing-ancestor.cypher)
- [Training receipt and all gate checks](training-receipt.json)
- [Checkpoint, source and episode-level evidence bundle](repro-v3.zip)
- [Bundle verification](bundle-verification.json), [study checksums](checksums.json), [prospective protocol](protocol.json)
- [Live Decision node](https://embodiweave.52.202.25.181.sslip.io/api/decisions/deci-20261016121309-c0c93f)

Artifact hash: `c6c910a7a9b826b3a23370e4c9762c95537cb7dfb9e1512d7c32ab37532ecd13`. Bundle SHA256: `5019c21b27b984d78e479883ef6b3c854385a7ce4c3eea8d64472860bc5d623c`. Numeric graph revisions can reset on rebuild; the saved query records and deployment commit identify this snapshot.
