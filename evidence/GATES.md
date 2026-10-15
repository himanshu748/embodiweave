# Gate evidence log

All commands ran in the Claude Code cloud container described in `gate0/readiness.md`
(x86_64, 4 CPU, 15.7 GiB, no GPU). Nothing here ran on the user's Mac.

## Gate 1: environment and reloadable PPO (2026-10-15, 09:25 to 09:37 IST)

Frozen contract `ew-contract-1:2f013b6f4849` (full dump: `gate1/frozen_contract.json`):
unicycle robot r=0.20 m, v in [0, 1.0] m/s, w in [-2, 2] rad/s, dt 0.1 s, no action repeat.
Frame = [goal_dist/10, cos bearing, sin bearing, prev v/vmax, prev w/wmax, 12 free ranges/4 m
(CCW from heading)] = 17 features; history 3 frames newest first = 51-dim observation; history
reset fills all slots with the episode's first frame. Actions [a_v, a_w] clipped to [-1, 1],
v = (a_v+1)/2*vmax, w = a_w*wmax. VecNormalize(obs+reward, clip 10) saved per checkpoint.
Reward `ew-reward-1`: progress 1.0/m, time -0.005/step, proximity up to -0.05 inside 0.4 m,
success +10 (goal < 0.3 m), collision -10; 250-step limit.

| Check | Command | Observed |
|---|---|---|
| Env tests (checker x4 families, seeding, motion, collisions, timeout, bounce, ray semantics, history reset, replay) | `pytest tests/test_env.py` | 16 passed |
| Throughput | `scripts/throughput.py` | env 13.7k steps/s (open), 8.4k (static_crossing); PPO 3,372 steps/s single process |
| Learnability (scratch PPO, then reload from disk and evaluate) | `scripts/learnability.py` x4 in parallel | open 1.00 success @200k; static 0.875 @300k; crossing 0.95 @300k; static_crossing 0.93 @400k (60 val episodes) |
| Reload consistency | final in-memory validation vs reloaded artifact | identical summaries (e.g. L-target 0.9333 / 0.05 both) |

Learnability decision: all four families are learnable on this host. Static_crossing from scratch
needs about 160k to 240k steps to pass 0.85 success, so a 60k adaptation budget is too small to be
informative (no parent reached threshold at 60k). The Gate 5 adaptation budget is set to 150k.

Checkpoint library (`scripts/build_library.py`, real PPO, library cost ~4.5 min wall):

| Policy | Origin | Trained on | Steps | Contract |
|---|---|---|---|---|
| P-open-a | scratch | open | 120,832 | v1 |
| P-static-a | P-open-a | static | 151,552 | v1 |
| P-cross-a | P-open-a | crossing | 151,552 | v1 |
| P-mirror | scratch | crossing | 200,704 | mirrored rays (same 51-dim shape) |
| P-static-b | P-static-a | static, 4 obstacles | 100,352 | v1 (latest library checkpoint) |
| P-static-a~cross-t1 | P-static-a | crossing (prior transfer measurement) | 61,440 | v1 |

## Gate 2: FalkorDB-backed selection (09:37 to 09:41 IST)

Pinned `falkordb/falkordb@sha256:107455e8...` (module 60002). Client falkordb 1.8.0.
Selection rule `ew-select-1` frozen in `ew/select.py` docstring before any benchmark.

Real decision sequence (`scripts/gate2_demo.py --trial 301`, log `gate2/decisions.log`):
1. D1: `evaluate_candidates`. 4 eligible checkpoints lacked a matched val-target-v1 evaluation;
   P-mirror rejected for a semantic contract mismatch (ray_order) despite identical shape.
2. Matched evaluations (60 episodes each, exact hashes): P-static-b 0.37 success / 0.48 collision
   (21 of 29 collisions with the mover), P-static-a 0.23/0.65, P-cross-a 0.02/0.55 (mostly timeouts
   and static hits), P-open-a 0.02/0.98. The deployed policy fails the target mission.
3. D2 selected P-static-b (all p_reach at the 0.5 prior, best matched validation).
4. Decision-launched trial from P-static-b, 60k budget, seed 301: threshold NOT reached within
   budget (schedule 0.43, 0.45, 0.48, 0.48, final 0.53 success). steps_to_threshold recorded as null.
5. D3 (and the library-catalog decision in `gate2/whatif_outage.log`): P-static-b drops to p_reach
   0.333 and last place; selection changes to P-static-a. This change came from measured evidence.

What-if (`gate2/whatif_outage.log`): GRAPH.COPY to `ew_whatif_*`; two hypothetical successful trials
for P-cross-a flip the choice to P-cross-a with the basis labelled "WHAT-IF: 2 hypothetical, not
measured". A hypothetical contract change rejects P-static-a. Production fingerprint (revision,
label counts, trials, contracts) identical before and after; writes to the production graph refused.

