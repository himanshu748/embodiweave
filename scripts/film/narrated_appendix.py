"""Deepgram narration for the existing 20-second appendix. Preserve all sources."""
import argparse
import hashlib
import json
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.film import voice
from scripts.film.mcp_update import validate_transcript

ROOT = Path(__file__).resolve().parents[2]
E = ROOT / 'evidence/film-v5-v4-narrated'
DOC = ROOT / 'docs/demo/v5-v4'
MODEL = 'aura-2-thalia-en'
SCENES = [
    (1, 118.1, 2, 'Version four.'),
    (2, 120.1, 6, 'The graph excludes the old origin using recorded regression evidence.'),
    (3, 126.1, 6, 'The agent chooses a different checkpoint. The fixed gate passes all four suites.'),
    (4, 132.1, 6, 'Target collisions rise from two in sixty to four in sixty. Not released.'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def narrate():
    E.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    outcome = json.loads((ROOT / 'evidence/mcp-agent-v4/outcome.json').read_text())
    target = next(s for s in outcome['suites'] if s['suite_id'] == 'val-target-v1')
    assert (target['parent_collisions'], target['child_collisions'], target['episodes']) == (2, 4, 60)
    receipt_path = E / 'voice-receipts.json'
    old = json.loads(receipt_path.read_text()) if receipt_path.exists() else []
    receipts, captions = [], []
    for scene, start, available, script in SCENES:
        audio = E / f'voice-{scene:02}.wav'
        transcript_path = E / f'transcript-{scene:02}.json'
        text_sha = hashlib.sha256(script.encode()).hexdigest()
        prior = next((r for r in old if r['scene'] == scene and r['text_sha256'] == text_sha), None)
        if prior and audio.exists() and sha(audio) == prior['audio_sha256']:
            receipt = prior.copy()
        else:
            raw, rid = voice.request('speak?model=' + MODEL + '&encoding=linear16&sample_rate=48000&container=wav',
                                     json.dumps({'text': script}).encode(), 'application/json')
            audio.write_bytes(voice.pcm_wav(raw))
            receipt = dict(scene=scene, model=MODEL, dg_request_id=rid, characters=len(script),
                           text_sha256=text_sha, audio_sha256=sha(audio), script=script)
        def checkpoint():
            write(receipt_path, list({r['scene']: r for r in old + receipts + [receipt]}.values()))
        checkpoint()
        if not receipt.get('stt_request_id'):
            stt, rid = voice.transcribe(audio.read_bytes())
            write(transcript_path, stt)
            receipt.update(stt_request_id=rid, stt_model='nova-3')
            checkpoint()
        alt = json.loads(transcript_path.read_text())['results']['channels'][0]['alternatives'][0]
        match = validate_transcript(script, alt['transcript'])
        with wave.open(str(audio)) as wav:
            seconds = wav.getnframes() / wav.getframerate()
        # Preserve the requested 2 + 18 second visuals; allow at most a mild
        # tempo adjustment and apply the same factor to Nova-3 word timestamps.
        tempo = max(1, seconds / (available - .15))
        if tempo > 1.15:
            raise RuntimeError(f'Scene {scene} needs shorter wording before assembly')
        receipt.update(seconds=seconds, start_seconds=start, tempo=tempo,
                       transcript=alt['transcript'], transcript_match_ratio=match,
                       audio=str(audio.relative_to(ROOT)))
        receipts.append(receipt)
        checkpoint()
        words = alt['words']
        for i in range(0, len(words), 7):
            group = words[i:i+7]
            captions.append([start + group[0]['start'] / tempo, start + group[-1]['end'] / tempo,
                             ' '.join(w.get('punctuated_word', w['word']) for w in group)])
        print(json.dumps({'scene': scene, 'seconds': seconds, 'tempo': tempo, 'transcript_match': match}), flush=True)
    write(E / 'captions.json', captions)
    original = (ROOT / 'web/media/embodiweave-demo-v5.srt').read_text().rstrip()
    last = int(original.split('\n\n')[-1].splitlines()[0])
    (DOC / 'embodiweave-demo-v5-with-v4-narrated.srt').write_text(original + '\n\n' + '\n\n'.join(
        f'{last+i}\n{voice.stamp(a)} --> {voice.stamp(b)}\n{text}'
        for i, (a, b, text) in enumerate(captions, 1)) + '\n')
    (DOC / 'SCRIPT.md').write_text('# Combined film: narrated v4 appendix\n\n'
        'The first 118.10 seconds retain the original v5 film and narration.\n\n'
        + '\n\n'.join(f'## {start:.2f}–{start+duration:.2f} seconds\n\n{text}'
                       for _, start, duration, text in SCENES) + '\n')


def assemble():
    receipts = json.loads((E / 'voice-receipts.json').read_text())
    captions = json.loads((E / 'captions.json').read_text())
    assert len(receipts) == 4
    media = ROOT / 'web/media'
    sources = {
        'web/media/embodiweave-demo-v5.mp4': '2dfe700299b8b30ad6143b4279268b191ed057d4d34385ec10503faa8b7d9e2e',
        'web/media/embodiweave-demo-v5-with-v4.mp4': 'c1212a08c9ace2baec173402c364fb0a9fad7e6cbbe553dbad2507464ca697c1',
    }
    for path, digest in sources.items():
        assert sha(ROOT / path) == digest
    output_dir = ROOT.parents[1] / 'outputs/film-v5-v4-narrated'
    output_dir.mkdir(parents=True, exist_ok=True)
    mix = output_dir / 'appendix.wav'
    inputs, filters, labels = [], [], []
    for i, receipt in enumerate(receipts):
        audio = ROOT / receipt['audio']
        assert sha(audio) == receipt['audio_sha256']
        inputs += ['-i', str(audio)]
        delay = round((receipt['start_seconds'] - 118.1) * 1000)
        filters.append(f'[{i}:a]atempo={receipt["tempo"]},adelay={delay}:all=1[a{i}]')
        labels.append(f'[a{i}]')
    filters.append(''.join(labels) + 'amix=inputs=4:normalize=0,apad,atrim=duration=20[a]')
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', *inputs,
                    '-filter_complex', ';'.join(filters), '-map', '[a]', '-ar', '48000',
                    '-ac', '2', '-c:a', 'pcm_s16le', str(mix)], check=True)

    tail = output_dir / 'captioned-appendix.mp4'
    decoder = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error',
        '-ss', '118.1', '-i', str(media / 'embodiweave-demo-v5-with-v4.mp4'),
        '-an', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'], stdout=subprocess.PIPE)
    encoder = subprocess.Popen(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1920x1080', '-r', '30', '-i', 'pipe:0',
        '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
        str(tail)], stdin=subprocess.PIPE)
    font = ImageFont.truetype(str(ROOT / 'docs/demo/assets/SpaceGrotesk.ttf'), 37)
    for frame in range(600):
        data = decoder.stdout.read(1920 * 1080 * 3)
        assert len(data) == 1920 * 1080 * 3
        image = Image.frombytes('RGB', (1920, 1080), data)
        draw = ImageDraw.Draw(image)
        # Replace the former silent-clip footer; leave the evidence table intact.
        if frame >= 60:
            draw.rectangle((0, 970, 1920, 1066), fill='#252d30')
        now = 118.1 + frame / 30
        caption = next((text for a, b, text in captions if a <= now <= b), None)
        if caption:
            width = draw.textlength(caption, font=font)
            assert width < 1760, 'Caption exceeds safe width'
            if frame < 60:
                draw.rectangle((0, 970, 1920, 1066), fill='#252d30')
            draw.text(((1920-width)/2, 993), caption, fill='white', font=font)
        encoder.stdin.write(image.tobytes())
    encoder.stdin.close()
    decoder.stdout.close()
    assert decoder.wait() == 0 and encoder.wait() == 0
    output = media / 'embodiweave-demo-v5-with-v4-narrated.mp4'
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-i', str(media / 'embodiweave-demo-v5.mp4'), '-i', str(tail), '-i', str(mix),
        '-filter_complex', '[0:v]setpts=PTS-STARTPTS[v0];[1:v]setpts=PTS-STARTPTS[v1];'
        '[v0][v1]concat=n=2:v=1:a=0[v];'
        '[0:a]apad,atrim=duration=118.1,asetpts=PTS-STARTPTS[a0];'
        '[a0][2:a]concat=n=2:v=0:a=1[a]',
        '-map', '[v]', '-map', '[a]', '-t', '138.1', '-r', '30',
        '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(output)], check=True)
    srt = DOC / 'embodiweave-demo-v5-with-v4-narrated.srt'
    output.with_suffix('.srt').write_bytes(srt.read_bytes())
    metadata = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                                   '-show_format', '-of', 'json', str(output)]))
    video = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
    assert video['nb_frames'] == '4143' and (video['width'], video['height']) == (1920, 1080)
    for path, digest in sources.items():
        assert sha(ROOT / path) == digest
    write(E / 'assembly.json', dict(source_sha256=sources, duration_seconds=138.1,
        output=str(output.relative_to(ROOT)), output_sha256=sha(output), bytes=output.stat().st_size,
        captions=str(srt.relative_to(ROOT)), captions_sha256=sha(srt),
        voice_model=MODEL, captions_model='nova-3',
        appendix_narration_seconds=sum(r['seconds']/r['tempo'] for r in receipts),
        editorial='Original v5 retained; four new Deepgram clips narrate the existing title and v4 evidence appendix. '
                  'No new simulation or training; original silent combined film also preserved.'))
    print(str(output))


