"""Runtime agent: talks to the EmbodiWeave MCP server over stdio.

  python -m ew.agent llm            # Anthropic model chooses tools (needs ANTHROPIC_API_KEY)
  python -m ew.agent deterministic  # fixed scripted tool sequence, labelled deterministic, same MCP tools

Both modes go through the real MCP protocol and the same bounded tools. Only 'llm' is an LLM run.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from . import records

MODEL = os.environ.get("EW_AGENT_MODEL", "claude-opus-5-5")
MAX_TURNS = int(os.environ.get("EW_AGENT_MAX_TURNS", "30"))

SYSTEM = """You operate EmbodiWeave, a graph-guided reinforcement-learning studio for a simulated unicycle robot.
The deployed policy fails the static_crossing mission. Your job: inspect the measured failure, use the FalkorDB
evidence tools to understand candidate parent checkpoints, get a recorded decision from the frozen selection rule,
make sure every eligible candidate has matched validation, launch exactly one bounded PPO adaptation from the
selected parent (seed 7, budget 150000), wait for it, evaluate the resulting checkpoint on the retained-behaviour
validation suites it still lacks (val-open-v1, val-static-v1, val-crossing-v1), request promotion of that exact
checkpoint and export its evidence bundle. Then report what was measured.
Rules: never claim an outcome a tool did not return. Distinguish measured failures from authored hypotheses.
A failed promotion or an adaptation that does not reach threshold is a valid result; report it plainly.
Do not retry training to get a better number."""


def _result(res) -> dict:
    sc = getattr(res, "structuredContent", None) or getattr(res, "structured_content", None)
    if sc:
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    texts = [c.text for c in res.content if getattr(c, "type", "") == "text"]
    try:
        return json.loads(texts[0]) if len(texts) == 1 else {"text": texts}
    except Exception:  # noqa: BLE001
        return {"text": texts}


def _server(session_id: str, mode: str) -> StdioServerParameters:
    env = {**os.environ, "EW_AGENT_SESSION": session_id, "EW_AGENT_MODE": mode,
           "PYTHONPATH": os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}
    for k in ("ANTHROPIC_API_KEY", "GROQ_API_KEY"):  # the tool server never sees model credentials
        env.pop(k, None)
    return StdioServerParameters(command=sys.executable, args=["-m", "ew.mcp_server"], env=env)


async def run_deterministic(session_id: str, seed: int = 7, budget: int = 150_000) -> dict:
    calls = []
    async with stdio_client(_server(session_id, "deterministic")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()

            async def call(name, **args):
                out = _result(await s.call_tool(name, args))
                calls.append({"tool": name, "args": args, "result": out})
                return out

            await call("inspect_mission")
            d = await call("propose_adaptation", budget=budget)
            if d.get("action") == "evaluate_candidates":
                ev = await call("evaluate_candidates", decision_id=d["decision_id"])
                for j in ev["jobs"]:
                    await call("wait_for_job", job_id=j["job_id"], timeout_s=240)
                d = await call("propose_adaptation", budget=budget)
            st = await call("start_training", decision_id=d["decision_id"], seed=seed)
            job = await call("wait_for_job", job_id=st["job_id"], timeout_s=240)
            while job["state"] in ("queued", "running"):
                job = await call("wait_for_job", job_id=st["job_id"], timeout_s=240)
            child = st["child_policy_id"]
            for sid in ("val-open-v1", "val-static-v1", "val-crossing-v1"):
                e = await call("evaluate_checkpoint", policy_id=child, suite_id=sid)
                await call("wait_for_job", job_id=e["job_id"], timeout_s=240)
            await call("request_promotion", policy_id=child)
            await call("export_evidence", policy_id=child)
    return {"calls": calls}


async def run_llm(session_id: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    transcript, usage = [], []
    async with stdio_client(_server(session_id, "llm-agent")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            listed = await s.list_tools()
            tools = [{"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
                     for t in listed.tools]
            messages = [{"role": "user", "content": "Investigate the failing deployed policy and run the failure-to-fix loop."}]
            final_text = ""
            for turn in range(MAX_TURNS):
                resp = client.beta.messages.create(
                    model=MODEL, max_tokens=16000, system=SYSTEM, tools=tools, messages=messages,
                    thinking={"type": "adaptive"}, output_config={"effort": "medium"},
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default")
                usage.append({"turn": turn, "model": resp.model, "input": resp.usage.input_tokens,
                              "output": resp.usage.output_tokens, "stop": resp.stop_reason})
                if resp.stop_reason == "refusal":
                    final_text = "model refused"
                    break
                messages.append({"role": "assistant", "content": resp.content})
                texts = [b.text for b in resp.content if b.type == "text"]
                if texts:
                    transcript.append({"turn": turn, "assistant_text": "\n".join(texts)})
                uses = [b for b in resp.content if b.type == "tool_use"]
                if resp.stop_reason != "tool_use" or not uses:
                    final_text = "\n".join(texts)
                    break
                results = []
                for b in uses:
                    out = _result(await s.call_tool(b.name, dict(b.input)))
                    transcript.append({"turn": turn, "tool": b.name, "args": b.input, "result": out})
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": json.dumps(out, default=str)[:20000],
                                    "is_error": isinstance(out, dict) and "error" in out})
                messages.append({"role": "user", "content": results})
    return {"provider": "anthropic", "model": MODEL, "transcript": transcript, "usage": usage, "final_text": final_text}


GROQ_MODEL = os.environ.get("EW_GROQ_MODEL", "auto")
# Strongest tool-calling families first. "auto" takes the first one the account offers and records which.
# Groq's free tier caps tokens per minute (8000 on gpt-oss-120b), and that cap counts the prompt plus the
# requested completion. Keep each request under it: bounded output, older tool results trimmed, wait on 429.
GROQ_MAX_OUTPUT = int(os.environ.get("EW_GROQ_MAX_OUTPUT", "2048"))
GROQ_CONTEXT_CHARS = int(os.environ.get("EW_GROQ_CONTEXT_CHARS", "10000"))
GROQ_RESULT_CHARS = 4000
GROQ_PREFERENCE = ("kimi-k2", "gpt-oss-120b", "llama-4-maverick", "qwen3-32b", "llama-3.3-70b", "gpt-oss-20b")


def pick_groq_model(available: set[str], wanted: str = GROQ_MODEL) -> str:
    if wanted != "auto":
        if wanted not in available:
            raise SystemExit(f"Groq model {wanted} not offered; set EW_GROQ_MODEL to one of {sorted(available)}")
        return wanted
    for fam in GROQ_PREFERENCE:
        hits = sorted((m for m in available if fam in m), reverse=True)  # newest-looking id first
        if hits:
            return hits[0]
    raise SystemExit(f"no known tool-calling model among {sorted(available)}; set EW_GROQ_MODEL")


def _fit(messages: list, budget: int = GROQ_CONTEXT_CHARS) -> list:
    """Trim the oldest tool results until the conversation fits the character budget. The newest stays whole."""
    size = lambda: sum(len(m.get("content") or "") + len(json.dumps(m.get("tool_calls", ""))) for m in messages)
    tools = [m for m in messages if m["role"] == "tool"][:-1]
    for m in tools:
        if size() <= budget:
            break
        if len(m["content"]) > 240:
            m["content"] = m["content"][:200] + ' ..."[trimmed to fit the rate limit; call the tool again if needed]"'
    return messages


def _groq_create(client, budget: int, rejected: list, **kw):
    """One completion, waiting out per-minute rate limits and shrinking the context if a request is too large."""
    import groq
    for attempt in range(12):
        try:
            return client.chat.completions.create(messages=_fit(kw["messages"], budget),
                                                  **{k: v for k, v in kw.items() if k != "messages"})
        except groq.APIStatusError as e:
            body = getattr(e, "body", None) or {}
            err = body.get("error", body) if isinstance(body, dict) else {}
            if e.status_code == 400 and isinstance(err, dict) and err.get("code") == "tool_use_failed":
                # The model named a tool that does not exist (e.g. a query template). Tell it and let it retry.
                names = sorted(t["function"]["name"] for t in kw.get("tools", []))
                kw["messages"].append({"role": "user", "content": f"Your last tool call was rejected: {err.get('message', '')[:300]}. "
                                       f"Call only these tools: {', '.join(names)}. Graph templates run through query_graph."})
                rejected.append(err.get("failed_generation", "")[:300])
                continue
            if e.status_code == 413:
                budget = int(budget * 0.7)
            elif e.status_code != 429:
                raise
            wait = float(e.response.headers.get("retry-after", 0) or 0) or 15.0
            time.sleep(min(wait, 65.0))
    raise SystemExit("Groq kept rate-limiting after 12 attempts")


async def run_groq(session_id: str) -> dict:
    """Same MCP tools and loop, with Groq's OpenAI-style chat completions as the runtime LLM."""
    from groq import Groq
    client = Groq()  # reads GROQ_API_KEY
    available = {m.id for m in client.models.list().data}
    model = pick_groq_model(available)
    transcript, usage, rejected = [], [], []
    async with stdio_client(_server(session_id, "llm-agent")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            listed = await s.list_tools()
            tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                                       "parameters": t.input_schema}} for t in listed.tools]
            messages = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": "Investigate the failing deployed policy and run the failure-to-fix loop."}]
            final_text = ""
            for turn in range(MAX_TURNS):
                resp = _groq_create(client, GROQ_CONTEXT_CHARS, rejected, model=model, messages=messages, tools=tools,
                                    tool_choice="auto", max_completion_tokens=GROQ_MAX_OUTPUT)
                ch = resp.choices[0]
                usage.append({"turn": turn, "model": resp.model, "input": resp.usage.prompt_tokens,
                              "output": resp.usage.completion_tokens, "stop": ch.finish_reason})
                msg = ch.message
                calls = msg.tool_calls or []
                messages.append({"role": "assistant", "content": msg.content or "",
                                 **({"tool_calls": [{"id": c.id, "type": "function",
                                                     "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                                    for c in calls]} if calls else {})})
                if msg.content:
                    transcript.append({"turn": turn, "assistant_text": msg.content})
                if not calls:
                    final_text = msg.content or ""
                    break
                for c in calls:
                    try:
                        args = json.loads(c.function.arguments or "{}")
                        out = _result(await s.call_tool(c.function.name, args))
                    except json.JSONDecodeError as e:
                        args, out = c.function.arguments, {"error": f"INVALID_JSON: {e}"}
                    transcript.append({"turn": turn, "tool": c.function.name, "args": args, "result": out})
                    messages.append({"role": "tool", "tool_call_id": c.id,
                                     "content": json.dumps(out, default=str)[:GROQ_RESULT_CHARS]})
    return {"provider": "groq", "model": model, "models_offered": sorted(available),
            "rejected_tool_calls": rejected, "transcript": transcript, "usage": usage, "final_text": final_text}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "deterministic"
    sid = records.new_id("agent")
    t0 = time.time()
    if mode == "llm":  # pick the provider whose key is configured; Groq first, it is the project's chosen provider
        mode = "llm-groq" if os.environ.get("GROQ_API_KEY") else "llm-anthropic"
    runner = {"llm-groq": run_groq, "llm-anthropic": run_llm, "deterministic": run_deterministic}[mode]
    out = asyncio.run(runner(sid))
    rec = records.write("agent_trace", {"id": sid, "mode": "llm-agent" if mode.startswith("llm") else "deterministic",
                                        "wall_s": round(time.time() - t0, 1), **out})
    print(json.dumps({"agent_trace_id": rec["id"], "mode": rec["mode"], "wall_s": rec["wall_s"]}))


if __name__ == "__main__":
    main()
