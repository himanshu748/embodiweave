'use strict';
(() => {
  const $=id=>document.getElementById(id), cache=new Map();
  const text=(tag,value,cls)=>{const node=document.createElement(tag);node.textContent=value;if(cls)node.className=cls;return node;};
  async function read(url){const response=await fetch(url,{signal:AbortSignal.timeout(45000)});const data=await response.json();if(!response.ok||data.error)throw new Error(data.error||data.detail||'Graph read failed');return data;}
  function paintDepth(depth,data){
    const box=$(`depth${depth}`);box.replaceChildren(text('h3',`Depth ${depth}`));
    const rows=data.origin_ranking||[],eligible=rows.filter(r=>!r.excluded).length;
    box.append(text('p',`${eligible} eligible; ${rows.length-eligible} excluded. Live graph revision ${data.queries?.at(-1)?.graph_revision ?? 'unavailable'}.`,'fine'));
    if(!rows.length)box.append(text('p',data.outcome==='unknown_policy'?'Target policy is not in the graph.':'No complete origin rows were returned. This is not evidence of safety.'));
    for(const row of rows){
      const item=document.createElement('details'),summary=document.createElement('summary');
      const state=row.unexamined_ancestors?.length?'unexamined, excluded':row.excluded?'excluded':'eligible';
      summary.append(text('code',row.origin_id),text('span',state,'origin-state'));item.append(summary);
      item.append(text('p',`Failed suites: ${row.failed_suites}. Collision clearance: ${Number(row.collision_clearance).toFixed(4)}.`,'fine'));
      for(const reason of [...row.reasons,...(row.unexamined_paths||[])]){
        const p=text('p',`${reason.reason}. Outcome: ${reason.outcome_id||'not observed within this depth'}.`,'fine');
        p.append(text('code',reason.path.join(' → '),'lineage-route'));item.append(p);
      }
      if(!row.excluded)item.append(text('p','No exclusion found within this examined lineage. Eligibility is not safety.','fine'));
      box.append(item);
    }
  }
  function caption(){
    if(!cache.has(1)||!cache.has(8))return;
    const one=cache.get(1).origin_ranking||[],eight=cache.get(8).origin_ranking||[];
    const changed=one.filter(a=>!a.excluded&&eight.some(b=>b.origin_id===a.origin_id&&b.excluded)).length;
    const cleared=one.filter(a=>a.excluded&&eight.some(b=>b.origin_id===a.origin_id&&!b.excluded)).length;
    const deeper=eight.filter(r=>r.reasons.some(x=>x.path?.length>2)).length;
    $('depthCaption').textContent=`From depth 1 to depth 8: ${changed} origins change from eligible to excluded; ${cleared} change from excluded to eligible after examining more lineage. Depth 8 returns regression paths longer than one hop for ${deeper} origins. Unexamined lineage is excluded, never labelled safe.`;
  }
  async function loadDepth(depth){
    const button=document.querySelector(`[data-depth="${depth}"]`);button.disabled=true;
    $(`depth${depth}`).replaceChildren(text('p',`Reading depth ${depth} from FalkorDB...`));
    try{const data=await read(`/api/graph-guide/depth?max_hops=${depth}`);cache.set(depth,data);paintDepth(depth,data);caption();}
    catch(e){$(`depth${depth}`).replaceChildren(text('p',`Could not read depth ${depth}: ${e.message}. Select this depth to retry.`,'error'));}
    finally{button.disabled=false;}
  }
  document.querySelectorAll('[data-depth]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('[data-depth]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));loadDepth(Number(button.dataset.depth));
  }));
  $('lineageTool').addEventListener('submit',async event=>{
    event.preventDefault();$('lineageRead').disabled=true;$('lineageResult').textContent='Resolving both policy IDs in FalkorDB...';
    try{const args=new URLSearchParams({from_policy:$('lineageFrom').value,to_policy:$('lineageTo').value});const data=await read(`/api/graph-guide/lineage-path?${args}`);
      $('lineageResult').textContent=data.outcome==='unknown_policy'?`Unknown policy: ${data.unknown_ids.join(', ')}. The algorithm was not run.`:
        data.paths.length?data.paths.map(p=>`${p.path.join(' → ')}\nUnweighted lineage distance: ${p.pathWeight}. Not a safety signal.`).join('\n'):
        'No outgoing lineage path found within eight hops. This does not establish safety.';
    }catch(e){$('lineageResult').textContent=`Could not read the lineage: ${e.message}. Retry when the graph is available.`;}
    finally{$('lineageRead').disabled=false;}
  });
  $('rationaleReview').addEventListener('click',async()=>{
    $('rationaleReview').disabled=true;$('rationaleStatus').textContent='Checking the saved v4 rationale against its returned rows...';
    try{const result=await read('/api/graph-guide/rationale-v4');$('rationaleStatus').textContent=result.note||'The sentence passed these lexical checks.';$('rationaleFlat').textContent=result.text;}
    catch(e){$('rationaleStatus').textContent=`Could not read the saved rationale: ${e.message}. Retry to check it.`;}
    finally{$('rationaleReview').disabled=false;}
  });
  // Both are read-only template calls; no LLM, decision write, training or evaluation.
  loadDepth(1);loadDepth(8);
})();
