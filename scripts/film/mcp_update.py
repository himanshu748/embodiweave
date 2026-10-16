"""V4 edit of the recorded MCP action. Never trains or evaluates a checkpoint.

All new narration uses Deepgram Aura-2 and Nova-3. V3 is immutable backup media.
"""
import argparse
import difflib
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import wave
import zipfile

from scripts.film import voice

ROOT = Path(__file__).resolve().parents[2]
E = ROOT / 'evidence/film-v4'
DOC = ROOT / 'docs/demo/v4'
OUT = ROOT.parents[1] / 'outputs/film-v4'
SOURCE = ROOT / 'evidence/mcp-agent-v2'
MODEL = 'aura-2-thalia-en'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def prepare():
    for p in (E, DOC, OUT):
        p.mkdir(parents=True, exist_ok=True)
    summary = json.loads((SOURCE/'summary.json').read_text())
    decision = json.loads((SOURCE/'decision.json').read_text())
    agent = json.loads((SOURCE/'agent-receipt.json').read_text())
    assert agent['decision_source'] == 'llm_mcp'
    assert decision['mode'] == 'llm' and decision['guardrail']['verdict'] == 'allowed'
    assert decision['selected'] == summary['chosen_origin']['policy_id']
    assert len(agent['calls']) == 4 and summary['consumed_steps'] == 61440
    assert sum(e['summary']['episodes'] for e in summary['evaluations']) == 180
    # Spoken counts are a fixed edit of this exact source. Refuse a different run.
    assert [e['summary']['collision_rate'] for e in summary['evaluations']] == [.05, 0, .025, .025]
    assert summary['origin_count'] == 17 and summary['algorithm']['hops'] == 1
    snapshot = {str(p.relative_to(ROOT)): sha(p) for base in
                (ROOT/'docs/demo/v3', ROOT/'evidence/film-v3', ROOT/'web/media')
                for p in base.rglob('*') if p.is_file() and (base.name != 'media' or 'v3' in p.name)}
    if (E/'v3-backup-checksums.json').exists():
        assert json.loads((E/'v3-backup-checksums.json').read_text()) == snapshot, 'V3 backup changed'
    else:
        write(E/'v3-backup-checksums.json', snapshot)
    specs = [
        ('The agent chooses its tools', 'My agent reads Falkor-D-B through M-C-P. It chooses tools to diagnose a checkpoint, compare origins, and trace a passing ancestor.', 'mcp-read'),
        ('The agent launches training', 'It chooses a starting checkpoint and calls start training. The guardrail approves the evidence and budget before the worker starts.', 'mcp-launch'),
        ('FalkorDB connects the evidence', 'Falkor-D-B connects policies, training runs, trials, evaluations, failures and decisions. The links preserve what produced what.', 'graph'),
        ('A shortest path through real lineage', 'The shortest-path tool runs inside Falkor-D-B. It returned the nearest passing ancestor, one hop away. The agent considered it alongside seventeen eligible origins.', 'algorithm'),
        ('The guardrail can veto the agent', 'Contracts tie a checkpoint to sensor and action meanings. The guardrail vetoes incompatible origins, stale hashes, incomplete validation, or unsupported budgets.', 'contracts'),
        ('The Decision precedes the action', 'Before training, the Decision saves the model, tool calls, Cypher, parameters and returned records. If Falkor-D-B is unavailable, planning stops.', 'decision'),
        ('Real PPO, then saved-policy evaluation', 'The worker trained sixty-one thousand, four hundred forty P-P-O steps, then reloaded the checkpoint for one hundred eighty validation episodes.', 'training'),
        ('Four suites. The same fixed gate.', 'All four suites passed the unchanged gate. Target collisions were three in sixty. Open had zero; static and crossing had one each in forty.', 'gate'),
        ('Target and crossing regressed', 'But the parent had two target collisions and no crossing collisions. Both measures got worse. Passing the gate does not establish an improvement, so I kept the demo policy unchanged.', 'regression'),
        ('Earlier results remain frozen', 'The earlier failure stays visible: thirteen target collisions in one hundred held-out episodes. The separate confirmed checkpoint still has eight in one hundred.', 'history'),
        ('Separate MuJoCo transfer evidence', 'That confirmed two-dimensional checkpoint also collided six times in forty MuJoCo target episodes, without retraining. This is a separate transfer study.', 'physics'),
        ('Every result has its evidence', 'The graph and checksummed evidence make these results inspectable. EmbodiWeave. Built on Falkor-D-B.', 'close'),
    ]
    write(E/'scenes.json', [{'id': i+1, 'title': title, 'narration': narration, 'visual': visual}
                            for i, (title, narration, visual) in enumerate(specs)])
    with zipfile.ZipFile(SOURCE/'repro-v3.zip') as z:
        names = [n for n in z.namelist() if n.startswith('replays/')]
        assert len(names) == 1
        (E/'policy-replay.json').write_bytes(z.read(names[0]))
    write(E/'source-records.json', {'study': 'agent-mcp-v2', 'summary': summary,
        'decision_path': 'evidence/mcp-agent-v2/decision.json',
        'source_checksums': {str(p.relative_to(ROOT)): sha(p) for p in SOURCE.iterdir() if p.is_file()},
        'edit': 'Recorded evidence replay. No new model decision, training, validation or held-out evaluation.',
        'robot_motion': 'New child: saved 2D validation poses. Physics: unchanged v3 MuJoCo footage, separate checkpoint/study.',
        'training_progress': 'Only a final progress sample is retained. Do not fabricate a learning curve or intermediate progress values.'})


