"""Render a disclosed, paired DEVELOPMENT episode from actual MuJoCo states."""
import hashlib,json,math,subprocess
from pathlib import Path
from PIL import Image,ImageDraw
from scripts.film.physics import Replay
from scripts.film.render import background,text,INK,ORANGE,PAPER,MUTED,font

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'evidence/physics-adapt-v1'
OUT=ROOT/'web/media/physics-development.mp4'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def render():
 s=json.loads((E/'summary.json').read_text())
 # Use the origin selected by the actual longer-run Decision, not a cinematic ranking.
 last=next(a for a in s['attempts'] if a['study']=='physics-followup-v1')
 decision=json.loads((ROOT/f"artifacts/records/decision/{last['decision_id']}.json").read_text())
 after=decision['selected'];before=json.loads((ROOT/'evidence/robustness-v2/selected.json').read_text())['policy_id']
 records=[json.loads((E/'development'/pid/'candidate-static_crossing.json').read_text()) for pid in (before,after)]
 pairs=[(a,b) for a,b in zip(records[0]['episodes'],records[1]['episodes']) if a['seed']==b['seed'] and a['outcome']=='collision' and a['hit']=='mover' and b['outcome']=='success']
 if not pairs:raise ValueError('No paired illustration meets the disclosed selection; do not fabricate footage')
 a,b=min(pairs,key=lambda pair:pair[0]['seconds'])
 pair={'seed':a['seed'],'before_policy':before,'after_policy':after,'decision_id':decision['id'],'before':a,'after':b,'selection':'Earliest 2D-parent pedestrian collision among same-seed physics-development successes of the graph-ranked origin. Illustrative development episode only. No confirmation access.'}
 (E/'filmed-development-pair.json').write_text(json.dumps(pair,indent=2)+'\n')
 seconds=15;scale=max(1,math.ceil(max(a['seconds'],b['seconds'])/(seconds-2)))
 replays=[Replay({**ep,'trajectory':'../physics-adapt-v1/development/'+pid+'/'+ep['trajectory']},'static_crossing',936,650) for ep,pid in zip((a,b),(before,after))]
 encoder=subprocess.Popen(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT)],stdin=subprocess.PIPE)
 for i in range(seconds*30):
  t=i/30;image=background();d=ImageDraw.Draw(image)
  text(d,(44,34),'MUJOCO DEVELOPMENT / SAME SEED / REAL RECORDED STATES',26,ORANGE,True)
  text(d,(44,85),'2D release vs mixed-domain physics lineage',42,INK)
  for x,replay,ep,label in zip((12,972),replays,(a,b),('2D-TRAINED RELEASE','TRAINED IN 2D + MUJOCO')):
   pixels,clock=replay.frame(max(0,t-.5)*scale,'wide' if t<10 else 'tactical',t/seconds)
   image.paste(Image.fromarray(pixels),(x,207));d=ImageDraw.Draw(image)
   text(d,(x+22,161),label,26,INK,True);d.rectangle((x+20,808,x+915,855),fill=INK)
   status=ep['outcome'].upper()+' / FROZEN' if clock>=ep['seconds']-.01 else 'RUNNING'
   text(d,(x+35,817),f't={clock:05.2f}s / {status}',25,PAPER,True)
  text(d,(44,890),f"Seed {a['seed']} / {scale}x sample-and-hold replay / selected illustration",26,ORANGE,True)
  text(d,(44,946),'The physics lineage passed 8/8 checks but missed extra crossing clearance.',28,INK)
  text(d,(44,997),'Physics confirmation remains unopened. Full suite results are reported separately.',26,MUTED)
  if i==225:image.resize((1280,720)).save(ROOT/'web/media/physics-development-poster.webp',quality=85)
  encoder.stdin.write(image.tobytes())
 encoder.stdin.close();assert encoder.wait()==0
 for replay in replays:replay.close()
 receipt={'seconds':seconds,'fps':30,'resolution':[1920,1080],'video_sha256':sha(OUT),'script_sha256':sha(__file__),'pair_sha256':sha(E/'filmed-development-pair.json'),'motion':'Actual recorded MuJoCo qpos and mocap poses, sampled and held without interpolation. Titles, camera movement, rays and trail are render overlays. Silent companion replay; main film narration remains Deepgram Aura-2.','policy_selection':decision['id']}
 (E/'replay-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))

if __name__=='__main__':render()
