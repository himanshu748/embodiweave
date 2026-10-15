"use strict";
const $ = s => document.querySelector(s);
const pct = x => `${(x * 100).toFixed(1)}%`;
const names = {"val-target-v1":"Target mission", "val-open-v1":"Open arena", "val-static-v1":"Static obstacles", "val-crossing-v1":"Crossing pedestrian"};
async function get(url) {
  const response = await fetch(url, {signal:AbortSignal.timeout(15000)});
  if (!response.ok) throw new Error(`Service returned ${response.status}`);
  return response.json();
}
function table(headers, rows) {
  const t=document.createElement("table"), head=document.createElement("tr");
  for (const label of headers) {const th=document.createElement("th");th.scope="col";th.textContent=label;head.append(th);}
  t.append(head);
  for (const row of rows) {const tr=document.createElement("tr");for(const value of row){const td=document.createElement("td");td.textContent=value??"—";tr.append(td);}t.append(tr);}
  return t;
}
async function recorded() {
  try {
    const data=await get("media/search-evidence.json");
    $("#headline").textContent=data.headline;
    const nodes=[{title:"Original checkpoint",outcome:`${data.origin.passed}/4 validation checks passed`,state:"rejected"},
      ...data.attempts.map((r,i)=>({title:i?"Rehearse earlier tasks":"Train longer",outcome:`${r.checks.filter(c=>c.pass).length}/4 validation checks passed`,state:r.verdict})),
      {title:"One held-out target test",outcome:`${pct(data.final_evaluation.metrics.collision_rate)} collisions · limit 10%`,state:"rejected"}];
    $("#lineage").replaceChildren();
    for(const node of nodes){const li=document.createElement("li"),title=document.createElement("b"),detail=document.createElement("span");title.textContent=node.title;detail.textContent=node.outcome;li.className=node.state;li.append(title,detail);$("#lineage").append(li);}
    $("#attempts").replaceChildren();
    for(const run of data.attempts){
      const article=document.createElement("article"), h=document.createElement("h3"), p=document.createElement("p"), region=document.createElement("div");
      h.textContent=`${run.label} · ${run.verdict === "promoted" ? "Passed validation gate" : "Rejected"}`;
      p.textContent=run.display_explanation;
      region.className="gate-values";region.tabIndex=0;region.setAttribute("role","region");region.setAttribute("aria-label",`${run.label} validation results`);
      region.append(table(["Suite","Success","Collisions","Gate"],run.checks.map(c=>[names[c.suite_id]||c.suite_id,pct(c.success_rate),pct(c.collision_rate),c.pass?"Pass":"Fail"])));
      const links=document.createElement("p"), replay=document.createElement("a"), bundle=document.createElement("a");
      replay.href=`studio.html?policy=${encodeURIComponent(run.policy_id)}`;replay.textContent="Replay this checkpoint";
      bundle.href=run.bundle_url;bundle.textContent="Download checksummed evidence";
      links.append(replay," · ",bundle);article.append(h,p,region,links);
      const details=document.createElement("details"), summary=document.createElement("summary"), pre=document.createElement("pre");
      summary.textContent="Checkpoint, source and decision IDs";pre.textContent=JSON.stringify(run,null,2);pre.tabIndex=0;details.append(summary,pre);article.append(details);$("#attempts").append(article);
    }
    if(data.final_evaluation){const p=document.createElement("p");p.textContent=data.final_evaluation.summary;$("#attempts").append(p);}
  } catch(_) {$("#recordedError").textContent="Recorded evidence could not load. Reload or open the source repository.";$("#attempts").replaceChildren();}
}
async function query(){
  $("#query").disabled=true;$("#queryStatus").textContent="Querying FalkorDB…";$("#recordedFallback").hidden=true;
  try{
    const r=await get("api/search/lineage");
    const unique=new Map();for(const row of r.rows){const x=Object.fromEntries(r.header.map((h,i)=>[h,row[i]]));unique.set(x.decision,x);}
    $("#cypher").textContent=r.cypher;$("#queryRows").replaceChildren(table(["Origin","Training change","Saved candidate","Validation gate"],[...unique.values()].map(x=>[x.origin,x.intervention,x.candidate,x.verdict])));
    $("#queryReceipt").textContent=JSON.stringify(r,null,2);
    $("#queryStatus").textContent=r.rows.length?`${r.rows.length} evidence rows returned by GRAPH.RO_QUERY at revision ${r.graph_revision}.` : "No search attempts are ingested in this graph yet. Recorded bundles remain available above.";
  }catch(_){$("#queryStatus").textContent="The live graph is unavailable. Retry in a moment.";$("#recordedFallback").hidden=false;}
  finally{$("#query").disabled=false;}
}
$("#query").addEventListener("click",query);
recorded();query();