NUMBERS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
NUMBERS.update(dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10))))


def normalized_tokens(text):
    text = re.sub(r'falkor[ -]*d[ -]*b', 'falkordb', text.lower())
    text = re.sub(r'\bm[ -]*c[ -]*p\b', 'mcp', text)
    text = re.sub(r'\bp[ -]*p[ -]*o\b', 'ppo', text)
    words = re.findall(r'\d+(?:,\d{3})*|[a-z]+', text)
    result, i = [], 0
    while i < len(words):
        word = words[i]
        if word not in NUMBERS:
            result.append(word.replace(',', '')); i += 1; continue
        total = current = 0
        while i < len(words) and words[i] in {*NUMBERS, 'hundred', 'thousand'}:
            w = words[i]
            if w == 'hundred': current = max(1, current)*100
            elif w == 'thousand': total += max(1, current)*1000; current = 0
            else: current += NUMBERS[w]
            i += 1
        result.append(str(total+current))
    return result


def validate_transcript(script, transcript):
    expected, actual = normalized_tokens(script), normalized_tokens(transcript)
    if [t for t in expected if t.isdigit()] != [t for t in actual if t.isdigit()]:
        raise ValueError('Spoken/transcribed numbers differ; resynthesize before rendering')
    ratio = difflib.SequenceMatcher(None, expected, actual).ratio()
    if ratio < .9:
        raise ValueError(f'Transcript differs from script ({ratio:.3f}); review before rendering')
    for term in ('falkordb', 'mcp', 'ppo', 'cypher'):
        if term in expected and term not in actual:
            raise ValueError(f'Pronunciation mismatch for {term}')
    return ratio


