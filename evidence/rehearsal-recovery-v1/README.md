# Rehearsal recovery development study

This is a local, deterministic, graph-selected development experiment. It is separate from the public MCP run shown in v4, and it did not replace the demo policy. The [protocol](protocol.json) was committed in `9b0b32d` before training. Parent selection used a real `GRAPH.RO_QUERY` against the earlier physics-study graph, with exact artifact verification. The [saved query, candidates and origin](parent-selection.json) are retained.

Each child independently continued the same parent for 60,000 requested, 61,440 actual PPO steps, seed 31. The only difference between the two new arms is cycling the four training families. Both use the baseline -10 collision cost. These are original 2D training and development measurements, without MuJoCo inference or a new held-out evaluation.

| Saved policy | Target collisions | Open | Static | Crossing | Total | Goals |
|---|---:|---:|---:|---:|---:|---:|
| Graph-selected parent | 3/60 | 0/40 | 0/40 | 4/40 | 7/180 | 173/180 |
| Target-only continuation | 4/60 | 0/40 | 0/40 | 3/40 | 7/180 | 173/180 |
| Rehearsal continuation | 3/60 | 0/40 | 1/40 | 3/40 | 7/180 | 173/180 |

All three met the original success floors and collision maxima on these **fresh development** episodes. This does not constitute a new promo-1 gate or confirmation. Rehearsal reduced target collisions relative to the target-only child but introduced a static collision; neither child reduced total collisions relative to the parent. The preregistered no-regression requirement failed. No recipe was adopted and no new checkpoint was released.

[Summary and exact hashes](summary.json), per-arm Decision/Run/Trial records, all 540 episode outcomes, compressed real simulator replays, the two checkpoint/source bundles and [checksums](checksums.json) are retained here. The public film's earlier MCP regression remains unchanged. This small, single-training-seed comparison establishes neither collision-free operation nor best-in-class performance.
