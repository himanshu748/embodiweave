# Public MCP follow-up v3: stopped before training

Protocol committed before the sole attempt in `1fcfade`. GPT-4.1 Mini called five MCP read tools, including the connected prior outcome and weighted regression degree. The tool output alone exceeded the 32,000-byte model-request cap before the second model response. The HTTP SDK wrapped that failure, producing the generic message retained in the original receipt.

No origin was selected, no training started, no validation episodes ran, and no gate result exists. No retry was made. The algorithm appeared in a real tool trace but did not produce a recorded decision change.

`v2-outcome-backfill.json` records the existing v2 comparison, without reevaluation: target 2/60 to 3/60 and crossing 0/40 to 1/40. Its weighted incoming degree is 1/60 + 1/40 = 0.0416667, supported by one child. Unknown origins have null degree, not zero risk. This descriptive ranking is not a safety estimator or evidence of planner advantage.

`agent-receipt.json` is the unchanged failed public receipt. `context-diagnosis.json` reproduces the serialization limit offline. `post-attempt-audit.json` and `decision.json` preserve a clearly labelled audit Decision written AFTER the failed attempt, not a fabricated pre-training decision. The new connected outcome preserves the original v2 Decision and all old evidence.

The implementation now compacts provider context, limits the weighted ranking to eligible origins and preserves bounded errors across SDK exception groups. Offline tests cover this repair. It was not used to rerun v3.
