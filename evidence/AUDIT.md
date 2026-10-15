# PRD and spec audit

Audited 15 October 2026 against `docs/v2-original/prd.md` (FR-01 to FR-18, section 12 release checklist)
and `docs/v2-original/spec.md` (section 16 acceptance matrix). Each line points at evidence in this repo or
at the live site. Status: **Done**, **Partial** (works, with a stated limit) or **Missing**.

Verdict: every functional requirement and every acceptance-matrix row is covered by code, tests or recorded
runs. The open items are the demo video, the fact that no trained checkpoint met the full collision limit,
and the small seed count, which the PRD itself treats as preliminary evidence.

## Functional requirements (PRD section 7)

| ID | Status | Evidence |
|---|---|---|
| FR-01 Evaluate a policy and scenario | Done | Evaluation records carry policy, artifact hash, suite, seeds: `artifacts/records/evaluation/`; `ew/service.py` evaluate |
| FR-02 Observation semantics fixed | Done | `evidence/gate1/frozen_contract.json`; `tests/test_env.py` ray semantics, history reset |
| FR-03 Enforce compatibility | Done | `tests/test_graph.py::test_compat_rejects_same_shape`, `tests/test_env.py::test_contract_ids_differ_with_same_shape`; P-mirror rejected for ray_order in every decision |
| FR-04 Retrieve connected evidence | Done | 10 read templates in `ew/graph/queries.py`; decision records store params, rows and record ids |
| FR-05 Compare all eligible parents | Done | `tests/test_graph.py::test_missing_validation_requires_evaluation_then_ranks_all`; no top-N cutoff, rejected list with reasons |
| FR-06 Record the selection rule | Done | Decision records: rule_version, graph_revision, ranking, explanation (`artifacts/records/decision/`) |
| FR-07 Real adaptation | Done | SB3 PPO worker `ew/jobs.py`; `tests/test_graph.py::test_reload_normalization_and_weights`, `test_parent_immutable_and_distinct_child` |
| FR-08 Retain unsuccessful trials | Done | `tests/test_graph.py::test_failed_trial_recorded_without_invented_steps`; 41 trials in the graph, most not reached, steps_to_threshold null |
| FR-09 Promote exact artifacts only | Done | `tests/test_gate3.py::test_promotion_requires_exact_artifact_evidence`; `prom-20261015060506-9a3c7a` binds to hash 556ec083 |
| FR-10 Independent test roles | Done | `tests/test_graph.py::test_final_test_protected`, `tests/test_env.py::test_protected_suites_disjoint_seeds`; spent suites refused in `ew/scenarios.py` |
| FR-11 Safe training resources | Done | `tests/test_gate3.py` idempotency, quota, cancel, restart recovery |
| FR-12 Real runtime agent | Done | OpenRouter run `agent-20261015060343-b9e6bc` (8 turns, full loop); deterministic runs labelled separately |
| FR-13 Genuine replay | Done | `tests/test_env.py::test_replay_trace_records_real_state`; landing replay built from stored replays by `scripts/make_hero_replay.py` |
| FR-14 Meaningful interaction | Done | Studio: scenario controls (mover speed and radius run a real evaluation), replay scrubber, candidate ranking, evidence tab, graph view |
| FR-15 Isolate counterfactuals | Done | `tests/test_graph.py::test_whatif_isolated_and_changes_choice`, `tests/test_select_v2.py::test_whatif_scratch_evidence_flips_to_scratch_and_cannot_launch` |
| FR-16 Graph outages | Done | `tests/test_graph.py::test_outage_stops_decisions`; `evidence/gate2/whatif_outage.log` (docker stop) |
| FR-17 Export reproducibility | Done | `ew/service.py::export_bundle`; `tests/test_graph.py::test_export_bundle_contains_reloadable_artifact`; bundles in `artifacts/exports/` |
| FR-18 Run without hardware | Done | Simulation only; `README.md` Run it (Docker plus Python, no GPU) |

## Release checklist (PRD section 12)

