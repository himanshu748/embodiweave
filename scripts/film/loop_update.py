"""V5: immutable source recordings, Deepgram narration, no new policy execution."""
import argparse,hashlib,json,math,shutil,wave
from pathlib import Path
from scripts.film import voice
from scripts.film.mcp_update import validate_transcript
ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'evidence/film-v5';DOC=ROOT/'docs/demo/v5';OUT=ROOT.parents[1]/'outputs/film-v5'
MODEL='aura-2-thalia-en'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def prepare():
 for p in (E,DOC,OUT):p.mkdir(parents=True,exist_ok=True)
 old=load(ROOT/'evidence/film-v4/scenes.json')
 # Exact v4 narration and source slides 01-09 are reused with their original receipts.
 scenes=[dict(id=1,title='A failure needs its history',narration="This robot collided. Choosing a checkpoint to retrain needs its lineage, sensor contract and exact test results. Falkor-D-B connects that evidence.",visual='problem')]
 for scene in old[:9]:
  scenes.append({**scene,'id':scene['id']+1,'reuse_v4_scene':scene['id'],'visual':'v4-'+str(scene['id'])})
 scenes += [dict(id=11,title='The next agent read the regression',narration="The next agent read that regression and the weighted graph ranking. Its context limit stopped the attempt before training. I did not retry.",visual='v3'),
 dict(id=12,title='The shipped checkpoint passed fresh confirmation',narration="The shipped graph-selected checkpoint passed all four validation suites and fresh confirmation. Eight target collisions in a hundred episodes, below the ten percent limit.",visual='success'),
 dict(id=13,title='Every action is a node you can query',narration="Every action is a node you can query. Inspect the Decision, the live demo and the evidence. EmbodiWeave. Built on Falkor-D-B.",visual='close')]
 edits={4:"Falkor-D-B connects each policy to its training run, evaluations, failures and recorded decisions.",
        5:"Its shortest-path query returned a passing ancestor, one hop away. The agent compared seventeen eligible origins and chose a different checkpoint.",
        6:"The guardrail checks sensor contracts, artifact hashes, complete validation and the training budget. It can veto an incompatible origin.",
        7:"Before training, a Decision saves the model, tool calls, Cypher, parameters and returned records. Planning stops without Falkor-D-B."}
 for scene in scenes:
  if scene['id'] in edits:scene['narration']=edits[scene['id']]
 write(E/'scenes.json',scenes)
 snapshot={str(p.relative_to(ROOT)):sha(p) for base in (ROOT/'docs/demo/v4',ROOT/'evidence/film-v4',ROOT/'web/media')
           for p in base.rglob('*') if p.is_file() and (base.name!='media' or 'v4' in p.name)}
 if (E/'v4-backup-checksums.json').exists():assert load(E/'v4-backup-checksums.json')==snapshot
 else:write(E/'v4-backup-checksums.json',snapshot)
 confirmed=load(ROOT/'evidence/robustness-v2/selected.json')
 assert confirmed['policy_id']=='robust-20261016140226-352fd7'
 # Success replay comes from the already recorded confirmation/validation artifact.
 candidates=list((ROOT/'artifacts/replays').glob('*.json'))
 matches=[]
 for p in candidates:
  r=load(p)
  if r.get('policy_id')==confirmed['policy_id']:
   successes=[e for e in r.get('episodes',[]) if e.get('trace') and e['trace'][-1].get('outcome')=='success']
   if successes:matches.append((p,r,successes[0]))
 if not matches:
  import zipfile
  for p in (ROOT/'evidence/robustness-v2').glob('*.zip'):
   with zipfile.ZipFile(p) as z:
    for n in z.namelist():
     if n.startswith('replays/') and n.endswith('.json'):
      r=json.loads(z.read(n))
      if r.get('policy_id')==confirmed['policy_id']:
       success=next((e for e in r.get('episodes',[]) if e.get('trace') and e['trace'][-1].get('outcome')=='success'),None)
       if success:matches.append((p,r,success))
 assert matches,'No saved success replay for confirmed artifact'
 p,r,episode=matches[0]
 write(E/'success-replay.json',{'policy_id':r['policy_id'],'artifact_hash':r['artifact_hash'],'episode':episode,
       'source':str(p.relative_to(ROOT)),'source_sha256':sha(p),'selection':'First successful recorded episode in the first matching saved artifact; illustration, not an aggregate.'})
 write(E/'source-records.json',{'mcp_v2':'evidence/mcp-agent-v2/summary.json','mcp_v3':'evidence/mcp-agent-v3/summary.json',
       'confirmed':'evidence/robustness-v2/selected.json','robot_motion':'Recorded policy-driven 2D simulator poses, no interpolation or new evaluation.',
       'editorial':'Graph layout, titles, highlights and replayed browser capture framing are editorial; no invented learning curve.'})

