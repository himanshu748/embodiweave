# Demo film and extended walkthrough

The shipped [60 second film](https://embodiweave.onrender.com/media/embodiweave-demo.mp4) is an edited
walkthrough captured from the running application through the Codex in-app browser. It uses actual
simulator replay frames, live database query responses, the recorded decision/gate and the agent trace
viewer. Captions and a choreographed pointer explain the sequence. No new training run is depicted.

| Time | Evidence |
|---|---|
| 00–11 | Same recorded seed 1300032: deployed collision at step 51, new checkpoint goal at step 112 |
| 11–21 | Actual live FalkorDB conditional parent-trial query; 27 rows, none reached threshold |
| 21–30 | Actual live scratch-history query; Cypher, parameters and returned rows |
| 30–43 | Recorded ew-select-3 ranking and rejected promotion; 1 of 4 suites passed |
| 43–52 | Studio runtime agent trace, public launch restriction and local consent control |
| 52–60 | Judge guide and local reproduction route |

Recorded decision: `deci-20261015060348-a7ee2c`. Promotion: `prom-20261015060506-9a3c7a`.
Agent: `agent-20261015060343-b9e6bc`, OpenRouter `anthropic/claude-sonnet-5.5`, 8 model turns, 13 tool calls,
94 seconds. New checkpoint artifact hash: `556ec083bc8589363d034745bac670bf7e0afb17fedf138ea0fd8b8797066baa`.

The live graph contains evidence appended after the featured decision. Live row counts can therefore
differ from the recorded decision’s ranking. The decision’s queries and revision remain inspectable.

## Extended interactive walkthrough

1. Open the landing replay and switch 3D / Top view. Aggregate target metrics come from 60 episodes.
2. Run parent and scratch trial queries. Compare their exact target, contract, recipe, threshold and budget.
3. Inspect the frozen ranking, semantic rejection of P-mirror and all four promotion checks.
4. Open Studio → Evidence and Graph. Trace the records, not just the summary.
5. Open What-if, add hypothetical successful parent trials, run it and inspect the unchanged production
   fingerprint. Training from a hypothetical decision is disabled.
6. Locally, enable a provider and `EW_ALLOW_LLM=1`, consent in Agent and launch one investigation.
   Jobs shows actual progress and cancellation. Public Render never launches this work.
7. Export a checkpoint and run the bundle’s own `REPRODUCE.md` command. New bundles contain source,
   source hashes, dependencies and checksums. Smoke subsets cannot pass full validation.
8. Close with limitations: software simulation, three seeds, no full benchmark threshold met and no
   demonstrated efficiency or real-world safety advantage.
