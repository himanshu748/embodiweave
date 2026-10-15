"""Deepgram-only narration and word-aligned captions. Never reads a key file.

Run after evidence generation: DEEPGRAM_API_KEY must be in the process environment.
Existing scene audio is reused only when text/model hashes match its receipt.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import wave

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/film"
MEDIA = ROOT / "docs/demo/voice"
KEYTERMS = ["FalkorDB", "EmbodiWeave", "PPO", "Cypher", "MuJoCo"]


def pcm_wav(data):
    """Finalize streamed WAV's unknown-length RIFF header without changing samples."""
    with wave.open(io.BytesIO(data)) as source:
        channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
        assert width == 2 and rate == 48000
        frames = source.readframes(len(data)//(channels*width))
    result = io.BytesIO()
    with wave.open(result, "wb") as target:
        target.setnchannels(channels); target.setsampwidth(width); target.setframerate(rate)
        target.writeframes(frames)
    return result.getvalue()


def transcribe(data):
    params = [("model", "nova-3"), ("smart_format", "true"), ("utterances", "true")]
    params += [("keyterm", term) for term in KEYTERMS]
    # Upload a compressed copy of the same clip, avoiding HTTP 408 on a slow
    # uplink. Ogg stores Opus pre-skip, preserving the clip's time origin.
    encoded = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
                              "-c:a", "libopus", "-b:a", "48k", "-f", "ogg", "pipe:1"],
                             input=data, stdout=subprocess.PIPE, check=True).stdout
    raw, rid = request("listen?"+urllib.parse.urlencode(params), encoded, "audio/ogg")
    return json.loads(raw), rid


