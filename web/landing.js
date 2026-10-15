// Landing page. Every number comes from the studio API (records and live FalkorDB) or from
// hero-replay.json, a trimmed copy of two stored simulator replays (scripts/make_hero_replay.py).
const $ = (s) => document.querySelector(s);
const pct = (x) => (x == null ? "n/a" : `${Math.round(x * 100)}%`);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const get = (u) => fetch(u).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${u}: ${r.status}`))));
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- live status ----------
async function live() {
  try {
    const s = await get("api/status");
    $("#liveDot").className = "dot " + (s.graph.up ? "up" : "down");
    $("#liveText").innerHTML = s.graph.up
      ? `FalkorDB live, graph revision <b class="mono">${s.graph.revision}</b>, deployed <b class="mono">${esc(s.deployed_policy)}</b>`
      : "FalkorDB is down. Recorded evidence is still browsable in the studio.";
  } catch {
    $("#liveDot").className = "dot down";
    $("#liveText").textContent = "Studio API not reachable. Refresh to retry.";
  }
}

// ---------- signature: two recorded episodes, same seed ----------
const WORLD = 10, S = 100 / WORLD, NS = "http://www.w3.org/2000/svg";
const X = (x) => x * S, Y = (y) => 100 - y * S;
function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  parent?.appendChild(e);
  return e;
}
function buildArena(svg, ep) {
  svg.replaceChildren();
  const g = el("g", { stroke: "var(--alt)", "stroke-width": ".3" }, svg);
  for (let i = 1; i < WORLD; i++) { el("line", { x1: i * S, y1: 0, x2: i * S, y2: 100 }, g); el("line", { x1: 0, y1: i * S, x2: 100, y2: i * S }, g); }
  const [gx, gy] = ep.layout.goal;
  el("circle", { cx: X(gx), cy: Y(gy), r: 3, fill: "none", stroke: "var(--goal)", "stroke-width": "1" }, svg);
  el("circle", { cx: X(gx), cy: Y(gy), r: .9, fill: "var(--goal)" }, svg);
  for (const s of ep.layout.statics) el("circle", { cx: X(s[0]), cy: Y(s[1]), r: s[2] * S, fill: "var(--obs)" }, svg);
  const mr = ep.layout.movers.map((m) => m[4] * S);
  const pedTrail = el("polyline", { fill: "none", stroke: "var(--ped)", "stroke-width": ".7", opacity: ".35" }, svg);
  const ped = mr.map((r) => el("circle", { r, fill: "var(--ped)" }, svg));
  const trail = el("polyline", { fill: "none", stroke: "var(--robot)", "stroke-width": "1.1", "stroke-linejoin": "round" }, svg);
  const bot = el("g", {}, svg);
  el("circle", { r: 2, fill: "var(--robot)" }, bot);
  el("line", { x1: 0, y1: 0, x2: 3.2, y2: 0, stroke: "var(--paper)", "stroke-width": ".8", "stroke-linecap": "round" }, bot);
  const mark = el("text", { "font-size": "7", "font-weight": "700", "text-anchor": "middle", "dominant-baseline": "central", opacity: 0 }, svg);
  return { ep, trail, pedTrail, ped, bot, mark };
}
function drawFrame(a, k) {
  const { ep } = a, n = ep.robot.length - 1, t = Math.min(k, n);
  a.trail.setAttribute("points", ep.robot.slice(0, t + 1).map((r) => `${X(r[0]).toFixed(2)},${Y(r[1]).toFixed(2)}`).join(" "));
  const r = ep.robot[t];
  a.bot.setAttribute("transform", `translate(${X(r[0]).toFixed(2)} ${Y(r[1]).toFixed(2)}) rotate(${(-r[2] * 180 / Math.PI).toFixed(1)})`);
  ep.movers[t].forEach((m, i) => { a.ped[i].setAttribute("cx", X(m[0])); a.ped[i].setAttribute("cy", Y(m[1])); });
  const lo = Math.max(0, t - 40);
  a.pedTrail.setAttribute("points", ep.movers.slice(lo, t + 1).map((ms) => `${X(ms[0][0]).toFixed(2)},${Y(ms[0][1]).toFixed(2)}`).join(" "));
  const done = t === n;
  a.mark.setAttribute("opacity", done ? 1 : 0);
  if (done) {
    const hit = ep.outcome === "collision";
    a.mark.textContent = hit ? "✕" : "✓";
    a.mark.setAttribute("fill", hit ? "var(--bad)" : "var(--ok)");
    a.mark.setAttribute("x", X(r[0])); a.mark.setAttribute("y", Y(r[1]) - 6);
  }
  return done;
}
function outcomeText(ep, foot) {
  const steps = ep.robot.length - 1;
  foot.className = "arena-foot " + (ep.outcome === "success" ? "ok" : "bad");
  foot.textContent = ep.outcome === "collision" ? `Collision at step ${steps}` : ep.outcome === "success" ? `Reached goal at step ${steps}` : `${ep.outcome} at step ${steps}`;
}
let raf = 0;
function play(A, B) {
  cancelAnimationFrame(raf);
  const total = Math.max(A.ep.robot.length, B.ep.robot.length) - 1;
  $("#outA").innerHTML = "&nbsp;"; $("#outB").innerHTML = "&nbsp;";
  const finish = () => { $("#prog").style.width = "100%"; drawFrame(A, total); drawFrame(B, total); $("#step").textContent = total; outcomeText(A.ep, $("#outA")); outcomeText(B.ep, $("#outB")); };
  if (reduced()) return finish();
  const STEPS_PER_S = 24, t0 = performance.now();
  let shownA = false;
  const tick = (now) => {
    const k = Math.max(0, Math.floor(((now - t0) / 1000) * STEPS_PER_S));
    if (drawFrame(A, k) && !shownA) { outcomeText(A.ep, $("#outA")); shownA = true; }
    drawFrame(B, k);
    $("#step").textContent = Math.min(k, total);
    $("#prog").style.width = `${(Math.min(k, total) / total) * 100}%`;
    if (k < total) raf = requestAnimationFrame(tick); else finish();
  };
  raf = requestAnimationFrame(tick);
}
async function hero() {
  const btn = $("#replayBtn");
  btn.disabled = true;
  try {
    const d = await get("hero-replay.json");
    $("#seed").textContent = d.before.seed;
    $("#labA").textContent = d.before.policy_id; $("#labB").textContent = d.after.policy_id;
    const A = buildArena($("#arenaA"), d.before), B = buildArena($("#arenaB"), d.after);
    drawFrame(A, 0); drawFrame(B, 0);
    btn.disabled = false;
    btn.addEventListener("click", () => play(A, B));
    // Play once when the replay is on screen; the visitor can replay it.
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); setTimeout(() => play(A, B), reduced() ? 0 : 450); } }, { threshold: .3 });
    io.observe($(".replay"));
  } catch {
    $("#replayCap span").textContent = "The recorded replay could not be loaded. Open the studio to browse every stored episode.";
    btn.hidden = true;
  }
}

// ---------- experiments ----------
async function results() {
  const body = $("#resultsTable tbody");
  try {
    const r = await get("api/results");
    const rows = (r.experiments || []).map((e) => {
      const arm = (n) => e.arms.find((a) => a.arm === n) || {};
      const g = arm("graph"), l = arm("latest"), b = arm("best_val");
      const best = Math.max(g.test_success ?? 0, l.test_success ?? 0, b.test_success ?? 0);
      const cell = (a) => `<td class="n ${a.test_success === best ? "win" : ""}">${pct(a.test_success)}<small>${pct(a.test_collision)} collisions</small></td>`;
      return `<tr><th scope="row">${esc(e.protocol.id)}</th><td class="mono">${esc(e.protocol.selection_rule)}</td>
        <td>${g.parent ? `<span class="mono">${esc(g.parent)}</span>` : "<span class='pill'>scratch</span>"}</td>${cell(g)}${cell(l)}${cell(b)}</tr>`;
    });
    body.innerHTML = rows.join("") || `<tr><td colspan="6" class="state">No experiments are recorded yet. Run one from the studio.</td></tr>`;
  } catch {
    body.innerHTML = `<tr><td colspan="6" class="state err">Results could not be loaded from the API. Refresh to retry.</td></tr>`;
  }
}

// ---------- live agent trace ----------
function stepFor(t) {
  const r = t.result || {}, a = t.args || {};
  switch (t.tool) {
    case "inspect_mission": {
      const s = r.deployed_target_evaluation?.summary || {};
      return ["Observe", `Deployed <span class="mono">${esc(r.deployed_policy)}</span> scores ${pct(s.success_rate)} success and ${pct(s.collision_rate)} collisions on target`];
    }
    case "query_graph": return ["Query", `<span class="mono">${esc(a.template)}</span> returned ${r.row_count ?? 0} rows from FalkorDB`];
    case "propose_adaptation": return ["Decide", esc(r.explanation || r.action)];
    case "start_training": return ["Train", `PPO, ${(r.budget || 0).toLocaleString()} steps, seed ${esc(a.seed)}, from ${r.parent ? `<span class="mono">${esc(r.parent)}</span>` : "scratch"}`];
    case "wait_for_job": {
      const j = r.result || {};
      if (r.kind === "transfer_trial") return ["Train", `Finished ${(r.consumed_steps || 0).toLocaleString()} steps, threshold ${j.threshold_reached ? "reached" : "not reached"}`];
      const s = j.summary || {};
      return ["Measure", `${pct(s.success_rate)} success and ${pct(s.collision_rate)} collisions over ${s.episodes} episodes`];
    }
    case "evaluate_checkpoint": return ["Measure", `Queued suite <span class="mono">${esc(a.suite_id)}</span>`];
    case "request_promotion": return ["Gate", `Verdict: <b>${esc(r.verdict)}</b>`];
    case "export_evidence": return ["Export", `Evidence bundle <span class="mono">${esc(r.bundle)}</span>`];
    default: return [esc(t.tool), ""];
  }
}
function fillStats(calls) {
  const im = calls.find((c) => c.tool === "inspect_mission")?.result?.deployed_target_evaluation?.summary;
  const prom = calls.find((c) => c.tool === "request_promotion")?.result;
  const tgt = prom?.checks?.find((c) => c.role === "target");
  if (im) { $("#sBefore").textContent = pct(im.success_rate); $("#cBefore").textContent = pct(im.collision_rate); }
  if (tgt) { $("#sAfter").textContent = pct(tgt.success_rate); $("#cAfter").textContent = pct(tgt.collision_rate); }
  if (prom) {
    const failed = (prom.checks || []).filter((c) => !c.pass).length, n = (prom.checks || []).length;
    $("#gate").textContent = prom.verdict === "promoted" ? "Promoted" : "Rejected";
    $("#gate").className = "num " + (prom.verdict === "promoted" ? "good" : "bad");
    $("#gateCap").textContent = prom.verdict === "promoted" ? `all ${n} suites passed` : `${failed} of ${n} suites failed, deployed policy kept`;
  }
}
async function agent() {
  const sub = $("#agentSub");
  try {
    const list = await get("api/agent_traces");
    const llm = list.filter((t) => t.mode === "llm-agent").sort((x, y) => (x.recorded_at < y.recorded_at ? 1 : -1));
    for (const meta of llm) {
      const t = await get(`api/agent_traces/${encodeURIComponent(meta.id)}`);
      const calls = (t.transcript || []).filter((x) => x.tool);
      const prom = calls.find((x) => x.tool === "request_promotion");
      if (!prom) continue;
      fillStats(calls);
      sub.innerHTML = `<b class="mono">${esc(t.model)}</b> via ${esc(t.provider)} chose every tool call over MCP: ${calls.length} calls in ${Math.round(t.wall_s)} seconds. Trace <span class="mono">${esc(t.id)}</span>.`;
      const items = calls.map((c) => { const [k, v] = stepFor(c); return `<li class="step k-${k.toLowerCase()}"><span class="k">${k}</span><span class="v">${v}</span></li>`; });
      const ol = $("#agentSteps"), SHOW = 7;
      ol.innerHTML = items.slice(0, SHOW).join("");
      if (items.length > SHOW) {
        const li = document.createElement("li"); li.className = "more";
        li.innerHTML = `<button type="button" class="btn ghost small">Show all ${items.length} calls</button>`;
        li.querySelector("button").addEventListener("click", () => { ol.innerHTML = items.join(""); });
        ol.appendChild(li);
      }
      const p = prom.result, ok = p.verdict === "promoted", v = $("#agentVerdict");
      v.className = "verdict " + (ok ? "ok" : "");
      v.innerHTML = `<h3>Promotion ${esc(p.verdict)}</h3><ul>${(p.reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <p>The gate makes the call, not the model. A rejected checkpoint stays out of deployment and its evidence stays in the graph for the next decision.</p>`;
      v.hidden = false;
      return;
    }
    sub.textContent = "No LLM run with a promotion request is recorded yet. Run python -m ew.agent llm locally to record one.";
  } catch {
    sub.textContent = "Agent traces could not be loaded from the API. Refresh to retry.";
  }
}

// ---------- graph schema (hand-built SVG of the real node labels and relationship types) ----------
const NODES = {
  Robot: [590, 40], Contract: [470, 120], Run: [120, 70], Policy: [300, 215], Family: [610, 215],
  Trial: [470, 300], Origin: [620, 390], Evaluation: [120, 330], Suite: [120, 440], Failure: [300, 400], Hypothesis: [470, 440],
};
const EDGES = [
  ["Run", "Policy", "PRODUCED"], ["Policy", "Contract", "USES_CONTRACT"], ["Contract", "Robot", "FOR_ROBOT"],
  ["Evaluation", "Policy", "ASSESSED"], ["Evaluation", "Suite", "ON_SUITE"], ["Failure", "Evaluation", "OBSERVED_IN"],
  ["Hypothesis", "Failure", "ABOUT"], ["Trial", "Policy", "FROM_PARENT"], ["Trial", "Origin", "FROM_ORIGIN"],
  ["Trial", "Family", "TARGETS"], ["Trial", "Contract", "UNDER_CONTRACT"], ["Policy", "Policy", "DERIVED_FROM"],
];
function schema() {
  const svg = $("#schema");
  if (!svg) return;
  const defs = el("defs", {}, svg);
  const m = el("marker", { id: "arw", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
  el("path", { d: "M0,0 L10,5 L0,10 z", fill: "context-stroke" }, m);
  const W = (name) => name.length * 8.6 + 28, H = 32;
  const edgeEls = [];
  for (const [a, b, rel] of EDGES) {
    const g = el("g", { class: "edge", "data-a": a, "data-b": b }, svg);
    const [x1, y1] = NODES[a], [x2, y2] = NODES[b];
    let d, lx, ly;
    if (a === b) { d = `M${x1 + 30},${y1 - 16} C${x1 + 70},${y1 - 80} ${x1 - 70},${y1 - 80} ${x1 - 30},${y1 - 16}`; lx = x1; ly = y1 - 66; }
    else {
      // shorten the line to stop at the target pill's edge
      const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L;
      const pad = (n) => Math.min(Math.abs((W(n) / 2) / (ux || 1e-6)), Math.abs((H / 2) / (uy || 1e-6))) + 4;
      const sx = x1 + ux * pad(a), sy = y1 + uy * pad(a), ex = x2 - ux * pad(b), ey = y2 - uy * pad(b);
      d = `M${sx.toFixed(1)},${sy.toFixed(1)} L${ex.toFixed(1)},${ey.toFixed(1)}`; lx = (sx + ex) / 2; ly = (sy + ey) / 2 - 6;
    }
    el("path", { d, fill: "none", "marker-end": "url(#arw)" }, g);
    const t = el("text", { x: lx, y: ly, "text-anchor": "middle" }, g); t.textContent = rel;
    edgeEls.push(g);
  }
  for (const [name, [x, y]] of Object.entries(NODES)) {
    const g = el("g", { class: "node" + (name === "Policy" ? " hub" : ""), tabindex: 0, "data-n": name, transform: `translate(${x} ${y})` }, svg);
    el("rect", { x: -W(name) / 2, y: -H / 2, width: W(name), height: H, rx: 16 }, g);
    const t = el("text", { "text-anchor": "middle", "dominant-baseline": "central" }, g); t.textContent = name;
    const on = () => { svg.classList.add("focus"); edgeEls.forEach((e) => e.classList.toggle("lit", e.dataset.a === name || e.dataset.b === name)); g.classList.add("lit"); };
    const off = () => { svg.classList.remove("focus"); edgeEls.forEach((e) => e.classList.remove("lit")); g.classList.remove("lit"); };
    g.addEventListener("mouseenter", on); g.addEventListener("mouseleave", off); g.addEventListener("focus", on); g.addEventListener("blur", off);
  }
}

// ---------- once-only section reveals (content stays visible if this never runs) ----------
function reveals() {
  if (reduced() || !("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.remove("pending"); io.unobserve(e.target); } }), { threshold: .15 });
  document.querySelectorAll(".reveal").forEach((n) => {
    if (n.getBoundingClientRect().top > innerHeight) { n.classList.add("pending"); io.observe(n); }
  });
}

reveals(); schema(); live(); hero(); results(); agent();
setInterval(live, 15000);
