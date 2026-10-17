"""Append the recorded v4 evidence clip to v5; never overwrite either source."""
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "web/media"
RECEIPTS = ROOT / "evidence/film-v5-v4"
TITLE = (
    "v4: graph-backed origin exclusion — same gate, different origin, "
    "still not released."
)
SOURCES = {
    "web/media/embodiweave-demo-v5.mp4":
        "2dfe700299b8b30ad6143b4279268b191ed057d4d34385ec10503faa8b7d9e2e",
    "web/media/embodiweave-v4-outcome-clip.mp4":
        "42e52af755cb9333d4b9ba7c781460f286efc3ca0478fbf91790952605d7c605",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(path),
    ]))


def main():
    for path, digest in SOURCES.items():
        assert sha(ROOT / path) == digest, f"Source changed: {path}"
    outcome_path = ROOT / "evidence/mcp-agent-v4/outcome.json"
    outcome = json.loads(outcome_path.read_text())
    target = next(s for s in outcome["suites"] if s["suite_id"] == "val-target-v1")
    assert (target["parent_collisions"], target["child_collisions"], target["episodes"]) == (2, 4, 60)
    assert outcome["release_verdict"] == "not_released_regression"

    RECEIPTS.mkdir(parents=True, exist_ok=True)
    card = RECEIPTS / "title-card.png"
    image = Image.new("RGB", (1920, 1080), "#f2f0e8")
    draw = ImageDraw.Draw(image)
    for x in range(0, 1920, 36):
        draw.line((x, 0, x, 1080), fill="#e5e5dc")
    for y in range(0, 1080, 36):
        draw.line((0, y, 1920, y), fill="#e5e5dc")
    face = str(ROOT / "docs/demo/assets/SpaceGrotesk.ttf")
    heading = ImageFont.truetype(face, 78)
    lines = ["v4: graph-backed origin exclusion —", "same gate, different origin,", "still not released."]
    assert " ".join(lines) == TITLE
    draw.rectangle((120, 322, 128, 742), fill="#e85d19")
    for index, line in enumerate(lines):
        draw.text((174, 350 + index * 123), line, font=heading,
                  fill="#e85d19" if index == 2 else "#252d30")
    image.save(card)

    output = MEDIA / "embodiweave-demo-v5-with-v4.mp4"
    # Normalize timestamps and add silent audio only after v5 ends. The appended
    # evidence clip is unchanged visually, including its six-second final table.
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-i", str(MEDIA / "embodiweave-demo-v5.mp4"),
        "-loop", "1", "-framerate", "30", "-t", "2", "-i", str(card),
        "-i", str(MEDIA / "embodiweave-v4-outcome-clip.mp4"),
        "-filter_complex",
        "[0:v]setpts=PTS-STARTPTS,setsar=1[v0];"
        "[1:v]setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v1];"
        "[2:v]setpts=PTS-STARTPTS,setsar=1[v2];"
        "[v0][v1][v2]concat=n=3:v=1:a=0[v];"
        "[0:a]apad,atrim=duration=118.1,asetpts=PTS-STARTPTS[a0];"
        "anullsrc=r=48000:cl=stereo,atrim=duration=20[a1];"
        "[a0][a1]concat=n=2:v=0:a=1[a]",
        "-map", "[v]", "-map", "[a]", "-r", "30", "-t", "138.1",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(output),
    ]
    subprocess.run(command, check=True)
    metadata = probe(output)
    video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    assert video["nb_frames"] == "4143"
    assert (video["width"], video["height"], video["r_frame_rate"]) == (1920, 1080, "30/1")
    assert abs(float(metadata["format"]["duration"]) - 138.1) < 0.03
    for path, digest in SOURCES.items():
        assert sha(ROOT / path) == digest
    source_srt = MEDIA / "embodiweave-demo-v5.srt"
    captions = output.with_suffix(".srt")
    original_captions = source_srt.read_text().rstrip()
    last_index = int(original_captions.split("\n\n")[-1].splitlines()[0])
    additions = [
        ("00:01:58,100 --> 00:02:00,100", TITLE),
        ("00:02:00,100 --> 00:02:06,100", "Recorded regression evidence excludes the old origin."),
        ("00:02:06,100 --> 00:02:12,100", "The MCP agent chooses robust-20261016140226-352fd7.\nA different origin is not proof of learning."),
        ("00:02:12,100 --> 00:02:18,100", "Target collisions: parent 2/60 → child 4/60.\nGate: 4/4. Not released: regression."),
    ]
    captions.write_text(original_captions + "\n\n" + "\n\n".join(
        f"{last_index + index}\n{timing}\n{caption}"
        for index, (timing, caption) in enumerate(additions, 1)
    ) + "\n")
    receipt = {
        "title_card_text": TITLE,
        "segments": [
            {"source": "web/media/embodiweave-demo-v5.mp4", "start_seconds": 0, "end_seconds": 118.1},
            {"source": "evidence/film-v5-v4/title-card.png", "start_seconds": 118.1, "end_seconds": 120.1},
            {"source": "web/media/embodiweave-v4-outcome-clip.mp4", "start_seconds": 120.1, "end_seconds": 138.1},
        ],
        "final_table_seconds": [132.1, 138.1],
        "target_collisions": {"parent": "2/60", "child": "4/60"},
        "outcome_source": {"path": str(outcome_path.relative_to(ROOT)), "sha256": sha(outcome_path)},
        "source_sha256": SOURCES,
        "output": {"path": str(output.relative_to(ROOT)), "sha256": sha(output), "bytes": output.stat().st_size,
                   "duration_seconds": float(video["duration"]), "frames": int(video["nb_frames"]),
                   "width": 1920, "height": 1080, "fps": 30},
        "title_card_sha256": sha(card),
        "captions": {"path": str(captions.relative_to(ROOT)), "sha256": sha(captions),
                     "source_path": str(source_srt.relative_to(ROOT)), "source_sha256": sha(source_srt),
                     "note": "Original v5 captions retained; appended text captions describe the silent evidence segment."},
        "audio": "Existing v5 soundtrack retained; two-second card and eighteen-second evidence clip are silent.",
        "editorial": "New title card and assembly only. No new robot footage, simulation, training, or result. Original v5 and v4 source files unchanged.",
    }
    (RECEIPTS / "assembly.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