def request(endpoint, body, content_type):
    key = os.environ.get("DEEPGRAM_API_KEY")
    if not key:
        raise SystemExit("DEEPGRAM_API_KEY is not set. Set it privately in the environment; never paste it into a command or log.")
    req = urllib.request.Request("https://api.deepgram.com/v1/" + endpoint, body,
          {"Authorization": "Token " + key, "Content-Type": content_type}, method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return response.read(), response.headers.get("dg-request-id")
        except urllib.error.HTTPError as error:
            if error.code in (408, 429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2*(attempt+1))
                continue
            # Response bodies might contain account metadata. Log only the HTTP status.
            raise RuntimeError(f"Deepgram HTTP {error.code}; no credential or response body logged") from None


def stamp(seconds):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{sec:02},{ms:03}"


def tokens(text):
    # Compare punctuation-insensitively; keep actual transcript/word timings as evidence.
    text = re.sub(r"falkor[ -]+d[ -]+b", "falkordb", text.lower())
    text = re.sub(r"p[ -]+p[ -]+o", "ppo", text)
    numbers = {"one":"1", "two":"2", "three":"3", "four":"4", "five":"5", "eight":"8", "ten":"10",
               "thirteen":"13", "fifteen":"15", "forty":"40", "hundred":"100", "thousand":"1000"}
    return [numbers.get(word, word) for word in re.findall(r"[a-z0-9]+", text)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="aura-2-thalia-en")
    parser.add_argument("--audition", action="store_true", help="Compare Thalia and Apollo on the same short line")
    args = parser.parse_args()
    MEDIA.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if args.audition:
        receipts = []
        prior_auditions = json.loads((EVIDENCE / "voice-auditions.json").read_text()) if (EVIDENCE / "voice-auditions.json").exists() else []
        for model in ("aura-2-thalia-en", "aura-2-apollo-en"):
            text = "I built EmbodiWeave. Robot training decisions you can audit."
            path = MEDIA / f"audition-{model}.wav"
            prior = next((r for r in prior_auditions if r["model"] == model), None)
            if prior and path.exists():
                data, rid = path.read_bytes(), prior["dg_request_id"]
            else:
                data, rid = request("speak?" + urllib.parse.urlencode({"model": model, "encoding": "linear16", "sample_rate": 48000, "container": "wav"}),
                                    json.dumps({"text": text}).encode(), "application/json")
            data = pcm_wav(data)
            path.write_bytes(data)
            stt, stt_id = transcribe(data)
            alt = stt["results"]["channels"][0]["alternatives"][0]
            receipts.append({"dg_request_id": rid, "model": model, "characters": len(text), "sha256": hashlib.sha256(data).hexdigest(),
                             "stt_request_id": stt_id, "stt_model": "nova-3", "transcript": alt["transcript"], "confidence": alt["confidence"]})
        (EVIDENCE / "voice-auditions.json").write_text(json.dumps(receipts, indent=2)+"\n")
        return
    scenes = json.loads((EVIDENCE / "scenes.json").read_text())
    receipt_path = EVIDENCE / "voice-receipts.json"
    old = json.loads(receipt_path.read_text()) if receipt_path.exists() else []
    receipts, captions, timeline = [], [], []
    cursor = 0.
    for scene in scenes:
        text = scene["narration"]
        assert 0 < len(text) <= 2000
        th = hashlib.sha256(text.encode()).hexdigest()
        audio = MEDIA / f"{scene['id']:02}.wav"
        prior = next((r for r in old if r["scene"] == scene["id"] and r["model"] == args.model and r["text_sha256"] == th), None)
        if prior and audio.exists() and hashlib.sha256(audio.read_bytes()).hexdigest() == prior["audio_sha256"]:
            receipt = prior
            data = pcm_wav(audio.read_bytes())
        else:
            data, rid = request("speak?" + urllib.parse.urlencode({"model": args.model, "encoding": "linear16", "sample_rate": 48000, "container": "wav"}),
                                json.dumps({"text": text}).encode(), "application/json")
            receipt = {"scene": scene["id"], "dg_request_id": rid, "model": args.model,
                       "characters": len(text), "text_sha256": th, "source_audio_sha256": hashlib.sha256(data).hexdigest()}
            data = pcm_wav(data)
        audio.write_bytes(data)
        receipt["audio_sha256"] = hashlib.sha256(data).hexdigest()
        # Persist the TTS receipt before STT so network retries do not resynthesize.
        checkpoint = [r for r in old if r["scene"] != scene["id"]] + receipts + [receipt]
        receipt_path.write_text(json.dumps(list({r["scene"]:r for r in checkpoint}.values()), indent=2)+"\n")
        if receipt.get("stt_keyterms") == KEYTERMS:
            stt = json.loads((EVIDENCE / f"transcript-{scene['id']:02}.json").read_text())
        else:
            stt, stt_rid = transcribe(data)
            (EVIDENCE / f"transcript-{scene['id']:02}.json").write_text(json.dumps(stt, indent=2)+"\n")
            receipt.update({"stt_request_id": stt_rid, "stt_model": "nova-3", "stt_keyterms": KEYTERMS,
                            "stt_transport": "Ogg Opus 48kbps copy of canonical 48kHz WAV"})
        with wave.open(str(audio)) as wav:
            assert wav.getframerate() == 48000 and wav.getsampwidth() == 2
            duration = wav.getnframes()/wav.getframerate()
        alternative = stt["results"]["channels"][0]["alternatives"][0]
        ratio = difflib.SequenceMatcher(None, tokens(text), tokens(alternative["transcript"])).ratio()
        receipt.update({"seconds": duration, "transcript_match_ratio": ratio, "transcript": alternative["transcript"]})
        receipts.append(receipt)
        receipt_path.write_text(json.dumps(receipts, indent=2)+"\n")
        if ratio < .88:
            raise RuntimeError(f"Scene {scene['id']} transcript differs from script. Review pronunciation before assembly.")
        if "Falkor" in text and "falkordb" not in "".join(tokens(alternative["transcript"])):
            raise RuntimeError(f"Scene {scene['id']} did not transcribe FalkorDB correctly; review pronunciation.")
        # Word-level Nova-3 timing, in compact readable caption groups.
        words = alternative["words"]
        for i in range(0, len(words), 7):
            group = words[i:i+7]
            caption = " ".join(w.get("punctuated_word", w["word"]) for w in group)
            caption = re.sub(r"\bcipher\b", "Cypher", caption, flags=re.IGNORECASE)
            captions.append((cursor+group[0]["start"], cursor+group[-1]["end"], caption))
        # Real narration determines each scene's duration, plus a short reading beat.
        length = math.ceil((duration + (.5 if scene["id"] not in (1, 12) else 1.5))*30)/30
        timeline.append({**scene, "start": cursor, "voice_seconds": duration, "duration": length,
                         "audio": str(audio.relative_to(ROOT))})
        cursor += length
        print(json.dumps({"scene": scene["id"], "seconds": round(duration, 3), "transcript_match": round(ratio, 3)}), flush=True)
    (ROOT / "docs/demo/embodiweave-demo-v2.srt").write_text("\n\n".join(
        f"{i+1}\n{stamp(a)} --> {stamp(b)}\n{text}" for i, (a,b,text) in enumerate(captions))+"\n")
    (EVIDENCE / "timeline.json").write_text(json.dumps({"model": args.model, "seconds": cursor, "scenes": timeline}, indent=2)+"\n")
    print(json.dumps({"scenes": len(timeline), "narration_seconds": sum(r["seconds"] for r in receipts), "film_seconds": cursor}))


if __name__ == "__main__":
    main()
