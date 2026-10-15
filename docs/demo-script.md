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

Do not present the Agent tab as an LLM run unless `python -m ew.agent llm` was actually run with an
API key; the existing trace is labelled "Deterministic rule run".
