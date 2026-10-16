# EmbodiWeave v5 — final narration and edit

Duration: 118.10 seconds. Narration: 114.64 seconds. Voice: Deepgram Aura-2 Thalia (`aura-2-thalia-en`). Captions: Deepgram Nova-3 word timings.

This edit uses saved evidence only. No new simulation, training or evaluation was performed for the film. The v3 attempt stopped before selecting an origin or launching training.

## 00:00–00:10 · A failure needs its history

This robot collided. Choosing a checkpoint to retrain needs its lineage, sensor contract and exact test results. Falkor-D-B connects that evidence.

## 00:10–00:17 · A complete MCP run: four gates passed

My agent used M-C-P and Falkor-D-B to launch real robot training. The run passed four validation gates.

## 00:17–00:25 · The agent launches training

It chooses a starting checkpoint and calls start training. The guardrail approves the evidence and budget before the worker starts.

## 00:25–00:33 · FalkorDB connects the evidence

Falkor-D-B connects each policy to its training run, evaluations, failures and recorded decisions.

## 00:33–00:42 · A shortest path through real lineage

Its shortest-path query returned a passing ancestor, one hop away. The agent compared seventeen eligible origins and chose a different checkpoint.

## 00:42–00:52 · The guardrail can veto the agent

The guardrail checks sensor contracts, artifact hashes, complete validation and the training budget. It can veto an incompatible origin.

## 00:52–01:01 · The Decision precedes the action

Before training, a Decision saves the model, tool calls, Cypher, parameters and returned records. Planning stops without Falkor-D-B.

## 01:01–01:09 · Real PPO, then saved-policy evaluation

The worker trained sixty-one thousand, four hundred forty P-P-O steps, then reloaded the checkpoint for one hundred eighty validation episodes.

## 01:09–01:19 · Four suites. The same fixed gate.

All four suites passed the unchanged gate. Target collisions were three in sixty. Open had zero; static and crossing had one each in forty.

## 01:19–01:30 · Target and crossing regressed

But the parent had two target collisions and no crossing collisions. Both measures got worse. Passing the gate does not establish an improvement, so I kept the demo policy unchanged.

## 01:30–01:38 · The next agent read the regression

The next agent read that regression and the weighted graph ranking. Its context limit stopped the attempt before training. I did not retry.

## 01:38–01:48 · The shipped checkpoint passed fresh confirmation

The shipped graph-selected checkpoint passed all four validation suites and fresh confirmation. Eight target collisions in a hundred episodes, below the ten percent limit.

## 01:48–01:58 · Every action is a node you can query

Every action is a node you can query. Inspect the Decision, the live demo and the evidence. EmbodiWeave. Built on Falkor-D-B.

## Evidence and editorial treatment

- Scenes 1–10: [completed v2 public MCP run](../../../evidence/mcp-agent-v2/), original [browser captures and source records](../../../evidence/film-v4/). The collision replay is recorded policy output. Slides, graph placement and highlights are editorial; browser captures replay the completed run.
- Scene 11: [stopped v3 attempt](../../../evidence/mcp-agent-v3/summary.json), [weighted graph output](../../../evidence/mcp-agent-v3/rank_regression_origins.json). The weight is 1/60 + 1/40 = 0.0416666666666667 across one measured child. It is descriptive evidence, not a probability or demonstrated planning advantage.
- Scene 12: [confirmed checkpoint](../../../evidence/robustness-v2/selected.json), [saved success replay](../../../evidence/film-v5/success-replay.json). The success clip is a validation episode from that checkpoint; 8/100 is the separate fresh-confirmation aggregate.
- Scene 13: the v2 Decision and connected outcome are recorded in [the outcome receipt](../../../evidence/mcp-agent-v3/v2-outcome-backfill.json).

## Narration changes and reproduction

The problem line was shortened and re-recorded after Nova-3 misheard the first take; the rejected take and receipt remain under revisions/. Graph, shortest-path, guardrail and Decision lines were shortened for timing. The previous earlier-study and MuJoCo scenes were removed from this film, while their results remain in the README. Five unchanged clips reuse their original Deepgram audio, timings and request IDs; receipts label this explicitly. The stopped v3 attempt and the shipped checkpoint replace the old closing sequence.

Run `bash scripts/film/narrate-v5.sh` from the repository; the hidden prompt puts the key only in the child environment. Render with `python -m scripts.film.loop_render render` then `python -m scripts.film.loop_render assemble`. Existing source captures, saved simulator traces, fonts, ffmpeg and the licensed Cipher track are required. Do not rerun the preregistered public attempt.

Music: “Cipher” by Kevin MacLeod, [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/), [source](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3). Edited and mixed about 18 dB below normalized narration. Fonts: Space Grotesk and IBM Plex Mono (SIL OFL; licences in ../assets/).

Narration: Deepgram Aura-2. Captions: Deepgram Nova-3.
