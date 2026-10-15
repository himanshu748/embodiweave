# EmbodiWeave
## Technical Specification

**Version:** 2.0, replacement document  
**Revision date:** 14 October 2026, Asia/Kolkata  
**Track:** Track 1 only, Agents That Act on Connected Data  
**Companion documents:** [PRD](prd.md) and [Claude kickoff](claude_initial_prompt.md)

> This is the revised technical specification. It integrates the accepted review corrections instead of delegating reconciliation to another handoff. No package combination, database procedure, query template, throughput estimate, training outcome, or host connection is represented as tested by this document.

## 0. Authority, provenance, and boundaries

This version supersedes the original technical specification wherever the requirements differ. It consolidates the accepted handoff sections 3.1 to 3.8, its unresolved checks and gates, and the subsequent clarifications concerning visual quality and optional routing. The original files and their dates remain unchanged.

The source handoff deferred document replacement until opening. The user has now explicitly requested the actual replacement documents; these are created on their stated 14 October date. Do not claim they were created after opening or certify their eligibility by relabeling them. The source reports restrictions on both main coding and design before 15 October 2026 at 00:01 IST. Re-check the current official rules before implementation and preserve all pre-event provenance.

This specification distinguishes:

- **Accepted requirements:** decisions already agreed in the handoff and now integrated here.
- **Logical contracts:** the information and behavior that the implementation must provide. These are not claims about an external library's exact API.
- **Unresolved implementation choices:** values or algorithms not established by the accepted sources, explicitly assigned to an implementation gate rather than silently invented.

### Non-negotiables

1. Genuine Gymnasium transitions and Stable-Baselines3 PPO updates, with reloadable artifacts.
2. FalkorDB-backed parent selection using actual compatibility, lineage, validation, and transfer evidence.
3. A meaningful choice between eligible checkpoints, not a fixed three-stage training chain.
4. One tested runtime LLM and one bounded MCP integration, separate from the coding assistant.
5. Immutable trial records, including unsuccessful attempts, and immutable source checkpoints.
6. Semantic compatibility, validation of retained behavior, and exact-artifact promotion enforced by trusted code.
7. Separate train, validation, and frozen final-test roles with fair experimental accounting.
8. A polished interactive studio whose replay and metrics come from actual simulation records.
9. Local-first reproducibility, bounded resources, explicit execution modes, and no unapproved spending.

## 1. System responsibilities

The MVP requires a small, local architecture. The accepted handoff does not require a particular frontend framework, distributed queue, or separate deployment for every component.

| Component | Responsibility | Must not do |
|---|---|---|
| Studio | Scenario controls, candidate comparison, replay, graph evidence, job status, exports | Invent trajectories, learning curves, or live status. |
| Trusted backend | Contracts, selection checks, graph writes, validation gates, artifacts, worker control | Delegate compatibility or promotion authority to an LLM. |
| Runtime agent | Inspect evidence and select permitted next tools | Control every simulator step, fabricate measurements, or execute arbitrary shell. |
| MCP integration | Bounded read templates and guarded training/evaluation/promotion operations | Accept unrestricted user Cypher mutations or arbitrary code. |
| FalkorDB | Connected operational evidence for eligibility, lineage, relevant trials, decisions, and promotion | Act as a decorative copy of a hidden hardcoded planner. |
| Worker | Execute a bounded real PPO or evaluation job and persist its outputs | Mark a run successful merely because a process ended. |
| Artifact storage | Preserve policies, normalization, configurations, logs, replays, and checksums | Rely on an ephemeral cloud graph as the only record of experiments. |
| Final-test runner | Evaluate a frozen experimental choice against the protected test suite | Feed test failures back into the adaptive planner while retaining an untouched-test claim. |

**Data flow:** user request -> graph-backed evidence retrieval -> recorded candidate decision -> guarded worker action -> actual checkpoint and validation -> exact-artifact promotion or rejection -> immutable evidence and replay.

The low-level robot action comes from the trained policy. The high-level agent chooses training and evaluation operations. These are distinct kinds of computation.

## 2. Execution host and dependency gate

### 2.1 Establish the actual environment

The preferred machine is the user's MacBook Air M4 with 16 GB RAM, but neither access to it nor its throughput has been verified. The previously reported Linux sandbox had 2 CPUs and 7 GB RAM; those observations are not measurements of the Mac.

Record the actual execution host, architecture, working directory, Python runtime, resources, Docker client, Docker daemon/context, and available artifact path. An attached folder or device-link claim is not proof that a process is executing on the Mac.

Native Python for the local worker and Docker for FalkorDB are the preferred arrangement from the preceding discussion, subject to successful tests. The host choice belongs to the user; do not build a remote-execution bridge as a prerequisite.

