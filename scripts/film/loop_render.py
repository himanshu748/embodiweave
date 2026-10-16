"""V5 uses saved robot poses and recorded query results; titles are editorial."""
import argparse,math,shutil,subprocess,textwrap
from PIL import Image,ImageDraw
from scripts.film.loop_update import ROOT,E,DOC,OUT,sha,load,write,prepare
from scripts.film.mcp_render import Film as V4,run,lines,card
from scripts.film.render import background,chrome,text,font,INK,PAPER,MUTED,ORANGE

class Film:
 def __init__(self):
  self.old=V4();self.success=load(E/'success-replay.json');self.v3=load(ROOT/'evidence/mcp-agent-v3/summary.json')
  self.images={i:Image.open(ROOT/'evidence/film-v4/browser'/name).convert('RGB') for i,name in enumerate(
   ['01-tools.png','02-tools.png','03-launch.png','04-guardrail.png'],1)}
 def replay(self,scene,t,success=False):
  image=background();old=self.old.episode
  if success:self.old.episode=self.success['episode']
  ep=self.old.episode
  # Change playback speed only; select saved frames without interpolating poses.
  elapsed=min((len(ep['trace'])-1)/10,t*max(1,(len(ep['trace'])-1)/10/(scene['duration']-1.5)))
  self.old.arena(image,elapsed);self.old.episode=old
  d=ImageDraw.Draw(image);d.rectangle((850,175,1920,955),fill=PAPER)
  if success:
   text(d,(880,210),'SHIPPED / CONFIRMED IN 2D',28,ORANGE,True)
   lines(d,(880,290),self.success['policy_id'],32,29,INK,True)
   text(d,(880,410),'4 / 4 validation suites',43)
   text(d,(880,500),'8 / 100 target collisions',43,ORANGE)
   text(d,(880,565),'Fresh confirmation / 10% limit',28)
   lines(d,(880,660),'Successful saved validation episode. Confirmation counts are a separate recorded batch.',46,27,MUTED)
   frame=ep['trace'][min(len(ep['trace'])-1,int(elapsed*10))]
   text(d,(880,795),'GOAL REACHED' if frame['outcome']=='success' else 'RECORDED REPLAY',36,ORANGE)
   text(d,(880,865),f"Seed {ep['seed']} / no new evaluation",23,MUTED,True)
  else:
   text(d,(880,210),'A RECORDED FAILURE',28,ORANGE,True)
   lines(d,(880,300),'Which checkpoint should I retrain?',28,52)
   for j,label in enumerate(['Lineage','Sensor and action contracts','Exact-artifact test results']):text(d,(880,525+j*75),label,33)
   text(d,(880,800),'FalkorDB connects the evidence.',34,ORANGE)
   text(d,(880,875),'V2 child / recorded target collision',23,MUTED,True)
  d.rectangle((0,925,1920,970),fill=PAPER)
  text(d,(90,936),'Saved simulator poses / no interpolation / recorded validation replay',23,MUTED,True)
  return image
 def frame(self,s,t):
  i=s['id']
  if i==1:image=self.replay(s,t)
  elif 2<=i<=10:
   original=i-1;source=None
   if original in (1,2):source=self.images[(1 if original==1 else 3)+(1 if t>3 else 0)]
   image=self.old.frame({**s,'id':original},t,source)
  elif i==11:
   image=background();d=ImageDraw.Draw(image)
   text(d,(80,195),'V3 / THE SINGLE PREREGISTERED ATTEMPT',25,ORANGE,True)
   card(d,(80,275,920,570),'MCP TOOLS CALLED','get_decision_outcomes\nrank_regression_origins','Actual calls in the saved agent trace',True)
   card(d,(1000,275,1840,570),'MEASURED V2 EDGE WEIGHT','1/60 + 1/40 = 0.04167','One observed child; unknown origins return null')
   text(d,(80,650),'Five graph reads completed. No origin was chosen.',41)
   text(d,(80,735),'Model context cap reached. No training. No retry.',36,ORANGE)
   lines(d,(80,825),'The weighted algorithm was called, but no decision change is established.',85,30)
  elif i==12:image=self.replay(s,t,True)
  else:
   image=background();d=ImageDraw.Draw(image)
   text(d,(80,200),'BUILT ON FALKORDB',70,ORANGE)
   text(d,(80,320),'Every action is a node you can query.',45)
   text(d,(80,420),'Decision → Run → Policy → Evaluation → Outcome',30,INK,True)
   text(d,(80,495),'deci-20261016121309-c0c93f',28,MUTED,True)
   text(d,(80,600),'github.com/himanshu748/embodiweave',33,INK,True)
   text(d,(80,660),'embodiweave.52.202.25.181.sslip.io',33,INK,True)
   text(d,(80,770),'Narration: Deepgram Aura-2. Captions: Deepgram Nova-3.',26)
   text(d,(80,825),'Music: Cipher / Kevin MacLeod / CC BY 3.0',25,MUTED)
   text(d,(80,885),'Evidence, scripts and receipts: evidence/film-v5/',24,MUTED,True)
  chrome(image,s,t,s['duration'],i,13)
  return image

