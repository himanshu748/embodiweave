"use strict";
// EmbodiWeave studio. Every value rendered here comes from the backend's records, jobs, or live graph queries.
const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined) e.append(k.nodeType ? k : String(k));
  return e;
};
const short = (h, n = 10) => (h ? String(h).slice(0, n) : "n/a");
const pct = (x) => (x === null || x === undefined ? "n/a" : (100 * x).toFixed(0) + "%");

const S = { status: null, catalog: [], evals: [], decisions: [], decision: null, replays: { A: null, B: null },
            ep: 0, t: 0, playing: false, speed: 1, mode: "Recorded", whatif: null, graphDown: false };

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "content-type": "application/json" }, ...opts });
  if (r.status === 503) { const j = await r.json(); setGraphDown(j.detail); throw new Error(j.detail); }
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (_) {} throw new Error(m); }
  return r.json();
}

function setMode(m) {
  S.mode = m;
  const b = $("#modeBadge");
  b.textContent = m; b.className = "badge mode " + (m === "Live" ? "live" : m === "What-if" ? "whatif" : "recorded");
}
function setGraphDown(detail) {
  S.graphDown = true;
  const b = $("#banner"); b.classList.remove("hidden");
  b.textContent = "FalkorDB is unreachable: graph-dependent decisions are stopped. Showing Recorded evidence only. (" + detail + ")";
  ["#btnPropose", "#btnEvalMissing", "#btnTrain", "#btnWhatIf"].forEach((s) => ($(s).disabled = true));
}

// ---------------- hosted read-only demo ----------------
// The hosted studio has no worker or torch. Controls that would train or evaluate are disabled with a reason,
// so nothing on screen is a dead button.
const WORKER_ONLY = ["#btnTrain", "#btnEvalMissing", "#scRun"];
const READONLY_WHY = "Hosted demo: training and evaluation run on the local setup (scripts/start.sh)";
function enterReadonly() {
  S.readonly = true;
  document.body.classList.add("readonly");
  WORKER_ONLY.forEach((x) => { const b = $(x); if (b) { b.disabled = true; b.title = READONLY_WHY; } });
  const n = $("#hostedNote");
  if (n) n.classList.remove("hidden");
}

// ---------------- status polling ----------------
async function pollStatus() {
  try {
    const s = await api("/api/status");
    S.status = s;
    const g = $("#graphBadge");
    if (s.graph.up) {
      g.textContent = `FalkorDB up · rev ${s.graph.revision}`; g.className = "badge up";
      if (S.graphDown) { S.graphDown = false; $("#banner").classList.add("hidden");
        ["#btnPropose", "#btnWhatIf"].forEach((x) => ($(x).disabled = false));
        if (!S.readonly) ["#btnEvalMissing", "#btnTrain"].forEach((x) => ($(x).disabled = false)); renderDecision(); }
    } else { g.textContent = "FalkorDB down"; g.className = "badge down"; setGraphDown("ping failed"); }
    const w = $("#workerBadge");
    if (s.hosted_readonly && !S.readonly) enterReadonly();
    if (s.hosted_readonly) { w.textContent = "Training runs locally"; w.className = "badge"; }
    else if (!s.worker.alive) { w.textContent = "Worker offline"; w.className = "badge down"; }
    else if (s.worker.running.length) { w.textContent = "Worker running 1 job"; w.className = "badge busy"; }
    else { w.textContent = "Worker idle"; w.className = "badge up"; }
    if (S.mode !== "What-if") setMode(s.worker.running.length ? "Live" : (S.liveScenario ? "Live" : "Recorded"));
  } catch (e) { /* banner already set */ }
}