def narrate():
 prepare(); previous=load(E/'voice-receipts.json') if (E/'voice-receipts.json').exists() else []
 originals=load(ROOT/'evidence/film-v4/voice-receipts.json')
 receipts=[];captions=[];timeline=[];cursor=0
 voice.KEYTERMS=[*voice.KEYTERMS,'MCP']
 for scene in load(E/'scenes.json'):
  i=scene['id'];script=scene['narration'];th=hashlib.sha256(script.encode()).hexdigest();assert len(script)<=2000
  audio=DOC/f'voice/{i:02}.wav';audio.parent.mkdir(parents=True,exist_ok=True)
  prior=next((r for r in previous if r['scene']==i and r['text_sha256']==th),None)
  reuse=next((r for r in originals if r['text_sha256']==th and r['model']==MODEL),None)
  if prior and audio.exists() and sha(audio)==prior.get('audio_sha256'):receipt=prior.copy()
  elif reuse:
   original=ROOT/reuse['audio'];assert sha(original)==reuse['audio_sha256'];shutil.copyfile(original,audio)
   receipt={**reuse,'scene':i,'reused_from':'evidence/film-v4/voice-receipts.json'}
   shutil.copyfile(ROOT/f"evidence/film-v4/transcript-{reuse['scene']:02}.json",E/f'transcript-{i:02}.json')
  else:
   raw,rid=voice.request('speak?model='+MODEL+'&encoding=linear16&sample_rate=48000&container=wav',json.dumps({'text':script}).encode(),'application/json')
   audio.write_bytes(voice.pcm_wav(raw));receipt={'scene':i,'model':MODEL,'dg_request_id':rid,'characters':len(script),'text_sha256':th,'audio_sha256':sha(audio)}
  def checkpoint():write(E/'voice-receipts.json',list({r['scene']:r for r in previous+receipts+[receipt]}.values()))
  checkpoint()
  if not receipt.get('stt_request_id'):
   stt,rid=voice.transcribe(audio.read_bytes());write(E/f'transcript-{i:02}.json',stt);receipt.update(stt_request_id=rid,stt_model='nova-3');checkpoint()
  alt=load(E/f'transcript-{i:02}.json')['results']['channels'][0]['alternatives'][0]
  ratio=validate_transcript(script.replace("a hundred", "one hundred"),alt["transcript"].replace("a 100", "one hundred"))
  with wave.open(str(audio)) as w:seconds=w.getnframes()/w.getframerate()
  receipt.update(seconds=seconds,transcript=alt['transcript'],transcript_match_ratio=ratio,audio=str(audio.relative_to(ROOT)))
  receipts.append(receipt);write(E/'voice-receipts.json',receipts)
  duration=math.ceil((seconds+.25)*30)/30
  timeline.append({**scene,'start':cursor,'duration':duration,'voice_seconds':seconds,'audio':str(audio.relative_to(ROOT))})
  words=[dict(w) for w in alt['words']]
  for word in words:
   for c in receipt.get('caption_corrections',[]):
    if word['start']==c['start']:word['punctuated_word']=c['caption']
  for j in range(0,len(words),7):
   group=words[j:j+7];captions.append([cursor+group[0]['start'],cursor+group[-1]['end'],' '.join(w.get('punctuated_word',w['word']) for w in group)])
  cursor+=duration
  print(json.dumps({'scene':i,'seconds':seconds,'transcript_match':ratio}),flush=True)
 write(E/'timeline.json',{'model':MODEL,'seconds':cursor,'scenes':timeline});write(E/'captions.json',captions)
 (DOC/'embodiweave-demo-v5.srt').write_text('\n\n'.join(f'{i+1}\n{voice.stamp(a)} --> {voice.stamp(b)}\n{t}' for i,(a,b,t) in enumerate(captions))+'\n')
 print(json.dumps({'film_seconds':cursor,'narration_seconds':sum(r['seconds'] for r in receipts)}))
 if cursor>=120:raise SystemExit('Edit needs shortening before rendering')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','voice']);a=p.parse_args();{'prepare':prepare,'voice':narrate}[a.action]()
