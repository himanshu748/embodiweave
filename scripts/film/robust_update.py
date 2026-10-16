"""Update scenes 9-11 from robustness-v2; preserve the original v2 film.

All narration remains Deepgram. Unchanged scene WAVs/receipts are reused, while
new lines get fresh Aura-2 audio and Nova-3 timings. Physics replays recorded
MuJoCo joint states; this script never trains, evaluates or fabricates motion.
"""
import argparse, difflib, hashlib, json, math, os, shutil, subprocess, textwrap, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scripts.film import voice
from scripts.film.render import background, chrome, text, font, W, H, PAPER, INK, ORANGE, MUTED, LINE
from scripts.film.physics import Replay

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'evidence/film-v3'
OUT=ROOT.parents[1]/'outputs/film-v3'
DOC=ROOT/'docs/demo/v3'
MODEL='aura-2-thalia-en'
CHANGES={
9:('The graph chose a stronger collision cost.', 'Falkor-D-B chose the rehearsal checkpoint for six hundred thousand more P-P-O steps, with double the collision penalty. The saved candidate passed all four unchanged validation suites.'),
10:('Frozen first. Confirmed once.', 'I froze its hash before a fresh confirmation batch. All four suites passed. Target collisions: eight in one hundred. The limit stayed ten percent. The earlier failure remains visible.'),
11:('New physics still exposed a gap.', 'Physics still exposed a gap. The same checkpoint, without retraining in MuJoCo, collided six times in forty target episodes, and four times in crossing. This is no physical safety certificate.')}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n')
def run(*args):subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',*map(str,args)],check=True)
def load():return json.loads((ROOT/'evidence/robustness-v2/summary.json').read_text())

def prepare():
 E.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True);DOC.mkdir(parents=True,exist_ok=True)
 data=load();decision=json.loads((ROOT/f"artifacts/records/decision/{data['attempts'][0]['decision_id']}.json").read_text())
 write(E/'decision.json',decision)
 before=json.loads((ROOT/'evidence/mujoco-v2/deployed-static_crossing.json').read_text())
 after=json.loads((ROOT/'evidence/mujoco-v2/robust-static_crossing.json').read_text())
 pairs=[(a,b) for a,b in zip(before['episodes'],after['episodes']) if a['outcome']=='collision' and a['hit']=='mover' and b['outcome']=='success']
 a,b=min(pairs,key=lambda pair:pair[0]['seconds'])
 write(E/'filmed-pair.json',{'seed':a['seed'],'before':a,'after':b,'selection':'Earliest historical-baseline mover collision among paired new-candidate successes. Selected illustration; all 320 episodes are reported.'})
 scenes=json.loads((ROOT/'evidence/film/timeline.json').read_text())['scenes']
 for s in scenes:
  if s['id'] in CHANGES:s['title'],s['narration']=CHANGES[s['id']]
 write(E/'scenes.json',scenes)

