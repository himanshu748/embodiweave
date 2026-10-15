"use strict";
const $ = (s) => document.querySelector(s);
let config = null, active = false, currentId = null, pollVersion = 0, receiptUrl = null;
async function request(path, options = {}) {
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json" }, signal: controller.signal });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The request failed. Please retry.");
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
    $("#limits").textContent = `Up to ${config.max_turns} model turns, ${config.max_tools} tool calls and 2 minutes. One investigation at a time; ${config.daily_runs} shared starts per UTC day, ${config.visitor_hourly} per browser per hour. Allowances reset if the free service restarts.`;
    ready();
  } catch (_) {
    $("#availability").textContent = "Could not connect. Free Render may be waking up. Reconnect in a moment.";
    $("#retryConnection").hidden = false;
  }
}
function summarize(call) {
  const r = call.result;
  if (r.error) return r.error;
  if (r.preview) return `Gate preview for ${r.policy_id}: ${r.verdict}. ${r.checks.filter((c) => c.pass).length}/${r.checks.length + r.missing.length} required validation suites passed${r.missing.length ? `; ${r.missing.length} missing` : ""}. Deployment unchanged.`;
  if (r.action) return `Fresh plan: ${r.selected || r.action.replaceAll("_", " ")} at revision ${r.graph_revision}. ${r.action === "train_from_scratch" ? "Fresh random weights, no parent. " : ""}No training started.`;
  const qs = r.queries || [];
  return qs.map((q) => `${q.template}: ${q.row_count} rows · rev ${q.graph_revision} · ${q.ms} ms`).join(" / ");
}
function paint(s) {
  currentId = s.id;
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
    details.append(label, pre); li.append(title, timing, summary, details); list.append(li);
  }
  $("#answerPanel").hidden = !s.answer;
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
    const s = await request("/api/judge/start", { method: "POST", body: JSON.stringify({ question: $("#question").value, consent: $("#consent").checked }) });
    $("#toolTrace").replaceChildren(); $("#answerPanel").hidden = true;
    sessionStorage.setItem("ew_judge_session", s.id); paint(s);
    poll(s.id, ++pollVersion);
  } catch (e) { $("#startError").textContent = e.name === "AbortError" ? "The connection timed out. Reconnect and try again." : e.message; active = false; ready(); }
});
(async () => { await connect(); const id = sessionStorage.getItem("ew_judge_session"); if (id) { currentId = id; await poll(id, ++pollVersion); } })();