| Item | Status | Evidence |
|---|---|---|
| Real failure-to-fix workflow, failed outcome supported | Done | Deployed P-static-b 0.37 success / 0.48 collision (`eval-20261015040917-9c0df8`); live run ends in a recorded rejection |
| More than one eligible parent in the demonstrated choice | Done | 4 eligible parents plus scratch ranked in `deci-20261015060348-a7ee2c` |
| Tested query-to-action provenance and exact-artifact promotion | Done | `decision_provenance` template, `tests/test_gate3.py`, landing Live console question 4 |
| PPO artifacts reload with normalization | Done | `tests/test_graph.py::test_reload_normalization_and_weights`; gate 1 reload check |
| Failed and successful trials retained immutably | Done | `artifacts/records/trial/`; records are write-once, opened with O_EXCL and mode 0444 (`ew/records.py`) |
| Train / validation / frozen-test separation, fair accounting | Done | `evidence/gate5/RESULTS.md`: equal 150k budgets, paired seeds, library cost reported separately, each test suite used once |
| Studio uses genuine simulated execution data | Done | Replays from stored simulator states; `evidence/gate4/` |
| Outage and What-if described accurately | Done | `README.md`, `evidence/GATES.md` gate 2 |
| Complete local reproduction and a truthful demo | **Partial** | Local setup and fresh-clone tests: `evidence/GATES.md` gate 6. **Demo video not recorded yet** (script: `docs/demo-script.md`) |
| README: graph model, queries, results, limitations, licenses, AI use, dates | Done | `README.md` sections of those names |
| Implementation history preserved, no unsupported claims | Done | Full git history; pre-event PRD and spec kept with their 14 Oct date and sha256 (`evidence/gate0/readiness.md`) |

## Acceptance test matrix (spec section 16)

| Area | Status | Evidence |
|---|---|---|
| Environment | Done | `tests/test_env.py` (checker, seeded reset, motion, collisions, timeout, replay) |
| Observation contract | Done | `tests/test_env.py` ray semantics, history order and reset |
| RL proof | Done | Weight change, save, reload, fixed-suite evaluation: `tests/test_graph.py`, gate 1 learnability logs |
| Normalization | Done | `tests/test_graph.py::test_reload_normalization_and_weights` |
| Compatibility | Done | Same-shape rejection tests (two) |
| Candidate selection | Done | `tests/test_graph.py`, `tests/test_select_v2.py::test_v3_uses_trial_child_validation_on_ties` |
| Prerequisites | Done | `tests/test_graph.py::test_mission_prerequisite_closure` |
| Routes (only if implemented) | Not applicable | Route planning not implemented (optional in PRD section 6) |
| Trial evidence | Done | Failed and cancelled trials: `tests/test_graph.py`, `tests/test_gate3.py` |
| Promotion | Done | Exact hash, suite thresholds, target plus retained suites; parent and wrong-hash evidence ignored: `tests/test_gate3.py::test_promotion_requires_exact_artifact_evidence` |
| Data roles | Done | Final-test protection tests; spent suites refused |
| MCP and agent | Done | `tests/test_gate3.py::test_agent_tool_guards`; live OpenRouter trace |
| Worker | Done | `tests/test_gate3.py` |
| Graph value | Done | Evidence changed the choice: gate 2 (P-static-b to P-static-a), exp-2 and exp-3 (scratch), What-if flips |
| What-if | Done | Isolation tests; production fingerprint unchanged (`evidence/gate2/whatif_outage.log`) |
| Graph outage | Done | `tests/test_graph.py::test_outage_stops_decisions` |
| Provenance | Done | Decision records hold params, returned ids, revision, action, run and result |
| Studio | Done | Scenario changes, replay comparison, mode badges, evidence, export; hosted read-only mode `tests/test_hosted.py` |
| Reproduction | Done | Fresh clone of the public repo, new venv from `requirements.lock`, 37 of 37 tests passed (39 with the tests added today): `evidence/GATES.md` gate 6 |

## Real gaps, stated plainly

1. **Demo video.** Not recorded. Only the owner can record and upload it. `docs/demo-script.md` has a
   3-minute script plus a 30-second opening for the hosted site.
2. **No arm met the full threshold.** The graph-chosen scratch arm reached about 0.70 test success, but
   collisions stayed near 0.18 against the 0.10 limit. The live agent's checkpoint got 0.87 success and 0.13
   collisions on the target suite and was rejected by the gate. The PRD sets no minimum success, so this is
   a disclosed limitation, not a missing requirement.
3. **Three seeds.** The graph arm beat the latest and best-validation checkpoints on every paired seed in
   exp-2 and exp-3. That is consistent but preliminary; no significance or general efficiency claim is
   made, as PRD section 8 requires.
4. **Selection rule revised twice after results.** Each revision was committed before its experiment and
   judged on an unused final-test suite. Disclosed in `evidence/gate5/RESULTS.md`.
5. **Pre-event documents.** The PRD and spec are dated 14 October, before kickoff. They are disclosed,
   not relabelled. Whether they count as notes or design work under rule 8 is the organizers' call.
6. **Host.** Everything ran on a Linux cloud container. The owner's MacBook was never used, so a Mac
   setup is untested.