def narrate():
 prepare();scenes=json.loads((E/'scenes.json').read_text());old=json.loads((ROOT/'evidence/film/voice-receipts.json').read_text())
 receipts=[];captions=[];cursor=0.;timeline=[]
 previous=json.loads((E/'voice-receipts.json').read_text()) if (E/'voice-receipts.json').exists() else []
 for s in scenes:
  i=s['id'];script=s['narration']
  if i not in CHANGES:
   r=next(r for r in old if r['scene']==i).copy();audio=ROOT/s['audio'];stt=json.loads((ROOT/f'evidence/film/transcript-{i:02}.json').read_text())
   r['reused_from']='evidence/film/voice-receipts.json'
  else:
   audio=DOC/f'voice/{i:02}.wav';audio.parent.mkdir(parents=True,exist_ok=True)
   r=next((r for r in previous if r['scene']==i and r['text_sha256']==hashlib.sha256(script.encode()).hexdigest()),None)
   if r and audio.exists():stt=json.loads((E/f'transcript-{i:02}.json').read_text())
   else:
    assert len(script)<=2000
    raw,rid=voice.request('speak?model='+MODEL+'&encoding=linear16&sample_rate=48000&container=wav',json.dumps({'text':script}).encode(),'application/json')
    audio.write_bytes(voice.pcm_wav(raw));stt,sid=voice.transcribe(audio.read_bytes())
    alt=stt['results']['channels'][0]['alternatives'][0]
    r={'scene':i,'model':MODEL,'characters':len(script),'dg_request_id':rid,'stt_request_id':sid,'stt_model':'nova-3','text_sha256':hashlib.sha256(script.encode()).hexdigest(),'audio_sha256':sha(audio),'transcript':alt['transcript'],'stt_transport':'Ogg Opus 48kbps copy of canonical 48kHz WAV'}
    write(E/f'transcript-{i:02}.json',stt)
  with wave.open(str(audio)) as f:
   assert f.getframerate()==48000 and f.getsampwidth()==2
   seconds=f.getnframes()/f.getframerate()
  alt=stt['results']['channels'][0]['alternatives'][0]
  ratio=difflib.SequenceMatcher(None,voice.tokens(script),voice.tokens(alt['transcript'])).ratio()
  if ratio<.88:raise ValueError(f'Scene {i} transcript mismatch: {ratio:.3f}')
  r.update({'seconds':seconds,'transcript_match_ratio':ratio,'audio':str(audio.relative_to(ROOT))});receipts.append(r)
  write(E/'voice-receipts.json',receipts)
  length=s['duration'] if i not in CHANGES else math.ceil((seconds+.5)*30)/30
  words=[dict(w) for w in alt['words']];r['caption_corrections']=[]
  for j,w in enumerate(words):
   correction=None
   if i==10 and w['word']=='and' and j and words[j-1]['word']=='eight':correction='in'
   if i==11 and w['word']=='to' and j+1<len(words) and words[j+1]['word']=='gap':correction='a'
   if correction:
    r['caption_corrections'].append({'start':w['start'],'end':w['end'],'raw':w['word'],'caption':correction})
    w['punctuated_word']=correction
  for j in range(0,len(words),7):
   group=words[j:j+7];line=' '.join(w.get('punctuated_word',w['word']) for w in group)
   line=line.replace('cipher','Cypher');captions.append((cursor+group[0]['start'],cursor+group[-1]['end'],line))
  timeline.append({**s,'audio':str(audio.relative_to(ROOT)),'start':cursor,'duration':length,'voice_seconds':seconds})
  cursor+=length
  write(E/'voice-receipts.json',receipts)
  print(json.dumps({'scene':i,'seconds':seconds,'match':ratio}),flush=True)
 if not 90<=cursor<=120:raise ValueError(f'Film duration {cursor:.2f} outside brief; revise wording, never speed speech')
 write(E/'timeline.json',{'seconds':cursor,'model':MODEL,'scenes':timeline});write(E/'captions.json',captions)
 (DOC/'embodiweave-demo-v3.srt').write_text('\n\n'.join(f'{i+1}\n{voice.stamp(a)} --> {voice.stamp(b)}\n{t}' for i,(a,b,t) in enumerate(captions))+'\n')
 (DOC/'SCRIPT.md').write_text('# EmbodiWeave v3\n\n'+f'{cursor:.2f} seconds. Scenes 1-8 retain the recorded search-v1 history. Scenes 9-11 report robustness-v2. Narration: Deepgram Aura-2 Thalia. Captions: Deepgram Nova-3.\n\n'+'\n\n'.join(f"## {voice.stamp(s['start'])} to {voice.stamp(s['start']+s['duration'])}: {s['title']}\n\n{s['narration']}" for s in timeline)+'\n')

def frame(scene,t):
 data=load();image=background();chrome(image,scene,t,scene['duration'],scene['id']);d=ImageDraw.Draw(image)
 if scene['id']==9:
  a=data['attempts'][0];dec=json.loads((E/'decision.json').read_text())
  text(d,(80,180),'FALKORDB / RECORDED DECISION BEFORE TRAINING',25,ORANGE,True)
  text(d,(80,230),f"{dec['selected']}  →  {a['policy_id']}",27,INK,True)
  text(d,(80,282),f"{dec['id']} / collision cost -20 / {a['actual_steps']:,} new PPO steps",25,INK,True)
  query=dec['queries'][0]['cypher'].strip().splitlines()
  for j,line in enumerate(query[:4]):text(d,(80,337+j*31),line.strip(),23,MUTED,True)
  text(d,(80,495),'SAVED CHECKPOINT / CANONICAL VALIDATION',26,ORANGE,True)
  for j,c in enumerate(a['checks']):
   y=555+j*78;text(d,(80,y),c['suite_id'],29,INK,True);text(d,(680,y),f"{c['success_rate']:.1%} success",29)
   text(d,(1120,y),f"{c['collision_rate']:.1%} collisions / {c['max_collision']:.0%} limit",28);text(d,(1730,y),'PASS',27,ORANGE,True)
  text(d,(80,908),f"Exact artifact {data['artifact_hash'][:40]}…",25,MUTED,True)
 elif scene['id']==10:
  text(d,(80,190),'ONE POST-SELECTION BATCH / 100 FRESH EPISODES PER FAMILY',26,ORANGE,True)
  for x,label in zip([80,540,850,1240,1650],['Suite','Goals','Collisions / limit','Timeouts','Result']):text(d,(x,290),label,29)
  for i,r in enumerate(data['confirmation']['results']):
   y=380+i*104;v=r['summary'];n=v['episodes']
   for x,value in zip([80,540,850,1240,1650],[r['family'].replace('_',' + '),f"{round(v['success_rate']*n)}/{n}",f"{round(v['collision_rate']*n)}/{n} / {r['max_collision']:.0%}",str(round(v['timeout_rate']*n)),'PASS' if r['pass'] else 'FAIL']):text(d,(x,y),value,30,INK,True)
   d.line((80,y+70,1820,y+70),fill=LINE,width=2)
  text(d,(80,850),'Earlier search-v1 confirmation: 13/100 target collisions, FAILED.',31,ORANGE)
  text(d,(80,910),'Old evidence stays frozen. No confirmation outcome enters the planner.',27,MUTED)
 return image