def balance_audio():
    media = ROOT / 'web/media'
    source = media / 'embodiweave-demo-v5-with-v4-narrated.mp4'
    mix = ROOT.parents[1] / 'outputs/film-v5-v4-narrated/appendix.wav'
    output = media / 'embodiweave-demo-v5-with-v4-final.mp4'
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-i', str(source), '-i', str(mix), '-filter_complex',
        '[0:a]atrim=duration=118.1,asetpts=PTS-STARTPTS[a0];'
        '[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.89,aresample=48000[a1];'
        '[a0][a1]concat=n=2:v=0:a=1[a]', '-map', '0:v', '-map', '[a]',
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-t', '138.1',
        '-movflags', '+faststart', str(output)], check=True)
    write(E / 'balanced-assembly.json', dict(source=str(source.relative_to(ROOT)),
        source_sha256=sha(source), output=str(output.relative_to(ROOT)),
        output_sha256=sha(output), duration_seconds=138.1,
        appendix_audio='loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.89,aresample=48000',
        video='Stream copy of the narrated export; timing and pictures unchanged.',
        prior_receipts='All earlier media and receipts retained unchanged.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['voice', 'assemble', 'balance'])
    args = parser.parse_args()
    {'voice': narrate, 'assemble': assemble, 'balance': balance_audio}[args.action]()
