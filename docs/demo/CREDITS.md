# Film credits and provenance

## Current v4 edit

The [v4 timed script](v4/SCRIPT.md) leads with the genuine public LLM → MCP → PPO action and reports the measured target/crossing regression. [V4 receipts](../../evidence/film-v4/) bind its source run, browser captures, native graph export, narration and final media hashes. The 2D replay uses saved poses from the new child's validation bundle. MuJoCo footage reuses the separate v3 transfer replay. Graph layout, titles, cursor movement and highlights are editorial; robot poses are never interpolated or invented. A final PPO progress sample is retained; v4 does not claim an intermediate learning curve.

Narration: Deepgram Aura-2. Captions: Deepgram Nova-3. V4 keeps Thalia for voice consistency, reuses two unchanged clips with original receipts, and generates ten new clips with new request IDs. Nova-3 word timings drive the SRT and burned captions. Its one “and” transcription is corrected to the spoken “in” in “three in sixty”; raw transcription and correction receipt remain available.

Reproduce this edit using the saved assets and narration:

```sh
python -m scripts.film.mcp_update prepare
python -m scripts.film.mcp_update voice
python -m scripts.film.mcp_render browser
python -m scripts.film.mcp_render render
python -m scripts.film.mcp_render assemble
```

The browser step needs the installed browser-video-recording skill renderer (`EW_BROWSER_RENDERER` can set its path). Python uses the pinned project and MuJoCo requirements plus Pillow; ffmpeg is required. The music file below belongs at `../cipher.mp3`. Saved narration can be reused without a key. To change voice text, use an environment-only `DEEPGRAM_API_KEY` or the hidden prompt in `scripts/film/narrate-v4.sh`. V3 assets remain unchanged.

## Earlier film generation and shared credits

- Robot footage: MuJoCo 3.3.7 offscreen rendering of actual recorded states
  produced by unchanged EmbodiWeave PPO checkpoints. No generated, hand-animated
  or keyframed robot motion. Camera movement, range overlays and trails are
  editorial visualization. macOS CGL was the offscreen rendering backend;
  physics ran on CPU. The renderer adjusts lighting and floor texture repeat
  for legibility, without changing geometry, contacts, sensors or trajectories.
- Narration: Deepgram Aura-2. Captions: Deepgram Nova-3.
  Chosen voice: `aura-2-thalia-en`. Both Thalia and Apollo were tested on the
  same line. Thalia's Nova-3 transcript confidence was 0.9946289, Apollo's
  0.9892578; both recognized the words. This is a transcription-based clarity
  check, not a claim of a human listening panel. Request IDs and audio hashes
  are in `evidence/film/voice-auditions.json` and `voice-receipts.json`.
- Captions use Nova-3 word timestamps from compressed copies of the original
  48 kHz WAVs. Ogg Opus transport avoids upload timeouts on this connection.
  Domain keyterms include FalkorDB, EmbodiWeave, PPO, Cypher and MuJoCo. The
  spelling “cipher” is corrected to “Cypher” without changing its word timing.
  Raw transcripts remain in the evidence directory. Streamed WAV headers are
  finalized without changing PCM samples.
- Music: **“Cipher” by Kevin MacLeod (incompetech.com)**, licensed under
  [Creative Commons Attribution 3.0](https://creativecommons.org/licenses/by/3.0/).
  [Author's source](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3)
  and [file/licence record](https://commons.wikimedia.org/wiki/File:Cipher_(ISRC_USUAN1100844).mp3).
  The excerpt is edited, faded, normalized and mixed about 18 dB below normalized
  narration. No endorsement is implied. Credit must remain in the YouTube
  description and the film. The standalone music is not redistributed here.
- Fonts: Space Grotesk and IBM Plex Mono, from Google Fonts' source repository,
  under the included SIL Open Font Licences in `assets/`.
- Graph figures: real FalkorDB records and returned Cypher rows, rendered in an
  editorial layout. Node highlights follow the narration's word timings. The
  decision sequence replays recorded history; it is not a newly launched run.
- Learning curves: actual recent-training-success progress samples from the
  two recorded PPO attempts. These are not validation learning curves. Logs'
  SHA-256 values and source samples are in `evidence/film/learning-progress.json`.
- Gate and held-out figures: existing recorded search-v1 evidence. No gate,
  validation result, policy weight or held-out result was changed for the film.
  Held-out outcomes remain outside the planning graph.

The original-generation commands below describe the earlier film pipeline; they are not needed for v4. Preserve the frozen study directories when reproducing experiments in a separate output location. Install `requirements.lock`, `requirements-mujoco.txt` and ffmpeg.
Run `python -m sim.mujoco.evaluate`, ingest with `python -m ew.graph.transfer`,
then `python -m scripts.film.prepare`. With `DEEPGRAM_API_KEY` privately set,
run `python scripts/film/voice.py --audition` and `python scripts/film/voice.py`.
Render with `python -m scripts.film.render`; download the licensed source to
`../cipher.mp3`, then run `python -m scripts.film.assemble`.
The API key is read from the environment only and is not part of the evidence.