// ---------------- arena ----------------
const WORLD = 10;
function drawArena(canvas, rep, ep, t) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width, sc = W / WORLD;
  const css = getComputedStyle(document.documentElement);
  const col = (n) => css.getPropertyValue(n).trim();
  ctx.clearRect(0, 0, W, W);
  ctx.fillStyle = col("--panel2"); ctx.fillRect(0, 0, W, W);
  ctx.strokeStyle = col("--grid"); ctx.lineWidth = 1;
  for (let i = 1; i < WORLD; i++) { ctx.beginPath(); ctx.moveTo(i * sc, 0); ctx.lineTo(i * sc, W); ctx.moveTo(0, i * sc); ctx.lineTo(W, i * sc); ctx.stroke(); }
  if (!rep || !rep.episodes[ep]) {
    ctx.fillStyle = col("--muted"); ctx.font = "14px system-ui"; ctx.textAlign = "center";
    ctx.fillText(rep ? "no episode" : "select an evaluation with a stored replay", W / 2, W / 2); return;
  }
  const e = rep.episodes[ep], tr = e.trace, k = Math.min(t, tr.length - 1), st = tr[k];
  const X = (x) => x * sc, Y = (y) => W - y * sc;
  // goal
  ctx.strokeStyle = col("--goal"); ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(X(e.layout.goal[0]), Y(e.layout.goal[1]), 0.3 * sc, 0, 7); ctx.stroke();
  ctx.beginPath(); ctx.arc(X(e.layout.goal[0]), Y(e.layout.goal[1]), 3, 0, 7); ctx.fillStyle = col("--goal"); ctx.fill();
  // statics
  ctx.fillStyle = col("--static");
  for (const s of e.layout.statics) { ctx.beginPath(); ctx.arc(X(s[0]), Y(s[1]), s[2] * sc, 0, 7); ctx.fill(); }
  // mover trail + body
  const mr = e.layout.movers.map((m) => m[4]);
  st.movers.forEach((m, i) => {
    ctx.strokeStyle = col("--mover"); ctx.globalAlpha = 0.25; ctx.lineWidth = 2; ctx.beginPath();
    for (let j = Math.max(0, k - 40); j <= k; j++) { const p = tr[j].movers[i]; j === Math.max(0, k - 40) ? ctx.moveTo(X(p[0]), Y(p[1])) : ctx.lineTo(X(p[0]), Y(p[1])); }
    ctx.stroke(); ctx.globalAlpha = 1;
    ctx.fillStyle = col("--mover"); ctx.beginPath(); ctx.arc(X(m[0]), Y(m[1]), mr[i] * sc, 0, 7); ctx.fill();
  });
  // robot trail
  ctx.strokeStyle = col("--robot"); ctx.lineWidth = 2; ctx.beginPath();
  for (let j = 0; j <= k; j++) { const r = tr[j].robot; j ? ctx.lineTo(X(r[0]), Y(r[1])) : ctx.moveTo(X(r[0]), Y(r[1])); }
  ctx.stroke();
  const r = st.robot;
  ctx.fillStyle = col("--robot"); ctx.beginPath(); ctx.arc(X(r[0]), Y(r[1]), 0.2 * sc, 0, 7); ctx.fill();
  ctx.strokeStyle = col("--bg"); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(X(r[0]), Y(r[1]));
  ctx.lineTo(X(r[0] + 0.32 * Math.cos(r[2])), Y(r[1] + 0.32 * Math.sin(r[2]))); ctx.stroke();
  // outcome marker
  const last = tr[tr.length - 1];
  if (k === tr.length - 1 && last.outcome) {
    const c = last.outcome === "success" ? col("--ok") : last.outcome === "collision" ? col("--bad") : col("--warn");
    const sym = last.outcome === "success" ? "✓" : last.outcome === "collision" ? "✕" : "◷";
    ctx.fillStyle = c; ctx.font = "bold 28px system-ui"; ctx.textAlign = "center"; ctx.fillText(sym, X(r[0]), Y(r[1]) - 14);
  }
  ctx.fillStyle = col("--muted"); ctx.font = "12px ui-monospace, monospace"; ctx.textAlign = "left";
  ctx.fillText(`t=${st.t}  v=${st.cmd[0].toFixed(2)} w=${st.cmd[1].toFixed(2)}`, 8, 16);
}

