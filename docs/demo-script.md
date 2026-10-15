# EmbodiWeave: 60-second judge film

Edited captures of the real browser interface. Captions describe recorded evidence
unless explicitly marked live. No fabricated robot footage or invented outcomes.

| Time | Browser view | Caption |
|---|---|---|
| 0–10s | Evidence page, graph lineage query and verdict | FalkorDB evidence chose the next robot training run. The new lineage passed validation; its held-out target still failed. |
| 10–20s | First attempt table | Longer training passed 3 of 4 suites. Open-arena success was 82.5%, below 90%. The rejection stayed in the graph. |
| 20–31s | Second attempt and its decision | The planner selected the improved child, then rehearsed all training families. All 4 validation suites passed. |
| 31–40s | Held-out result and limits | One held-out target test: 86 goals, 13 collisions, 1 timeout. Collision limit: 10%. No further tuning. |
| 40–50s | Live training page or clearly recorded simulator replay | Judges can train real PPO and watch the 2D or 3D simulator. The gate checks the saved artifact on 180 validation episodes. |
| 50–60s | Bundle download, Cypher and source links | Inspect the graph decision, rejected runs, exact artifact hashes and checksummed evidence. Try EmbodiWeave on the live webpage. |

The planner's priorities are authored rules. New search decisions are deterministic;
the optional live model chooses bounded graph tools. The film must not imply the
LLM invented rehearsal, that validation passed on held-out retained tasks, or that
production weights changed. The original rejected replay remains on the landing page.
