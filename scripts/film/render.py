"""Evidence-driven 1080p film. Graphics are editorial; robot frames are MuJoCo.

python -m scripts.film.render --backup   # labelled narration-free 120s cut
python -m scripts.film.render            # scene lengths from Deepgram WAVs
Frames stream to ffmpeg. No raw image sequence or fabricated robot motion.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import subprocess
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from scripts.film.physics import Replay
from ew.criteria import PROMOTION

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parents[1] / "outputs/film-v2"
E = ROOT / "evidence/film"
FPS, W, H = 30, 1920, 1080
PAPER, INK, MUTED, ORANGE, LINE = "#f2f0e8", "#252d30", "#657074", "#e85d19", "#d7d9d1"
FONTS = ROOT / "docs/demo/assets"


@lru_cache(maxsize=100)
def font(size, mono=False):
    return ImageFont.truetype(str(FONTS / ("IBMPlexMono-Regular.ttf" if mono else "SpaceGrotesk.ttf")), size)


def text(draw, xy, value, size=32, fill=INK, mono=False):
    draw.text(xy, str(value), font=font(size, mono), fill=fill, spacing=12)


def wrap(draw, xy, value, width=60, size=32, fill=INK, mono=False):
    lines = textwrap.wrap(value, width=width)
    for i, line in enumerate(lines): text(draw, (xy[0], xy[1]+i*(size+14)), line, size, fill, mono)


def background():
    image = Image.new("RGB", (W,H), PAPER)
    d = ImageDraw.Draw(image)
    for x in range(0,W,36): d.line((x,0,x,H), fill="#e5e5dc")
    for y in range(0,H,36): d.line((0,y,W,y), fill="#e5e5dc")
    return image


def gate_table_rows():
    """Bind film labels to recorded validation checks and the frozen criteria."""
    rule=PROMOTION['promo-1'];criteria=[rule['target'],*rule['retained']]
    percent=lambda value:f'{100*value:.2f}'.rstrip('0').rstrip('.')
    rows=[('CANDIDATE','TARGET','OPEN','STATIC','CROSSING','GATE'),
          ('Collision limit',*[f"≤{percent(c['max_collision'])}%" for c in criteria],'All four')]
    promotions=[json.loads(p.read_text()) for p in (ROOT/'artifacts/records/promotion').glob('*.json')]
    for label,policy in [('Original scratch','scratch~a7ee2c-s7'),('Longer training','search-20261015185536-6720c9'),
                         ('Rehearsal lineage','search-20261015185749-4a6581')]:
        candidates=[r for r in promotions if r.get('policy_id')==policy and r.get('rule')=='promo-1']
        record=sorted(candidates,key=lambda r:r['id'])[-1]
        checks={c['suite_id']:c for c in record['checks']}
        values=[f"{percent(checks[c['suite_id']]['success_rate'])} / {percent(checks[c['suite_id']]['collision_rate'])}" for c in criteria]
        rows.append((label,*values,f"{sum(c['pass'] for c in checks.values())} / 4"))
    return rows,criteria


def chrome(image, scene, elapsed, duration, index, total=12):
    d = ImageDraw.Draw(image)
    d.rectangle((0,0,W,158), fill=PAPER)
    d.rectangle((72,42,84,60), fill=ORANGE)
    text(d, (100,32), "EMBODIWEAVE / FIELD NOTES", 25, mono=True)
    text(d, (W-310,32), f"{index:02} / {total:02}  •  FALKORDB", 22, mono=True)
    # Ease titles into place; this never moves simulator objects.
    entrance = (1-min(1,elapsed/.45))**3
    text(d, (72,77+int(16*entrance)), scene["title"], 55)
    d.line((72,151,W-72,151), fill=LINE, width=2)
    d.rectangle((0,H-110,W,H), fill=INK)
    text(d,(72,H-103), "REAL CHECKPOINTS  /  FIXED GATE  /  REPRODUCIBLE EVIDENCE",18,"#a9b2af",True)
    d.rectangle((0,H-4,int(W*min(1,elapsed/duration)),H),fill=ORANGE)


class Film:
    def __init__(self):
        self.pair = json.loads((E/"filmed-pair.json").read_text())
        family = "static_crossing" if "static_crossing" in self.pair["suite"] else "crossing"
        self.wide = Replay(self.pair["deployed"],family)
        self.left = Replay(self.pair["deployed"],family,width=936,height=650)
        self.right = Replay(self.pair["rehearsal"],family,width=936,height=650)
        self.graph = json.loads((E/"graph-records.json").read_text())
        self.queries = json.loads((E/"queries.json").read_text())
        self.learning = json.loads((E/"learning-progress.json").read_text())
        self.transfer = json.loads((ROOT/"evidence/mujoco-v1/summary.json").read_text())
        self.positions = {
            'scratch~10715f-s7':(90,270),'search-20261015185536-6720c9':(700,270),'search-20261015185749-4a6581':(1310,270),
            'deci-20261015185536-da13c7':(390,180),'deci-20261015185749-420707':(1000,180),
            'run-20261015185536-140d3e':(390,440),'run-20261015185749-177cb3':(1000,440),
            'tria-20261015185709-8932b2':(390,570),'tria-20261015185835-ce926e':(1000,570),
            'ew-contract-1:2f013b6f4849':(90,570),
        }
        # Show a readable subgraph, retaining only nodes and edges actually returned.
        for identifier,labels,props in self.graph['nodes']:
            if labels[0]=='Evaluation' and props.get('artifact_hash') in [
                'a08219d163fdb404bf481f544ceb158c63e33e49baf75685e5e7aae07b87941b',
                'b7e2fcc958695920db1970a4abdb40c65788a76f35e756bf6332729a8e3ba565']:
                x=700 if props['artifact_hash'].startswith('a082') else 1310
                self.positions[identifier]=(x,700)
                failure=identifier+':collision:mover'
                if any(n[0]==failure for n in self.graph['nodes']):self.positions[failure]=(x,815)

    def graph_view(self,image,elapsed,highlight=None):
        d = ImageDraw.Draw(image)
        shown = set(self.positions)
        for a,relationship,b in self.graph["edges"]:
            if a not in shown or b not in shown: continue
            x1,y1=self.positions[a];x2,y2=self.positions[b]
            p1=np.array([x1+140,y1+35]);p2=np.array([x2+140,y2+35])
            direction=p2-p1;length=np.linalg.norm(direction)
            if length:
                direction=direction/length;normal=np.array([-direction[1],direction[0]])
                end=p2-direction*52
                d.line((*p1,*end),fill="#b1b8b3",width=2)
                d.polygon([tuple(end),tuple(end-direction*11+normal*5),tuple(end-direction*11-normal*5)],fill=MUTED)
                midpoint=(p1+end)/2
                # Label vertical evidence edges; long diagonal joins remain contextual.
                if abs(x1-x2)<30:
                    text(d,(midpoint[0]+10,midpoint[1]-12),relationship,14,MUTED,True)
        kind_order=["Policy","Run","Trial","Evaluation","Failure","Decision"]
        active = highlight or kind_order[min(5,int(elapsed/1.2))]
        timings=E/'transcript-03.json'
        if not highlight and timings.exists():
            words=json.loads(timings.read_text())['results']['channels'][0]['alternatives'][0]['words']
            names={'policies':'Policy','runs':'Run','trials':'Trial','evaluations':'Evaluation','failures':'Failure','decisions':'Decision'}
            for word in words:
                if word['start']<=elapsed and word['word'].lower() in names:active=names[word['word'].lower()]
        for identifier,labels,properties in self.graph["nodes"]:
            if identifier not in shown:continue
            x,y=self.positions[identifier];kind=labels[0]
            emph=kind==active
            d.rounded_rectangle((x,y,x+280,y+76),radius=6,fill=PAPER,outline=ORANGE if emph else MUTED,width=3 if emph else 1)
            text(d,(x+12,y+8),kind.upper(),17,ORANGE if emph else MUTED,True)
            short=identifier.replace("20261015","")
            aliases={'scratch~10715f-s7':'ROOT CHECKPOINT','search-20261015185536-6720c9':'LONGER TRAINING','search-20261015185749-4a6581':'REHEARSAL LINEAGE'}
            if identifier in aliases:
                text(d,(x+12,y+32),aliases[identifier],21,INK)
                text(d,(x+12,y+58),short,13,MUTED,True)
            else:text(d,(x+12,y+37),short if len(short)<27 else short[:23]+"…",17,INK,True)
        text(d,(72,885),f"Real FalkorDB records • graph revision {self.graph['revision']} • recorded history, editorial layout",22,MUTED,True)

    def query_view(self,image,name,elapsed):
        d=ImageDraw.Draw(image);q=self.queries[name]
        cypher=q["cypher"]
        lines=[]
        for line in cypher.splitlines(): lines.extend(textwrap.wrap(line,width=125,replace_whitespace=False) or [""])
        d.rounded_rectangle((72,190,1848,600),radius=8,fill=INK)
        text(d,(100,209),"GRAPH.RO_QUERY  /  EXACT CYPHER",22,"#ffb080",True)
        for i,line in enumerate(lines): text(d,(100,253+i*29),line,21,"#f2f0e8",True)
        text(d,(90,627),f"RETURNED RECORDS  •  {len(q['rows'])} rows  •  {q['ms']} ms",23,ORANGE,True)
        if name=="diagnosis":
            rows=q["rows"]
            for i,row in enumerate(rows):
                text(d,(90,678+i*45),f"{row[0]:<20}  success {100*row[2]:5.1f}%   collisions {100*row[3]:5.1f}%",28,INK,True)
            text(d,(90,878),"Matched artifact: a08219d163fd…  /  Open success 82.5% < required 90%",24,ORANGE,True)
        elif name=="lineage":
            unique={row[0]:dict(zip(q['header'],row)) for row in q['rows']}
            for i,row in enumerate(unique.values()):
                y=680+i*90
                text(d,(90,y),f"{row['origin']} → {row['intervention']} → {row['candidate']}",24,INK,True)
                text(d,(90,y+38),f"{row['decision']}  /  validation gate: {row['verdict'].upper()}",24,ORANGE,True)
            text(d,(90,878),"Full parameters and all eight returned evidence rows: evidence/film/queries.json",23,MUTED,True)
        else:
            for i,row in enumerate(q["rows"][:4]):
                value="  |  ".join(str(x) for x in row[:5])
                text(d,(90,680+i*42),value[:100],23,INK,True)
            text(d,(90,878),"Full parameters and returned records: evidence/film/queries.json",23,MUTED,True)

    def learning_view(self,image,elapsed,duration):
        d=ImageDraw.Draw(image)
        text(d,(100,198),"RECORDED PPO PROGRESS / recent training success",25,MUTED,True)
        x0,y0,x1,y1=160,785,1580,300
        for value in [.7,.8,.9,1.]:
            y=y0-(value-.65)/.35*(y0-y1)
            d.line((x0,y,x1,y),fill=LINE,width=2);text(d,(85,y-15),f"{value:.0%}",22,MUTED,True)
        for k,attempt in enumerate(self.learning):
            color=ORANGE if k else INK
            points=[]
            for sample in attempt["samples"]:
                x=x0+sample["steps"]/300000*(x1-x0)
                y=y0-(sample["train_success_recent"]-.65)/.35*(y0-y1)
                if sample["steps"]/300000 <= min(1,elapsed/(duration*.65)):
                    points.append((x,y));d.ellipse((x-8,y-8,x+8,y+8),fill=color)
                    text(d,(x-35,y-39),f"{sample['train_success_recent']:.1%}",21,color,True)
            if len(points)>1:d.line(points,fill=color,width=5)
            text(d,(160,835+k*40),attempt["attempt"].upper()+"  /  301,056 actual additional steps",24,color,True)
        text(d,(650,790),"75k         150k         225k         300k",23,MUTED,True)
        text(d,(100,936),"At most 200 recent training episodes per point. These are not validation scores.",22,MUTED)

    def gate_view(self,image,elapsed):
        d=ImageDraw.Draw(image)
        text(d,(95,196),"180 validation episodes per candidate. Success / collision rate.",28,MUTED)
        cols=[95,640,900,1140,1380,1630]
        rows,criteria=gate_table_rows()
        for i,row in enumerate(rows):
            y=300+i*98
            if i==4:d.rectangle((72,y-12,1848,y+78),fill="#e3e8dc")
            for x,value in zip(cols,row):text(d,(x,y),value,25 if i!=1 else 28,ORANGE if i==1 else INK,i<2)
            d.line((72,y+82,1848,y+82),fill=LINE,width=1)
        floors=', '.join(f"{c['suite_id'].removeprefix('val-').removesuffix('-v1')} {c['min_success']:.0%}" for c in criteria)
        text(d,(95,850),f"Success floors: {floors}.",26,MUTED)
        text(d,(95,896),"Crossing collisions meet the 15% limit exactly. Gates were not relaxed.",26,ORANGE)

    def transfer_view(self,image,elapsed,duration):
        if elapsed > duration*.70:
            return self.transfer_table(image)
        # Paired physical states use the same simulation clock; freeze a terminal side.
        d=ImageDraw.Draw(image)
        end=max(self.pair['deployed']['seconds'],self.pair['rehearsal']['seconds'])
        playback=2.0 if end>duration*.70-1 else 1.0
        simtime=max(0,elapsed-1)*playback
        for x,replay,key,title in [(12,self.left,"deployed","DEPLOYED / P-static-b"),(972,self.right,"rehearsal","GRAPH-SELECTED / REHEARSAL")]:
            frame,clock=replay.frame(simtime,"tactical" if elapsed>duration*.65 else "wide",elapsed/duration)
            image.paste(Image.fromarray(frame),(x,220))
            d=ImageDraw.Draw(image)
            text(d,(x+24,175),title,25,INK,True)
            terminal=simtime>=self.pair[key]["seconds"]
            tag=self.pair[key]["outcome"].upper()+" / FROZEN" if terminal else "RUNNING"
            d.rectangle((x+20,818,x+912,866),fill=INK)
            text(d,(x+35,826),f"t={clock:05.2f}s  /  {tag}",24,PAPER,True)
        d=ImageDraw.Draw(image)
        text(d,(72,892),f"SAME SEED {self.pair['seed']}  •  {playback:g}x replay  •  2D-trained weights, no MuJoCo training",25,ORANGE,True)
        target={r['label']:r['summary'] for r in self.transfer['results'] if r['family']=='static_crossing'}
        text(d,(72,936),f"Fresh target suite (n=40): collisions deployed {target['deployed']['collision']}/40, original {target['original']['collision']}/40, rehearsal {target['rehearsal']['collision']}/40",24,INK)

    def transfer_table(self,image):
        d=ImageDraw.Draw(image)
        text(d,(90,200),"MUJOCO TRANSFER / COLLISIONS OUT OF 40 PER SUITE",27,ORANGE,True)
        labels=['open','static','crossing','static_crossing']
        columns=[90,620,1010,1420]
        for x,value in zip(columns,['Suite','Deployed','Original scratch','Rehearsal']):text(d,(x,310),value,32,INK)
        for i,family in enumerate(labels):
            y=410+i*100
            text(d,(90,y),family.replace('_',' + '),34,INK)
            for x,label in zip(columns[1:],['deployed','original','rehearsal']):
                row=next(r for r in self.transfer['results'] if r['label']==label and r['family']==family)
                count=row['summary']['collision']
                text(d,(x,y),f"{count}/40  ({count/40:.1%})",32,ORANGE if family=='crossing' else INK,True)
            d.line((90,y+70,1810,y+70),fill=LINE,width=2)
        text(d,(90,855),"Crossing remains weak: rehearsal collides in 8/40 episodes (20%).",30,ORANGE)
        text(d,(90,911),"Fresh seeds. Unchanged 2D-trained weights. No transfer result is a promotion decision.",26,MUTED)

    def frame(self,scene,elapsed,duration,backup=False):
        image=background();visual=scene["visual"];d=ImageDraw.Draw(image)
        if visual=="physics-hook":
            end=self.pair['deployed']['seconds']
            if elapsed<duration*.65:
                t=max(0,end-duration*.65)+elapsed
                view="wide" if elapsed<1.3 else "chase"
                replay=False
            else:
                t=end-(duration-elapsed)*.25
                view="chase";replay=True
            frame,clock=self.wide.frame(min(end,t),view,elapsed/duration)
            image=Image.fromarray(frame)
            d=ImageDraw.Draw(image)
            d.rectangle((72,735,1370,894),fill=INK)
            text(d,(96,750),"SIM-TO-SIM TRANSFER / MUJOCO",28,"#ffb080",True)
            text(d,(96,798),f"P-static-b   seed {self.pair['seed']}   t={clock:.2f}s",29,PAPER,True)
            text(d,(96,847),"REPLAY 0.25x / real recorded contact" if replay else "Unchanged checkpoint. Actual contact physics.",24,PAPER)
        elif visual=="problem":
            text(d,(90,235),"Retraining has two decisions.",67)
            for i,(number,title,desc) in enumerate([("01","Where do I start?","Reuse a compatible checkpoint with relevant evidence."),("02","Can I ship it?","Evaluate the saved artifact against the same fixed gate.")]):
                y=390+i*230;text(d,(95,y),number,45,ORANGE,True);text(d,(240,y),title,50)
                text(d,(240,y+85),desc,32,MUTED)
        elif visual=="graph":self.graph_view(image,elapsed)
        elif visual=="diagnose":self.query_view(image,"diagnosis",elapsed)
        elif visual=="contracts":
            text(d,(90,220),"51 floats ≠ the same sensor meanings",58)
            text(d,(90,330),"Policy → USES_CONTRACT → Contract",37,ORANGE,True)
            q=self.queries['contracts'];header=q['header']
            keep=[r for r in q['rows'] if r[0] in ['P-static-b','P-mirror','search-20261015185749-4a6581']]
            for i,row in enumerate(keep):
                y=460+i*110
                text(d,(90,y),str(row[0]),29,INK,True)
                ci=header.index('contract_id');mi=header.index('contract_match')
                text(d,(900,y),str(row[ci]),26,MUTED,True)
                text(d,(1570,y),"ELIGIBLE" if row[mi] else "EXCLUDED",27,ORANGE,True)
            text(d,(90,850),"Actual candidate_eligibility query records. Frozen per-checkpoint normalization.",25,MUTED)
        elif visual=="decision":
            if elapsed<duration*.5:self.graph_view(image,elapsed,highlight="Decision")
            else:self.query_view(image,"lineage",elapsed)
            d=ImageDraw.Draw(image);text(d,(90,920),"Recorded decision replay. The decision preceded its training run.",24,ORANGE)
        elif visual=="closed":
            text(d,(90,300),"FalkorDB unavailable",83)
            text(d,(90,440),"Planning stops.",100,ORANGE)
            text(d,(95,660),"Fail-closed behavior tested in CI. This is a title card, not a staged outage.",30,MUTED)
        elif visual=="learning":self.learning_view(image,elapsed,duration)
        elif visual=="gate":self.gate_view(image,elapsed)
        elif visual=="heldout":
            text(d,(90,215),"ONE HELD-OUT TARGET EVALUATION",28,ORANGE,True)
            text(d,(80,282),"13%",220)
            text(d,(570,355),"collisions",66)
            text(d,(90,570),"10% collision limit",52,ORANGE)
            text(d,(90,670),"86 goals. 13 collisions. 1 timeout. 100 episodes.",43)
            text(d,(90,770),"Not promoted to production. P-static-b stays deployed.",35)
            text(d,(90,870),"Held-out evidence is checksummed and kept outside the planning graph. No further tuning.",25,MUTED)
        elif visual=="transfer":self.transfer_view(image,elapsed,duration)
        elif visual=="close":
            text(d,(90,235),"EmbodiWeave",115)
            text(d,(95,400),"Built on FalkorDB",57,ORANGE)
            text(d,(95,535),"github.com/himanshu748/embodiweave",37,INK,True)
            text(d,(95,610),"embodiweave.52.202.25.181.sslip.io",37,INK,True)
            text(d,(95,738),"Narration: Deepgram Aura-2. Captions: Deepgram Nova-3." if not backup else "Narration-free backup. Deepgram narration is a separate required deliverable.",25,MUTED)
            text(d,(95,789),"Music: Cipher, Kevin MacLeod (incompetech.com). CC BY 3.0.",25,MUTED)
            text(d,(95,835),"Music edited and mixed. Film sources, seeds and checksums in the repository.",25,MUTED)
        chrome(image,scene,elapsed,duration,scene["id"])
        return image

    def close(self):
        for replay in (self.wide,self.left,self.right):replay.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backup',action='store_true');parser.add_argument('--preview',type=int);parser.add_argument('--scene',type=int)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    scenes=json.loads((E/'scenes.json').read_text())
    if args.backup:
        durations=[7,9,9,8,7,10,4,8,12,10,18,8]
        timeline=[];cursor=0
        for scene,duration in zip(scenes,durations):
            timeline.append({**scene,'start':cursor,'duration':duration});cursor+=duration
        (E/'backup-timeline.json').write_text(json.dumps({'seconds':cursor,'scenes':timeline},indent=2)+'\n')
    else:
        record=json.loads((E/'timeline.json').read_text());timeline=record['scenes'];cursor=record['seconds']
        if not 90<=cursor<=120:raise RuntimeError('Narration timing is outside 90–120 seconds. Edit script and regenerate affected scenes.')
    film=Film()
    if args.preview:
        scene=timeline[args.preview-1];frame=film.frame(scene,scene['duration']*.7,scene['duration'],args.backup)
        frame.save(OUT/f'preview-{args.preview:02}.png');film.close();return
    name='embodiweave-demo-v2-narration-free' if args.backup else 'picture-v2'
    if args.scene:
        timeline=[s for s in timeline if s['id']==args.scene]
        name=f'scene-{args.scene:02}'
    path=OUT/f'{name}.mp4'
    command=['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}',
             '-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','21','-maxrate','2600k',
             '-bufsize','5200k','-pix_fmt','yuv420p','-movflags','+faststart',str(path)]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        # Round each scene to a frame boundary and retain the actual edit duration.
        for scene in timeline:
            count=round(scene['duration']*FPS)
            for i in range(count):proc.stdin.write(film.frame(scene,i/FPS,scene['duration'],args.backup).tobytes())
            print(f"Rendered scene {scene['id']} ({count} frames)",flush=True)
        proc.stdin.close()
        if proc.wait()!=0:raise RuntimeError('ffmpeg failed')
    finally:film.close()
    print(str(path),flush=True)


if __name__=='__main__':main()
