# Demo script (about 3 minutes)

Recorded against the local studio (`bash scripts/start.sh`, then http://127.0.0.1:8000). Every number
on screen comes from stored records; say "simulated robot" at least once.

1. **The failure (0:00-0:25).** Arena replay, Before = deployed P-static-b on val-target-v1. Play an
   episode where it hits the crossing mover. Point at the meta line: 37% success, 48% collision on 60
   matched episodes, 21 of 29 collisions with the mover.
2. **What the graph knows (0:25-0:55).** Decision tab. Read the explanation of the latest decision:
   rule ew-select-3, scratch ranked first. Show the ranked rows: each parent's trials as red crosses,
   scratch with two green ticks, children scores. Open Rejected: P-mirror has the same tensor shape
   but a different ray order, so it is rejected with the differing field.
3. **The Cypher (0:55-1:20).** Evidence tab. Expand `candidate_eligibility` and `scratch_trials`;
   show params, returned record ids and the graph revision. Mention GRAPH.RO_QUERY: these reads cannot
   write.
4. **The graph view (1:20-1:40).** Graph tab: the decision node, SELECTED edge to the scratch Origin,
   REJECTED edge to P-mirror, trials hanging off each parent. Click a trial to show its immutable record.
5. **Acting (1:40-2:05).** Seed field, Launch training. Jobs tab shows the queued job and real step
   progress. (Optional: Cancel to show cancellation.) Say that the worker re-runs the rule before it
   starts and refuses a stale decision.
6. **What-if (2:05-2:25).** Open What-if, add two hypothetical successful trials for P-static-b, Run.
   The ranking flips and is labelled hypothetical; production revision is unchanged; Launch is disabled.
7. **Did it help? (2:25-3:00).** Results tab. exp-1: the first rule chose among parents only and was
   no better than baselines; scratch won. exp-2 and exp-3 on fresh test suites: the graph chose
   scratch, about 0.70 test success against 0.37 to 0.39 for the latest or best-validation checkpoint,
   on every paired seed. Close on the honest caveats: three seeds, no arm met the full collision limit.

Agent tab: show trace `agent-20261015060343-b9e6bc` (OpenRouter, `anthropic/claude-sonnet-5.5`, 8 turns). It
is a real LLM run: the model chose every tool call, the rule chose scratch, PPO missed the threshold and the
gate rejected the checkpoint (target 0.87 success but 0.13 collisions against a 0.10 limit). Say that the
rejection is the system working. Do not present the deterministic trace as an LLM run.

## 30-second opening for the hosted site (https://embodiweave.onrender.com)

1. Hero: let the two replays play. "Same seed. The deployed policy hits the pedestrian at step 51, the
   checkpoint the agent trained reaches the goal."
2. The dark Live card under it: "This just queried FalkorDB. Fine-tuning a parent: 0 of 27 matching trials
   ever reached the threshold. From scratch: 2 of 12. That is why the agent trained from scratch."
3. Scroll to Live from FalkorDB, click questions 2 and 5 to show the Cypher, params and returned rows.
4. Scroll to From rows to a decision: the ranked options and the four gate checks that rejected it.
