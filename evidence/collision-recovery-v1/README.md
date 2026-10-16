# Collision-cost recovery development study

The [protocol](protocol.json) was committed in `5f38e90` before training; measurement labels were corrected in `441a800` before execution. This is a local, deterministic, graph-selected development study, separate from the public MCP run in v4. The graph selected the same exact parent using existing canonical validation, before the new development measurements.

One new child independently continued that parent for 60,000 requested, 61,440 actual PPO steps, seed 31. Its -40 terminal collision cost is the **only** setting changed from the saved -10 rehearsal control, which used the same parent, seed, optimizer and budget. All inference uses unchanged original 2D dynamics, observations and evaluation reward. These checkpoints were not run in MuJoCo for this study.

| Saved policy | Target collisions | Open | Static | Crossing | Total | Goals |
|---|---:|---:|---:|---:|---:|---:|
| Graph-selected parent | 6/60 | 0/40 | 1/40 | 5/40 | 12/180 | 168/180 |
| Saved -10 rehearsal control | 7/60 | 0/40 | 2/40 | 5/40 | 14/180 | 166/180 |
| New -40 rehearsal continuation | 6/60 | 0/40 | 1/40 | 5/40 | 12/180 | 168/180 |

These are a **new paired development batch**, with different seeds from rehearsal-recovery-v1. Do not compare their totals as if they were the same episodes. The -40 child recovered the control's extra target and static collisions on this batch, but its aggregate outcomes only matched the parent. It did not meet the preregistered requirement to reduce collisions relative to both references. The target-only public regression has not been proved fixed.

The child and parent met all four original reference limits on these development episodes; the control exceeded the target collision limit. No promo-1 evaluation, new confirmation, release or best-in-class result is claimed. No additional run follows this stopped protocol.

The [summary](summary.json) links exact artifact hashes, every evaluation and the actual consumed budget. Decision/Run/Trial JSON, all 540 episode outcomes, compressed real simulator replays, the new checkpoint/source bundle and [checksums](checksums.json) are retained. The earlier frozen studies, the confirmed demo policy and the v4 film remain unchanged.
