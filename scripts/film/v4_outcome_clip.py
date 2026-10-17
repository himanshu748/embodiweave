"""18-second, silent evidence clip. Editorial highlights of saved MCP records.

No simulation, training, model request, or robot animation runs in this script.
"""
import hashlib,json,math,subprocess,textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'evidence/mcp-agent-v4'
W,H,FPS,SECONDS=1920,1080,30,18
PAPER,INK,MUTED,ORANGE,LINE='#f2f0e8','#252d30','#657074','#e85d19','#d7d9d1'
def load(name):return json.loads((E/name).read_text())
def font(size,mono=False):return ImageFont.truetype(str(ROOT/'docs/demo/assets'/('IBMPlexMono-Regular.ttf' if mono else 'SpaceGrotesk.ttf')),size)
def text(d,xy,s,size=32,color=INK,mono=False):d.text(xy,str(s),font=font(size,mono),fill=color)
def lines(d,xy,s,width=75,size=30,color=INK,mono=False):
 for j,line in enumerate(textwrap.wrap(str(s),width,break_long_words=True)):
  text(d,(xy[0],xy[1]+j*(size+12)),line,size,color,mono)
def box(d,xy,title,body,accent=False):
 d.rounded_rectangle(xy,radius=12,fill='#faf9f4',outline=ORANGE if accent else LINE,width=3)
 text(d,(xy[0]+24,xy[1]+20),title,25,ORANGE if accent else MUTED,True)
 lines(d,(xy[0]+24,xy[1]+72),body,max(18,(xy[2]-xy[0]-48)//20),31)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 s=load('summary.json');dec=load('decision.json');ranking=load('rank_origins_excluding_regressed.json')['origin_ranking'];outcome=load('outcome.json')
 assert s['origin_changed'] and s['completed']
 old=s['v2_origin'];chosen=s['origin'];excluded=next(r for r in ranking if r['origin_id']==old)
 assert excluded['excluded'] and not next(r for r in ranking if r['origin_id']==chosen)['excluded']
 sources={n:sha(E/n) for n in ['summary.json','decision.json','rank_origins_excluding_regressed.json','outcome.json','gate.json']}
 dest=ROOT/'web/media/embodiweave-v4-outcome-clip.mp4';poster=dest.with_suffix('.webp')
 captions=[('The recorded regression excludes the old origin.','FalkorDB applies the authored rule to connected outcomes.'),('The MCP agent chooses a different surviving origin.','The Decision is saved before training starts.'),('The fixed gate and parent comparison remain separate.','A different origin is not proof of learning or improvement.')]
 def frame(t):
  image=Image.new('RGB',(W,H),PAPER);d=ImageDraw.Draw(image)
  for x in range(0,W,36):d.line((x,0,x,H),fill='#e5e5dc')
  for y in range(0,H,36):d.line((0,y,W,y),fill='#e5e5dc')
  scene=min(2,int(t/6));text(d,(70,45),'EMBODIWEAVE / V4',28,ORANGE,True)
  text(d,(70,105),captions[scene][0],49)
  text(d,(70,175),captions[scene][1],30,MUTED)
  if scene==0:
   box(d,(70,275,910,495),'PRIOR ORIGIN',old,True)
   box(d,(990,275,1850,495),'GRAPH VERDICT','excluded = true',True)
   d.line((912,385,988,385),fill=ORANGE,width=5)
   text(d,(90,550),'REGRESSED_AGAINST + DecisionOutcome',36,INK,True)
   ids=sorted({r['outcome_id'] for r in excluded['reasons'] if r.get('outcome_id')})
   for j,oid in enumerate(ids[:2]):text(d,(90,620+j*55),oid,29,MUTED,True)
   lines(d,(90,775),'ORDER BY excluded, failed_suites, collision_clearance DESC, origin_id',90,29,INK,True)
  elif scene==1:
   box(d,(70,270,1850,465),'MODEL-CHOSEN ORIGIN',chosen,True)
   text(d,(90,505),'rank_origins_excluding_regressed → start_training',31,INK,True)
   lines(d,(90,575),'The Decision cites regression-lineage-exclusion-v1 and outcome-deci-20261016121309-c0c93f. The old origin is excluded; the chosen origin survives the fresh graph guardrail.',100,32)
   text(d,(90,755),'Authored rule. No learning or safety advantage established.',28,MUTED)
   text(d,(90,825),dec['id'],29,ORANGE,True)
   text(d,(90,875),f"{s['consumed_steps']:,} PPO steps / {s['validation_episodes']} validation episodes",31)
  else:
   headers=['SUITE','PARENT','CHILD','LIMIT','GATE'];xs=[90,500,790,1100,1470]
   for x,h in zip(xs,headers):text(d,(x,285),h,27,MUTED,True)
   checks={c['suite_id']:c for c in load('gate.json')['checks']}
   limits={'val-target-v1':10,'val-open-v1':5,'val-static-v1':10,'val-crossing-v1':15}
   for j,row in enumerate(outcome['suites']):
    y=360+j*85;sid=row['suite_id'];n=row['episodes']
    vals=[sid.replace('val-','').replace('-v1',''),f"{row['parent_collisions']}/{n}",f"{row['child_collisions']}/{n}",f"{limits[sid]}%",'Pass' if checks[sid]['pass'] else 'Fail']
    for x,v in zip(xs,vals):text(d,(x,y),v,36,ORANGE if x==790 and row['collision_delta']>0 else INK)
   text(d,(90,755),f"Gate: {s['passed_suites']}/4. {s['release_verdict']}",35,ORANGE)
   text(d,(90,825),'Deployed policy unchanged. No improvement claim.',31)
  d.rectangle((0,970,W,H),fill=INK)
  text(d,(70,997),'Recorded MCP evidence / editorial layout / silent captioned clip',25,'#ffffff',True)
  d.rectangle((0,1067,int(W*t/SECONDS),1080),fill=ORANGE)
  return image
 encoder=subprocess.Popen(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],stdin=subprocess.PIPE)
 for i in range(SECONDS*FPS):encoder.stdin.write(frame(i/FPS).tobytes())
 encoder.stdin.close();assert encoder.wait()==0
 frame(7).save(poster,quality=88)
 receipt={'seconds':SECONDS,'fps':FPS,'width':W,'height':H,'audio':'none; captioned evidence clip','sources':sources,'files':{str(p.relative_to(ROOT)):sha(p) for p in [dest,poster]},'editorial':'Typesetting, connectors and highlights animate saved MCP records. No robot footage or new simulation. V5 media unchanged.'}
 (E/'clip-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))
if __name__=='__main__':main()
