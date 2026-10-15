# EmbodiWeave

**GraphHacks 2026, Track 1: Agents That Act on Connected Data.** FalkorDB is the primary database.

**Live demo:** [embodiweave.onrender.com](https://embodiweave.onrender.com) (free tier, the first load can take up to a minute) · **License:** MIT · **Demo video:** [60 second walkthrough](https://embodiweave.onrender.com/media/embodiweave-demo.mp4) · [Judge guide](https://embodiweave.onrender.com/guide.html)

EmbodiWeave turns robot failures into evidence-backed training decisions. A simulated mobile robot
fails a new mission (static obstacles plus a crossing pedestrian). An agent queries a FalkorDB graph of
checkpoints, contracts, evaluations, failures and past adaptation trials, decides where to start
training from (an existing checkpoint or scratch), launches real PPO training, measures the result on a
matched validation suite, writes the outcome back to the graph, and asks a promotion gate whether the
new checkpoint may replace the deployed one. The next decision changes when the evidence changes.

Everything is a software simulation. No physical robot is involved.

## Start here: a judge’s walkthrough

1. [Watch the recorded paired replay](https://embodiweave.onrender.com): seed 1300032, deployed collision at step 51, new checkpoint goal at step 112. A good episode is not a passed gate.
2. [Run live Cypher](https://embodiweave.onrender.com/#live): query the same conditional transfer evidence the agent used. Query text, parameters, rows and graph revision are visible.
3. [Inspect selection and the gate](https://embodiweave.onrender.com/#decide): scratch wins the recorded ranking; target collisions remain 13%, over the 10% limit. Three of four suites fail. Promotion is rejected.
4. [Open the studio](https://embodiweave.onrender.com/studio.html): browse the real Sonnet MCP trace, replay different episodes, inspect evidence, and try an isolated What-if.
5. [Watch the demo film](https://embodiweave.onrender.com/guide.html#film), then reproduce locally below.

**Evidence boundaries:** Live means a current query to running FalkorDB. Recorded means stored PPO,
simulator or LLM execution evidence. What-if means a labelled sandbox copy. Training, scenario evaluation
and new agent launches require the full local stack; they are disabled on the free public demo.
The demo film is an edited browser walkthrough, with captions and a choreographed pointer. Its replay
frames and interface states were captured from the running app. It does not show a new training run.

## Why FalkorDB is essential

FalkorDB is the decision layer. The agent asks which compatible parent, or scratch origin, has
transfer evidence under the exact mission family, semantic contract, recipe, threshold and budget.
Trial relationships connect those starts to the checkpoints they produced; Evaluation relationships
connect exact artifact hashes to versioned Suites. Decisions retain the graph revision and query evidence.
This connected history changes the next training action. The planner stops if the database is unavailable.

The JSON records are an immutable recovery log, not a fallback planner. Rebuilding them into FalkorDB
restores the query layer. Read templates execute through `GRAPH.RO_QUERY`; trusted tools append outcomes.
What-if uses `GRAPH.COPY`, checks production’s fingerprint and drops the sandbox. Final tests never enter
the planning graph. This project uses FalkorDB for operational decisions, not only visualization or search.

## What the graph decides, and what it got right

Measured on three fresh final-test suites (details: [`evidence/gate5/RESULTS.md`](evidence/gate5/RESULTS.md)):

| Experiment | Graph rule | Graph picked | Graph arm test success | Latest checkpoint | Best-validation checkpoint |
|---|---|---|---|---|---|
| exp-1 | ew-select-1 | P-static-a | 0.33 | 0.35 | 0.35 |
| exp-2 | ew-select-2 | scratch | **0.71** | 0.39 | 0.39 |
| exp-3 | ew-select-3 | scratch | **0.70** | 0.37 | 0.37 |

exp-1 is a negative result: warm starts from this library plateau, and the first rule could only choose
among parents. The graph's measured transfer history showed that, so scratch became a graph option
(exp-2), and a tie blind spot found after exp-2 was fixed (exp-3). Each rule change was committed
before its experiment and judged on a previously unused test suite. Three seeds per arm: preliminary.

## Graph model

Authored world facts (`ew/graph/ingest.py: init_world`):

```
(:Robot)<-[:FOR_ROBOT]-(:Contract)                    semantic obs/action contract, hashed id
(:Mission)-[:REQUIRES]->(:Competency)-[:REQUIRES]->(:Competency)
(:Suite {role:'validation'|'final_test'})-[:DRAWS_FROM]->(:Family), -[:EVALUATES]->(:Competency)
(:Threshold)-[:MEASURED_ON]->(:Suite)
(:Hypothesis)-[:SUGGESTS]->(:Competency)              authored, labelled measured=false
(:Origin {id:'scratch'})                              the "no parent" option
```

Measured evidence, appended from immutable JSON records under `artifacts/records/`:

```
(:Run)-[:PRODUCED]->(:Policy)-[:USES_CONTRACT]->(:Contract)
(:Run)-[:STARTED_FROM]->(:Policy), (:Run)-[:TRAINED_ON]->(:Family)
(:Policy)-[:DERIVED_FROM]->(:Policy)
(:Evaluation)-[:ASSESSED]->(:Policy), -[:ON_SUITE]->(:Suite)       validation only, exact artifact hash
(:Failure)-[:OBSERVED_IN]->(:Evaluation), (:Hypothesis)-[:ABOUT]->(:Failure)
(:Trial)-[:FROM_PARENT]->(:Policy) | -[:FROM_ORIGIN]->(:Origin)
(:Trial)-[:TARGETS]->(:Family), -[:UNDER_CONTRACT]->(:Contract), -[:PRODUCED]->(:Policy)
(:Trial)-[:VIA_RUN]->(:Run), -[:VALIDATED_ON]->(:Suite)
(:Decision)-[:CONSIDERED|REJECTED]->(:Policy), -[:SELECTED]->(:Policy|:Origin)
(:Decision)-[:BASED_ON]->(:Trial|:Evaluation), -[:LAUNCHED]->(:Run)
(:Promotion)-[:FOR]->(:Policy), -[:USED_EVALUATION]->(:Evaluation)
(:Meta {revision})                                     bumped on every write; cited by decisions
```

The graph can be rebuilt from the records at any time (`ew.graph.ingest.rebuild()`).
Final-test evaluations are never ingested, so no query can leak them into a decision.

## Cypher the agent runs

All decision reads are fixed, parameterized templates (`ew/graph/queries.py`) executed through
`GRAPH.RO_QUERY`, so they cannot write. Each result is logged with its Cypher, parameters, returned
record ids and graph revision, and the studio shows them in the Evidence tab. Highlights:

Compatibility goes beyond tensor shape. The mirrored-ray checkpoint has the same 51-dim input and is
still rejected, with the fields that differ:

```cypher
MATCH (tc:Contract {id:$contract})-[:FOR_ROBOT]->(tr:Robot {id:$robot})
MATCH (p:Policy)-[:USES_CONTRACT]->(pc:Contract)-[:FOR_ROBOT]->(pr:Robot)
OPTIONAL MATCH (run:Run)-[:PRODUCED]->(p)
RETURN p.id AS policy_id, p.artifact_hash AS artifact_hash, p.status AS status,
       pc.id = tc.id AS contract_match, pr.id = tr.id AS robot_match,
       [k IN ['ray_order','n_rays','history','history_reset','dt_s','action_map','normalization']
        WHERE pc[k] <> tc[k]] AS differing_fields
```

Transfer evidence is conditioned on the exact target, contract, recipe, threshold and budget:

```cypher
UNWIND $ids AS pid
MATCH (p:Policy {id:pid})
OPTIONAL MATCH (t:Trial)-[:FROM_PARENT]->(p)
WHERE t.threshold_id = $threshold AND t.recipe = $recipe AND t.budget = $budget
  AND (t)-[:TARGETS]->(:Family {id:$family})
  AND (t)-[:UNDER_CONTRACT]->(:Contract {id:$contract})
RETURN pid AS policy_id, t.id AS trial_id, t.status AS status, t.threshold_reached AS reached,
       t.steps_to_threshold AS steps_to_threshold, coalesce(t.hypothetical, false) AS hypothetical
```

Scratch is an option with its own evidence:

```cypher
MATCH (o:Origin {id:'scratch'})
OPTIONAL MATCH (t:Trial)-[:FROM_ORIGIN]->(o)
WHERE t.threshold_id = $threshold AND t.recipe = $recipe AND t.budget = $budget
  AND (t)-[:TARGETS]->(:Family {id:$family}) AND (t)-[:UNDER_CONTRACT]->(:Contract {id:$contract})
RETURN t.id AS trial_id, t.status AS status, t.threshold_reached AS reached
```

What the trials actually produced (the ew-select-3 tie-breaker):

```cypher
UNWIND $trial_ids AS tid
MATCH (t:Trial {id:tid})-[:PRODUCED]->(c:Policy)
MATCH (s:Suite {id:$suite}) WHERE s.role = 'validation'
OPTIONAL MATCH (e:Evaluation)-[:ASSESSED]->(c)
WHERE (e)-[:ON_SUITE]->(s) AND e.artifact_hash = c.artifact_hash
  AND e.complete_suite = true AND e.suite_fingerprint = s.fingerprint
RETURN tid AS trial_id, e.success_rate AS success_rate, e.collision_rate AS collision_rate
```

Other templates: `mission_requirements` (variable-length `REQUIRES*1..6`), `candidate_ancestry`
(`DERIVED_FROM*0..8`), `matched_validation`, `non_applicable_trials`, `failure_inspection`,
`promotion_evidence`, `decision_provenance`, `policy_lineage_graph`.

## Selection rule

The rule is code, not an LLM opinion (`ew/select.py`, history in its docstring):

1. Eligible = same robot, same semantic contract, completed checkpoint, artifact hash verified on disk.
2. Every eligible candidate needs a complete matched validation of its exact artifact, including canonical seeds, family, contract and suite version; otherwise the decision is
   `evaluate_candidates`.
3. p_reach = (reached + 1) / (completed + 2) over conditioned trials. A failed trial counts as "not
   reached within budget"; no steps-to-threshold value is ever invented.
4. ew-select-3 ranks parents and scratch together by p_reach, then the mean validation score of the
   checkpoints their trials produced, then the parent's own validation, then id.

What-if mode copies the graph (`GRAPH.COPY`), applies hypothetical trials or contract changes there,
labels every hypothetical input, refuses writes to production and cannot launch training.

## Agent and tools

`ew/agent_tools.py` exposes 11 bounded tools (inspect mission, read-only query templates, propose,
evaluate candidates, start training, job status, wait, cancel, evaluate checkpoint, request promotion,
export evidence), also served over MCP stdio by `ew/mcp_server.py`. Training runs in a single worker
(`ew/jobs.py`) with OS locks for atomic idempotency and quota reservation, a single worker lease, a per-job cap
(200k actual rollout steps), a total quota (3M steps), cancellation and restart recovery. A 150k request
reserves 151,552 steps; failed or interrupted jobs retain the full reservation because work after the last
progress callback is unknown. Identical submissions return the original job even after failure. Queued
cancellation writes an immutable Trial with zero work and no checkpoint. `start_training` re-runs the rule and refuses a stale decision.

`python -m ew.agent deterministic` runs the full loop over MCP with a scripted policy and is labelled
"Deterministic rule run". `python -m ew.agent llm` runs the same loop with a real LLM choosing the tool calls,
using the first key it finds: OpenRouter (`OPENROUTER_API_KEY`, model `EW_OPENROUTER_MODEL`, default
`anthropic/claude-sonnet-5.5`), Groq (`GROQ_API_KEY`, `EW_GROQ_MODEL`, default `auto`: the strongest known
tool-calling model the account offers) or Claude (`ANTHROPIC_API_KEY`). The model is recorded in the trace.

Live LLM runs (15 Oct, traces in `artifacts/records/agent_trace/`):
- `agent-20261015060343-b9e6bc`, OpenRouter `anthropic/claude-sonnet-5.5`, 8 turns, 94 s: full loop. Rule
  ew-select-3 chose train from scratch; PPO seed 7 / 150k did not reach threshold; target 0.87 success /
  0.13 collisions (deployed policy: 0.37 / 0.48); retained suites open 0.725, static 0.95, crossing 0.725 /
  0.175 collisions; promotion **rejected** by the gate, P-static-b stays deployed; evidence bundle exported.
- `agent-20261015053827-2f1a08`, Groq free tier `openai/gpt-oss-120b`: same decision and training, but the
  8000 tokens/min cap and repeated template-name mistakes used up its 40-turn budget before promotion.
  A second Groq attempt (`agent_traces/agent-20261015055357-535ef1.jsonl`, 80-turn budget) was cut off by
  Groq rate limits after its first evaluation and wrote no agent_trace record.

## Ask the agent locally

Set one provider key in your shell and `EW_ALLOW_LLM=1` **before starting the API**, then open Studio → Agent.
Keys remain on the server. The consent checkbox authorizes provider API usage and one bounded training
investigation. The launcher allows at most 12 model turns and one new training job per session, requires a live local worker and deduplicates
concurrent starts. Inspect the session state and final trace in Agent; cancel training in Jobs. Without
explicit opt-in or a provider key, launch is disabled. The public Render demo always disables launch.
Existing real LLM traces remain browsable without a key. Provider API usage may incur charges.

## Studio

`web/` is a static page served by the FastAPI app (`ew/api.py`): matched before/after replays drawn
from recorded simulator states, scenario controls that run a real evaluation, candidate ranking with
rejection reasons, the Cypher evidence, a live graph view, jobs, agent traces and the results table.
Badges show Recorded, Live or What-if, and a banner appears when the graph is unreachable.

Both the landing page and the studio arena have a 3D view (`web/robot3d.js`, three.js r160 vendored in
`web/vendor/`). It renders only stored simulator states: a two-wheeled robot whose wheel spin follows the recorded
motion, the pedestrian as a walking person with its collision radius on the floor, and the 12 lidar rays recomputed
from each recorded pose with the simulator's own ray geometry. A Top view toggle shows the plain 2D replay.

The landing page (`web/index.html`) leads with the recorded simulator replay, a card that queries FalkorDB
live on load, a console that re-runs five of the agent's read templates against the live graph, and the
recorded decision ranking and gate checks.

![Decision tab](evidence/gate4/studio-decision.png)

## Run it

Requirements: Linux or macOS with Docker, Python 3.13. No GPU needed (4 CPU cores used here).

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.lock
bash scripts/start.sh                   # FalkorDB (pinned digest), worker, studio on 127.0.0.1:8000
.venv/bin/python -m pytest -q           # 63 tests, needs FalkorDB on localhost:6379
```

The launcher uses a dedicated `embodiweave-db` container bound to loopback, waits for database readiness,
initializes an empty graph, preserves an existing worker and serves only on 127.0.0.1. Logs are in `logs/`.
Python 3.13 dependencies were installed and the full suite was run on Apple Silicon macOS with CPU PyTorch
and the pinned FalkorDB container. CUDA-only pins have been removed. The dependency lock includes the
HTTP clients used by the runtime providers.

For an existing checkout upgraded from the earlier schema, stop the local API and worker, then rebuild
derived graph fields from immutable records before restarting:

```bash
.venv/bin/python -c 'from ew.graph.ingest import rebuild; rebuild()'
```

Use `EW_FALKOR_PORT` for a non-default database port and `EW_DB_CONTAINER` for a dedicated container name. This release was tested with an isolated container
on 16379 and `EW_FALKOR_PORT=16379 .venv/bin/python -m pytest -q`.

### Reproduce an exported checkpoint

In the local studio use Export, or call `ew.service.export_bundle(policy_id)`. A [new-format bundle of the recorded checkpoint](https://embodiweave.onrender.com/api/download/scratch~a7ee2c-s7-556ec083bc85-repro-v2.zip) is available for direct download. New bundles end in
`-repro-v2.zip` and include the checkpoint, normalization, semantic contract, evidence, Python source,
source commit and per-file hashes, dependencies, and checksums of every payload entry. Extract one, then:

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.lock
PYTHONPATH=source .venv/bin/python -m ew.cli evaluate --policy-dir policy --suite val-target-v1
```

The regression suite actually executes this command against the exported source in a separate process
and compares the saved checkpoint’s evaluation with the original. `--episodes 2` is available for a smoke
check and explicitly reports `complete_suite: false`; subset measurements cannot rank or promote policies.
Historical ZIPs stay byte-for-byte unchanged because recorded traces cite their hashes. Their old
instructions are superseded by the new bundle format. Historical training source was not captured;
exports say so instead of inventing provenance. New training manifests capture source hashes.

To rebuild the evidence from nothing: `scripts/build_library.py`, `scripts/gate2_demo.py`,
`scripts/experiment.py`, `scripts/backfill_scratch_trials.py`, `scripts/experiment2.py`,
`scripts/experiment3.py`. A spent final-test suite is refused, so rerunning an experiment needs a fresh
artifacts directory (`EW_ARTIFACTS=/path`).

## Limitations

- 2D kinematic simulator with ray sensors, not a physics engine or real robot.
- Three training seeds per arm and 150k-step budgets. No arm met the full test threshold (collision
  stayed near 0.18 against a 0.10 limit).
- The library is small (5 checkpoints) and was trained with short budgets, which is partly why reuse
  lost. A single-seed diagnostic suggests the parents' low exploration noise limits adaptation.
- The selection rule was revised twice after seeing results; see `evidence/gate5/RESULTS.md`.
- The live LLM agent run trained a checkpoint that cut collisions from 0.48 to 0.13 on the target suite but
  still missed the 0.10 limit and lost ground on retained suites, so the gate rejected it. That rejection is
  the correct outcome, not a demo of an improvement.
- No demonstrated efficiency advantage is claimed: with three seeds the scratch-vs-warm-start gap is
  consistent across paired seeds but not a statistical result, and no arm reached the full threshold.

## Evidence

Per-gate commands and outputs: [`evidence/GATES.md`](evidence/GATES.md). Readiness and rule checks:
[`evidence/gate0/readiness.md`](evidence/gate0/readiness.md). Demo script: [`docs/demo-script.md`](docs/demo-script.md).

## Documents, dates and AI disclosure

- `docs/v2-original/prd.md` and `spec.md` are dated 14 October 2026, before the event started. They
  are pre-event planning material and are included unchanged (sha256 in `evidence/gate0/readiness.md`).
- All code, training runs and results were produced after kickoff, on 15 October 2026 (git history).
- AI tool disclosure: Claude Code (Anthropic) produced the initial code, experiments and documentation.
  OpenAI Codex assisted the independent PRD audit, queue and validation fixes, reproducible exports, local
  agent launcher, tests, judge guide and landing updates, browser QA and edited demo film. Both were
  directed by the project owner. Runtime provider/model identity is recorded separately in each agent trace.

## Acknowledgements

FalkorDB, Stable-Baselines3, Gymnasium, PyTorch, FastAPI, three.js, the Model Context Protocol Python SDK and the
Anthropic Python SDK. License: MIT (see `LICENSE`).

## Hosted demo

The landing page has a **Live from FalkorDB** console: five buttons re-run, against the live graph, the read-only
templates the recorded agent run used (`failure_inspection`, `relevant_trials`, `scratch_trials`, `decision_provenance`,
`promotion_evidence`) with the parameters stored in its decision and promotion records. Endpoints:
`GET /api/live/overview` (node and edge counts), `GET /api/live/query/{failure|transfer|scratch|decision|gate}` and
`GET /api/live/featured` (the recorded decision ranking and gate checks). All go through `GRAPH.RO_QUERY`.

`Dockerfile` builds a read-only studio: the pinned FalkorDB image plus the FastAPI studio, without torch or the
worker (about 80 MB of memory). On boot it rebuilds the graph from the committed records, so the hosted graph
matches this repository. Browsing, decisions and what-ifs work there; training, evaluation, promotion and export
return 403 and run on the full local setup (`scripts/start.sh`). The landing page is `web/index.html`, the judge guide is `web/guide.html`, and the
studio is `web/studio.html`. Dynamic measurements come from records or live queries; the guide identifies
the specific recorded run it describes. `design/design.md` is the committed shared visual guide.

```
docker build -t embodiweave . && docker run -p 8000:8000 embodiweave
```

## License

MIT, see [LICENSE](LICENSE).
