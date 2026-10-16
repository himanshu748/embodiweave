'use strict';
const $ = id => document.getElementById(id);
const percent = n => `${(n*100).toFixed(1)}%`;
function table(id, headers, rows) {
  const t=document.createElement('table');
  const h=t.createTHead().insertRow();
  headers.forEach(label=>{const c=document.createElement('th');c.scope='col';c.textContent=label;h.append(c);});
  const body=t.createTBody();
  rows.forEach(row=>{const r=body.insertRow();row.forEach(value=>{r.insertCell().textContent=String(value);});});
  $(id).replaceChildren(t);
}
async function load() {
  try {
    const response=await fetch('media/physics-evidence.json');
    if(!response.ok) throw new Error('The evidence index could not be loaded.');
    const s=await response.json();
    $('verdict').textContent=s.physics_confirmation ? (s.physics_confirmation_pass ? 'The selected mixed-domain checkpoint met all four physics confirmation requirements.' : 'The frozen candidate failed one or more physics confirmation requirements. The result stays visible.') : (s.selected_policy ? 'Selection is frozen. The one-time physics confirmation has not completed.' : 'No candidate has completed the registered selection rule. Physics confirmation remains unopened.');
    const order=['static_crossing','open','static','crossing'];
    table('trials',['Candidate / recipe','2D validation','Target / 10%','Open / 5%','Static / 10%','Crossing / 15%','Selection / extra clearance','PPO steps'],s.attempts.map(a=>[`${a.policy_id} / ${a.recipe}`,`${a.canonical_checks.filter(c=>c.pass).length}/4`,...order.map(f=>{const r=a.physics_development.find(r=>r.family===f);return `${r.summary.collision}/${r.summary.episodes} (${r.pass?'Pass':'Fail'})`;}),`${a.validation_suites_passed}/8; ${a.physics_clearance_deficit} episodes short of clearance`,a.actual_steps]));
    if(s.physics_confirmation) table('confirmation',['Family','Goals','Collisions / limit','Timeouts','Result'],s.physics_confirmation.map(r=>[r.family,`${r.summary.success}/${r.summary.episodes}`,`${r.summary.collision}/${r.summary.episodes} / ${percent(r.max_collision)}`,r.summary.timeout,r.pass?'Pass':'Fail']));
    else $('confirmation').textContent='No completed confirmation. Development results are shown separately above.';
  } catch(e) {
    $('verdict').textContent='The study evidence could not be loaded. Reload this page or open the repository evidence link.';
    $('trials').textContent='Results unavailable. No verdict is inferred.';
    $('confirmation').textContent='Confirmation status unavailable.';
  }
}
$('query').addEventListener('click',async()=>{
  $('query').disabled=true;$('queryStatus').textContent='Querying FalkorDB…';$('error').textContent='';
  try {
    const response=await fetch('/api/physics/lineage');
    if(!response.ok)throw new Error('FalkorDB did not return the lineage. Try again shortly.');
    const r=await response.json();$('cypher').textContent=r.cypher;$('receipt').textContent=JSON.stringify(r,null,2);
    if(r.rows.length)table('rows',r.header,r.rows.map(row=>row.map(v=>v===null?'':typeof v==='object'?JSON.stringify(v):v)));
    else $('rows').textContent='No completed physics decisions are present in this graph.';
    $('queryStatus').textContent=`${r.rows.length} returned records from live FalkorDB. Graph revision ${r.graph_revision}.`;
  }catch(e){$('queryStatus').textContent='The live graph query did not complete.';$('error').textContent=e.message;}
  finally{$('query').disabled=false;}
});
load();
