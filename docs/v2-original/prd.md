# EmbodiWeave
## Product Requirements Document

**Version:** 2.0, replacement document  
**Revision date:** 14 October 2026, Asia/Kolkata  
**Track:** Track 1 only, Agents That Act on Connected Data  
**Subtitle:** Turn robot failures into evidence-backed training decisions.  
**Companion documents:** [Technical specification](spec.md) and [Claude kickoff](claude_initial_prompt.md)

> This is the actual revised PRD, not a handoff note. It incorporates the accepted failure-to-fix corrections and replaces the v1 product requirements. The original files remain unchanged. No implementation, training result, runtime test, or competition-eligibility certification is supplied with this revision.

### Document provenance and timing

This replacement consolidates the original PRD, the accepted corrections in `embodiweave-handoff-note.md` sections 3.1 to 3.8, its implementation gates, and the three subsequent editorial clarifications. Rejected recommendations from the earlier review are not governing requirements. All needed requirements are integrated here and in `spec.md`; a builder does not need to resolve a stack of conflicting handoff notes.

The user requested these replacements now, rather than another instruction to rewrite them later. Their actual 14 October creation date must remain visible. The handoff reports an event window of 15 October 2026 at 00:01 IST through 18 October at 23:59 IST, and a rule restricting main coding and design to that window. These claims are carried from that source, not newly verified here. Re-check the official rules before implementation. Do not backdate these documents, conceal pre-event material, or assume that changing a document's label establishes eligibility.

## 1. Executive summary

EmbodiWeave is a graph-guided reinforcement-learning studio for robotics developers and students who work in simulation.

**Product promise:** A robot policy fails. EmbodiWeave uses checkpoint history and failure evidence to choose what to reuse or train next, executes real PPO, and verifies the result.

A user selects a supported mission, evaluates an existing policy, and inspects the actual failure. An agent queries FalkorDB for compatible checkpoints, policy ancestry, relevant validation results, and previous transfer trials. It chooses a justified training experiment, starts a bounded worker, evaluates the resulting checkpoint, and either promotes or rejects it through deterministic gates.

The user receives a real policy artifact, reproducibility records, synchronized before-and-after replay, and an inspectable explanation of the graph-backed decision.

**The environment is simulated. The training and evaluation records are measurements from software execution.** They are not observations from a physical robot. No hardware purchase is needed for this product scope.

## 2. Problem and audience

The primary audience is robotics and reinforcement-learning developers working on supported mobile-navigation tasks. Secondary users are Indian engineering-college robotics clubs, student researchers, and builders without physical robot access.

The problem being addressed is the work between a failed policy and the next useful training experiment: finding a compatible parent, understanding which evidence is relevant, avoiding repeated unproductive transfers, preserving previously useful behavior, and proving what the new artifact can actually do.

**Job to be done:** Given a failed policy and a supported target task, help me select what to train next and provide a tested artifact with evidence I can inspect and reproduce.

Demand and performance advantages remain product hypotheses. No user interviews, adoption statistics, or benchmark improvements have been established by the supplied documents.

## 3. Core decision: parent selection, not a fixed curriculum

The MVP is a small branching parent-selection problem. It must contain a handful of distinct checkpoints with genuinely different, documented training histories and more than one eligible choice for at least one demonstrated decision.

The product does not require a large checkpoint catalog, multiple robot types, or a graph with a target node count. Duplicate checkpoints and invented histories do not create useful complexity.

Every candidate must be checked against the robot's semantic input/output contract. Eligible candidates must be evaluated on a comparable, versioned validation suite. Relevant transfer history can then inform selection under a documented selection rule.

The three-stage `ReachGoal -> AvoidStatic -> YieldDynamic` chain is no longer the main product or benchmark. Those scenario families can still be used for training and testing, but their names do not prescribe a universal training order.

### What the system must not infer

- A collision category is an observation, not proof of a particular missing skill or root cause.
- A handwritten connection from a failure type to a competency is a labeled hypothesis, not measured evidence.
- Several policies covering different competencies do not automatically form one executable controller.
- Finishing PPO training does not establish that a checkpoint is suitable for a mission.
- A short live run does not guarantee an improvement.

## 4. What FalkorDB does

FalkorDB is the operational decision graph. Typed relationships connect robot configurations, policies, training runs, validation evaluations, scenario distributions, failure evidence, competencies, and transfer trials.

The graph supports the following consequential decisions:

1. Whether a source checkpoint can be reused under the current robot and policy contract.
2. Which candidate histories and trial outcomes are relevant to the requested adaptation.
3. Which compatible parent should be selected under the recorded selection rule.
4. Whether the exact resulting checkpoint has sufficient validation evidence for promotion.

The UI exposes query parameters, returned record IDs, graph revision, decision, action, and outcome. The graph must affect the executable choice, not merely the explanation text.

### Three separate claims

| Claim | Required evidence |
|---|---|
| Graph-backed behavior | Relevant evidence or compatibility changes produce a traceable, justified change in selection, allowed reuse, or promotion. |
| Operational dependency handling | When FalkorDB is unavailable, graph-dependent decisions stop explicitly instead of using a hidden substitute. |
| Better RL outcomes | Fair measured comparisons show whether the selection method improves adaptation outcomes. Improvement is not assumed. |

An outage test proves failure handling, not a graph-performance advantage. No claim is made that another properly implemented graph engine could not express similar relationships.

## 5. Primary user journey

### A. Observe the failure

The user chooses a supported robot configuration, mission, existing policy, and scenario. The application runs or replays an actual evaluation. A moving crossing obstacle is one useful scenario, but any failure claim must be supported by that evaluation's trajectory and metrics.

The display clearly distinguishes the simulated environment from the origin of the displayed run: Live, Recorded, or What-if.

### B. Inspect candidate parents

The user asks the agent to investigate. The agent retrieves failure evidence and queries FalkorDB for candidate policies, their lineage, semantic compatibility, matched validation results, and relevant previous transfers.

The comparison panel includes all eligible candidates in the small catalog. It also explains rejected candidates. There is no arbitrary top-three cutoff or ranking by the best score from unrelated tasks.

### C. Train the selected candidate

The agent selects a graph-backed experiment through bounded tools. The trusted backend validates the selection, budget, and source artifacts before launching a real worker. The original checkpoint remains immutable; the new run produces a separate candidate.

Progress must come from actual environment steps and training events. Cancellation and explicit failure reporting remain available.

### D. Validate and decide

The resulting checkpoint is evaluated on the target competency and the prerequisite behaviors it must retain. Promotion binds to the exact artifact hash and required versioned validation suite.

A failure is a valid result. It is retained as evidence and may affect a later planning decision. The UI does not substitute a successful recorded checkpoint for the live result.

### E. Inspect and export

The user can compare actual trajectories, inspect query-to-action provenance, and export the policy, normalization artifacts, configuration, metrics, and reproduction instructions.

## 6. MVP scope

### Required

- One supported simulated mobile-robot configuration with a fixed temporal observation and action contract.
- A CPU-friendly Gymnasium environment and actual Stable-Baselines3 PPO training.
- A handful of distinct, documented checkpoints; a meaningful choice between eligible parents.
- A pinned FalkorDB runtime, tested read templates, and typed experiment relationships.
- One runtime LLM provider tested with one bounded MCP integration.
- One bounded training worker with quotas, cancellation, idempotency, restart recovery, and artifact checks.
- Matched candidate evaluation, immutable successful and unsuccessful transfer trials, and guarded promotion.
- An isolated, clearly labeled What-if copy for the evidence-intervention demonstration; never mutate measured production records.
- One polished interactive studio with synchronized replay, graph evidence, candidate comparison, and useful scenario controls.
- Separate training, validation, and frozen final-test roles; fair comparison arms.
- Reproducible local setup, real demo artifacts, and truthful disclosures.

### Optional, only after the core passes

- A clearly labeled static evidence/replay website after hosting entitlements are verified.
- A thin 3D presentation driven by the same simulator states as the core viewer.
- Multi-stage transfer-route planning, but only with a state representation that can express compatibility and retained competence correctly.

An isolated What-if demonstration belongs to the evidence gate. If a safe copy mechanism cannot be verified, disable editable What-if interactions and report that acceptance check as incomplete. Never edit production measurements as a substitute or silently count an unsafe demonstration as passing.

### Outside v1

ROS, Gazebo, Isaac, URDF import, arbitrary robot support, physical robot operation, distributed workers, fleet coordination, a checkpoint zoo, multiple mandatory LLM providers, and a mandatory heavyweight frontend framework.

## 7. Functional requirements