Outage: `docker stop falkordb` -> the decision raises GraphUnavailable immediately, no fallback;
records stay readable on disk; after restart the graph is back at the same revision.

Tests: `pytest tests` -> 26 passed (adds RO write rejection, reload/normalization, parent
immutability, prerequisite closure, same-shape compatibility rejection, missing-evidence handling,
failed trial without invented steps plus decision provenance, final-test protection, What-if
isolation, outage).

## Gate 5 follow-up: rules ew-select-2 and ew-select-3, exp-2 and exp-3 (10:00 to 10:30 IST)

Full write-up: `gate5/RESULTS.md`. Commands, in order:

| Step | Command | Observed |
|---|---|---|
| Transfer diagnostics | `scripts/diag_transfer.py` x4 (seed 601, P-open-a) | val success at 150k: parent_norm 0.08, fresh_norm 0.08, reset_value 0.13, reset_std 0.33 (`gate5/diag-*.json`) |
| ew-select-2 tests | `pytest tests/test_select_v2.py` | scratch trials link FROM_ORIGIN; v1 ignores scratch; What-if scratch flip cannot launch; scratch decision queues a parentless job |
| Backfill | `scripts/backfill_scratch_trials.py` | 3 Trial records derived from exp-1 scratch runs (1 reached at 75k) |
| v2 decision | see `gate5/v2_decision_after_backfill.log` | train_from_scratch, p 0.40 vs best parent 0.25 |
| exp-2 | `scripts/experiment2.py` (frozen in commit 238ddb0) | graph=scratch 0.713 test success vs latest/best_val 0.393; v1 pick P-cross-a 0.093 |
| v2 after exp-2 | `gate5/v2_decision_after_exp2.log` | tie at p 0.25, reuse kept (P-open-a): flaw |
| ew-select-3 + test-target-v3 | commit 0622c9a, `pytest -q` | 37 passed |
| exp-3 | `scripts/experiment3.py` | graph=scratch 0.700 vs latest/best_val 0.370; v2 pick P-open-a 0.133 |
| v3 after exp-3 | `gate5/v3_decision_after_exp3.log` | train_from_scratch, p 0.27 (2/9) |

Spent final-test suites are refused in code: v1 by exp-1, v2 by exp-2, v3 by exp-3.

## Gate 3: agent loop (2026-10-15)

| Check | Evidence | Observed |
|---|---|---|
| Worker idempotency, quota, cancellation, restart recovery, exact-artifact promotion, tool guards, stale decision refusal | `pytest tests/test_gate3.py` | 6 passed |
| MCP stdio server with bounded tools | `ew/mcp_server.py`, `ew/agent_tools.py` | 11 tools; `query_graph` accepts only the 10 read templates, run through GRAPH.RO_QUERY |
| Real runtime LLM, full loop | `artifacts/records/agent_trace/agent-20261015060343-b9e6bc.json`, `artifacts/agent_traces/agent-20261015060343-b9e6bc.jsonl` | OpenRouter `anthropic/claude-sonnet-5.5`, 8 turns, 94 s. Decision `deci-20261015060348-a7ee2c` train_from_scratch; trial reached threshold false; promotion `prom-20261015060506-9a3c7a` rejected (1 of 4 suites passed) |
| Weaker provider, honestly reported | `agent-20261015053827-2f1a08` | Groq free tier ran out of its 40-turn budget before promotion; recorded as incomplete |

## Gate 4: interactive studio

Screenshots in `gate4/`. Replays are drawn from recorded simulator states; scenario controls run a real
evaluation; Live, Recorded and What-if badges; graph-down banner; keyboard focus styles and reduced motion.

## Gate 6: release

| Item | Evidence |
|---|---|
| Public repo, MIT | https://github.com/himanshu748/embodiweave, `LICENSE` |
| Live deploy (read-only hosted mode) | https://embodiweave.onrender.com, `Dockerfile`, `scripts/hosted.sh`; training, evaluation, promotion and export return 403 there (`tests/test_hosted.py`) |
| Graph model and exact Cypher | `README.md` sections Graph model and Cypher the agent runs; `ew/graph/queries.py` |
| Negative findings | `README.md` Limitations, `evidence/gate5/RESULTS.md` (exp-1) |
| Document dates and AI disclosure | `README.md` Documents, dates and AI disclosure; `gate0/readiness.md` |
| Fresh-clone run | 15 Oct: `git clone https://github.com/himanshu748/embodiweave` at bd2129c, new Python 3.13 venv, `pip install -r requirements.lock` (exit 0), `pytest -q` -> 37 passed in 88.6 s. With `tests/test_hosted.py` and the export test added: 39 passed |
| Demo video | not yet recorded (owner) |