def render(scene_ids=(9,10,11)):
 OUT.mkdir(parents=True,exist_ok=True);timeline=json.loads((E/'timeline.json').read_text());caps=json.loads((E/'captions.json').read_text());pair=json.loads((E/'filmed-pair.json').read_text())
 for s in timeline['scenes']:
  if s['id'] not in scene_ids:continue
  encoder=subprocess.Popen(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p',str(OUT/f"scene-{s['id']:02}.mp4")],stdin=subprocess.PIPE)
  replays=[]
  if s['id']==11:
   replays=[Replay({**pair[k],'trajectory':'../mujoco-v2/'+pair[k]['trajectory']},'static_crossing',936,650) for k in ('before','after')]
  for index in range(round(s['duration']*30)):
   t=index/30
   if s['id']!=11:image=frame(s,t)
   else:
    image=background();chrome(image,s,t,s['duration'],11);d=ImageDraw.Draw(image)
    if t<s['duration']*.7:
     scale=max(1,math.ceil(max(pair[k]['seconds'] for k in ('before','after'))/max(1,s['duration']*.7-1)))
     for x,replay,key,label in zip((12,972),replays,('before','after'),('HISTORICAL / P-static-b','CONFIRMED IN 2D / NEW CHECKPOINT')):
      pixels,clock=replay.frame(max(0,t-.5)*scale,'wide' if t<s['duration']*.45 else 'tactical',t/s['duration']);image.paste(Image.fromarray(pixels),(x,225));d=ImageDraw.Draw(image)
      text(d,(x+22,180),label,24,INK,True);d.rectangle((x+20,817,x+915,864),fill=INK)
      status=pair[key]['outcome'].upper()+' / FROZEN' if clock>=pair[key]['seconds']-.01 else 'RUNNING'
      text(d,(x+35,827),f't={clock:05.2f}s / {status}',24,PAPER,True)
     text(d,(80,894),f"Same seed {pair['seed']} / {scale}x replay / selected illustration",26,ORANGE,True)
     text(d,(80,936),'2D-trained checkpoints. MuJoCo physics. No retraining.',26,MUTED)
    else:
     data=load();text(d,(80,205),'MUJOCO / ALL FRESH TRANSFER EPISODES',27,ORANGE,True)
     for x,label in zip([80,630,1100,1560],['Suite','P-static-b','New checkpoint','Collision limit']):text(d,(x,315),label,29)
     for i,family in enumerate(['open','static','crossing','static_crossing']):
      y=415+i*100;text(d,(80,y),family.replace('_',' + '),31)
      for x,label in [(630,'deployed'),(1100,'robust')]:
       r=next(r for r in data['transfer'] if r['label']==label and r['family']==family);text(d,(x,y),f"{r['summary']['collision']}/40",32,INK,True)
      limit=next(r['max_collision'] for r in data['confirmation']['results'] if r['family']==family);text(d,(1560,y),f'{limit:.0%}',31,ORANGE,True)
     text(d,(80,863),'Target transfer still fails: 6/40 collisions (15%) > 10%.',32,ORANGE)
     text(d,(80,921),'A confirmed 2D policy is not a physical safety certificate.',28,MUTED)
   d=ImageDraw.Draw(image);active=next((line for a,b,line in caps if a<=s['start']+t<b),None)
   if active:
    lines=textwrap.wrap(active,76)
    for j,line in enumerate(lines):d.text((960,1016-(len(lines)-1)*39+j*39),line,font=font(36),fill='white',anchor='mt',stroke_width=1,stroke_fill=INK)
   encoder.stdin.write(image.tobytes())
   if index==round(s['duration']*15):image.save(OUT/f"preview-{s['id']:02}.png")
  encoder.stdin.close();assert encoder.wait()==0
  for r in replays:r.close()
  print('Rendered scene',s['id'],flush=True)

def assemble():
 data=json.loads((E/'timeline.json').read_text());old=json.loads((ROOT/'evidence/film/timeline.json').read_text());source=ROOT/'web/media/embodiweave-demo-v2.mp4'
 common=['-an','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-r','30']
 run('-i',source,'-t',old['scenes'][8]['start'],*common,OUT/'head.mp4')
 run('-ss',old['scenes'][11]['start'],'-i',source,'-t',old['scenes'][11]['duration'],*common,OUT/'close.mp4')
 parts=[OUT/'head.mp4',*[OUT/f'scene-{i:02}.mp4' for i in (9,10,11)],OUT/'close.mp4']
 (OUT/'picture-list.txt').write_text(''.join(f"file '{p}'\n" for p in parts));run('-f','concat','-safe','0','-i',OUT/'picture-list.txt','-c','copy',OUT/'picture.mp4')
 voices=[]
 for s in data['scenes']:
  p=OUT/f"voice-{s['id']:02}.wav";run('-i',ROOT/s['audio'],'-af',f"apad,atrim=duration={s['duration']}",'-ar','48000','-c:a','pcm_s16le',p);voices.append(p)
 (OUT/'voices.txt').write_text(''.join(f"file '{p}'\n" for p in voices));run('-f','concat','-safe','0','-i',OUT/'voices.txt','-c:a','pcm_s16le',OUT/'narration.wav')
 seconds=data['seconds'];music=ROOT.parent/'cipher.mp3'
 mix=f'[0:a]atrim=duration={seconds},asetpts=PTS-STARTPTS,loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.1258925,afade=t=in:st=0:d=1,afade=t=out:st={seconds-3}:d=3[m];[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[v];[m][v]amix=inputs=2:normalize=0,alimiter=limit=0.89[a]'
 run('-i',music,'-i',OUT/'narration.wav','-filter_complex',mix,'-map','[a]','-t',seconds,'-ar','48000',OUT/'mix.wav')
 master=OUT/'embodiweave-demo-v3.mp4';run('-i',OUT/'picture.mp4','-i',OUT/'mix.wav','-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k','-t',seconds,'-movflags','+faststart',master)
 backup=OUT/'embodiweave-demo-v3-narration-free.mp4';run('-i',OUT/'picture.mp4','-i',music,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k','-af',f'loudnorm=I=-20:TP=-1.5:LRA=11,afade=t=out:st={seconds-3}:d=3','-t',seconds,'-movflags','+faststart',backup)
 site=OUT/'embodiweave-demo-v3-720p.mp4';run('-i',master,'-vf','scale=1280:720','-c:v','libx264','-preset','fast','-crf','23','-c:a','aac','-b:a','96k','-movflags','+faststart',site)
 gif=OUT/'embodiweave-demo-v3.gif';s=data['scenes'][10];run('-ss',s['start'],'-t',10,'-i',master,'-filter_complex','[0:v]fps=10,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=bayer',gif)
 run('-i',OUT/'scene-11.mp4','-vf','scale=1280:720','-an','-c:v','libx264','-preset','fast','-crf','23','-movflags','+faststart',ROOT/'web/media/mujoco-v2-replay.mp4')
 assert master.stat().st_size<50_000_000
 for p in (master,site,gif):shutil.copyfile(p,ROOT/'web/media'/p.name)
 shutil.copyfile(DOC/'embodiweave-demo-v3.srt',ROOT/'web/media/embodiweave-demo-v3.srt')
 run('-ss','2','-i',OUT/'scene-11.mp4','-frames:v','1',DOC/'thumbnail.png')
 with Image.open(DOC/'thumbnail.png') as poster:poster.resize((1280,720),Image.Resampling.LANCZOS).save(ROOT/'web/media/demo-v3-poster.webp',quality=85)
 receipt={'seconds':seconds,'fps':30,'width':1920,'height':1080,'narration_model':MODEL,'narration_seconds':sum(s['voice_seconds'] for s in data['scenes']),'assets':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in (master,site,backup,gif)},'reused_v2_sha256':sha(source),'physics':'Recorded MuJoCo-v2 joint states, no interpolation or policy retraining. Selected episode; complete aggregates visible.','history':'Scenes 1-8 are frozen search-v1 history. Scenes 9-11 are the separately preregistered robustness-v2 study. Old failure remains visible.'}
 write(E/'film-receipt.json',receipt);print(json.dumps(receipt,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','voice','render','assemble']);p.add_argument('--scenes',nargs='+',type=int,default=[9,10,11]);a=p.parse_args()
 {'prepare':prepare,'voice':narrate,'render':lambda:render(a.scenes),'assemble':assemble}[a.action]()