Do not reject the chat sandbox or guarantee the Mac's capacity from hardware labels alone. Measure the chosen workload after implementation is permitted.

### 2.2 Pin only a tested set

Required core families are Python, NumPy, Gymnasium, Stable-Baselines3, PyTorch, the FalkorDB client, one MCP implementation, and a small backend/UI arrangement.

The handoff listed versions seen by `pip index versions`, but explicitly did not establish compatibility. They are historical availability observations, not the installation prescription for this specification.

Record and lock the package set that installs and imports successfully on the actual host. Pin the FalkorDB image that was tested. Record runtime versions with every experiment. Do not claim a database algorithm or read-only behavior is verified until it has been exercised on that pinned instance.

## 3. Simulation and policy contract

### 3.1 Supported environment

Use one CPU-friendly Gymnasium environment for a simulated mobile robot. The original project direction is differential-drive or unicycle-style navigation with goals, static obstacles, and a moving crossing obstacle. These are supported scenario families, not mandatory sequential learning stages.

The environment must expose genuine seeded reset and step behavior, observations, bounded actions, reward, termination/truncation state, and actual simulator state for replay. It must pass the SB3 environment checker plus invariants for motion, collisions, seed behavior, and episode boundaries.

No ROS, Gazebo, Isaac, URDF importer, hardware interface, or universal robot support is required in v1. A custom simulator is not automatically physically equivalent to a robotics simulator or real robot.

### 3.2 Freeze semantics before the first reusable checkpoint

The accepted correction is a fixed temporal observation contract across compatible checkpoints. Array shape alone is insufficient.

The versioned contract must record:

| Aspect | Required information |
|---|---|
| Observation ordering | Ordered features and their meanings, including goal-relative features and any range measurements. |
| Units and frames | Units, coordinate frame, orientation conventions, and field interpretation. |
| Range processing | Bounds, normalization, clipping, and invalid or missing-value behavior. |
| Temporal history | History length, feature stacking order, reset initialization, and wrapper behavior. |
| Actions | Action ordering, units, scale, bounds, clipping, and mapping to control commands. |
| Time | Control timestep and any action repeat or history sampling interval. |
| Wrappers | Ordered wrapper configuration, including frame stacking and normalization behavior. |
| Normalization | Exact associated statistics/configuration and how they are restored for evaluation. |
| Robot configuration | Supported body/control parameters relevant to the policy interface. |

The exact ray count, history length, numeric world dimensions, reward coefficients, action limits, and timestep are not fixed by the accepted handoff. Choose and document them at Gate 1 before building the reusable checkpoint catalog. Do not leave temporal history optional or change it silently between stages.

History must reset between episodes. A test must detect accidental carryover from a previous episode. Any later contract change creates a distinct compatibility case; do not reuse an old checkpoint solely because the observation array has the same length.

### 3.3 Reward and outcome separation

Choose and version the reward definition during the learnability gate. Keep success, collision, timeout, and retained-behavior criteria separately measurable. A higher reward does not by itself establish that the target behavior passed.

Do not introduce outcomes designed to force the desired demo result. A shown failure must occur in the actual recorded or live evaluation.

### 3.4 Checkpoint training, reload, and normalization

A training run must perform actual policy updates and produce a separate artifact with lineage to its parent, or an explicit from-scratch origin. Preserve the source checkpoint unchanged.

Save the normalization setup with every checkpoint. When normalization is used, save the statistics and test save/load behavior. Restore the same semantic observation pipeline for evaluation, including history and wrapper order.

Gate 1 evidence must show that weights changed, the artifact was saved, the saved artifact reloaded, and evaluation ran against fixed validation cases. A binary file checksum alone is not enough to establish a useful trained behavior. Record both the smoke-training proof and the separate learnability observation.

Do not promise bitwise identical outcomes across different hardware or package versions. Define the intended reproduction comparison and record any tolerance or nondeterminism encountered.

## 4. Scenario suites and data roles

### 4.1 Three distinct roles

| Role | May be used for | Must not be used for |
|---|---|---|
| Training | Policy updates and development experiments | Presenting an untouched estimate of final generalization. |
| Validation | Candidate comparison, tuning, stopping/promotion criteria, failure-driven selection | Claiming independence after the planner has repeatedly adapted to its results. |
| Frozen final test | Reporting the locked final methods and checkpoints | Prompting another adaptation while still calling the same suite untouched. |

Version scenario definitions, generation parameters, and seed assignments. Make role and suite identity explicit in every evaluation. The planner's evidence queries must not expose final-test outcomes as selection input.

If development changes are made after inspecting final-test results, mark the suite as spent. A fresh independent suite is needed for a new untouched-test claim. Do not rename the old suite and imply it is fresh.