function maxT() {
  return Math.max(...["A", "B"].map((s) => { const r = S.replays[s]; return r && r.episodes[S.ep] ? r.episodes[S.ep].trace.length - 1 : 0; }));
}
// 3D view: the same recorded states rendered by web/robot3d.js (loaded on demand)
let R3 = null;
const V3 = { A: null, B: null };
function toEp(rep, i) {
  const e = rep && rep.episodes[i];
  if (!e) return null;
  return { layout: e.layout, robot: e.trace.map((s) => s.robot), movers: e.trace.map((s) => s.movers), outcome: e.trace[e.trace.length - 1].outcome };
}
function draw3d(side) {
  const rep = S.replays[side], key = rep ? `${rep.evaluation_id}:${S.ep}` : "";
  if (V3[side]?.key !== key) {
    V3[side]?.view.dispose(); V3[side] = null;
    const ep = toEp(rep, S.ep);
    if (ep) V3[side] = { key, view: new R3.Arena3D($("#v3" + side), [{ ep, body: side === "A" ? "#6b7480" : "#ea580c" }], { fit: 1.18 }) };
  }
  V3[side]?.view.setStep(S.t);
}
async function setArenaView(v) {
  if (v === "3d" && !R3) {
    try { R3 = await import("./robot3d.js"); if (!R3.webglOK()) throw new Error("no webgl"); }
    catch { R3 = null; v = "top"; document.querySelector('.viewtabs [data-view="3d"]').disabled = true; }
  }
  S.view3d = v === "3d";
  document.querySelectorAll(".viewtabs button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === v)));
  for (const s of ["A", "B"]) { $("#can" + s).hidden = S.view3d; $("#v3" + s).hidden = !S.view3d; }
  renderArena();
  if (S.view3d) for (const s of ["A", "B"]) V3[s]?.view.resize();
}
function renderArena() {
  if (S.view3d && R3) { try { draw3d("A"); draw3d("B"); } catch { setArenaView("top"); } }
  else { drawArena($("#canA"), S.replays.A, S.ep, S.t); drawArena($("#canB"), S.replays.B, S.ep, S.t); }
  $("#scrub").max = maxT(); $("#scrub").value = S.t; $("#tLabel").textContent = `t=${S.t}`;
  for (const s of ["A", "B"]) {
    const r = S.replays[s], m = $("#meta" + s);
    if (!r) { m.textContent = ""; continue; }
    const e = r.episodes[S.ep];
    m.innerHTML = "";
    m.append(el("b", {}, r.policy_id), ` · hash ${short(r.artifact_hash)} · ${r.suite_id} · seed ${e ? e.seed : "n/a"} · `,
      el("span", { class: e && e.outcome === "success" ? "ok" : e && e.outcome === "collision" ? "bad" : "warn" },
        e ? `${e.outcome}${e.hit ? " (" + e.hit + ")" : ""} at t=${e.steps}` : ""),
      el("br"), "evaluation ", el("span", { class: "chip", onclick: () => inspect(r.evaluation_id) }, r.evaluation_id),
      r._live ? el("span", { class: "badge small mode live" }, "Live") : el("span", { class: "badge small" }, "Recorded"));
  }
  const a = S.replays.A, b = S.replays.B, note = $("#matchNote");
  if (a && b) {
    const same = a.suite_id === b.suite_id && a.suite_id !== "custom" && a.episodes[S.ep] && b.episodes[S.ep] && a.episodes[S.ep].seed === b.episodes[S.ep].seed;
    note.className = same ? "note" : "note alert";
    note.textContent = same ? `Matched comparison: same suite (${a.suite_id}) and same scenario seed, so both robots face identical layouts.`
      : "Not a matched pair: suites or seeds differ, so the two panels show different scenarios.";
  } else note.textContent = "";
}
function fillEpisodes() {
  const sel = $("#episode"); sel.innerHTML = "";
  const n = Math.max(...["A", "B"].map((s) => (S.replays[s] ? S.replays[s].episodes.length : 0)), 0);
  for (let i = 0; i < n; i++) {
    const oa = S.replays.A?.episodes[i]?.outcome, ob = S.replays.B?.episodes[i]?.outcome;
    const sym = (o) => (o === "success" ? "✓" : o === "collision" ? "✕" : o === "timeout" ? "◷" : "·");
    sel.append(el("option", { value: i }, `#${i} ${sym(oa)} → ${sym(ob)}`));
  }
  S.ep = Math.min(S.ep, Math.max(0, n - 1)); sel.value = S.ep;
}
async function loadReplay(side, evalId) {
  if (!evalId) { S.replays[side] = null; fillEpisodes(); renderArena(); return; }
  try { S.replays[side] = await api(`/api/replay/${evalId}`); } catch (e) { S.replays[side] = null; }
  fillEpisodes(); S.t = 0; renderArena();
}
function tick() {
  if (S.playing) {
    S.t += S.speed;
    if (S.t >= maxT()) { S.t = maxT(); S.playing = false; $("#play").textContent = "▶"; }
    S.t = Math.floor(S.t); renderArena();
  }
  setTimeout(tick, 60);
}

function evalOption(e) {
  return el("option", { value: e.id }, `${e.policy_id} · ${e.suite_id} · ${pct(e.summary.success_rate)} ok / ${pct(e.summary.collision_rate)} coll · ${e.id.slice(-6)}`);
}
async function loadEvals() {
  S.evals = (await api("/api/evaluations")).filter((e) => e.has_replay);
  for (const side of ["A", "B"]) {
    const sel = $("#eval" + side), cur = sel.value; sel.innerHTML = "";
    sel.append(el("option", { value: "" }, "Choose an evaluation"));
    for (const e of S.evals.slice().reverse()) sel.append(evalOption(e));
    if (cur) sel.value = cur;
  }
}

// ---------------- decisions ----------------
async function loadDecisions(selectId) {
  S.decisions = await api("/api/decisions");
  const sel = $("#decisionSel"); sel.innerHTML = "";
  for (const d of S.decisions.slice().reverse())
    sel.append(el("option", { value: d.id }, `${d.recorded_at.slice(11, 19)} ${d.mode} · ${d.action} → ${d.selected || "n/a"} · rev ${d.graph_revision}`));
  if (selectId) sel.value = selectId;
  if (sel.value) await selectDecision(sel.value);
  else { $("#decisionHead").innerHTML = "<div class='empty'>No decisions yet. Propose one with the rule.</div>"; }
}
async function selectDecision(id) {
  S.decision = await api(`/api/decisions/${id}`);
  renderDecision(); renderQueries(); if (!$("#tab-graph").classList.contains("hidden")) renderGraph();
}
function modeBadge(m) {
  const cls = m === "what-if" ? "hyp" : m === "llm-agent" ? "measured" : "authored";
  const label = m === "what-if" ? "What-if (hypothetical)" : m === "llm-agent" ? "LLM agent" : "Deterministic rule run";
  return el("span", { class: "badge small " + cls }, label);
}
function childScore(c) {
  if (c.trial_child_score === undefined) return "";
  return el("div", { class: "hint", title: "mean (success - collision) on the validation suite of checkpoints these trials produced" },
    c.trial_child_score === null ? "no measured trial child" : `children score ${c.trial_child_score.toFixed(2)} (n=${c.n_trial_child_scores})`);
}
function renderDecision() {
  const d = S.decision; if (!d) return;
  $("#decisionMode").replaceWith(Object.assign(modeBadge(d.mode), { id: "decisionMode" }));
  const head = $("#decisionHead"); head.innerHTML = "";
  head.append(el("div", {}, el("span", { class: "act" }, d.action.replaceAll("_", " ")), d.selected ? [" → ", el("span", { class: "chip", onclick: () => inspect(d.selected) }, d.selected)] : "",
      `  ·  rule ${d.rule_version} · graph ${d.graph} rev ${d.graph_revision} · budget ${d.request.budget.toLocaleString()}`),
    el("div", { style: "margin-top:6px" }, d.explanation));
  if (d.needs_evaluation) head.append(el("div", { class: "note alert" }, "Missing matched validation: " + d.needs_evaluation.join(", ")));
  if (d.launched_trials && d.launched_trials.length) {
    for (const t of d.launched_trials) head.append(el("div", { style: "margin-top:6px" }, "Outcome: ",
      el("span", { class: "chip " + (t.threshold_reached ? "pass" : "fail"), onclick: () => inspect(t.id) }, t.id), " ",
      t.threshold_reached ? `reached threshold at ≤${t.steps_to_threshold.toLocaleString()} steps` : `not reached within ${t.consumed_steps.toLocaleString()} steps (steps-to-threshold unknown)`,
      t.child_policy_id ? [" · child ", el("span", { class: "chip", onclick: () => inspect(t.child_policy_id) }, t.child_policy_id)] : ""));
  }
  const tbl = $("#rankTbl"); tbl.innerHTML = "";
  tbl.append(el("tr", {}, ...["#", "Checkpoint", "Transfer estimate", "Matched validation", "Applicable trials", "Lineage"].map((h) => el("th", {}, h))));
  for (const c of d.ranking || []) {
    const v = c.validation;
    tbl.append(el("tr", { class: c.policy_id === d.selected ? "sel" : "" },
      el("td", {}, c.option_rank ?? c.rank),
      el("td", {}, el("span", { class: "chip", onclick: () => inspect(c.policy_id) }, c.policy_id)),
      el("td", {}, el("b", {}, c.p_reach.toFixed(2)), el("div", { class: c.p_basis.includes("WHAT-IF") ? "hint what" : "hint" }, c.p_basis)),
      el("td", {}, `${pct(v.success_rate)} ok · ${pct(v.collision_rate)} coll`, el("div", {}, el("span", { class: "chip", onclick: () => inspect(v.evaluation_id) }, v.evaluation_id.slice(-6)), ` n=${v.episodes}`)),
      el("td", {}, (c.trials || []).length ? (c.trials || []).map((t) => el("span", { class: "chip " + (t.hypothetical ? "hyp" : t.reached ? "pass" : "fail"),
          title: t.hypothetical ? "hypothetical (What-if)" : t.reached ? `reached at ≤${t.steps_to_threshold}` : "not reached within budget",
          onclick: () => t.hypothetical ? null : inspect(t.trial_id) }, (t.hypothetical ? "hyp " : "") + (t.reached ? "✓" : "✕") + " s" + (t.seed ?? "?"))) : el("span", { class: "hint" }, "none"),
          childScore(c)),
      el("td", { class: "hint" }, (c.lineage || []).filter((l) => l.depth > 0).map((l) => l.policy).join(" ← ") || "scratch")));
  }
  if (d.scratch_option) {
    const so = d.scratch_option;
    const srow = (el("tr", { class: d.action === "train_from_scratch" ? "sel" : "" },
      el("td", {}, so.option_rank ?? (d.action === "train_from_scratch" ? "1" : "n/a")),
      el("td", {}, el("span", { class: "chip" }, "Origin: scratch"), el("div", { class: "hint" }, "no parent weights")),
      el("td", {}, el("b", {}, so.p_reach.toFixed(2)), el("div", { class: "hint" }, so.p_basis)),
      el("td", { class: "hint" }, "n/a (no checkpoint yet)"),
      el("td", {}, (so.trials || []).length ? so.trials.map((t) => el("span", { class: "chip " + (t.hypothetical ? "hyp" : t.reached ? "pass" : "fail"),
          title: t.reached ? `reached at ≤${t.steps_to_threshold}` : "not reached within budget", onclick: () => inspect(t.trial_id) },
          (t.reached ? "✓" : "✕") + " s" + (t.seed ?? "?"))) : el("span", { class: "hint" }, "none"), childScore(so)),
      el("td", { class: "hint" }, "no parent")));
    if (so.option_rank && tbl.children[so.option_rank]) tbl.insertBefore(srow, tbl.children[so.option_rank]); else tbl.append(srow);
  }
  if (!(d.ranking || []).length) tbl.append(el("tr", {}, el("td", { colspan: 6, class: "empty" }, d.action === "evaluate_candidates" ? "Ranking withheld until every eligible candidate has matched validation." : "No eligible candidates.")));
  const rej = $("#rejected"); rej.innerHTML = "";
  const outside = d.rejected.filter((r) => r.reasons.every((x) => x.startsWith("outside requested catalog")));
  for (const r of d.rejected.filter((r) => !outside.includes(r)))
    rej.append(el("li", {}, el("span", { class: "chip", onclick: () => inspect(r.policy_id) }, r.policy_id), " ", r.reasons.join("; ")));
  if (outside.length) rej.append(el("li", {}, el("details", {}, el("summary", { class: "hint" }, `${outside.length} checkpoints outside the requested library catalog (trial children)`),
    ...outside.map((r) => el("div", {}, el("span", { class: "chip", onclick: () => inspect(r.policy_id) }, r.policy_id), " ", el("span", { class: "hint" }, r.reasons[0]))))));
  if (!d.rejected.length) rej.append(el("li", { class: "hint" }, "none"));
  $("#btnTrain").disabled = S.readonly || S.graphDown || d.mode === "what-if" || !["train_from_parent", "train_from_scratch"].includes(d.action);
  $("#btnEvalMissing").disabled = S.readonly || S.graphDown || d.action !== "evaluate_candidates";
}
function renderQueries() {
  const box = $("#queries"); box.innerHTML = "";
  const d = S.decision; if (!d) return;
  for (const q of d.queries) {
    box.append(el("div", { class: "qcard" },
      el("h4", {}, q.template, el("span", { class: "hint" }, `${q.ms} ms · ${q.graph} rev ${q.graph_revision} · ${q.rows.length} rows`)),
      el("div", { class: "hint" }, "params: ", el("code", {}, JSON.stringify(q.params))),
      el("div", {}, "returned: ", q.record_ids.length ? q.record_ids.map((id) => el("span", { class: "chip", onclick: () => inspect(id) }, id)) : el("span", { class: "hint" }, "no ids")),
      el("details", {}, el("summary", {}, "Cypher"), el("pre", { class: "code" }, q.cypher)),
      el("details", {}, el("summary", {}, "Rows"), el("pre", { class: "code" }, JSON.stringify(q.rows, null, 1)))));
  }
}

// ---------------- graph view ----------------
async function renderGraph() {
  const svg = $("#graphSvg"); svg.innerHTML = "";
  const d = S.decision; if (!d) return;
  let g;
  try { g = await api(`/api/subgraph/${d.id}`); }
  catch (e) { svg.innerHTML = `<text x="16" y="30">${e.message}</text>`; return; }
  $("#graphCypher").textContent = g.cypher + `\n\n-- ${g.ms} ms, graph revision ${g.graph_revision}`;
  const cols = { Decision: 0, Policy: 1, Origin: 1, Evaluation: 2, Trial: 2, Contract: 3 };
  const byCol = {}; g.nodes.forEach((n) => (byCol[cols[n.label] ?? 3] ||= []).push(n));
  const W = 820, colX = [50, 230, 450, 640], pos = {};
  const H = Math.max(460, 40 + 34 * Math.max(...Object.values(byCol).map((a) => a.length)));
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.style.height = H + "px";
  for (const [c, arr] of Object.entries(byCol)) arr.forEach((n, i) => (pos[n.id] = [colX[c], 30 + (i + 0.5) * (H - 40) / arr.length]));
  const ns = "http://www.w3.org/2000/svg", mk = (t, a) => { const e = document.createElementNS(ns, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
  for (const e of g.edges) {
    const [x1, y1] = pos[e.from], [x2, y2] = pos[e.to];
    svg.append(mk("path", { d: `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`, class: "edge " + e.type }));
    if (["SELECTED", "REJECTED", "CONSIDERED"].includes(e.type)) { const t = mk("text", { x: (x1 + x2) / 2, y: (y1 + y2) / 2 - 3, class: "elabel" }); t.textContent = e.type; svg.append(t); }
  }
  const css = getComputedStyle(document.documentElement), col = (n) => css.getPropertyValue(n).trim();
  const color = (n) => n.label === "Decision" ? col("--accent") : n.label === "Policy" ? (n.id === d.selected ? col("--accent") : col("--static"))
    : n.label === "Evaluation" ? col("--ok") : n.label === "Trial" ? (n.reached ? col("--ok") : col("--bad")) : col("--what");
  for (const n of g.nodes) {
    const [x, y] = pos[n.id], gEl = mk("g", { class: "node", tabindex: 0, role: "button", "aria-label": `${n.label} ${n.id}` });
    gEl.append(mk("circle", { cx: x, cy: y, r: n.label === "Decision" ? 11 : 8, fill: color(n) }));
    const t = mk("text", { x: x + 13, y: y + 4 });
    t.textContent = n.label === "Evaluation" ? `eval ${n.id.slice(-6)} ${pct(n.success_rate)}` : n.label === "Trial" ? `trial ${n.id.slice(-6)} ${n.reached ? "✓" : "✕"} ${n.budget / 1000}k` : n.id.length > 26 ? n.id.slice(0, 26) + "…" : n.id;
    gEl.append(t);
    const go = () => (n.label === "Contract" ? null : inspect(n.id));
    gEl.addEventListener("click", go); gEl.addEventListener("keydown", (ev) => ev.key === "Enter" && go());
    svg.append(gEl);
  }
}

// ---------------- jobs ----------------
async function renderJobs() {
  let js; try { js = await api("/api/jobs"); } catch (_) { return; }
  const box = $("#jobs"); box.innerHTML = "";
  if (!js.length) { box.append(el("div", { class: "empty" }, "No jobs yet.")); return; }
  for (const j of js.slice(0, 25)) {
    const budget = j.params.budget, steps = j.progress?.steps ?? j.consumed_steps ?? 0;
    const card = el("div", { class: "job" },
      el("div", { class: "top" }, el("b", {}, `${j.kind.replace("_", " ")} · ${j.state}`), el("span", { class: "hint mono" }, j.id)),
      j.kind === "transfer_trial" ? el("div", {}, `${j.params.parent_id} → ${j.params.child_id} · seed ${j.params.seed}`) : el("div", {}, `${j.params.policy_id} on ${j.params.suite_id}`));
    if (budget) card.append(el("div", { class: "bar", role: "progressbar", "aria-valuenow": steps, "aria-valuemax": budget }, el("i", { style: `width:${Math.min(100, 100 * steps / budget)}%` })),
      el("div", { class: "hint" }, `${steps.toLocaleString()} / ${budget.toLocaleString()} env steps` + (j.progress?.train_success_recent != null ? ` · recent training-episode success ${pct(j.progress.train_success_recent)}` : "")));
    if (j.error) card.append(el("div", { class: "bad" }, j.error));
    if (j.result) {
      const r = j.result;
      if (r.trial_id) card.append(el("div", {}, el("span", { class: "chip " + (r.threshold_reached ? "pass" : "fail"), onclick: () => inspect(r.trial_id) }, r.trial_id), " ",
        r.threshold_reached ? `threshold reached at ≤${r.steps_to_threshold}` : "threshold not reached within budget",
        " · val schedule ", (r.schedule || []).map((p) => `${(p.steps / 1000).toFixed(0)}k:${pct(p.success_rate)}`).join(" ")));
      if (r.evaluation_id) card.append(el("div", {}, el("span", { class: "chip", onclick: () => inspect(r.evaluation_id) }, r.evaluation_id), ` ${pct(r.summary.success_rate)} ok / ${pct(r.summary.collision_rate)} coll`));
      if (r.child_policy_id) {
        card.append(el("div", { class: "row" },
          el("button", { class: "needs-worker", disabled: S.readonly || null, title: S.readonly ? READONLY_WHY : null, onclick: async () => { for (const s of ["val-open-v1", "val-static-v1", "val-crossing-v1"]) await api("/api/evaluate", { method: "POST", body: JSON.stringify({ policy_id: r.child_policy_id, suite_id: s }) }); renderJobs(); } }, "Evaluate retained behaviours"),
          el("button", { class: "needs-worker", disabled: S.readonly || null, title: S.readonly ? READONLY_WHY : null, onclick: async (ev) => { const p = await api(`/api/promote/${r.child_policy_id}`, { method: "POST" }); ev.target.after(el("div", { class: p.verdict === "promoted" ? "ok" : "bad" }, `${p.verdict}: ${p.reasons.join("; ") || "all gates passed"}`)); } }, "Request promotion"),
          el("button", { class: "needs-worker", disabled: S.readonly || null, title: S.readonly ? READONLY_WHY : null, onclick: async (ev) => { const b = await api(`/api/export/${r.child_policy_id}`, { method: "POST" }); ev.target.after(el("a", { href: b.download }, ` download bundle (sha256 ${short(b.sha256, 12)})`)); } }, "Export"),
          el("button", { onclick: () => { $("#evalB").value = r.final_evaluation_id; loadReplay("B", r.final_evaluation_id); } }, "Replay as After")));
      }
    }
    if (["queued", "running"].includes(j.state)) card.append(el("button", { onclick: async () => { await api(`/api/jobs/${j.id}/cancel`, { method: "POST" }); renderJobs(); } }, "Cancel"));
    box.append(card);
  }
}

// ---------------- agent traces ----------------
async function loadTraces() {
  const cfg = await api("/api/agent/config");
  const start = $("#agentStart"), consent = $("#agentConsent");
  $("#agentAvailability").textContent = cfg.enabled ? `Ready: ${cfg.provider}. API usage may be billed by your provider.` : cfg.reason;
  consent.disabled = !cfg.enabled;
  const update = () => { start.disabled = !cfg.enabled || !consent.checked; };
  consent.onchange = update; update();
  start.onclick = (e) => busy(e.target, async () => {
    const session = await api("/api/agent/start", { method: "POST", body: JSON.stringify({ consent: consent.checked }) });
    $("#agentSession").textContent = `${session.id}: ${session.state}. Training progress is in Jobs.`;
    const poll = async () => {
      const result = await api(`/api/agent/sessions/${session.id}`);
      $("#agentSession").textContent = `${session.id}: ${result.state}`;
      if (result.state === "running") setTimeout(() => poll().catch(() => { $("#agentSession").textContent = "Session status unavailable. Check Jobs or refresh."; }), 3000);
      else if (result.trace_id) { await loadTraces(); $("#traceSel").value = result.trace_id; await renderTrace(result.trace_id); }
    };
    await poll();
  });
  const ts = await api("/api/agent_traces"); const sel = $("#traceSel"); sel.innerHTML = "";
  for (const t of ts.slice().reverse()) sel.append(el("option", { value: t.id }, `${t.recorded_at.slice(11, 19)} ${t.mode} · ${t.n_calls} tool calls`));
  if (sel.value) renderTrace(sel.value); else $("#trace").innerHTML = "<li class='empty'>No agent sessions yet.</li>";
}
async function renderTrace(id) {
  const t = await api(`/api/agent_traces/${id}`);
  $("#traceMode").textContent = t.mode === "llm-agent" ? `LLM agent · ${t.model}` : "Deterministic script (not an LLM run)";
  $("#traceMode").className = "badge small " + (t.mode === "llm-agent" ? "measured" : "authored");
  const ol = $("#trace"); ol.innerHTML = "";
  for (const c of t.server_log) {
    ol.append(el("li", {}, el("b", {}, c.tool), " ", el("span", { class: "hint" }, `rev ${c.graph_revision ?? "n/a"} · ${new Date(c.t * 1000).toLocaleTimeString()}`),
      c.error ? el("div", { class: "bad" }, c.error) : "",
      el("details", {}, el("summary", {}, "arguments / result"), el("pre", { class: "code" }, JSON.stringify({ args: c.args, result: c.result }, null, 1)))));
  }
  for (const x of t.transcript || []) if (x.assistant_text) ol.append(el("li", { class: "hint" }, "model: " + x.assistant_text));
  if (t.final_text) ol.append(el("li", {}, el("b", {}, "Final report: "), t.final_text));
}

// ---------------- results ----------------
async function renderResults() {
  const r = await api("/api/results"); const box = $("#results"); box.innerHTML = "";
  if (r.status === "not_run") { box.append(el("div", { class: "empty" }, "No comparison experiment has been reported yet.")); return; }
  box.append(el("p", { class: "hint" }, "Each experiment froze its protocol before running and used its own final-test suite once. " +
    "Arms that chose the same parent share the same runs. 3 training seeds per arm: treat differences as preliminary."));
  for (const x of r.experiments.slice().reverse()) {
    const p = x.protocol;
    box.append(el("h3", {}, `${p.id} · rule ${p.selection_rule} · final test ${p.final_test_suite}`),
      el("div", { class: "hint" }, `Frozen ${p.frozen_at}. ${p.budget.toLocaleString()} PPO steps per arm and seed; seeds ${p.comparison_seeds.join(", ")}.`));
    if (x.graph_explanation) box.append(el("div", { class: "note" }, "Graph decision: ", x.graph_decision ? el("span", { class: "chip", onclick: () => inspect(x.graph_decision) }, x.graph_decision.slice(-6)) : "", " ", x.graph_explanation));
    const tbl = el("table", { class: "tbl restbl" });
    tbl.append(el("tr", {}, ...["Arm", "Start", "Reached thr.", "Mean test success", "Mean test coll.", "Per seed test success"].map((h) => el("th", {}, h))));
    const best = Math.max(...x.arms.map((a) => a.test_success));
    for (const a of x.arms)
      tbl.append(el("tr", { class: a.arm === "graph" ? "sel" : "" }, el("td", {}, a.arm), el("td", {}, a.parent || "scratch"),
        el("td", { class: "num" }, `${a.reached}/${a.n}`),
        el("td", { class: "num" }, el(a.test_success === best ? "b" : "span", {}, pct(a.test_success))),
        el("td", { class: "num" }, pct(a.test_collision)),
        el("td", { class: "num hint" }, a.rows.map((row) => `s${row.seed} ${pct(row.final_test.success_rate)}`).join(" · "))));
    box.append(tbl);
  }
}

// ---------------- inspector ----------------
async function inspect(id) {
  if (!id) return;
  try {
    const r = await api(`/api/evidence/${encodeURIComponent(id)}`);
    $("#inspTitle").textContent = `${r.kind} · ${id}`;
    const measured = ["evaluation", "trial", "run", "policy", "promotion"].includes(r.kind);
    $("#inspKind").innerHTML = "";
    $("#inspKind").append(el("span", { class: "badge small " + (r.kind === "decision" && r.record.mode === "what-if" ? "hyp" : measured ? "measured" : "authored") },
      r.kind === "decision" ? `decision (${r.record.mode})` : measured ? "measured record" : r.kind));
    $("#inspBody").textContent = JSON.stringify(r.record, null, 1);
  } catch (e) { $("#inspTitle").textContent = id; $("#inspKind").textContent = ""; $("#inspBody").textContent = "Authored configuration or not a stored record: " + e.message; }
  $("#inspector").classList.remove("hidden"); $("#inspClose").focus();
}

// ---------------- wiring ----------------
function wire() {
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-selected", x === b));
    document.querySelectorAll(".tabpanel").forEach((p) => p.classList.toggle("hidden", p.id !== "tab-" + b.dataset.tab));
    ({ graph: renderGraph, jobs: renderJobs, agent: loadTraces, results: renderResults }[b.dataset.tab] || (() => {}))();
  }));
  $("#evalA").addEventListener("change", (e) => loadReplay("A", e.target.value));
  $("#evalB").addEventListener("change", (e) => loadReplay("B", e.target.value));
  $("#episode").addEventListener("change", (e) => { S.ep = +e.target.value; S.t = 0; renderArena(); });
  $("#scrub").addEventListener("input", (e) => { S.t = +e.target.value; renderArena(); });
  document.querySelectorAll(".viewtabs button").forEach((b) => b.addEventListener("click", () => setArenaView(b.dataset.view)));
  setArenaView("3d");
  $("#speed").addEventListener("change", (e) => (S.speed = +e.target.value));
  const toggle = () => { S.playing = !S.playing; if (S.playing && S.t >= maxT()) S.t = 0; $("#play").textContent = S.playing ? "⏸" : "▶"; $("#play").setAttribute("aria-label", S.playing ? "Pause" : "Play"); };
  $("#play").addEventListener("click", toggle);
  const ep = (d) => { const n = $("#episode").options.length; if (!n) return; S.ep = (S.ep + d + n) % n; $("#episode").value = S.ep; S.t = 0; renderArena(); };
  $("#prevEp").addEventListener("click", () => ep(-1)); $("#nextEp").addEventListener("click", () => ep(1));
  document.addEventListener("keydown", (e) => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (e.key === " ") { e.preventDefault(); toggle(); }
    else if (e.key === "ArrowRight") { S.t = Math.min(maxT(), S.t + 1); renderArena(); }
    else if (e.key === "ArrowLeft") { S.t = Math.max(0, S.t - 1); renderArena(); }
    else if (e.key === "]") ep(1); else if (e.key === "[") ep(-1);
    else if (e.key === "Escape") $("#inspector").classList.add("hidden");
  });
  $("#inspClose").addEventListener("click", () => $("#inspector").classList.add("hidden"));
  $("#decisionSel").addEventListener("change", (e) => { S.whatif = null; setMode("Recorded"); selectDecision(e.target.value); });
  const busy = async (btn, fn) => { btn.disabled = true; const t = btn.textContent; btn.classList.add("loading"); try { await fn(); } catch (e) { alert(e.message); } finally { btn.disabled = false; btn.classList.remove("loading"); btn.textContent = t; } };
  $("#btnPropose").addEventListener("click", (e) => busy(e.target, async () => { const d = await api("/api/decide", { method: "POST", body: JSON.stringify({ budget: +$("#budgetSel").value }) }); await loadDecisions(d.id); }));
  $("#btnEvalMissing").addEventListener("click", (e) => busy(e.target, async () => { await api(`/api/evaluate_candidates/${S.decision.id}`, { method: "POST" }); document.querySelector('[data-tab="jobs"]').click(); }));
  $("#btnTrain").addEventListener("click", (e) => busy(e.target, async () => { await api("/api/train", { method: "POST", body: JSON.stringify({ decision_id: S.decision.id, seed: +$("#seedIn").value }) }); document.querySelector('[data-tab="jobs"]').click(); }));
  $("#btnWhatIf").addEventListener("click", (e) => busy(e.target, async () => {
    const n = +$("#wiCount").value, trials = Array.from({ length: n }, () => ({ parent_id: $("#wiParent").value, reached: $("#wiReached").value === "1", steps_to_threshold: $("#wiReached").value === "1" ? 112500 : null }));
    const body = { budget: +$("#budgetSel").value, hypothetical_trials: $("#wiParent").value ? trials : [], contract_overrides: $("#wiContract").value ? [$("#wiContract").value] : [] };
    const r = await api("/api/whatif", { method: "POST", body: JSON.stringify(body) });
    S.decision = { ...r.decision, launched_trials: [] }; setMode("What-if"); renderDecision(); renderQueries();
    $("#wiResult").innerHTML = ""; $("#wiResult").append(el("div", { class: "note" }, `What-if selection: ${r.decision.selected || r.decision.action}. Production graph unchanged: ${r.production_unchanged ? "yes" : "NO"} (rev ${r.production_revision}). The copy was dropped after the decision.`));
  }));
  for (const [i, o] of [["#scSpeed", "#scSpeedOut"], ["#scRadius", "#scRadiusOut"]]) $(i).addEventListener("input", () => ($(o).textContent = $(i).value));
  $("#scenarioForm").addEventListener("submit", (e) => { e.preventDefault(); busy($("#scRun"), async () => {
    const body = { policy_id: $("#scPolicy").value, base_family: $("#scFamily").value, n_static: +$("#scStatic").value, mover_speed: +$("#scSpeed").value, mover_radius: +$("#scRadius").value, episodes: +$("#scEps").value };
    $("#scResult").textContent = "Running real episodes…";
    const r = await api("/api/scenario_eval", { method: "POST", body: JSON.stringify(body) });
    S.liveScenario = true; setMode("Live");
    $("#scResult").textContent = `Live evaluation ${r.evaluation_id}: ${pct(r.summary.success_rate)} success, ${pct(r.summary.collision_rate)} collision over ${r.summary.episodes} episodes (${r.wall_s}s). Custom scenarios are never used for decisions.`;
    const side = $("#scSide").value; S.replays[side] = { ...(await api(`/api/replay/${r.evaluation_id}`)), _live: true }; fillEpisodes(); S.t = 0; renderArena();
  }); });
}