| ID | Requirement | Acceptance condition |
|---|---|---|
| FR-01 | Evaluate a supported policy and scenario | Metrics and replay identify the exact policy, scenario suite, configuration, and seeds. |
| FR-02 | Preserve observation semantics | Ordering, units, history, normalization, action scaling, timestep, and wrappers are fixed and recorded. |
| FR-03 | Enforce compatibility | A semantic mismatch rejects reuse even when tensor shapes match. |
| FR-04 | Retrieve relevant connected evidence | Actual graph results contain candidate lineage, compatibility, validation, and applicable trial IDs. |
| FR-05 | Compare eligible parents fairly | All eligible candidates are scored on a comparable versioned validation suite; exclusions are explained. |
| FR-06 | Record the selection rule | Inputs, rule version, graph revision, selected parent, and explanation are inspectable. |
| FR-07 | Execute real adaptation | A worker performs PPO updates and saves a separate reloadable checkpoint. |
| FR-08 | Retain unsuccessful trials | Budget, seed, validation schedule, threshold status, and artifacts are retained without invented steps-to-threshold. |
| FR-09 | Promote exact artifacts only | Required target and retained-behavior validation applies to the artifact being promoted. |
| FR-10 | Enforce independent test roles | The planner cannot tune against the frozen final-test suite. |
| FR-11 | Handle training resources safely | Quotas, cancellation, idempotency, recovery, and explicit failure states work. |
| FR-12 | Keep a real runtime agent | Actual tool calls through a tested provider are logged; deterministic mode is labeled separately. |
| FR-13 | Show genuine replay | Robot and obstacle positions come from the selected execution, not independent animation. |
| FR-14 | Support meaningful interaction | Scenario selection/control, replay scrubbing, parent inspection, and evidence navigation work. |
| FR-15 | Isolate counterfactuals | What-if edits cannot overwrite measured production evidence or silently change a real job. |
| FR-16 | Handle graph outages | New graph-dependent decisions stop with an explicit error. Recorded evidence may remain viewable as Recorded. |
| FR-17 | Export reproducibility evidence | The checkpoint, normalization contract/artifacts, configuration, seeds, logs, and hashes are available. |
| FR-18 | Run without hardware | The documented local workflow requires no physical robot or privileged robotics data. |

## 8. Evaluation and success criteria

### Engineering success

A credible release completes the failure-to-fix loop with genuine artifacts: valid environment, measured throughput, actual PPO update, reloadable policy, graph-backed parent choice, runtime tool action, exact-artifact validation, and export.

It must demonstrate at least one justified changed decision when relevant graph evidence changes. A changed caption without a changed eligible choice or action is insufficient.

### Experimental comparison

The required arms are:

1. Graph-selected warm start.
2. Latest compatible eligible checkpoint.
3. Best checkpoint on matched validation.
4. Training from scratch.

Use equal adaptation budgets, the same target environment and algorithm, a consistent evaluation protocol, and paired seeds. Charge intermediate training stages to adaptation. Report library-building and prior transfer-measurement costs separately. An incompatible checkpoint is a rejection test, not a deliberately weak baseline.

Where feasible, compare the full planner with a variant without transfer history while keeping compatibility and evaluation rules the same.

Training data drives policy updates. Validation supports tuning, candidate selection, and promotion. The frozen final test evaluates the final locked choice and method. If the system adapts to final-test outcomes, that test is spent and cannot remain an untouched benchmark.

Report per-training-seed success, collisions, budget, wall-clock time, and whether the threshold was reached. Repeated episodes from one checkpoint are not independent training runs. Three seeds provide preliminary evidence, not a broad performance guarantee.

### Product and scientific limits

No minimum success percentage or training-speed improvement is promised. The accepted sources do not establish numeric thresholds, measured run budgets, or the final parent-scoring formula. These must be set, versioned, and tested at the relevant implementation gates, before benchmark comparison and final testing.

If the experiment is negative or inconclusive, show that result. The product may still produce useful provenance and reject unsupported transfers, but must not claim a demonstrated efficiency advantage.

## 9. Studio experience

The visual ambition remains a polished, deeply interactive robotics workspace. Simplifying the renderer does not mean replacing the product with a graph table and disconnected buttons.

**Arena:** actual simulated trajectories, playback controls, obstacle motion, goal, collision/timeout markers, and synchronized before/after comparison.

**Candidate comparison:** eligible parents, rejection reasons, matched validation evidence, relevant transfer history, and the selected parent with its recorded reasoning.

**Graph and evidence:** selectable paths and records, query parameters, graph revision, artifact IDs, and links from an explanation to the measured evidence supporting it.

**Training controls:** bounded launch, status, cancellation, completed evaluation, promotion outcome, and export.

**Scenario controls:** a small number of meaningful supported changes that alter actual evaluation configuration. Editing a scenario is not the same as editing measured evidence.

