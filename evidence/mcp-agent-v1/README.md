# Public MCP fallback demonstration (v1)

This is a **deterministic fallback**, not an LLM-selected origin. OpenRouter exhausted its daily free-model quota before returning a model reply. The fallback made four real MCP calls and cited the native shortest-path result before launching PPO.

- Agent: `judge-ac370e535ba2636a28f2ba7c114c97b1`; Decision: `deci-20261016115640-8e0dbc`.
- Parent: `physics-20261016150004-25da9c` (mixed 2D + MuJoCo training history). This child trained only in the original 2D simulator.
- 60000 requested / 61440 consumed steps; fixed seed 29.
- 180 canonical validation episodes; unchanged promo-1: **4/4 pass**. No confirmation or deployment change.

| Suite | Goals | Collisions | Collision limit | Gate |
|---|---:|---:|---:|---|
| val-target-v1 | 57/60 | 3/60 | 10% | Pass |
| val-open-v1 | 40/40 | 0/40 | 5% | Pass |
| val-static-v1 | 39/40 | 1/40 | 10% | Pass |
| val-crossing-v1 | 39/40 | 1/40 | 15% | Pass |

The parent had target collisions of 2/60 and crossing collisions of 0/40 in the origin read; this child had 3/60 and 1/40. Passing the gate does **not** establish an improvement over that parent. All measured records remain in the receipts.

[Agent tool trace](agent-receipt.json) · [Training, Decision and gate receipt](training-receipt.json) · [Summary](summary.json) · [Exact checkpoint, source, validation outcomes and internal checksums.json](fallback-repro-v3.zip) · [Prospective protocol](protocol.json).