async function init() {
  wire(); tick();
  await pollStatus(); setInterval(pollStatus, 3000);
  setInterval(() => { if (!$("#tab-jobs").classList.contains("hidden")) renderJobs(); }, 2500);
  try {
    S.catalog = await api("/api/catalog");
    for (const p of S.catalog) {
      $("#scPolicy").append(el("option", { value: p.id }, `${p.id} (${p.family})`));
      if (p.run_kind === "library" && p.contract.startsWith("ew-contract-1:")) { $("#wiParent").append(el("option", { value: p.id }, p.id)); $("#wiContract").append(el("option", { value: p.id }, p.id)); }
    }
  } catch (e) { /* graph down: catalog comes from the graph */ }
  await loadEvals();
  // default matched pair: deployed policy vs the newest child that follows the latest production decision
  // (a scratch child if the graph recommends scratch, else a child of the selected parent)
  let last = null;
  try { const ds = (await api("/api/decisions")).filter((d) => d.mode !== "what-if"); last = ds[ds.length - 1]; } catch (_) {}
  const prefix = last ? (last.action === "train_from_scratch" ? "scratch~" : last.selected ? last.selected + "~" : null) : null;
  const dep = S.status?.deployed_policy, tgt = S.evals.filter((e) => e.suite_id === "val-target-v1");
  const children = tgt.filter((e) => e.policy_id.includes("~"));
  const before = tgt.filter((e) => e.policy_id === dep).pop();
  const after = (prefix && children.filter((e) => e.policy_id.startsWith(prefix)).pop()) || children.pop();
  if (before) { $("#evalA").value = before.id; await loadReplay("A", before.id); }
  if (after) { $("#evalB").value = after.id; await loadReplay("B", after.id); }
  try { await loadDecisions(); } catch (_) {}
}
init();