### 4.2 Comparable evidence

All eligible parents in the small catalog are evaluated on one comparable, versioned validation suite for the target decision. Do not mix scores from easier or unrelated scenarios or pick the maximum historical success value.

The suite must identify the target competency and any prerequisite behaviors the resulting controller needs to retain. A candidate's past pass on a different checkpoint or suite is not a current promotion certificate.

### 4.3 Failure evidence and hypotheses

Record actual outcomes such as collision, timeout, or other supported episode-level observations. Keep their source trajectory and evaluation IDs.

A handwritten mapping from one failure category to a competency or suggested training scenario is a hypothesis. Label it separately. The graph may help the agent investigate it, but the existence of the edge does not establish causation.

Scenario configurations are authored inputs. Evaluation outcomes and trial budgets are measured records. Do not present both as the same class of evidence.

## 5. Checkpoint and trial records

### 5.1 Required checkpoint information

Each reusable checkpoint must be linked to its immutable artifact, hash, originating run, parent when present, robot configuration, semantic observation/action contract, wrapper configuration, normalization artifacts, environment/recipe versions, and relevant evaluations.

Store source revision and dependency lock information with the run or reproducibility bundle. A checkpoint can be eligible only under a tested compatibility and evidence policy. The source checkpoint does not become a new artifact merely because it was selected for another experiment.

### 5.2 Conditioned transfer evidence

Do not maintain a universal averaged `Skill -> Skill` training cost as the decisive value.

A transfer trial must identify at least:

- Exact parent checkpoint, or an explicitly justified source class.
- Target scenario distribution and versioned validation suite.
- Robot configuration and semantic observation/action contract.
- Training recipe and threshold definition.
- Training seed, assigned budget, actual budget consumed, and validation schedule.
- Whether the threshold was reached, and the supporting evaluation when observed.
- Child checkpoint and artifact hashes that exist.
- Actual completion, failure, cancellation, or interruption status.

These are immutable trial records. Preserve unsuccessful attempts rather than updating the history only after a pass.

For a completed trial that did not reach the defined threshold, record **not reached within the observed budget**. Its exact steps-to-threshold is unknown. The budget consumed is not an observed time-to-success. Do not assign a made-up success step.

For interrupted or incomplete evaluation, preserve the amount actually observed and the uncertainty. Do not claim that unevaluated steps established an outcome.

A prior is labeled as a prior. Any estimated training cost is an estimate, not a measured saving. The initial absence of transfer history must be visible rather than filled with invented runs.

## 6. FalkorDB evidence model

### 6.1 Logical record types

The following table defines the information model required by the accepted corrections. It is a logical contract, not a claim that a tested schema migration already exists. Choose concrete labels and properties consistently during Gate 2 and document their actual names.

| Record | Required meaning and connections |
|---|---|
| Robot configuration | Supported control/body configuration and its policy contract. |
| Policy contract | Observation/action semantics, history, timing, wrappers, normalization requirements. |
| Mission | Supported desired behavior and mandatory competencies/prerequisites. |
| Competency | Behavior and applicable validation requirements, not an unsupported learned-status flag. |
| Scenario distribution/suite | Versioned scenario input, role, seed definitions, and competencies evaluated. |
| Policy | Immutable checkpoint identity, artifact hash, parent lineage, contract, and originating run. |
| Run | Actual training or evaluation execution, recipe, seeds, budget, status, and outputs. |
| Transfer trial | Conditioned parent-to-target attempt, including unsuccessful evidence. |
| Evaluation | Exact evaluated artifact, suite, episode count, observed outcomes, and retained-behavior results. |
| Failure evidence | Measured outcome connected to its evaluation and trace. |
| Hypothesis | Authored explanation or remedy suggestion, explicitly distinguished from a measured observation. |
| Decision | Graph revision, evidence query records, selection-rule version, chosen action, and resulting run. |
| Artifact/evidence reference | Persistent URI/path, hash, and provenance for relevant logs, snapshots, weights, and normalization. |

Typed links must allow traversal between policy lineage, compatibility, applicable trials, matched validation, and the target decision. Artifact binaries remain outside the graph but are identified by persistent references and hashes.

### 6.2 Relationship semantics

The graph must express these directed relationships, regardless of the final identifier spelling:

- A policy was produced by a run and may derive from a parent policy.
- A policy uses a defined robot/observation/action contract.
- An evaluation assesses a specific artifact on a particular versioned suite.
- A transfer trial starts from a particular parent and targets a defined distribution with a particular recipe and threshold.
- A trial produced a child artifact or ended without an acceptable one.
- A mission requires competencies; mandatory prerequisite relationships have AND semantics.
- Failure evidence was observed in an evaluation; authored hypotheses may refer to it without becoming measured facts.
- A decision is based on identified query results and selects a permitted training or evaluation action.

