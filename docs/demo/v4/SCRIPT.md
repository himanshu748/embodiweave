# EmbodiWeave v4: the agent acts through MCP

Final edit: **117.60 seconds**, 1080p, 30 fps. Training-launch narration finishes at **00:17.340**. Narration is Deepgram Aura-2 Thalia; captions use Deepgram Nova-3 word timings. V3 media, script and evidence remain unchanged as backup.

The script retains the facts in the requested draft and uses shorter wording to fit 120 seconds. It leads with the recorded MCP action, then explains the graph. It reports the new gate pass and the measured regression; earlier confirmation and physics results appear only as separately labelled studies.

Recorded source: [MCP run summary](../../../evidence/mcp-agent-v2/summary.json), [agent receipt](../../../evidence/mcp-agent-v2/agent-receipt.json), [pre-action Decision](../../../evidence/mcp-agent-v2/decision.json), [checkpoint bundle](../../../evidence/mcp-agent-v2/repro-v3.zip). No new model, training or evaluation run was performed for this film.

## 00:00.000–00:10.100: The agent chooses its tools

My agent reads Falkor-D-B through M-C-P. It chooses tools to diagnose a checkpoint, compare origins, and trace a passing ancestor.

**On screen:** Actual public-page captures of the completed MCP tool trace; readable highlights are editorial. Source: `agent-receipt.json`. Label: recorded evidence replay, waiting time removed.

## 00:10.100–00:17.700: The agent launches training

It chooses a starting checkpoint and calls start training. The guardrail approves the evidence and budget before the worker starts.

**On screen:** Actual `start_training` arguments, allowed guardrail and queued result. The pending tool response is not a completed training result. Chosen origin: `physics-20261016150004-25da9c`; request 60,000 steps, seed 29.

## 00:17.700–00:27.600: FalkorDB connects the evidence

Falkor-D-B connects policies, training runs, trials, evaluations, failures and decisions. The links preserve what produced what.

**On screen:** Real nodes and edges returned by `GRAPH.RO_QUERY` at revision 10; layout and word-timed highlights are editorial. See `graph-records.json`.

## 00:27.600–00:38.767: A shortest path through real lineage

The shortest-path tool runs inside Falkor-D-B. It returned the nearest passing ancestor, one hop away. The agent considered it alongside seventeen eligible origins.

**On screen:** The actual `nearest-passing-ancestor.cypher` and returned one-hop ancestor. It returns an unweighted lineage path, not a safety prediction. The chosen origin is different; the model considered 17 eligible origins.

## 00:38.767–00:49.800: The guardrail can veto the agent

Contracts tie a checkpoint to sensor and action meanings. The guardrail vetoes incompatible origins, stale hashes, incomplete validation, or unsupported budgets.

**On screen:** Real Contract node fields and implemented guardrail checks. This run was allowed; no veto fixture is presented as a real rejected run.

## 00:49.800–01:00.833: The Decision precedes the action

Before training, the Decision saves the model, tool calls, Cypher, parameters and returned records. If Falkor-D-B is unavailable, planning stops.

**On screen:** Fields of `deci-20261016121309-c0c93f`, written before Run `run-20261016121310-0bfccc`. The graph revision is the recorded decision revision, not a claim that no later graph change is possible.

## 01:00.833–01:09.633: Real PPO, then saved-policy evaluation

The worker trained sixty-one thousand, four hundred forty P-P-O steps, then reloaded the checkpoint for one hundred eighty validation episodes.

**On screen:** Original 2D simulator states from the new saved checkpoint, target validation seed 1300030, the first collision in its suite. Poses are sampled at their recorded 10 Hz and never interpolated. This is post-training evaluation footage, not a learning-progress recording. Only final PPO progress was retained; no intermediate curve is invented.

## 01:09.633–01:19.333: Four suites. The same fixed gate.

All four suites passed the unchanged gate. Target collisions were three in sixty. Open had zero; static and crossing had one each in forty.

**On screen:** All 180 episodes and fixed `promo-1` checks from `training-receipt.json`. Limits target/open/static/crossing: 10/5/10/15 percent. Goals and minimum success thresholds also remain visible. Nova-3 transcribed spoken "in" as "and" in "three in sixty"; the caption corrects that one word at its original timing, with a correction receipt. Counts are unchanged.

## 01:19.333–01:30.733: Target and crossing regressed

But the parent had two target collisions and no crossing collisions. Both measures got worse. Passing the gate does not establish an improvement, so I kept the demo policy unchanged.

**On screen:** Matched validation comparison against the chosen parent: target 2/60 to 3/60 collisions; crossing 0/40 to 1/40. Gate pass is not evidence of improvement. The run did not change the current demo policy.

## 01:30.733–01:40.833: Earlier results remain frozen

The earlier failure stays visible: thirteen target collisions in one hundred held-out episodes. The separate confirmed checkpoint still has eight in one hundred.

**On screen:** Separate frozen studies: earlier search-v1 held-out failure 13/100 target collisions; robustness-v2 fresh confirmation 8/100. Neither is the new MCP child. No held-out test was rerun.

## 01:40.833–01:50.733: Separate MuJoCo transfer evidence

That confirmed two-dimensional checkpoint also collided six times in forty MuJoCo target episodes, without retraining. This is a separate transfer study.

**On screen:** Reuses the genuine MuJoCo-v2 joint-state replay from v3, with new title/caption bands. Same recorded paired seed 5203012; selected illustration. The confirmed 2D checkpoint, unchanged in physics, had target 6/40 and crossing 4/40 collisions across the full suite. It is not the new MCP child and was not trained in MuJoCo.

## 01:50.733–01:57.600: Every result has its evidence

The graph and checksummed evidence make these results inspectable. EmbodiWeave. Built on Falkor-D-B.

**On screen:** Editorial end card. Repo and live links; Deepgram and music credits. No simulated robot motion in this card.
