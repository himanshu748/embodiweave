"use strict";
const $ = (s) => document.querySelector(s);
let config = null, active = false, currentId = null, pollVersion = 0, receiptUrl = null;
let ppoRestorePromise = Promise.resolve();
async function request(path, options = {}) {
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json" }, signal: controller.signal });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail :
      Array.isArray(result.detail) ? result.detail.map(x => x.msg).join(". ") : "The request failed. Please retry.");
    return result;
  } finally { clearTimeout(timer); }
}
function ready() { $("#start").disabled = active || !config?.enabled || !$("#consent").checked; }
async function connect() {
  $("#retryConnection").hidden = true;
  try {
    config = await request("/api/judge/config");
    const graph = await request("/api/status");
    $("#availability").textContent = !graph.graph.up ? "FalkorDB unavailable. Investigations will stop until it recovers."
      : config.enabled ? `FalkorDB live · revision ${graph.graph.revision} · ${config.provider} agent ready` : config.reason;
    $("#providerName").textContent = config.provider || "the configured provider";
    $("#consent").disabled = !config.enabled;
    $("#limits").textContent = `Up to ${config.max_turns} model turns, ${config.max_tools} tool calls and 2 minutes. One investigation at a time; ${config.daily_runs} shared starts per UTC day, ${config.visitor_hourly} per browser per hour. ${config.ephemeral ? "Allowances reset if the free service restarts." : "Completed receipts and allowances persist on this server."}`;
    ready();
  } catch (_) {
    $("#availability").textContent = "Could not connect. Reconnect in a moment.";
    $("#retryConnection").hidden = false;
  }
}
function summarize(call) {
  const r = call.result;
  if (r.error) return r.error;
  if (r.preview) return `Gate preview for ${r.policy_id}: ${r.verdict}. ${r.checks.filter((c) => c.pass).length}/${r.checks.length + r.missing.length} required validation suites passed${r.missing.length ? `; ${r.missing.length} missing` : ""}. Deployment unchanged.`;
  if (r.action) return `Fresh plan: ${r.selected || r.action.replaceAll("_", " ")} at revision ${r.graph_revision}. ${r.action === "train_from_scratch" ? "Fresh random weights, no parent. " : ""}No training started.`;
  if (r.training_session_id) return `Real PPO workflow ${r.state}. Follow the separate training panel for measured results.`;
  const qs = r.queries || [];
  return qs.map((q) => `${q.template}: ${q.row_count} rows · rev ${q.graph_revision} · ${q.ms} ms`).join(" / ");
}
function gateValues(result) {
  const region = document.createElement("div"), table = document.createElement("table"), caption = document.createElement("caption");
  region.className = "gate-values"; region.tabIndex = 0; region.setAttribute("role", "region"); region.setAttribute("aria-label", "Measured promotion gate results");
  caption.textContent = "Deployment checks for this checkpoint"; table.append(caption);
  const head = document.createElement("tr");
  for (const label of ["Test suite", "Success / required", "Collisions / limit", "Result"]) { const th = document.createElement("th"); th.textContent = label; th.scope = "col"; head.append(th); }
  table.append(head);
  const percent = (x) => (100 * x).toFixed(1) + "%";
  for (const check of result.checks) {
    const row = document.createElement("tr");
    for (const text of [({"val-target-v1":"New mission", "val-open-v1":"Open arena", "val-static-v1":"Static obstacles", "val-crossing-v1":"Crossing pedestrian"}[check.suite_id] || check.suite_id), `${percent(check.success_rate)} / ${percent(check.min_success)}`, `${percent(check.collision_rate)} / ${percent(check.max_collision)}`, check.pass ? "Pass" : "Fail"]) { const td = document.createElement("td"); td.textContent = text; row.append(td); }
    table.append(row);
  }
  region.append(table);
  const comparison = result.comparison_to_deployed;
  if (comparison?.available) {
    const p = document.createElement("p"); p.className = "tool-result";
    p.textContent = `Measured target comparison with P-static-b: success ${percent(comparison.baseline.success_rate)} → ${percent(comparison.candidate.success_rate)}; collision ${percent(comparison.baseline.collision_rate)} → ${percent(comparison.candidate.collision_rate)}. Gate requirements remain unchanged.`;
    region.append(p);
  }
  return region;
}
function paint(s) {
  currentId = s.id;
  if (s.training_session_id && (!ppoCurrent || s.training_session_id === ppoId || s.started_at > ppoCurrent.started_at)) followTraining(s.training_session_id);
  $("#runState").textContent = s.state;
  $("#runStatus").textContent = s.detail;
  $("#runMeta").textContent = `${s.id} · ${s.turns}/${config?.max_turns || 6} model turns · ${s.calls.length} tool calls` + (s.models.length ? `\n${s.models.join(", ")}` : "");
  $(".evidence-sheet").classList.toggle("running", s.state === "running");
  $("#traceEmpty").hidden = !!s.calls.length;
  const list = $("#toolTrace");
  for (const c of s.calls.slice(list.children.length)) {
    const li = document.createElement("li"), title = document.createElement("div"), timing = document.createElement("span"), summary = document.createElement("p");
    title.className = "tool-title"; title.textContent = c.tool;
    timing.className = "tool-time"; timing.textContent = `${new Date(c.t * 1000).toLocaleTimeString()} · ${c.wall_ms} ms`;
    summary.className = "tool-result"; summary.textContent = summarize(c);
    const details = document.createElement("details"), label = document.createElement("summary"), pre = document.createElement("pre");
    label.textContent = "Inspect arguments, Cypher and evidence";
    pre.textContent = JSON.stringify({ arguments: c.args, result: c.result }, null, 2);
    details.append(label, pre); li.append(title, timing, summary);
    if (c.result.preview) li.append(gateValues(c.result));
    li.append(details); list.append(li);
  }
  $("#answerPanel").hidden = !s.answer;
  $("#answerPanel h3").textContent = s.answer_source === "compiled_live_graph_evidence" ? "Measured lineage report" : "Model explanation";
  renderAnswer(s.answer || "");
  if (receiptUrl) URL.revokeObjectURL(receiptUrl);
  receiptUrl = URL.createObjectURL(new Blob([JSON.stringify(s, null, 2)], { type: "application/json" }));
  $("#downloadReceipt").href = receiptUrl;
  $("#downloadReceipt").hidden = s.state === "running";
  active = s.state === "running"; ready();
}
function inlineText(node, text) {
  for (const part of text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)) {
    if (part.startsWith("**") && part.endsWith("**")) { const strong = document.createElement("strong"); strong.textContent = part.slice(2, -2); node.append(strong); }
    else if (part.startsWith("`") && part.endsWith("`")) { const code = document.createElement("code"); code.textContent = part.slice(1, -1); node.append(code); }
    else node.append(document.createTextNode(part));
  }
}
function renderAnswer(text) {
  const box = $("#answer"); box.replaceChildren(); let list = null;
  for (const line of text.split("\n")) {
    if (!line.trim()) { list = null; continue; }
    if (/^[-*] /.test(line)) {
      if (!list) { list = document.createElement("ul"); box.append(list); }
      const item = document.createElement("li"); inlineText(item, line.slice(2)); list.append(item);
    } else { list = null; const p = document.createElement("p"); inlineText(p, line.replace(/^#{1,4} /, "")); box.append(p); }
  }
}
async function poll(id, version) {
  if (version !== pollVersion) return;
  try {
    const s = await request(`/api/judge/sessions/${encodeURIComponent(id)}`);
    if (version !== pollVersion) return;
    paint(s); $("#resume").hidden = true;
    if (s.state === "running") setTimeout(() => poll(id, version), 1800);
  } catch (e) {
    $("#runStatus").textContent = `Status unavailable: ${e.message}. Use Resume session status to reconnect.`;
    $("#resume").hidden = false;
    active = false; ready();
  }
}
document.querySelectorAll("[data-question]").forEach((b) => b.addEventListener("click", () => { $("#question").value = b.dataset.question; $("#question").focus(); }));
$("#consent").addEventListener("change", ready);
$("#retryConnection").addEventListener("click", connect);
$("#resume").addEventListener("click", () => { if (currentId) poll(currentId, ++pollVersion); });
$("#investigationForm").addEventListener("submit", async (e) => {
  e.preventDefault(); active = true; ready(); $("#startError").textContent = "";
  try {
    const s = await request("/api/judge/start", { method: "POST", body: JSON.stringify({ question: $("#question").value, consent: $("#consent").checked, training_consent: $("#agentTrainingConsent").checked }) });
    $("#toolTrace").replaceChildren(); $("#answerPanel").hidden = true;
    sessionStorage.setItem("ew_judge_session", s.id); paint(s);
    poll(s.id, ++pollVersion);
  } catch (e) { $("#startError").textContent = e.name === "AbortError" ? "The connection timed out. Reconnect and try again." : e.message; active = false; ready(); }
});
const connectionReady = connect();
(async () => { await connectionReady; await ppoRestorePromise; const id = sessionStorage.getItem("ew_judge_session"); if (id) { currentId = id; await poll(id, ++pollVersion); } })();

let ppoConfig = null, ppoActive = false, ppoId = null, ppoVersion = 0, ppoCurrent = null;
let frameId = null, frameVersion = 0;
const arenaReady = import("./live-arena.js").then(m => new m.RunArena());
function ppoReady() { $("#ppoStart").disabled = ppoActive || !ppoConfig?.enabled; }
function ppoPaint(s) {
  attachRunView(s.id); ppoCurrent = s;
  ppoId = s.id; ppoActive = ["queued", "running", "cancelling"].includes(s.state);
  $("#ppoState").textContent = s.state === "completed" ? "Training finished" : s.state === "cancelled" ? "Stopped" : ({select:"Choosing checkpoint",train:"Training",validate:"Testing",gate:"Checking results"}[s.phase] || s.state); $("#ppoStatus").textContent = s.detail;
  $("#ppoProgress").max = s.reserved_steps || s.budget; $("#ppoProgress").value = s.consumed_steps; $("#ppoCancel").hidden = !ppoActive;
  $("#ppoCancel").disabled = s.state === "cancelling";
  $("#ppoMeta").textContent = `${s.consumed_steps.toLocaleString()} steps trained · ${s.budget.toLocaleString()} requested · ${s.evaluations.length}/4 test suites complete` +
    (s.parent_id !== undefined ? ` · Started from ${s.parent_id || "random weights"} · seed ${s.seed}` : "");
  $("#ppoGate").replaceChildren();
  if (s.gate) {
    const passed = s.gate.checks.filter(c => c.pass).length;
    const verdict = document.createElement("h3"), explanation = document.createElement("p");
    verdict.textContent = s.gate.verdict === "promoted" ? "Passed deployment checks" : s.gate.verdict === "rejected" ? "Checkpoint not approved for deployment" : "More test results needed";
    explanation.textContent = `${passed} of ${s.gate.checks.length+s.gate.missing.length} test suites passed. ` + (s.gate.verdict === "promoted" ? "This checkpoint is ready for review. " : "The checkpoint is saved with its measured results. ") + "The deployed policy remains P-static-b.";
    $("#ppoGate").append(verdict, explanation, gateValues(s.gate));
  }
  $("#arenaReplay").disabled = s.state !== "completed";
  $("#ppoLinks").hidden = s.state !== "completed";
  if (s.state === "completed") { $("#ppoDownload").href = `/api/public-training/sessions/${encodeURIComponent(s.id)}/bundle`; $("#ppoReplay").href = `studio.html?policy=${encodeURIComponent(s.policy_id)}`; }
  $("#ppoDetails").hidden = false; $("#ppoReceipt").textContent = JSON.stringify(s, null, 2); ppoReady();
}
async function pollTraining(id, version) {
  if (version !== ppoVersion) return;
  try {
    const s = await request(`/api/public-training/sessions/${encodeURIComponent(id)}`);
    if (version !== ppoVersion) return;
    ppoPaint(s); $("#ppoResume").hidden = true;
    if (ppoActive) setTimeout(() => pollTraining(id, version), 2000);
  } catch (e) { $("#ppoStatus").textContent = `Status unavailable: ${e.message}`; $("#ppoResume").hidden = false; }
}
function followTraining(id) { if (ppoId === id) return Promise.resolve(); ppoId = id; sessionStorage.setItem("ew_ppo_session", id); return pollTraining(id, ++ppoVersion); }
$("#ppoResume").addEventListener("click", () => { if (ppoId) { frameId=null; pollTraining(ppoId, ++ppoVersion); } });
$("#ppoForm").addEventListener("submit", async (e) => {
  e.preventDefault(); ppoActive = true; ppoReady(); $("#ppoError").textContent = "";
  try {
    const s = await request("/api/public-training/start", {method:"POST",body:JSON.stringify({seed:Number($("#ppoSeed").value),budget:Number($("#ppoBudget").value),consent:true})});
    ppoPaint(s); sessionStorage.setItem("ew_ppo_session", s.id); pollTraining(s.id, ++ppoVersion);
  } catch(e) { $("#ppoError").textContent = e.message; ppoActive = false; ppoReady(); }
});
$("#ppoCancel").addEventListener("click", async () => {
  try { ppoPaint(await request("/api/public-training/cancel", {method:"POST",body:JSON.stringify({session_id:ppoId})})); }
  catch(e) { $("#ppoError").textContent = e.message; }
});
ppoRestorePromise = (async () => {
  try { await connectionReady; ppoConfig = await request("/api/public-training/config"); $("#ppoState").textContent = ppoConfig.enabled ? "Ready to train" : "Unavailable";
    $("#ppoLimits").textContent = ppoConfig.enabled ? `${ppoConfig.daily_runs} runs available each UTC day, ${ppoConfig.visitor_hourly} per browser each hour. One run at a time, for up to eight minutes. Training uses complete PPO rollouts, so the final step count may be slightly higher than requested.` : ppoConfig.reason;
    ppoReady(); const id = sessionStorage.getItem("ew_ppo_session"); if (id) await followTraining(id);
  } catch(e) { $("#ppoStatus").textContent = "CPU service unavailable. Reconnect or reload to try again."; }
})();

function attachRunView(id) {
  if (frameId === id) return;
  frameId = id; const version = ++frameVersion;
  arenaReady.then(arena => { if (version !== frameVersion) return; arena.reset(); $("#arenaReplay").disabled = ppoCurrent?.id !== id || ppoCurrent?.state !== "completed"; pollFrames(id, 0, version); });
}
async function pollFrames(id, after, version, failures=0) {
  if (version !== frameVersion) return;
  try {
    const data = await request(`/api/public-training/sessions/${encodeURIComponent(id)}/frames?after=${after}`);
    if (version !== frameVersion) return;
    const arena = await arenaReady; arena.ingest(data.frames);
    if (data.finished) arena.finish();
    if (!data.finished) setTimeout(() => pollFrames(id,data.latest,version),350);
  } catch (_) {
    if (version === frameVersion && failures < 8) setTimeout(() => pollFrames(id,after,version,failures+1),1500);
    else if (version === frameVersion) $("#arenaCaption").textContent = "The simulator view disconnected. Reconnect to the run to try again.";
  }
}
$("#arenaReplay").addEventListener("click", async () => {
  if (!ppoCurrent?.replay_evaluation_id) return;
  try { const replay = await request(`/api/replay/${encodeURIComponent(ppoCurrent.replay_evaluation_id)}`); (await arenaReady).loadReplay(replay); }
  catch (e) { $("#arenaCaption").textContent = `Could not load the replay: ${e.message}`; }
});
