# EmbodiWeave

An agent that reads a robot's training history in FalkorDB, decides which checkpoint to retrain, launches training, and proves whether the new policy got safer.

Track: Agents That Act on Connected Data

## Result: confirmed in 2D

Graph-selected `robust-20261016140226-352fd7` passed 4/4 unchanged validation suites and fresh preregistered confirmation: 100 episodes per family. Collisions: target 8/100 (10% limit), open 0/100 (5%), static 4/100 (10%), crossing 5/100 (15%). [Evidence](../evidence/robustness-v2/).

## Why Track 01

FalkorDB connects exact artifacts, semantic sensor/action contracts, origins, trials, evaluations, failures and Decisions. Decisions save model, tool calls, Cypher, parameters, candidates and verdict before training. [Queries](../README.md#why-track-01).

## The agent acting on the graph, and the guardrail

GPT-4.1 Mini discovered MCP tools, diagnosed a checkpoint, compared origins and read FalkorDB's shortestPath to a passing ancestor. It chose `physics-20261016150004-25da9c`, launching 60,000 requested / 61,440 consumed CPU PPO steps. The reloaded checkpoint passed 4/4 gates across 180 validation episodes. Target 3/60 and crossing 1/40 collisions regressed against the parent's 2/60 and 0/40. The comparison kept this child from release; the demo policy stayed unchanged. [Recorded action](../evidence/mcp-agent-v2/).

The pre-training guardrail can veto missing evidence, incompatible semantics, stale hashes or unsupported budgets. Provider failure uses a labelled [deterministic MCP fallback](../evidence/mcp-agent-v1/); graph failure stops planning.

## Judge walkthrough

Watch 2D simulation or its 3D rendering and download evidence.

## Earlier studies and MuJoCo

Earlier rehearsal failed held-out target collisions at 13/100. Unchanged-weight MuJoCo target transfer remains 6/40; physics confirmation is unopened.

## Honest limitations

[Rehearsal](../evidence/rehearsal-recovery-v1/): parent and both children had 7/180 collisions. [Stronger collision cost](../evidence/collision-recovery-v1/): 12/180 versus control 14/180, parent 12/180.

These simulations establish no hardware safety, improvement over the parent or planner advantage.

Next: independent training seeds and stronger crossing behaviour. Claude and Codex assisted implementation and experiments; measurements come from saved checkpoints.