Mandatory prerequisites are separate from alternatives. Directed prerequisite closure must not silently omit mandatory relationships or treat a shortest path as sufficient coverage.

Evidence spread across several unrelated policies does not imply that the final mission controller possesses all those behaviors. Promotion evaluates the actual resulting controller.

### 6.3 Integrity and reconstruction

Use stable record identities and idempotent ingestion. Prevent logical duplicates, preserve source hashes, and validate required references. If database constraints are used, verify their creation and effective status on the pinned runtime instead of assuming behavior from documentation alone.

Do not overwrite measured trials for visual drama. Corrections must remain traceable to their source records. Keep real artifacts and records outside ephemeral graph storage so the graph can be rebuilt without fabricating history.

A rebuild is a recovery mechanism, not a runtime permission to replace graph-dependent decisions with a hidden JSON planner.

## 7. Graph read-template contracts

Implement bounded, parameterized read templates and execute them on real FalkorDB. Document the actual Cypher and its tested behavior in the repository. These are required query behaviors, not verified external procedure signatures.

| Template responsibility | Input | Required result |
|---|---|---|
| Mission requirements | Supported mission and robot contract | Directed mandatory prerequisites and relevant validation requirements. |
| Candidate eligibility | Target request, robot configuration, semantic contract | All candidate policy IDs in the small catalog, compatibility information, and explicit rejection reasons. |
| Candidate ancestry | Candidate policy IDs | Parent/run lineage and source artifact identities. |
| Matched validation | Candidate IDs and exact suite version | Comparable evaluation evidence with artifact hashes and missing-result status. |
| Relevant transfer trials | Parent IDs, target distribution, contract, recipe, threshold | Applicable immutable trials, including non-successes, consumed budgets, and provenance. |
| Failure inspection | Evaluation or run ID | Measured outcome and trace references, plus separately labeled hypotheses. |
| Promotion evidence | Candidate artifact and required suite | Target and retained-behavior evidence bound to the exact checkpoint. |
| Decision provenance | Decision ID and graph revision | Query parameters, returned IDs/rows reference, rule version, action, run, and result. |

No top-three truncation before scoring. Bounded responses must still allow complete evaluation of the small eligible catalog. If pruning is introduced, document why it cannot drop the best feasible candidate under the chosen rule.

Use safe read templates for agent access. Test that `GRAPH.RO_QUERY` rejects writes on the pinned runtime. Do not assume a particular MCP implementation is read-only because another implementation is.

`algo.bfs` and `algo.SPpaths` are not mandatory. Explicit directed multi-hop queries can satisfy the required relationship traversal. If BFS is used, test traversal direction and start-node behavior. If multi-stage route planning is introduced, test the actual procedure semantics before using them.

## 8. Parent selection

### 8.1 Selection sequence

1. Validate the supported mission, target distribution, budget, and contract.
2. Retrieve actual failure evidence. Keep diagnoses provisional where only hypotheses exist.
3. Query the small candidate catalog and reject semantic incompatibilities.
4. Obtain comparable validation evidence for every eligible candidate.
5. Retrieve conditioned transfer history, including unsuccessful and incomplete trials.
6. Apply the documented selection rule to this graph-backed evidence.
7. Record selected parent or from-scratch decision, rule version, graph revision, input evidence IDs, and uncertainty.
8. Revalidate permissions, artifacts, and budget before the worker starts.

No hidden fixed chain may determine the result regardless of graph evidence. A model-generated explanation must not replace the recorded selection inputs or trusted eligibility checks.

### 8.2 Selection-rule decision that remains open

The accepted sources define evidence requirements and fair baselines, but do not supply a final mathematical scoring function, estimator, weights, or tie-breaking rule. This document does not invent one and call it previously agreed.

At Gate 2, select and document a simple deterministic rule appropriate to the available measured history. It must specify treatment of comparable validation, conditioned transfer successes, threshold-not-reached observations, missing data, priors if any, and ties. Freeze its version before benchmark comparison.

The selected rule must not treat a failed trial as a measured step-to-success, pool unrelated target distributions without justification, or rank by maximum performance from unrelated evaluations. Do not claim predicted optimality or calibrated uncertainty without evidence.

If the history is insufficient to justify a transfer-based preference, report that limitation. A transparent choice from matched validation or a from-scratch experiment is better than invented confidence. However, the submitted graph-value demonstration still needs a case where meaningful relevant evidence changes a permitted or selected action.

### 8.3 Optional multi-stage routes

