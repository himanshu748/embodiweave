// Live samples and completed replays use positions supplied by the Python simulator.
const q = s => document.querySelector(s);
export class RunArena {
  constructor() {
    this.mode = '2d'; this.trace = []; this.key = null; this.view = null; this.R3 = null;
    this.paused = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.replay = null; this.finished = false; this.playing = false; this.index = 0; this.raf = null;
    q('#arenaPause').textContent = this.paused ? 'Show latest frame' : 'Pause view';
    document.querySelectorAll('[data-run-view]').forEach(b => b.addEventListener('click',()=>this.setMode(b.dataset.runView)));
    q('#arenaPause').addEventListener('click',()=> {
      if(this.replay) { this.playing = !this.playing; if(this.index >= this.trace.length-1) this.index = 0; this.animate(); }
      else { this.paused = !this.paused; if(!this.paused && this.latest) this.ingest([this.latest],true); else if(this.paused) { q('#arenaSource').textContent='View paused';q('#arenaCaption').textContent='The run continues on the server. Resume the view to see new frames.'; } }
      this.controls();
    });
    q('#arenaEpisode').addEventListener('change',()=>this.selectEpisode(Number(q('#arenaEpisode').value)));
    q('#arenaSeek').addEventListener('input',()=>{ this.playing=false; this.index=Number(q('#arenaSeek').value); this.render(); this.controls(); });
    this.draw2d();this.controls();
  }
  reset() { this.latest=null; this.trace=[]; this.key=null; this.replay=null; this.finished=false; this.playing=false; this.view?.dispose(); this.view=null; q('#arenaSeek').disabled=true; q('#arenaReplay').disabled=true; q('#arenaEpisode').hidden=true; q('#arenaSource').textContent='Waiting for simulator'; q('#arenaCaption').textContent='The robot will appear here when training starts.'; this.controls(); this.draw2d(); }
  async setMode(mode) {
    if(mode==='3d' && !this.R3) {
      try { this.R3=await import('./robot3d.js?v=labels2'); if(!this.R3.webglOK()) throw new Error(); }
      catch { q('[data-run-view="3d"]').disabled=true; q('#arenaCaption').textContent='3D is unavailable in this browser. You can use 2D.'; return; }
    }
    this.mode=mode; q('#arena2d').hidden=mode!=='2d'; q('#arena3d').hidden=mode!=='3d';
    document.querySelectorAll('[data-run-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.runView===mode)));
    this.render(true);
  }
  ingest(samples, force=false) {
    if(!samples.length || this.replay) return;
    this.latest=samples[samples.length-1]; if(this.paused && !force && this.trace.length) return;
    for(const sample of samples) {
      const key=`${sample.phase}:${sample.suite||''}:${sample.episode}`;
      if(this.key!==key) {this.key=key;this.trace=[];this.layout=sample.layout;this.worldChanged=true;}
      if(!this.trace.length || sample.frame.t > this.trace[this.trace.length-1].t) this.trace.push(sample.frame);
      else if(sample.frame.t===this.trace[this.trace.length-1].t) this.trace[this.trace.length-1]=sample.frame;
    }
    this.index=this.trace.length-1;
    q('#arenaSource').textContent=this.latest.phase==='train' ? 'Live training sample' : 'Live test sample';
    q('#arenaCaption').textContent=(this.latest.phase==='train' ? 'Environment 1 of 8' : `${this.latest.suite} · episode ${this.latest.episode+1}`)+` · simulator step ${this.latest.frame.t}. Positions are sampled while the server runs.`;
    this.render(); this.controls();
  }
  finish() {
    this.finished=true;
    if (this.replay) return;
    if (this.latest) {
      this.ingest([this.latest],true);
      q('#arenaSource').textContent='Last simulator sample';
      q('#arenaCaption').textContent=`Run finished. Last sample: ${this.latest.suite || 'training'} · episode ${this.latest.episode+1} · step ${this.latest.frame.t}. Load the run replay to explore complete episodes.`;
    } else { q('#arenaSource').textContent='No simulator frames';q('#arenaCaption').textContent='There are no live samples for this run. You can load its replay if testing completed.'; }
    this.controls();
  }
  loadReplay(data) {
    this.replay=data;this.playing=false;this.view?.dispose();this.view=null;
    const sel=q('#arenaEpisode');sel.replaceChildren();sel.hidden=false;
    data.episodes.forEach((e,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`Episode ${i+1} · seed ${e.seed} · ${e.outcome}`;sel.append(o);});
    this.selectEpisode(0);
  }
  selectEpisode(i) {
    const ep=this.replay.episodes[i];this.trace=ep.trace;this.layout=ep.layout;this.key=`replay:${i}`;this.worldChanged=true;
    this.index=matchMedia('(prefers-reduced-motion: reduce)').matches ? this.trace.length-1 : 0;
    this.playing=false;q('#arenaSeek').disabled=false;q('#arenaSeek').max=this.trace.length-1;
    q('#arenaSource').textContent='Replay of this run';q('#arenaCaption').textContent=`${this.replay.suite_id} · seed ${ep.seed} · ${ep.outcome}. These frames were saved during this run.`;
    this.render();this.controls();
  }
  controls() { q('#arenaPause').disabled=!this.trace.length || (this.finished && !this.replay); q('#arenaPause').textContent=this.replay ? (this.playing?'Pause replay':'Play replay') : this.paused?'Resume view':'Pause view';q('#arenaSeek').value=this.index; }
  animate() {
    if(this.raf) cancelAnimationFrame(this.raf); if(!this.playing) return;
    let last=0;
    const tick=now=>{ if(!this.playing) return; if(now-last>=70) {last=now;this.index=Math.min(this.index+1,this.trace.length-1);this.render();this.controls();if(this.index===this.trace.length-1) {this.playing=false;this.controls();return;}}this.raf=requestAnimationFrame(tick);};
    this.raf=requestAnimationFrame(tick);
  }
  render(force=false) {
    if(!this.trace.length) {this.draw2d();return;}
    q('#arenaStep').textContent=`Step ${this.trace[this.index].t}`;
    if(this.mode==='2d') {this.draw2d();return;}
    const ep={layout:this.layout,robot:this.trace.map(s=>s.robot),movers:this.trace.map(s=>s.movers),outcome:this.trace[this.trace.length-1].outcome};
    try {
      if(!this.view) this.view=new this.R3.Arena3D(q('#arena3d'),[{ep,body:'#ea580c'}],{fit:1.65});
      else if(this.worldChanged) this.view.setEpisodes([{ep,body:'#ea580c'}]);
      else if(!this.replay || force) this.view.updateEpisode(ep);
      this.worldChanged=false;this.view.setStep(this.index);this.view.resize();
    } catch { this.setMode('2d');q('#arenaCaption').textContent='The 3D view stopped. The 2D view is still available.'; }
  }
  draw2d() {
    const c=q('#arena2d'),ctx=c.getContext('2d'),w=c.width,sc=w/10,X=x=>x*sc,Y=y=>w-y*sc;
    ctx.fillStyle='#fbfaf7';ctx.fillRect(0,0,w,w);ctx.strokeStyle='#e4e0d5';ctx.lineWidth=1;
    for(let i=0;i<=10;i++){ctx.beginPath();ctx.moveTo(X(i),0);ctx.lineTo(X(i),w);ctx.moveTo(0,Y(i));ctx.lineTo(w,Y(i));ctx.stroke();}
    if(!this.trace.length){ctx.fillStyle='#555b62';ctx.font='18px "IBM Plex Sans", sans-serif';ctx.textAlign='center';ctx.fillText('Start training to see the robot',w/2,w/2);return;}
    const f=this.trace[this.index],l=this.layout;
    ctx.strokeStyle='#367341';ctx.lineWidth=3;ctx.beginPath();ctx.arc(X(l.goal[0]),Y(l.goal[1]),sc*.3,0,Math.PI*2);ctx.stroke();
    ctx.fillStyle='#7d838a';for(const [x,y,r]of l.statics){ctx.beginPath();ctx.arc(X(x),Y(y),r*sc,0,Math.PI*2);ctx.fill();}
    ctx.fillStyle='#2b4c7e';f.movers.forEach((m,i)=>{ctx.beginPath();ctx.arc(X(m[0]),Y(m[1]),l.movers[i][4]*sc,0,Math.PI*2);ctx.fill();});
    ctx.strokeStyle='#b93d0b';ctx.lineWidth=2;ctx.beginPath();this.trace.slice(0,this.index+1).forEach((p,i)=>i?ctx.lineTo(X(p.robot[0]),Y(p.robot[1])):ctx.moveTo(X(p.robot[0]),Y(p.robot[1])));ctx.stroke();
    const [x,y,a]=f.robot;ctx.fillStyle='#ea580c';ctx.beginPath();ctx.arc(X(x),Y(y),sc*.2,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#1b2026';ctx.beginPath();ctx.moveTo(X(x),Y(y));ctx.lineTo(X(x+Math.cos(a)*.35),Y(y+Math.sin(a)*.35));ctx.stroke();
    if(f.outcome){ctx.fillStyle=f.outcome==='success'?'#367341':'#a52b20';ctx.font='bold 18px "IBM Plex Sans", sans-serif';ctx.textAlign='left';ctx.fillText(f.outcome==='success'?'Goal reached':f.outcome==='collision'?'Collision':'Time limit',14,26);}
  }
}