def render(scene_ids=None):
 prepare();film=Film();timeline=load(E/'timeline.json');caps=load(E/'captions.json')
 for s in timeline['scenes']:
  i=s['id']
  if scene_ids and i not in scene_ids:continue
  path=OUT/f'scene-{i:02}.mp4'
  encoder=subprocess.Popen(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p',str(path)],stdin=subprocess.PIPE)
  try:
   for index in range(round(s['duration']*30)):
    t=index/30;image=film.frame(s,t);d=ImageDraw.Draw(image)
    active=next((line for a,b,line in caps if a<=s['start']+t<b),None)
    if active:
     wrapped=textwrap.wrap(active,76)
     for j,line in enumerate(wrapped):d.text((960,1016-(len(wrapped)-1)*39+j*39),line,font=font(36),fill='white',anchor='mt')
    encoder.stdin.write(image.tobytes())
    if index==round(s['duration']*15):image.save(OUT/f'preview-{i:02}.png')
  finally:encoder.stdin.close()
  assert encoder.wait()==0
  print('Rendered v5 scene',i,flush=True)

def assemble():
 data=load(E/'timeline.json');seconds=data['seconds'];assert seconds<120
 parts=[OUT/f"scene-{s['id']:02}.mp4" for s in data['scenes']]
 (OUT/'picture-list.txt').write_text(''.join(f"file '{p}'\n" for p in parts))
 run('-f','concat','-safe','0','-i',OUT/'picture-list.txt','-r','30','-fps_mode','cfr','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',OUT/'picture.mp4')
 voices=[]
 for s in data['scenes']:
  p=OUT/f"voice-{s['id']:02}.wav";run('-i',ROOT/s['audio'],'-af',f"apad,atrim=duration={s['duration']}",'-ar','48000','-c:a','pcm_s16le',p);voices.append(p)
 (OUT/'voices.txt').write_text(''.join(f"file '{p}'\n" for p in voices))
 run('-f','concat','-safe','0','-i',OUT/'voices.txt','-c:a','pcm_s16le',OUT/'narration.wav')
 music=ROOT.parent/'cipher.mp3'
 mix=f'[0:a]atrim=duration={seconds},asetpts=PTS-STARTPTS,loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.1258925,afade=t=in:st=0:d=1,afade=t=out:st={seconds-3}:d=3[m];[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[v];[m][v]amix=inputs=2:normalize=0,alimiter=limit=0.89[a]'
 run('-i',music,'-i',OUT/'narration.wav','-filter_complex',mix,'-map','[a]','-t',seconds,'-ar','48000',OUT/'mix.wav')
 master=OUT/'embodiweave-demo-v5.mp4'
 run('-i',OUT/'picture.mp4','-i',OUT/'mix.wav','-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k','-t',seconds,'-movflags','+faststart',master)
 backup=OUT/'embodiweave-demo-v5-narration-free.mp4'
 run('-i',OUT/'picture.mp4','-i',music,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k','-af',f'loudnorm=I=-20:TP=-1.5:LRA=11,afade=t=out:st={seconds-3}:d=3','-t',seconds,'-movflags','+faststart',backup)
 site=OUT/'embodiweave-demo-v5-720p.mp4'
 run('-i',master,'-vf','scale=1280:720','-c:v','libx264','-preset','fast','-crf','23','-c:a','aac','-b:a','96k','-movflags','+faststart',site)
 gif=OUT/'embodiweave-demo-v5.gif'
 start=next(s['start'] for s in data['scenes'] if s['id']==12)
 run('-ss',start,'-t',10,'-i',master,'-filter_complex','[0:v]fps=10,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=bayer',gif)
 assert master.stat().st_size<50_000_000
 for p in (master,site,backup,gif):shutil.copyfile(p,ROOT/'web/media'/p.name)
 shutil.copyfile(DOC/'embodiweave-demo-v5.srt',ROOT/'web/media/embodiweave-demo-v5.srt')
 run('-ss',start+data['scenes'][11]['duration']-1,'-i',master,'-frames:v',1,DOC/'thumbnail.png')
 with Image.open(DOC/'thumbnail.png') as p:p.resize((1280,720),Image.Resampling.LANCZOS).save(ROOT/'web/media/demo-v5-poster.webp',quality=88)
 write(E/'film-receipt.json',{'seconds':seconds,'width':1920,'height':1080,'fps':30,'narration_model':data['model'],
 'narration_seconds':sum(s['voice_seconds'] for s in data['scenes']),
 'assets':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in (master,site,backup,gif)},
 'scene_video_sha256':{p.name:sha(p) for p in parts},'music':{'title':'Cipher','artist':'Kevin MacLeod','license':'CC BY 3.0','sha256':sha(music),'gain_below_normalized_voice_db':18},
 'new_experiments_for_film':False,'v3_result':'Five reads; context limit; no chosen origin or training; no retry.',
 'v4_unchanged':True,'robot_motion':'Saved v2 child collision and robust confirmed-checkpoint validation success. No new simulation or interpolated poses.',
 'editorial':'Titles, layout and highlights are editorial. V4 browser captures replay completed evidence. No learning curves invented.'})
 prepare()
 print('Assembled v5',seconds,'seconds',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['render','assemble']);a=p.parse_args();{'render':render,'assemble':assemble}[a.action]()