Parent selection is the MVP. Multi-stage planning is optional and cannot be added merely to make a named graph algorithm appear central.

If implemented, the state must retain enough context for robot compatibility and verified competence to make transitions meaningful. All mandatory prerequisites must hold. A summed route cost is a planning estimate, not guaranteed learning cost. Re-evaluate and replan after each stage, and charge each stage to the adaptation budget.

Directed route-validity tests apply only when this feature exists. Prerequisite-validity tests remain mandatory for the relationships used by the MVP.

## 9. Runtime agent and MCP tools

### 9.1 One tested provider

Choose one runtime LLM provider only after verifying a working credential, tool calling, and quota. Do not promise access based on a Claude Chat/Code subscription or third-party free-tier claims. Keep credentials server-side and out of graph evidence, prompts shown publicly, and exported logs.

The agent investigates evidence and chooses bounded tools. It does not generate arbitrary Python for execution, control a physical robot, or self-certify a checkpoint.

Without credentials, deterministic graph and RL tests may proceed. Label that mode clearly, and record the exact blocked live-agent test. Do not silently present a deterministic trace as an LLM run.

### 9.2 Project-local operation contracts

These names describe application operations, not provider APIs or claimed existing MCP tool names. The builder may choose consistent actual names while preserving behavior.

| Operation | Guarded behavior |
|---|---|
| Inspect supported mission/failure | Retrieve bounded authored configuration and measured evaluation evidence. |
| Inspect candidates and history | Execute read templates for compatibility, lineage, matched validation, and conditioned trials. |
| Propose an adaptation | Create a recorded graph-backed choice with a parent or explicit from-scratch origin and a capped budget. |
| Start training | Revalidate graph-backed selection, exact source artifacts, contract, quota, and idempotency before launching the worker. |
| Evaluate a checkpoint | Use an approved validation suite and exact checkpoint; the agent cannot request protected final-test feedback. |
| Promote or reject | Trusted code applies exact-artifact and retained-behavior gates. |
| Inspect job / cancel | Return actual worker state or request cancellation with persistent outcome reporting. |
| Export evidence | Return the actual artifact bundle with hashes and provenance, never a fabricated link. |

Agent access to arbitrary shell, arbitrary URLs/repositories, unrestricted code execution, arbitrary paths, and arbitrary graph writes is outside scope.

The trusted backend writes measured runs and decisions. It must reject a fabricated metric payload supplied by the agent as proof of promotion.

### 9.3 Trace requirements

For each decision, preserve tool identity, template identity, query parameters, actual returned record IDs or result snapshot, graph revision, selected action, resulting run ID, and observed result. Store or reference the actual Cypher used. Redact secrets.

Explanations must distinguish observed failure, inferred hypothesis, prior, estimated transfer outcome, measured trial, and final action.

## 10. Worker and artifact handling

Use one bounded worker and polling if sufficient. No distributed queue is required. The exact internal job-state enumeration is an implementation choice, but it must distinguish not-started, running, completed training, evaluated outcome, process failure, cancellation, and promotion status accurately.

Required behavior:

- Hard training quotas and bounded concurrency.
- Idempotent launches so duplicate requests do not create duplicate expensive runs.
- Safe cancellation with actual consumed budget and preserved outputs recorded.
- Restart recovery that reports incomplete or interrupted work rather than inventing completion.
- Immutable source checkpoints and uniquely identified child artifacts.
- Artifact checks before evaluation, reuse, promotion, and export.
- An explicit separation between successful process completion, successful evaluation, and promotion.

Progress polling must reflect an actual worker or persisted recorded execution. Live status is invalid when no matching process/job is running.

Save actual trajectory states and timestamps or step indices with run identifiers. A replay is evidence from a run, not a separately scripted animation. An export includes the policy, normalization artifacts or explicit normalization configuration, environment and contract definitions, recipe, seeds, metric logs, evaluation records, source revision, dependency lock, and checksums needed to reproduce it.

Do not call hashes digital signatures. If cryptographic signing is not implemented and verified, describe these as checksummed artifacts.

## 11. Validation and promotion

Promotion is a trusted service action, not a statement from the LLM and not a mutable `passed=true` flag accepted without evidence.

Before promotion, verify:

1. The evaluated checkpoint hash matches the candidate being promoted.
2. Its robot, observation/action, wrapper, and normalization contracts are the intended ones.
3. The required versioned validation suite and declared threshold definition were used.
4. The resulting policy itself passes both target behavior and required retained/prerequisite behavior.
5. The evidence belongs to the actual run and artifact, rather than an earlier parent or unrelated evaluation.
6. Artifacts required for reproduction exist and match their recorded hashes.

