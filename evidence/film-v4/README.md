# Film v4 evidence

The film is a new edit of the recorded public `agent-mcp-v2` action. It does not invoke another agent, trainer or evaluator. [Run source](../mcp-agent-v2/README.md) · [Final timed script](../../docs/demo/v4/SCRIPT.md).

- `source-records.json`: exact input checksums and run summary.
- `graph-records.json`: fresh, read-only FalkorDB node/edge export, including Cypher and parameters; validation-only ID whitelist.
- `browser/`: actual public-page evidence captures. The browser renderer adds only editorial cursor motion. `browser-edit-*.json` preserve its edit instructions.
- `policy-replay.json`: saved original-2D validation states from the checkpoint bundle. The film shows seed 1300030, the first target collision; full-suite counts remain visible.
- `voice-receipts.json`: Aura-2 model, request IDs, character counts, audio hashes, Nova-3 receipt IDs and transcript comparison. Scenes 3 and 12 reuse unchanged original Deepgram clips. Raw transcripts remain unchanged. One caption word (and → in) is corrected to match the spoken script at its original word timing.
- `timeline.json`, `captions.json`: scene and word-timed caption edit, 117.6 seconds total.
- `v3-backup-checksums.json`: immutable v3 media, docs and evidence snapshot, checked before and after rendering.
- `film-receipt.json`: final output sizes, hashes, duration, source physics clip and music credit.
- `checksums.json`: this evidence directory and final public media checksums.

The new child passes 4/4 gates, but target/crossing collisions regress against its parent. No default deployment changed. Historical 13/100 failure, 8/100 fresh confirmation and 6/40 MuJoCo transfer belong to distinct frozen studies. No new confirmation was opened. The MuJoCo footage is the unchanged-weight 2D checkpoint in a separate physics test, reused from v3.

## Reproduce the edit

Use the pinned project Python dependencies, `requirements-mujoco.txt`, Pillow and ffmpeg. A matching installed browser-video-recording skill renders the captured UI clips. No keys are needed to reuse the saved narration:

```sh
python -m scripts.film.mcp_update prepare
python -m scripts.film.mcp_update voice
python -m scripts.film.mcp_render browser
python -m scripts.film.mcp_render render
python -m scripts.film.mcp_render assemble
```

New voice text requires `DEEPGRAM_API_KEY` in the process environment only; `scripts/film/narrate-v4.sh` accepts it through a hidden prompt. Never save the key in a file. The pipeline never modifies frozen criteria, suites, checkpoint weights or v3 backups. Outputs go to the workspace `outputs/film-v4/` directory, and finished public exports to `web/media/`.