def narrate():
    prepare()
    scenes = json.loads((E/'scenes.json').read_text())
    previous = json.loads((E/'voice-receipts.json').read_text()) if (E/'voice-receipts.json').exists() else []
    originals = json.loads((ROOT/'evidence/film/voice-receipts.json').read_text())
    voice.KEYTERMS = [*voice.KEYTERMS, 'MCP']
    receipts, captions, timeline, cursor = [], [], [], 0.
    for scene in scenes:
        i, script = scene['id'], scene['narration']
        assert 0 < len(script) <= 2000
        text_hash = hashlib.sha256(script.encode()).hexdigest()
        prior = next((r for r in previous if r['scene'] == i and r['text_sha256'] == text_hash), None)
        reuse = next((r for r in originals if r['text_sha256'] == text_hash and r['model'] == MODEL), None)
        audio = DOC/f'voice/{i:02}.wav'
        audio.parent.mkdir(parents=True, exist_ok=True)
        if prior and audio.exists() and sha(audio) == prior.get('audio_sha256'):
            receipt = dict(prior)
        elif reuse:
            original = ROOT/f"docs/demo/voice/{reuse['scene']:02}.wav"
            assert sha(original) == reuse['audio_sha256']
            audio.write_bytes(original.read_bytes())
            receipt = {**reuse, 'scene': i, 'reused_from': 'evidence/film/voice-receipts.json'}
            (E/f'transcript-{i:02}.json').write_bytes((ROOT/f"evidence/film/transcript-{reuse['scene']:02}.json").read_bytes())
        else:
            raw, rid = voice.request('speak?model='+MODEL+'&encoding=linear16&sample_rate=48000&container=wav',
                                     json.dumps({'text': script}).encode(), 'application/json')
            audio.write_bytes(voice.pcm_wav(raw))
            receipt = {'scene': i, 'model': MODEL, 'dg_request_id': rid, 'characters': len(script),
                       'text_sha256': text_hash, 'audio_sha256': sha(audio)}
        checkpoint = [r for r in previous if r['scene'] != i] + receipts + [receipt]
        write(E/'voice-receipts.json', list({r['scene']: r for r in checkpoint}.values()))
        if not (E/f'transcript-{i:02}.json').exists() or not receipt.get('stt_request_id'):
            stt, stt_id = voice.transcribe(audio.read_bytes())
            write(E/f'transcript-{i:02}.json', stt)
            receipt.update(stt_request_id=stt_id, stt_model='nova-3')
            checkpoint[-1] = receipt
            write(E/'voice-receipts.json', list({r['scene']: r for r in checkpoint}.values()))
        stt = json.loads((E/f'transcript-{i:02}.json').read_text())
        alt = stt['results']['channels'][0]['alternatives'][0]
        ratio = validate_transcript(script, alt['transcript'])
        with wave.open(str(audio)) as wav:
            assert wav.getframerate() == 48000 and wav.getsampwidth() == 2
            seconds = wav.getnframes()/wav.getframerate()
        receipt.update(seconds=seconds, transcript=alt['transcript'], transcript_match_ratio=ratio,
                       audio=str(audio.relative_to(ROOT)))
        receipts.append(receipt)
        write(E/'voice-receipts.json', receipts)
        length = math.ceil((seconds + (.7 if i in (9, 12) else .35))*30)/30
        timeline.append({**scene, 'start': cursor, 'duration': length, 'voice_seconds': seconds,
                         'audio': str(audio.relative_to(ROOT))})
        words = [dict(w) for w in alt['words']]
        receipt['caption_corrections'] = []
        for j, word in enumerate(words):
            # Nova-3 heard the short spoken "in" as "and"; keep raw STT intact
            # and retain its timing. The script and measured 3/60 are unchanged.
            if (i == 8 and word['word'] == 'and' and j > 0
                    and words[j-1]['word'] == 'three' and words[j+1]['word'] == 'sixty'):
                receipt['caption_corrections'].append({'start': word['start'], 'end': word['end'],
                    'raw': word['word'], 'caption': 'in', 'reason': 'Match spoken script and recorded 3/60 count'})
                word['punctuated_word'] = 'in'
        for j in range(0, len(words), 7):
            group = words[j:j+7]
            captions.append([cursor+group[0]['start'], cursor+group[-1]['end'],
                             ' '.join(w.get('punctuated_word', w['word']) for w in group)])
        cursor += length
        write(E/'voice-receipts.json', receipts)
        print(json.dumps({'scene': i, 'voice_seconds': round(seconds, 3), 'transcript_match': ratio}), flush=True)
    assert timeline[1]['start']+timeline[1]['duration'] <= 20, 'Launch narration must finish in first 20 seconds'
    assert 90 <= cursor <= 120, f'Revise wording; {cursor:.2f}s is outside the 90–120 second brief'
    write(E/'timeline.json', {'model': MODEL, 'seconds': cursor, 'scenes': timeline})
    write(E/'captions.json', captions)
    (DOC/'embodiweave-demo-v4.srt').write_text('\n\n'.join(
        f'{i+1}\n{voice.stamp(a)} --> {voice.stamp(b)}\n{text}' for i, (a, b, text) in enumerate(captions))+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'voice'])
    args = parser.parse_args()
    {'prepare': prepare, 'voice': narrate}[args.action]()
