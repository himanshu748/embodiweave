"""Put measured physics records in README without touching historical result tables."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def sync():
 s=json.loads((ROOT/'evidence/physics-adapt-v1/summary.json').read_text())
 order=['static_crossing','open','static','crossing']
 lines=['<!-- physics-adapt-v1:start -->','## Separate MuJoCo adaptation','',
 '**These new checkpoints train in both 2D and MuJoCo.** The unchanged-weight transfer measurements above remain frozen. This preregistered study uses fresh physics development suites and keeps the confirmed 2D parent as the default 2D demo policy.','',
 '| Completed trial | Original 2D gate | Physics target | Physics open | Physics static | Physics crossing | Selection |',
 '|---|---:|---:|---:|---:|---:|---|',
 '| **Collision limit (maximum)** | Four suites | **10%** | **5%** | **10%** | **15%** | Extra clearance required |']
 for a in s['attempts']:
  cells=[]
  for f in order:
   r=next(r for r in a['physics_development'] if r['family']==f)
   cells.append(f"{r['summary']['collision']}/{r['summary']['episodes']} ({'Pass' if r['pass'] else 'Fail'})")
  passed=sum(c['pass'] for c in a['canonical_checks'])
  label=a['recipe']+(' (600k follow-up)' if a.get('study')=='physics-followup-v1' else '')
  count=a['physics_clearance_deficit']
  lines.append('| '+label+' | '+str(passed)+'/4 | '+' | '.join(cells)+f" | {a['validation_suites_passed']}/8; {count} {'episode' if count==1 else 'episodes'} short of clearance |")
 lines += ['', 'Physics cells show collision counts on 40 development episodes per family. Pass also requires the original success floors: target 80%, open 90%, static 75%, crossing 75%. The original three trials request 300,000 steps each; a separately preregistered longer follow-up requests 600,000. All use fixed seed 23. Actual rollout-rounded steps and exact artifact hashes are in the evidence index. The authored graph rule requires all eight validation suites plus one episode of physics collision clearance before selection stops. Promo-1 code and thresholds are unchanged.','']
 if s['physics_confirmation']:
  lines += ['### One fresh physics confirmation','',
   ('The frozen mixed-domain candidate met all four physics confirmation requirements.' if s['physics_confirmation_pass'] else 'The frozen mixed-domain candidate failed one or more physics confirmation requirements. No training followed this confirmation.'),
   '', '| Physics confirmation | Target | Open | Static | Crossing |','|---|---:|---:|---:|---:|','| **Collision limit (maximum)** | **10%** | **5%** | **10%** | **15%** |']
  for label,key in [('Goals','success'),('Collisions','collision'),('Timeouts','timeout')]:
   lines.append('| '+label+' | '+' | '.join(str(next(r for r in s['physics_confirmation'] if r['family']==f)['summary'][key])+'/100' for f in order)+' |')
  lines+=['',f"Frozen policy: `{s['selected_policy']}`. The single batch contains 400 physics episodes, opened after selection stopped. Confirmation outcomes never entered FalkorDB. No new 2D held-out evaluation was authorized for this child.",'']
 else:lines += ['No new child has completed the registered physics selection rule. The one-time physics confirmation remains unopened.','']
 lines += ['[Recorded physics comparison](https://embodiweave.52.202.25.181.sslip.io/physics.html#replay) · [Physics judge page](https://embodiweave.52.202.25.181.sslip.io/physics.html) · [Protocol and interpretation](docs/physics-adaptation.md) · [Every episode and checksum](evidence/physics-adapt-v1/)','',
 'Successful simulation does not establish hardware safety. The base uses velocity servos and scripted pedestrians; the documented dynamics and sensor mismatches remain.','<!-- physics-adapt-v1:end -->','']
 p=ROOT/'README.md';text=p.read_text();block='\n'.join(lines)
 if '<!-- physics-adapt-v1:start -->' in text:
  start=text.index('<!-- physics-adapt-v1:start -->');end=text.index('<!-- physics-adapt-v1:end -->')+len('<!-- physics-adapt-v1:end -->');text=text[:start]+block.rstrip()+text[end:]
 else:text=text.replace('## Earlier study: search-v1',block+'\n## Earlier study: search-v1')
 text=text.replace('No physics safety claim is made, and no MuJoCo outcome is used for further tuning.','No physics safety claim is made. This transfer study remains frozen; the separately authorized adaptation below uses new physics development suites.')
 p.write_text(text)

if __name__=='__main__':sync()