Numeric promotion thresholds are not established by the accepted sources. Choose and version them before comparison and final testing; do not tune them to pass a disappointing final result. A failed or incomplete gate blocks promotion and remains visible in the trial history.

Do not infer mission capability by combining passing results from separate unrelated policies. No automatic skill-composition controller is specified in v1.

## 12. What-if and outage behavior

### What-if

Use an isolated, clearly labeled copy for graph interventions. The copy mechanism is an unresolved Gate 2 check. A copied artifact reference does not authorize overwriting that source artifact.

Possible demonstrations include changing a compatibility fact or adding a clearly hypothetical transfer observation in the isolated copy, then inspecting whether the selected parent or permitted action changes. Label such inputs as hypothetical. Do not present the injected outcome as measured.

The production evidence graph and real runs remain unchanged. No What-if result can silently become a production training/promotion decision. The studio must show the active mode and graph revision.

### Outage

When FalkorDB is unavailable, stop new graph-dependent planning, reuse decisions, and promotion explicitly. Preserved recorded evidence may remain viewable, labeled Recorded. Do not secretly reconstruct a second decision engine in memory to make the demo look live.

This is an operational test. It is not evidence that graph-guided selection improves RL outcomes or that no other database could implement the application.

## 13. Studio implementation requirements

No mandatory Next.js, Cytoscape, React Three Fiber, or dedicated chart package is imposed. Choose the simplest maintainable stack that achieves the experience. A strong top-down 2D or light isometric renderer is sufficient.

### Arena and replay

Show actual robot and obstacle states, goal, trajectory, outcome markers, and selected run. Provide pause, scrub, and synchronized before/after viewing. Match run/suite identities for comparisons so different scenarios are not presented as the same trial.

### Candidate panel

Display all eligible parents, incompatible candidates with reasons, comparable validation, relevant transfer evidence, and the selected parent. Let a user inspect the records behind a choice rather than display only an unexplained winner.

### Graph and evidence inspector

Highlight returned paths and records from actual queries. Selecting evidence reveals its type, source run, configuration/suite, artifact hash, and decision relevance. Hypotheses and authored configurations are visibly distinct from measurements.

### Scenario and worker controls

Supported scenario changes must affect real configuration. Ask Agent, launch, evaluate, cancel, compare, and export controls must have correct enabled/disabled and failure states. Unsupported configurations are rejected, not animated as successful requests.

### Mode and accessibility

Use persistent Live, Recorded, and What-if indicators. Also make the simulated-world scope explicit. Deterministic mode is separate from the LLM-agent mode. Provide readable labels, keyboard access, useful empty/loading/error states, and a usable smaller-screen layout where practical.

A static evidence site is Recorded only. It cannot imply live graph querying, model inference, or training.

## 14. Experimental protocol

### 14.1 Four comparison arms

| Arm | Definition |
|---|---|
| Graph-selected warm start | Parent chosen by the frozen graph-backed selection method using admissible validation and conditioned transfer history. |
| Latest compatible eligible checkpoint | Latest candidate under a documented time/ordering definition, subject to the same compatibility/eligibility requirements. |
| Best matched-validation checkpoint | Candidate with best performance under a declared criterion on the same matched validation suite. |
| From scratch | No parent weights; same target adaptation environment, algorithm, and accounting rules. |

The exact criterion for matched-validation ranking and selection-rule treatment of ties must be recorded before the comparison. Do not deliberately weaken baselines. An incompatible checkpoint belongs in a rejection test.

If the graph method chooses the same checkpoint as a baseline, report that agreement. Do not force an alternative outcome to create apparent differentiation.

### 14.2 Equal-budget accounting

Use the same target environment, algorithm, evaluation protocol, and paired training seeds. Equal adaptation budgets apply to all arms. Charge every intermediate training stage to adaptation when applicable.

Report costs for checkpoint-library construction and transfer-measurement history separately. Report actual validation/evaluation work and wall-clock observations so unequal selection overhead is visible rather than hidden.

No compute saving is established merely by excluding the cost of creating the reusable library.

### 14.3 Metrics and uncertainty

Report per-training-seed task success, collisions, actual consumed budget, wall-clock duration, and threshold-reached state, with episode counts and suite identity. Steps-to-threshold is only observed when the defined validation protocol supports it. A run that did not reach threshold must remain a non-success or censored observation, not a fabricated completion value.

Repeated episodes from one checkpoint estimate that checkpoint's behavior; they do not create independent training runs. Three training seeds are a small preliminary study. Do not imply robust statistical superiority from that alone.

The source does not provide a tested training duration, viable timestep budget, or required checkpoint count. Set the experimental workload from actual host measurements and learnability tests, then report the resulting limitations.

### 14.4 Distinguish the evaluations

