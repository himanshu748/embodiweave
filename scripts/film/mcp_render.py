"""Render the recorded MCP run; never invokes an agent, trainer or evaluation.

Browser shots are actual public-page captures. Robot poses are saved validation
states; MuJoCo footage is the immutable v3 transfer replay. Only editorial
graphics, camera framing and evidence highlights are animated here.
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import numpy as np
from PIL import Image, ImageDraw

from scripts.film.mcp_update import ROOT, E, DOC, OUT, SOURCE, sha, write, prepare
from scripts.film.render import background, chrome, text, font, W, H, PAPER, INK, ORANGE, MUTED, LINE
from scripts.film import voice
from ew.contract import get_contract

FPS = 30


def run(*args):
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', *map(str, args)], check=True)


def load(path):
    return json.loads(path.read_text())


def lines(d, xy, value, width=70, size=28, fill=INK, mono=False, leading=None):
    for j, line in enumerate(textwrap.wrap(str(value), width, break_long_words=True)):
        text(d, (xy[0], xy[1]+j*(leading or size+12)), line, size, fill, mono)


def card(d, box, title, value, detail='', accent=False):
    d.rounded_rectangle(box, radius=16, fill='#faf9f4', outline=ORANGE if accent else LINE, width=3)
    x, y = box[:2]
    text(d, (x+24, y+20), title, 24, ORANGE if accent else MUTED, True)
    lines(d, (x+24, y+65), value, width=max(15, (box[2]-x-48)//18), size=32)
    if detail:
        lines(d, (x+24, box[3]-80), detail, width=max(15, (box[2]-x-48)//14), size=23, fill=MUTED)


class Clip:
    def __init__(self, path):
        self.process = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(path),
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def read(self, size):
        raw = self.process.stdout.read(size[0]*size[1]*3)
        if not raw:
            raise RuntimeError('Source video ended before its declared edit')
        return Image.frombytes('RGB', size, raw)

    def close(self):
        self.process.stdout.close()
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait()


def browser_clips():
    """Use the browser-video-recording skill renderer for captured UI motion."""
    capture = E/'browser'
    capture.mkdir(exist_ok=True)
    for p in (OUT/'browser').glob('*.png'):
        shutil.copyfile(p, capture/p.name)
    timelines = load(E/'timeline.json')['scenes']
    configs = [
        {'shots': {'overview': '01-tools.png', 'tools': '02-tools.png'},
         'scene_starts': [[0, 'overview'], [2.5, 'tools', 'scroll']],
         'cursor_keys': [[0, 700, 450], [2, 825, 550], [3.1, 800, 170], [5, 825, 330], [8, 830, 520]],
         'click_times': []},
        {'shots': {'launch': '03-launch.png', 'allowed': '04-guardrail.png'},
         'scene_starts': [[0, 'launch'], [3.6, 'allowed']],
         'cursor_keys': [[0, 860, 450], [2.3, 860, 585], [4.2, 850, 515], [6.8, 850, 580]],
         'click_times': []},
    ]
    renderer = Path(os.environ.get('EW_BROWSER_RENDERER',
        str(Path.home()/'.codex/skills/browser-video-recording/scripts/render_browser_demo.py')))
    for i, config in enumerate(configs, 1):
        config.update(duration=timelines[i-1]['duration'], fps=30, output_size=[1280, 720],
            source_size=[1280, 720], camera_keys=[[0, 640, 360, 1]], cursor_scale=1.2,
            cursor_asset=str((capture/'pointer.png').relative_to(ROOT)), cursor_hotspot=[11, 2], crf=20, preset='fast',
            output=os.path.relpath(OUT/f'browser-{i:02}.mp4', ROOT))
        config['shots'] = {key: str((capture/value).relative_to(ROOT)) for key, value in config['shots'].items()}
        write(E/f'browser-edit-{i:02}.json', config)
        subprocess.run([sys.executable, str(renderer), '--config',
                        str(E/f'browser-edit-{i:02}.json')], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Film:
    def __init__(self):
        self.summary = load(SOURCE/'summary.json')
        self.decision = load(SOURCE/'decision.json')
        self.graph = load(E/'graph-records.json')
        self.nodes = {n[0]: (n[1][0], n[2]) for n in self.graph['nodes']}
        self.replay = load(E/'policy-replay.json')
        self.episode = next(e for e in self.replay['episodes'] if e['seed'] == 1300030)
        assert self.episode['trace'][-1]['outcome'] == 'collision'
        self.contract_id = next(k for k, (label, _) in self.nodes.items() if label == 'Contract')
        self.contract = self.nodes[self.contract_id][1]
        self.old = load(ROOT/'evidence/robustness-v2/summary.json')
        s = self.summary
        self.positions = {
            s['chosen_origin']['policy_id']: (95, 210), s['decision_id']: (675, 205),
            s['run_id']: (1255, 210), s['policy_id']: (1255, 480),
            s['trial_id']: (675, 480), self.contract_id: (95, 600),
            s['evaluations'][0]['id']: (1255, 745),
            s['evaluations'][0]['id']+':collision:mover': (675, 765),
        }
        self.aliases = {s['chosen_origin']['policy_id']: 'Chosen origin', s['policy_id']: 'New checkpoint',
                        s['evaluations'][0]['id']: 'Target validation',
                        s['evaluations'][0]['id']+':collision:mover': 'Pedestrian collisions'}

    def graph_view(self, image, t):
        d = ImageDraw.Draw(image)
        # Animation highlights database labels at their actual narrated word times.
        words = load(E/'transcript-03.json')['results']['channels'][0]['alternatives'][0]['words']
        mapping = {'policies': 'Policy', 'runs': 'Run', 'trials': 'Trial',
                   'evaluations': 'Evaluation', 'failures': 'Failure', 'decisions': 'Decision'}
        active = 'Policy'
        for w in words:
            if w['start'] <= t and w['word'] in mapping:
                active = mapping[w['word']]
        for a, relation, b in self.graph['edges']:
            if a not in self.positions or b not in self.positions:
                continue
            x1, y1 = self.positions[a]; x2, y2 = self.positions[b]
            a0, b0 = np.array([x1+180., y1+60.]), np.array([x2+180., y2+60.])
            diff = b0-a0; length = np.linalg.norm(diff)
            if not length:
                continue
            direction = diff/length; normal = np.array([-direction[1], direction[0]])
            end = b0-direction*90
            d.line([tuple(a0), tuple(end)], fill='#aab4b1', width=3)
            d.polygon([tuple(end), tuple(end-direction*15+normal*7), tuple(end-direction*15-normal*7)], fill=MUTED)
            if relation in ('SELECTED', 'LAUNCHED', 'PRODUCED', 'ASSESSED', 'OBSERVED_IN'):
                mid = (a0+b0)/2
                text(d, (mid[0]-90, mid[1]-28), relation, 19, MUTED, True)
        for identifier, (x, y) in self.positions.items():
            kind, props = self.nodes[identifier]
            d.rounded_rectangle((x, y, x+360, y+120), 14, fill=INK if kind == active else '#faf9f4',
                                outline=ORANGE if kind == active else LINE, width=3)
            fill = PAPER if kind == active else INK
            text(d, (x+16, y+12), kind.upper(), 21, ORANGE, True)
            text(d, (x+16, y+45), self.aliases.get(identifier, kind+' record'), 27, fill)
            label = identifier if len(identifier) <= 32 else identifier[:13]+'…'+identifier[-12:]
            text(d, (x+16, y+83), label, 17, fill, True)
        text(d, (80, 925), 'Actual FalkorDB nodes + edges / GRAPH.RO_QUERY / revision 10 / editorial layout', 23, MUTED, True)

    def arena(self, image, t):
        d = ImageDraw.Draw(image)
        ep = self.episode
        trace = ep['trace']
        frame = trace[min(len(trace)-1, int(t*10))]
        x0, y0, scale = 90, 195, 72
        xy = lambda p: (x0+p[0]*scale, y0+(10-p[1])*scale)
        d.rectangle((x0, y0, x0+720, y0+720), fill='#e4e6dd', outline=INK, width=5)
        for i in range(1, 10):
            d.line((x0+i*scale, y0, x0+i*scale, y0+720), fill='#cfd5ca')
            d.line((x0, y0+i*scale, x0+720, y0+i*scale), fill='#cfd5ca')
        for x, y, r in ep['layout']['statics']:
            cx, cy = xy((x, y)); r *= scale
            d.ellipse((cx-r, cy-r, cx+r, cy+r), fill='#59655f', outline=INK, width=3)
        gx, gy = xy(ep['layout']['goal'])
        d.ellipse((gx-24, gy-24, gx+24, gy+24), outline=ORANGE, width=5)
        for mover in frame['movers']:
            cx, cy = xy(mover)
            d.ellipse((cx-36, cy-36, cx+36, cy+36), fill='#e8ae84', outline=ORANGE, width=3)
        points = [xy(f['robot']) for f in trace[:frame['t']+1]]
        if len(points)>1:
            d.line(points, fill=ORANGE, width=4)
        rx, ry = xy(frame['robot']); theta = frame['robot'][2]
        radius = get_contract(self.contract_id).robot.radius_m*scale
        d.ellipse((rx-radius, ry-radius, rx+radius, ry+radius), fill=INK, outline=PAPER, width=3)
        d.line((rx, ry, rx+31*math.cos(theta), ry-31*math.sin(theta)), fill=ORANGE, width=6)
        text(d, (880, 215), 'SAVED POLICY / REAL 2D SIMULATOR', 25, ORANGE, True)
        text(d, (880, 275), '61,440 PPO steps', 55)
        text(d, (880, 350), '60,000 requested · seed 29', 29, MUTED, True)
        text(d, (880, 430), 'Then: 180 validation episodes', 37)
        lines(d, (880, 490), 'Original 2D task. This public run did not train in MuJoCo.', 42, 29)
        text(d, (880, 605), f'Saved target replay / seed {ep["seed"]}', 27, ORANGE, True)
        text(d, (880, 655), f'Step {frame["t"]} / {len(trace)-1}', 33, INK, True)
        text(d, (880, 705), 'COLLISION' if frame['outcome'] else 'RUNNING', 49, ORANGE)
        lines(d, (880, 790), 'One of the three target collisions. All 60 target episodes appear in the next table.', 49, 28, MUTED)
        text(d, (90, 932), 'Saved poses at 10 Hz / no interpolated robot motion / post-training replay', 23, MUTED, True)

    def frame(self, scene, t, source=None):
        image = background(); d = ImageDraw.Draw(image)
        i, s = scene['id'], self.summary
        if i in (1, 2):
            # Crop the real evidence panel; don't recreate the application's UI.
            panel = source.crop((570, 65, 1205, 715)).resize((674, 690), Image.Resampling.LANCZOS)
            image.paste(panel, (1165, 220)); d = ImageDraw.Draw(image)
            text(d, (80, 185), 'RECORDED PUBLIC RUN / LLM → MCP', 25, ORANGE, True)
            if i == 1:
                text(d, (80, 240), 'The model chose', 48)
                text(d, (80, 298), 'what to ask.', 48)
                names = s['mcp_calls'][:3]
                for j, name in enumerate(names):
                    y = 410+j*130
                    focus = j == min(2, int(max(0, t-2)/2.5))
                    d.rounded_rectangle((80, y, 1065, y+92), 12, fill=INK if focus else '#faf9f4', outline=LINE, width=2)
                    text(d, (105, y+27), f'{j+1:02}  {name}', 34, PAPER if focus else INK, True)
                text(d, (80, 844), 'GPT-4.1 Mini / 3 model turns / 4 tool calls', 26, INK, True)
            else:
                text(d, (80, 244), '04  start_training', 48, INK, True)
                card(d, (80, 340, 1065, 515), 'MODEL-SELECTED ORIGIN', s['chosen_origin']['policy_id'], accent=True)
                card(d, (80, 545, 1065, 760), 'ACTUAL TOOL RESULT', 'guardrail: allowed', '60,000 steps requested · seed 29 · queued')
                text(d, (80, 820), s['decision_id'], 27, ORANGE, True)
                text(d, (80, 865), 'Decision saved before the worker started.', 30)
            text(d, (80, 929), 'Completed run evidence replay / waiting time removed / no new training for the film', 23, MUTED, True)
        elif i == 3:
            self.graph_view(image, t)
        elif i == 4:
            text(d, (80, 183), 'ACTUAL CYPHER / GRAPH.RO_QUERY', 25, ORANGE, True)
            query = (SOURCE/'nearest-passing-ancestor.cypher').read_text().strip()
            y = 235
            for raw in query.splitlines():
                for line in textwrap.wrap(raw, 95, replace_whitespace=False):
                    text(d, (80, y), line, 20, INK, True); y += 29
            a = s['algorithm']
            text(d, (80, 600), 'ACTUAL PARAMETERS', 24, ORANGE, True)
            text(d, (80, 645), 'policy: robust-20261016140226-352fd7 / suite: val-target-v1', 23, INK, True)
            text(d, (80, 685), 'max_hops: 8 / min_success: 0.8 / max_collision: 0.1', 23, INK, True)
            text(d, (80, 758), 'RETURNED PATH', 24, ORANGE, True)
            text(d, (80, 800), 'robust-20261016140226-352fd7 → search-20261015185749-4a6581', 23, INK, True)
            text(d, (80, 842), f"evaluation: {a['evaluation_id']} / collisions: {a['collision_rate']:.0%}", 23, MUTED, True)
            card(d, (1290, 220, 1840, 535), 'RETURNED RECORD', f"{a['hops']} lineage hop", a['ancestor_id'], accent=True)
            lines(d, (1310, 585), 'Unweighted shortest path to a passing ancestor.', 28, 30)
            lines(d, (1310, 720), 'The agent also considered 17 eligible origins and chose a different checkpoint.', 30, 29, MUTED)
            text(d, (80, 925), 'Exact-artifact validation + compatible contract / this algorithm does not predict safety', 23, MUTED, True)
        elif i == 5:
            text(d, (80, 190), 'THE CHECKPOINT CARRIES ITS MEANING', 25, ORANGE, True)
            c = self.contract
            card(d, (80, 255, 900, 555), 'CONTRACT NODE', self.contract_id,
                 f"{c['obs_dim']} observations · {c['n_rays']} rays · {c['history']} frames · {c['dt_s']}s step")
            lines(d, (105, 595), c['action_map'], 52, 27, INK, True)
            lines(d, (105, 720), 'Normalization state travels with the saved weights.', 41, 31)
            for j, name in enumerate(['Compatible sensor / action contract', 'Exact artifact hash + complete evidence', 'Supported budget + available worker']):
                y = 260+j*155
                d.line((1020, y+30, 1060, y+30), fill=ORANGE, width=5)
                lines(d, (1090, y), name, 33, 32)
            card(d, (1015, 760, 1840, 914), 'THIS RECORDED RUN', 'ALLOWED — no veto occurred', accent=True)
        elif i == 6:
            text(d, (80, 187), 'PRE-ACTION AUDIT / RECORDED DECISION', 25, ORANGE, True)
            fields = [('Decision', self.decision['id']), ('Model', self.decision['model']),
                      ('Source', self.decision['mode']+' / MCP streamable HTTP'),
                      ('Chosen origin', self.decision['selected']),
                      ('Graph revision', str(self.decision['graph_revision'])),
                      ('Recorded before run', self.decision['recorded_at'])]
            for j, (name, value) in enumerate(fields):
                y=260+j*72; text(d, (80, y), name, 25, MUTED, True); text(d, (445, y), value, 29, INK, True)
            text(d, (80, 730), 'Cypher + parameters + candidates + returned records', 34)
            text(d, (80, 790), 'Stored before the training action.', 34, ORANGE)
            text(d, (80, 875), 'Graph unavailable → planning stops. No local evidence substitute.', 31)
        elif i == 7:
            self.arena(image, t)
        elif i == 8:
            text(d, (80, 185), 'SAVED CHECKPOINT / 180 VALIDATION EPISODES / PROMO-1', 25, ORANGE, True)
            columns = [(80, 'SUITE'), (430, 'GOALS / REQUIRED'), (990, 'COLLISIONS / LIMIT'), (1640, 'RESULT')]
            for x, label in columns:
                text(d, (x, 280), label, 25, MUTED, True)
            for j, (e, check) in enumerate(zip(s['evaluations'], s['gate']['checks'])):
                v=e['summary']; n=v['episodes']; y=365+j*115
                if j == min(3, int(t/2.1)):
                    d.rectangle((60, y-10, 1860, y+86), fill='#e5e5dc')
                for x, value in [(80, e['suite_id'].replace('val-', '').replace('-v1','').title()),
                    (430, f"{round(v['success_rate']*n)}/{n} ({v['success_rate']:.1%}) / ≥{check['min_success']:.0%}"),
                    (990, f"{round(v['collision_rate']*n)}/{n} ({v['collision_rate']:.1%}) / ≤{check['max_collision']:.0%}"), (1640, 'PASS')]:
                    text(d, (x, y), value, 31, ORANGE if x==1640 else INK, x!=80)
                d.line((80,y+85,1840,y+85), fill=LINE, width=2)
            text(d, (80, 866), '4 / 4 passed the fixed gate. The demo policy was not replaced.', 36, ORANGE)
            text(d, (80, 926), f"Artifact {s['artifact_hash'][:48]}…", 23, MUTED, True)
        elif i == 9:
            text(d, (80, 185), 'MATCHED VALIDATION / PARENT → NEW CHILD', 25, ORANGE, True)
            for j, (name, before, after, n) in enumerate([('Target', 2, 3, 60), ('Crossing', 0, 1, 40)]):
                y=270+j*255
                text(d, (80, y), name, 46)
                text(d, (80, y+65), f'{before}/{n} → {after}/{n}', 54, ORANGE, True)
                text(d, (80, y+135), 'collisions', 26, MUTED)
                for x, value, label, color in [(650,before,'Chosen parent',INK),(1210,after,'MCP child',ORANGE)]:
                    text(d, (x, y), label, 27, color, True)
                    d.rectangle((x,y+55,x+max(4,value*150),y+120),fill=color)
                    text(d, (x, y+140), str(value), 36, color, True)
            text(d, (80, 825), 'A gate pass does not establish an improvement.', 43)
            text(d, (80, 890), 'I kept the regression visible. No deployment changed.', 34, ORANGE)
        elif i == 10:
            text(d, (80, 190), 'SEPARATE STUDIES / EXISTING RESULTS PRESERVED', 25, ORANGE, True)
            card(d, (80, 280, 915, 735), 'EARLIER REHEARSAL / SEARCH-V1', '13 / 100 target collisions', '13% > 10% limit · held-out FAILED', accent=True)
            card(d, (1005, 280, 1840, 735), 'ROBUSTNESS-V2 / CURRENT DEMO', '8 / 100 target collisions', '8% ≤ 10% limit · fresh confirmation passed')
            text(d, (80, 810), 'Different frozen studies. Neither result is this MCP child.', 35)
            lines(d, (80, 875), 'No new held-out evaluation was opened or repeated for this edit.', 90, 28, MUTED)
        elif i == 11:
            # V3 is genuine MuJoCo joint-state playback, kept byte-for-byte as backup.
            # Cover its original title/caption bands with this edit's own framing.
            image=source; d=ImageDraw.Draw(image)
            d.rectangle((0, 158, W, 222), fill=PAPER)
            text(d, (34, 180), 'HISTORICAL / P-static-b', 24, INK, True)
            text(d, (994, 180), 'ROBUSTNESS-V2 / confirmed in 2D', 24, INK, True)
            d.rectangle((0, 877, W, 970), fill=PAPER)
            text(d, (80, 882), 'MUJOCO-V2 / same seed 5203012 / selected illustration / no retraining', 25, ORANGE, True)
            text(d, (80, 924), 'Target: 6/40 (15%) > 10% limit. Crossing: 4/40. This is not the MCP child.', 28)
        elif i == 12:
            text(d, (80, 200), 'EMBODIWEAVE', 94)
            text(d, (80, 338), 'Built on FalkorDB', 61, ORANGE)
            text(d, (80, 450), 'github.com/himanshu748/embodiweave', 37, INK, True)
            text(d, (80, 520), 'embodiweave.52.202.25.181.sslip.io', 37, INK, True)
            text(d, (80, 635), 'Narration: Deepgram Aura-2. Captions: Deepgram Nova-3.', 28)
            text(d, (80, 690), 'Music: “Cipher” / Kevin MacLeod / CC BY 3.0', 26, MUTED)
            text(d, (80, 802), 'Real policies. Recorded actions. Inspectable results.', 42)
            text(d, (80, 882), 'Script, source records and checksums: evidence/film-v4/', 25, MUTED, True)
        chrome(image, scene, t, scene['duration'], i)
        return image


def render(scene_ids):
    prepare(); film=Film(); timeline=load(E/'timeline.json'); caps=load(E/'captions.json')
    for s in timeline['scenes']:
        i=s['id']
        if i not in scene_ids:
            continue
        source = Clip(OUT/f'browser-{i:02}.mp4') if i in (1,2) else (
            Clip(OUT.parent/'film-v3/scene-11.mp4') if i == 11 else None)
        encoder=subprocess.Popen(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo',
            '-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','pipe:0','-an','-c:v','libx264',
            '-preset','fast','-crf','21','-pix_fmt','yuv420p',str(OUT/f'scene-{i:02}.mp4')],stdin=subprocess.PIPE)
        try:
            for index in range(round(s['duration']*30)):
                t=index/30
                image=film.frame(s,t,source.read((1280,720) if i in (1,2) else (1920,1080)) if source else None)
                d=ImageDraw.Draw(image)
                active=next((line for a,b,line in caps if a<=s['start']+t<b),None)
                if active:
                    wrapped=textwrap.wrap(active,76)
                    for j,line in enumerate(wrapped):
                        d.text((960,1016-(len(wrapped)-1)*39+j*39),line,font=font(36),fill='white',anchor='mt')
                encoder.stdin.write(image.tobytes())
                if index==round(s['duration']*15):
                    image.save(OUT/f'preview-{i:02}.png')
        finally:
            encoder.stdin.close()
            if source:
                source.close()
        assert encoder.wait()==0
        print('Rendered v4 scene',i,flush=True)


def assemble():
    data=load(E/'timeline.json');seconds=data['seconds']
    parts=[OUT/f"scene-{s['id']:02}.mp4" for s in data['scenes']]
    (OUT/'picture-list.txt').write_text(''.join(f"file '{p}'\n" for p in parts))
    # Normalize scene-boundary timestamps: stream-copy concat leaves fractional
    # frame durations in MP4, even though every source was rendered at 30 Hz.
    run('-f','concat','-safe','0','-i',OUT/'picture-list.txt','-r','30','-fps_mode','cfr',
        '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',OUT/'picture.mp4')
    voices=[]
    for s in data['scenes']:
        p=OUT/f"voice-{s['id']:02}.wav"
        run('-i',ROOT/s['audio'],'-af',f"apad,atrim=duration={s['duration']}",'-ar','48000','-c:a','pcm_s16le',p)
        voices.append(p)
    (OUT/'voices.txt').write_text(''.join(f"file '{p}'\n" for p in voices))
    run('-f','concat','-safe','0','-i',OUT/'voices.txt','-c:a','pcm_s16le',OUT/'narration.wav')
    music=ROOT.parent/'cipher.mp3'
    mix=f'[0:a]atrim=duration={seconds},asetpts=PTS-STARTPTS,loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.1258925,afade=t=in:st=0:d=1,afade=t=out:st={seconds-3}:d=3[m];[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[v];[m][v]amix=inputs=2:normalize=0,alimiter=limit=0.89[a]'
    run('-i',music,'-i',OUT/'narration.wav','-filter_complex',mix,'-map','[a]','-t',seconds,'-ar','48000',OUT/'mix.wav')
    master=OUT/'embodiweave-demo-v4.mp4'
    run('-i',OUT/'picture.mp4','-i',OUT/'mix.wav','-map','0:v','-map','1:a','-c:v','copy',
        '-c:a','aac','-b:a','128k','-t',seconds,'-movflags','+faststart',master)
    backup=OUT/'embodiweave-demo-v4-narration-free.mp4'
    run('-i',OUT/'picture.mp4','-i',music,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac',
        '-b:a','128k','-af',f'loudnorm=I=-20:TP=-1.5:LRA=11,afade=t=out:st={seconds-3}:d=3',
        '-t',seconds,'-movflags','+faststart',backup)
    site=OUT/'embodiweave-demo-v4-720p.mp4'
    run('-i',master,'-vf','scale=1280:720','-c:v','libx264','-preset','fast','-crf','23',
        '-c:a','aac','-b:a','96k','-movflags','+faststart',site)
    gif=OUT/'embodiweave-demo-v4.gif'
    run('-t',10,'-i',master,'-filter_complex','[0:v]fps=10,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=bayer',gif)
    assert master.stat().st_size < 50_000_000
    for p in (master,site,backup,gif):
        shutil.copyfile(p,ROOT/'web/media'/p.name)
    shutil.copyfile(DOC/'embodiweave-demo-v4.srt',ROOT/'web/media/embodiweave-demo-v4.srt')
    run('-ss','3','-i',master,'-frames:v','1',DOC/'thumbnail.png')
    with Image.open(DOC/'thumbnail.png') as p:
        p.resize((1280,720),Image.Resampling.LANCZOS).save(ROOT/'web/media/demo-v4-poster.webp',quality=88)
    receipt={'seconds':seconds,'fps':30,'width':1920,'height':1080,'narration_model':data['model'],
        'narration_seconds':sum(s['voice_seconds'] for s in data['scenes']),
        'training_launch_scene_start':data['scenes'][1]['start'],
        'launch_narration_ends':data['scenes'][1]['start']+data['scenes'][1]['voice_seconds'],
        'assets':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in (master,site,backup,gif)},
        'music':{'title':'Cipher','artist':'Kevin MacLeod','license':'CC BY 3.0','sha256':sha(music),
                 'url':'https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3','gain_below_normalized_voice_db':18},
        'physics_source':{'path':'outputs/film-v3/scene-11.mp4','sha256':sha(OUT.parent/'film-v3/scene-11.mp4')},
        'new_robot_motion':{'source':'evidence/film-v4/policy-replay.json','seed':1300030,'domain':'original 2D simulator',
                            'selection':'First target collision in the recorded suite; all aggregates shown. No interpolated poses.'},
        'editorial':'Browser captures replay completed evidence; waiting time removed. Graph layout, titles and highlights are editorial. No learning curve is invented.',
        'outcome':'Gate 4/4; target 2→3/60 and crossing 0→1/40 collisions relative to chosen parent. No default deployment change.'}
    write(E/'film-receipt.json',receipt)
    prepare()  # Fails if any v3 backup bytes changed.
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['browser','render','assemble'])
    parser.add_argument('--scenes',nargs='+',type=int,default=list(range(1,13)))
    args=parser.parse_args()
    {'browser':browser_clips,'render':lambda:render(args.scenes),'assemble':assemble}[args.action]()
