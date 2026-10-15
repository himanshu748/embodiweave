// Landing page: every number below is fetched from the studio API, which reads records and live FalkorDB.
const $ = (s) => document.querySelector(s);
const pct = (x) => (x == null ? "–" : `${Math.round(x * 100)}%`);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const get = (u) => fetch(u).then((r) => (r.ok ? r.json() : Promise.reject(r.status)));

async function live() {
  try {
    const s = await get("api/status");
    $("#liveDot").className = "dot " + (s.graph.up ? "up" : "down");
    $("#liveText").innerHTML = s.graph.up
      ? `FalkorDB live · graph <b>${esc(s.graph.name)}</b> rev ${s.graph.revision} · deployed policy <b>${esc(s.deployed_policy)}</b>` +
        (s.hosted_readonly ? " · hosted read-only demo" : "")
      : "FalkorDB is down: recorded evidence is still browsable";
  } catch {
    $("#liveDot").className = "dot down";
    $("#liveText").textContent = "Studio API not reachable";
  }
}

async function results() {
  const body = $("#resultsTable tbody");
  try {
    const r = await get("api/results");
    const rows = (r.experiments || []).map((e) => {
      const arm = (n) => e.arms.find((a) => a.arm === n) || {};
      const g = arm("graph"), l = arm("latest"), b = arm("best_val");
      const best = Math.max(g.test_success ?? 0, l.test_success ?? 0, b.test_success ?? 0);
      const cell = (a) => `<td class="${a.test_success === best ? "win" : ""}">${pct(a.test_success)}<small>${pct(a.test_collision)} collisions</small></td>`;
      return `<tr><td><b>${esc(e.protocol.id)}</b></td><td class="mono">${esc(e.protocol.selection_rule)}</td>
        <td>${g.parent ? esc(g.parent) : "<span class='pill'>scratch</span>"}</td>${cell(g)}${cell(l)}${cell(b)}</tr>`;
    });
    body.innerHTML = rows.join("") || `<tr><td colspan="6" class="muted">No experiments recorded.</td></tr>`;
  } catch {
    body.innerHTML = `<tr><td colspan="6" class="muted">Results unavailable.</td></tr>`;
  }
}

function stepFor(t) {
  const r = t.result || {}, a = t.args || {};
  switch (t.tool) {
    case "inspect_mission": {
      const s = r.deployed_target_evaluation?.summary || {};
      return ["Observe", `Deployed ${esc(r.deployed_policy)}: ${pct(s.success_rate)} success, ${pct(s.collision_rate)} collisions on target`];
    }
    case "query_graph": return ["Query", `<span class="mono">${esc(a.template)}</span> → ${r.row_count ?? 0} rows from FalkorDB`];
    case "propose_adaptation": return ["Decide", esc(r.explanation || r.action)];
    case "start_training": return ["Train", `PPO, ${(r.budget || 0).toLocaleString()} steps, seed ${a.seed} from ${r.parent ? esc(r.parent) : "scratch"}`];
    case "wait_for_job": {
      const j = r.result || {};
      if (r.kind === "transfer_trial") return ["Train", `Finished ${(r.consumed_steps || 0).toLocaleString()} steps · threshold ${j.threshold_reached ? "reached" : "not reached"}`];
      const s = j.summary || {};
      return ["Measure", `${pct(s.success_rate)} success, ${pct(s.collision_rate)} collisions over ${s.episodes} episodes`];
    }
    case "evaluate_checkpoint": return ["Measure", `Queued <span class="mono">${esc(a.suite_id)}</span>`];
    case "request_promotion": return ["Gate", `Verdict: <b>${esc(r.verdict)}</b>`];
    case "export_evidence": return ["Export", `Evidence bundle <span class="mono">${esc(r.bundle)}</span>`];
    default: return [t.tool, ""];
  }
}

async function agent() {
  try {
    const list = await get("api/agent_traces");
    const llm = list.filter((t) => t.mode === "llm-agent").sort((x, y) => (x.recorded_at < y.recorded_at ? 1 : -1));
    for (const meta of llm) {
      const t = await get(`api/agent_traces/${encodeURIComponent(meta.id)}`);
      const calls = (t.transcript || []).filter((x) => x.tool);
      const prom = calls.find((x) => x.tool === "request_promotion");
      if (!prom) continue;
      $("#agentSub").innerHTML = `<b>${esc(t.model)}</b> via ${esc(t.provider)} chose every tool call over MCP: ${calls.length} calls in ${Math.round(t.wall_s)} s. ` +
        `Trace <span class="mono">${esc(t.id)}</span>.`;
      $("#agentSteps").innerHTML = calls.map((c) => {
        const [k, v] = stepFor(c);
        return `<div class="step k-${k.toLowerCase()}"><span class="k">${esc(k)}</span><span class="v">${v}</span></div>`;
      }).join("");
      const p = prom.result;
      $("#agentVerdict").innerHTML = `<div class="badge ${p.verdict === "promoted" ? "ok" : "bad"}">Promotion ${esc(p.verdict)}</div>
        <ul>${(p.reasons || []).map((x) => `<li class="mono">${esc(x)}</li>`).join("")}</ul>
        <p>The gate, not the model, makes the call. A rejected checkpoint stays out of deployment and its evidence stays in the graph for the next decision.</p>`;
      return;
    }
    $("#agentSub").textContent = "No LLM trace with a promotion request is recorded yet.";
  } catch {
    $("#agentSub").textContent = "Agent traces unavailable.";
  }
}

live(); results(); agent();
setInterval(live, 15000);