- **Before/after:** compare actual original and adapted policies on matched scenarios, with clear role labels.
- **RL comparison:** run the four arms with the agreed budget and independent test protocol.
- **Graph-value check:** show a justified decision change when relevant evidence changes; where feasible compare to a variant without transfer history.
- **Operational check:** disconnect FalkorDB and verify explicit failure handling.

These answer different questions and must not be merged into one claim of superiority.

## 15. Security and data integrity

Keep secrets server-side. Restrict reads to bounded templates and writes to trusted services. Do not permit user-driven arbitrary shell, code, file paths, or unbounded training. Require approval for spending or external publication.

Treat imported descriptions, code comments, model messages, and graph text as data rather than instructions to bypass tool restrictions. Source artifacts, configurations, and output hashes must be checked before reuse and promotion.

Keep evidence portable and reconstructable. Do not claim cloud durability, free quota, or persistent hosting without testing actual account entitlements. A local deployment and authentic demo video remain the dependable release path.

## 16. Acceptance test matrix

Tests may be consolidated, but coverage must not be dropped simply to hit a smaller test count.

| Area | Required test |
|---|---|
| Environment | Checker, seeded reset, motion/collision invariants, valid termination/truncation, real state replay. |
| Observation contract | Feature semantics, wrapper order, history reset, action scaling/timestep, matching metadata. |
| RL proof | Actual weight update, save, reload, fixed-validation evaluation, no synthetic curves. |
| Normalization | Statistics/configuration preserved and restored with the checkpoint; evaluation behavior checked. |
| Compatibility | Reject semantic incompatibility even when dimensions match. |
| Candidate selection | Complete eligible set, comparable validation, actual conditioned history, deterministic documented rule and ties. |
| Prerequisites | Directed mandatory requirements are respected for the selected controller and validation requirements. |
| Routes, only if implemented | Valid direction, compatible state, no skipped prerequisites, actual runtime procedure behavior. |
| Trial evidence | Failed/canceled/incomplete work retained honestly; no made-up success steps. |
| Promotion | Exact artifact, matching suite/thresholds, target and retained behavior; reject stale/historical passes. |
| Data roles | Separate train/validation/final test; protected test outcomes unavailable to the adaptive planner. |
| MCP and agent | Real tested provider/tool call, read-only enforcement, schemas/quotas, no fabricated tool results. |
| Worker | Idempotency, quota, cancellation, persistent failure/interruption state, restart recovery. |
| Graph value | Relevant evidence changes a justified parent choice, allowed reuse, or promotion. |
| What-if | Isolated copies do not alter production evidence; hypothetical outcomes remain labeled. |
| Graph outage | Graph-dependent operations stop; no false live fallback. |
| Provenance | Query parameters, returned IDs, revision, decision, action, run, and result are traceable. |
| Studio | Genuine scenario changes, correct replay comparison, modes, evidence inspection, export, accessibility basics. |
| Reproduction | Fresh setup runs the documented workflow with the declared artifacts and dependencies. |

## 17. Ordered implementation gates

### Gate 0: Actual host, current rules, existing documents

Verify clock, official rules, execution host, workspace, dependency availability, and permissions. Record that these v2 documents already exist and preserve their dates. Do not begin another full rewrite; make only focused changes needed for verified implementation findings, with history.

The source reports an opening of 15 October 2026 at 00:01 IST and closing of 18 October at 23:59 IST. Re-check rather than treating those source claims as newly observed. Before implementation is allowed, restrict work to permitted readiness checks and stop. Do not schedule yourself to resume.

### Gate 1: Environment, throughput, and reloadable policy

Freeze the semantic observation/action contract. Implement and test the CPU environment. Measure the real host, run actual PPO, save/reload normalization and weights, and evaluate fixed validation cases. Record whether the target behaviors are learnable within the measured budget before major UI work.

### Gate 2: FalkorDB-backed selection

Pin the database, verify actual read behavior, implement typed records and real queries, and record the selection rule. Demonstrate distinct eligible parents, compatibility rejection, comparable validation, conditioned failed/successful history, and one justified evidence-driven decision change. Verify the isolated What-if mechanism before enabling edits.

### Gate 3: Real agent and worker loop

Test one provider and MCP integration end to end. Launch bounded training, evaluate real artifacts, enforce target and retained-behavior promotion, record failures, and test quotas/cancellation/recovery. Missing credentials block the LLM-agent gate but not independent RL/graph tests.

### Gate 4: Interactive studio

Wire genuine replay, candidate comparison, graph evidence, scenario controls, job status, cancellation/export, and honest modes. Preserve polished interaction while avoiding unnecessary simulator or framework complexity.

### Gate 5: Benchmarks and demonstrations

