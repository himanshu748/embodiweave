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
  function dicts(result){return result.rows.map(row=>Object.fromEntries(result.header.map((h,i)=>[h,row[i]])));}
  function decisionStory(origins){
    $('#decisionStory').hidden=!origins.length;
    if(!origins.length)return;
    const chosen=origins.find(x=>x.option===x.origin);
    if(!chosen)throw new Error('The selected origin is missing from the returned graph evidence.');
    $('#decisionReason').textContent=chosen.rationale;
    const path=$('#decisionPath');path.replaceChildren();
    for(const [edge,label,id] of [['Selected origin','Policy',chosen.origin],['← SELECTED','Decision',chosen.decision],['LAUNCHED →','Run',chosen.run],['PRODUCED →','Policy',chosen.candidate],['← FOR','Promotion',chosen.promotion]]){
      const li=document.createElement('li'),relation=document.createElement('span'),name=document.createElement('b'),code=document.createElement('code');
      relation.className='edge';relation.textContent=edge;name.textContent=label;code.textContent=id;li.append(relation,name,code);path.append(li);
    }
    const t=table(['Rank','Training origin / recipe','Suites passed','Clearance deficit','Choice'],origins.map(x=>{
      const key=JSON.parse(x.ranking_key);
      return [x.rank,`${x.option} / ${x.option_recipe||'recipe unavailable'}`,`${4-key[0]}/4`,`${key[1]} ${key[1]===1?'episode':'episodes'}`,x.option===x.origin?'Selected':'Lower ranked'];
    }));
    origins.forEach((x,i)=>{if(x.option===x.origin)t.rows[i+1].classList.add('selected');});
    $('#origins').replaceChildren(t);
  }
  async function query(){$('#query').disabled=true;$('#queryStatus').textContent='Querying FalkorDB…';$('#error').textContent='';$('#decisionStory').hidden=true;$('#rows').replaceChildren();try{const r=await get('api/robustness/lineage');$('#cypher').textContent=r.cypher;$('#receipt').textContent=JSON.stringify(r,null,2);
    const rows=dicts(r),origins=r.origins?dicts(r.origins):[];
    $('#rows').replaceChildren(table(['Origin evidence suite','Success','Collisions','Candidate 2D gate'],rows.map(x=>[x.evidence_suite,pct(x.origin_success),pct(x.origin_collisions),x.verdict])));
    decisionStory(origins);$('#originCypher').textContent=r.origins?.cypher||'';
    $('#queryStatus').textContent=origins.length?`${origins.length} ranked origins and ${rows.length} selected-parent validation rows from live GRAPH.RO_QUERY. Decision saved at revision ${origins[0].decision_revision}; current graph revision ${r.graph_revision}.`:'No decision records are loaded yet. Recorded measurements remain above.';
  }catch(e){$('#queryStatus').textContent='The live graph did not answer. Retry in a moment; recorded results remain above.';$('#error').textContent=e.message;$('#decisionStory').hidden=true;}finally{$('#query').disabled=false;}}
  $('#query').addEventListener('click',query);recorded();
})();
