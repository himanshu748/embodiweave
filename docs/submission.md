# EmbodiWeave

An agent that reads a robot's training history in FalkorDB, decides which checkpoint to retrain, launches training, and proves whether the new policy got safer.

Track: Agents That Act on Connected Data

I built EmbodiWeave to make checkpoint selection and deployment checks inspectable.

FalkorDB connects exact artifacts, semantic sensor/action contracts, training origins, trials, evaluations, failures and Decisions. The live agent discovers domain tools through MCP. It diagnoses a checkpoint, compares eligible origins and calls FalkorDB's shortest-path algorithm to find a passing ancestor. It proposes its own origin and launches CPU PPO. An authored guardrail can veto missing evidence, incompatible semantics, stale hashes or unsupported budgets. Each Decision saves the model, actual tool calls, Cypher, parameters, candidates and verdict before training.

The trusted worker reloads the new artifact, runs 180 validation episodes and applies the unchanged promotion gate. Provider failure uses an explicitly labelled deterministic MCP fallback; graph failure stops planning. Judges can watch the 2D simulator or its 3D rendering and download evidence.

Frozen results remain visible: the earlier rehearsal checkpoint failed held-out target collisions at 13/100. A separate study passed all four fresh confirmation families, with 8/100 target collisions against a 10% limit. Its unchanged-weight MuJoCo transfer still had 6/40 target collisions. Physics confirmation remains unopened. These are simulation results, not hardware-safety proof.

The new MCP demonstration has its own [protocol and evidence](../evidence/mcp-agent-v1/). [Why Track 01 and actual queries](../README.md#why-track-01). Next: independent training seeds and stronger crossing behaviour. Claude and Codex assisted with implementation and experiments; measured results come from saved checkpoints.
