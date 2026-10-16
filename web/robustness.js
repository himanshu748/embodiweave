"use strict";
(() => {
  const $=s=>document.querySelector(s), pct=x=>`${(100*x).toFixed(1)}%`;
  const names={"static_crossing":"Target",open:"Open",static:"Static",crossing:"Crossing"};
  const families=["static_crossing","open","static","crossing"];
  function table(headers,rows){const t=document.createElement('table'),h=document.createElement('tr');
    headers.forEach(x=>{const th=document.createElement('th');th.scope='col';th.textContent=x;h.append(th);});t.append(h);
    rows.forEach(row=>{const tr=document.createElement('tr');row.forEach(x=>{const td=document.createElement('td');td.textContent=x;tr.append(td);});t.append(tr);});return t;}
  async function get(url){const r=await fetch(url,{signal:AbortSignal.timeout(15000)});if(!r.ok)throw new Error(`Service returned ${r.status}`);return r.json();}
  async function recorded(){try{const d=await get('media/robustness-evidence.json'),a=d.attempts.find(x=>x.policy_id===d.selected_policy);
    $('#validation').replaceChildren(table(['Suite','Success','Collisions / limit','Gate'],a.checks.map(c=>[c.suite_id,pct(c.success_rate),`${pct(c.collision_rate)} / ${pct(c.max_collision)}`,c.pass?'Pass':'Fail'])));
    $('#confirmation').replaceChildren(table(['Suite','Goals / 100','Collisions / limit','Timeouts','Result'],d.confirmation.results.map(r=>[names[r.family],Math.round(r.summary.success_rate*100),`${Math.round(r.summary.collision_rate*100)}/100 / ${pct(r.max_collision)}`,Math.round(r.summary.timeout_rate*100),r.pass?'Pass':'Fail'])));
    const limits=Object.fromEntries(d.confirmation.results.map(r=>[r.family,r.max_collision]));
    $('#transfer').replaceChildren(table(['Suite','Historical P-static-b collisions','New checkpoint collisions','Reference limit'],families.map(f=>{const b=d.transfer.find(r=>r.label==='deployed'&&r.family===f),n=d.transfer.find(r=>r.label==='robust'&&r.family===f);return [names[f],`${b.summary.collision}/40`,`${n.summary.collision}/40`,pct(limits[f])];})));
    $('#bundle').href=a.bundle_url;$('#bundle').textContent='Download the checkpoint and evidence bundle';
  }catch(e){['validation','confirmation','transfer'].forEach(id=>{$('#'+id).textContent='Recorded results could not load. Reload or open the source evidence.';});$('#error').textContent=e.message;}}
  async function query(){$('#query').disabled=true;$('#queryStatus').textContent='Querying FalkorDB…';try{const r=await get('api/robustness/lineage');$('#cypher').textContent=r.cypher;$('#receipt').textContent=JSON.stringify(r,null,2);
    const rows=r.rows.map(row=>Object.fromEntries(r.header.map((h,i)=>[h,row[i]])));
    $('#rows').replaceChildren(table(['Origin','Intervention','Candidate','Validation verdict'],rows.slice(0,1).map(x=>[x.origin,x.intervention,x.candidate,x.verdict])));
    $('#queryStatus').textContent=rows.length?`${rows.length} evidence rows from GRAPH.RO_QUERY, graph revision ${r.graph_revision}.`:'No decision records are loaded yet. Recorded measurements remain above.';
  }catch(e){$('#queryStatus').textContent='The live graph did not answer. Retry in a moment; recorded results remain above.';}finally{$('#query').disabled=false;}}
  $('#query').addEventListener('click',query);recorded();
})();
