# Film credits and provenance

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

To reproduce, install `requirements.lock`, `requirements-mujoco.txt` and ffmpeg.
Run `python -m sim.mujoco.evaluate`, ingest with `python -m ew.graph.transfer`,
then `python -m scripts.film.prepare`. With `DEEPGRAM_API_KEY` privately set,
run `python scripts/film/voice.py --audition` and `python scripts/film/voice.py`.
Render with `python -m scripts.film.render`; download the licensed source to
`../cipher.mp3`, then run `python -m scripts.film.assemble`.
The API key is read from the environment only and is not part of the evidence.