**Honesty and accessibility:** readable labels, keyboard controls, useful loading/empty/error states, and persistent Live / Recorded / What-if indicators. A static replay never claims to perform live graph queries.

## 10. Constraints and deployment

The preferred machine is the user's MacBook Air M4 with 16 GB RAM, but execution access and throughput remain unmeasured. The earlier 2 CPU / 7 GB observations belong to Claude Chat's Linux sandbox, not the Mac. The build session must establish its actual host rather than infer access from an attached folder.

Measure the real environment and PPO throughput before choosing run counts. Use one bounded worker; polling is sufficient if it supports the workflow. Do not require a distributed queue or a GPU.

The dependable release path is local execution with complete setup and a genuine demo video. A static evidence site is optional. Verify provider entitlements instead of assuming a free tier or working deployment. Persist original evidence outside an ephemeral graph so the graph can be rebuilt from real records.

Runtime LLM access is separate from the coding assistant. Select one provider only after verifying credentials, tool calling, and quota. Deterministic tests may continue without credentials, but that mode must not be represented as the LLM-agent demonstration. No spending or external publication without approval.

## 11. Ordered delivery gates

| Gate | Deliverable | Evidence required |
|---|---|---|
| 0 | Execution and eligibility readiness | Current clock, official-rule recheck, actual host/workspace, runtime availability, and truthful document provenance. These v2 documents already exist; no rewrite cycle is required. |
| 1 | Environment and reloadable PPO | Environment checks, observation invariants, frame reset, measured throughput, updated weights, normalization reload, fixed-validation evaluation. |
| 2 | Real graph decisions | Pinned runtime, tested templates, all eligible candidates, compatibility rejection, and an evidence change that alters a justified decision. |
| 3 | Agent loop | One tested provider and MCP integration, real worker actions, failed-trial recording, and guarded exact-artifact promotion. |
| 4 | Interactive studio | Synchronized replay, graph paths, parent comparison, evidence inspection, scenario controls, honest modes, accessibility. |
| 5 | Experimental evidence | Equal-budget comparison arms, per-seed results, frozen final test, separate library cost, isolated What-if demonstration when used, outage test. |
| 6 | Release | Fresh-clone run, exact query documentation, real artifacts/video, negative findings, original-document dates, AI disclosure, Track 1 named. |

Gate 1 includes a learnability decision before major UI work. A changed checkpoint hash alone is not proof of a useful learned behavior. Adjust only development/training/validation scenarios as needed, record changes, and do not tune against the frozen test.

Scope reduction must preserve real RL, meaningful graph decisions, comparison integrity, safeguards, and the interactive core. Cut optional robotics integrations, route planning, deployment complexity, extra models, and elaborate effects first.

## 12. Release checklist

- [ ] Real failure-to-fix workflow, with a failed outcome supported when shown.
- [ ] More than one meaningful eligible parent in the demonstrated choice.
- [ ] Tested query-to-action provenance and exact-artifact promotion.
- [ ] Actual PPO artifacts that reload with their normalization setup.
- [ ] Failed and successful transfer trials retained immutably.
- [ ] Train/validation/frozen-test separation and fair experimental accounting.
- [ ] Interactive studio uses genuine simulated execution data.
- [ ] Outage and isolated What-if demonstrations are described accurately.
- [ ] Complete local reproduction and a truthful recorded/live demo.
- [ ] README includes graph model, queries, results and limitations, sources/licenses, AI use, and document dates.
- [ ] Actual implementation history is preserved; no eligibility or winning claim without support.

## 13. Source traceability

| Source material | Integrated here |
|---|---|
| Handoff 3.1 and 3.2 | Product promise, audience-facing limits, parent-selection problem. |
| Handoff 3.3 and 3.4 | Immutable transfer evidence, semantic compatibility, matched scoring, exact-artifact promotion. |
| Handoff 3.5 and 3.6 | Graph value, What-if isolation, test separation, fair arms and costs. |
| Handoff 3.7 and 3.8 | Polished lean studio, bounded tools, one provider, local-first release. |
| Handoff 4 and 5 | Unresolved runtime checks and Gates 0 through 6. |
| Subsequent editorial clarifications | Correct gate references, preserved visual quality, conditional route tests. |

The original review is background only where the accepted handoff retains a recommendation. This revision does not reintroduce universal skill-transfer costs, a fixed-curriculum benchmark, a large policy zoo, or mandatory `algo.bfs`, `algo.SPpaths`, Next.js, or 3D.