Freeze the selection/validation protocol, run fair comparison arms at measured budgets, report per-seed results and separate library cost, and use the frozen final test for the locked experiment. Show isolated What-if and outage behavior accurately. Host a static replay only after verifying entitlement and clear Recorded labeling.

### Gate 6: Reproducible release

Fresh-clone run, exact Cypher/query documentation, graph model, setup, actual results including negative ones, original-document dates, and AI disclosure. Demo footage identifies run IDs and artifacts. Live fine-tuning proves an action, not guaranteed improvement. Name Track 1 and avoid unauthorized publication or spending.

## 18. Unresolved choices and checks

These are bounded implementation decisions, not a reason to restart product ideation. The accepted sources do not establish their values.

| Decision/check | Resolve at | Required record |
|---|---|---|
| Current event wording and execution permission | Gate 0 | Current clock, source checked, observed rule text. |
| Actual host and Docker daemon/context | Gate 0 | Host/path/runtime observations, not inferred device access. |
| Compatible package lock and FalkorDB image | Gates 0 to 2 | Installed versions/image and actual smoke-test results. |
| Fixed observation history and numeric simulator/reward values | Gate 1 | Versioned complete contract before reusable checkpoints. |
| Normalization behavior on save/reload | Gate 1 | Command/test output and actual checkpoint artifacts. |
| Throughput, workable budgets, and task learnability | Gate 1 | Measured environment/optimizer workload and validation results. |
| Read-only command, parameter, constraint, and optional algorithm semantics | Gate 2 | Tests against the pinned database runtime. |
| Parent scoring rule, missing data, priors, and ties | Gate 2 | Versioned method using accepted evidence constraints. |
| Numeric validation/promotion thresholds | Before comparison | Fixed versioned criteria, not chosen from final-test performance. |
| Isolated graph-copy mechanism | Gate 2 | Demonstration that measured production evidence is unaffected. |
| One runtime model, credentials, tool calling, and quota | Gate 3 | Actual provider smoke test with secrets redacted. |
| Frontend implementation stack | Gate 4 | Choice supporting the agreed interactions without mandatory heavyweight frameworks. |
| Final benchmark workload and host cost | Gate 5 | Measured per-arm budget and separate prior-library costs. |
| Static-hosting entitlement | Gate 5, optional | Actual account capability; disable unsupported deployment rather than pretending. |

## 19. Changes incorporated from v1

| Removed or superseded | v2 requirement |
|---|---|
| Fixed three-stage curriculum as core | Branching parent selection from meaningful checkpoints. |
| Fixed-curriculum comparison | Four fair adaptation arms and optional no-transfer-history variant. |
| Universal averaged skill-transfer cost | Immutable conditioned trials including threshold-not-reached records. |
| Maximum unrelated success score / top-three shortlist | All eligible candidates on a matched versioned validation suite. |
| Failure category automatically identifies missing skill | Measured observation plus separately labeled hypothesis. |
| Shape-only compatibility | Full semantic contract, history, timing, wrappers, normalization. |
| Historical or multi-policy coverage implies promotion | Exact candidate artifact validated on target and retained behavior. |
| Graph outage proves superiority | Separate operational test, graph-value demonstration, and RL comparison. |
| Direct edits of measured graph evidence | Isolated labeled What-if copies. |
| Mandatory BFS/SPpaths and route planner | Actual multi-hop query behavior; route planning optional. |
| Mandatory Next.js/heavy 3D/distributed queue | Polished lean studio, one worker, suitable framework choice. |
| Assumed Mac bridge, throughput, free models/hosting | Actual host/account/runtime measurements. |
| New builder starts by rewriting old documents | These are the replacements; proceed to verification and implementation gates. |

## 20. Source map

This specification consolidates `embodiweave-handoff-note.md`: sections 3.1/3.2 for scope and parent selection; 3.3 for transfer evidence; 3.4 for contracts and promotion; 3.5 for graph value and What-if behavior; 3.6 for experimental roles and baselines; 3.7 for the studio; 3.8 for tools and deployment; section 4 for unresolved checks; and section 5 for gates and acceptance.

The original v1 specification supplies retained general context such as simulated mobile navigation and artifact-oriented execution only where the accepted handoff does not supersede it. Earlier rejected recommendations remain rejected. The later clarifications retain visual quality, correct the gate reference, and make route-specific tests conditional.

Official references to re-check during implementation, carried from the supplied documents: WeMakeDevs FalkorDB event and rules pages; FalkorDB runtime/client/query documentation; Gymnasium custom-environment documentation; Stable-Baselines3 environment/PPO/normalization documentation; and the selected model and deployment providers' own documentation. They were not newly fetched or runtime-tested while creating this replacement set.
