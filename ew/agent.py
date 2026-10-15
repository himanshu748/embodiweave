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
    env.pop("ANTHROPIC_API_KEY", None)  # the tool server never sees model credentials
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
    return {"model": MODEL, "transcript": transcript, "usage": usage, "final_text": final_text}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "deterministic"
    sid = records.new_id("agent")
    t0 = time.time()
    out = asyncio.run(run_llm(sid) if mode == "llm" else run_deterministic(sid))
    rec = records.write("agent_trace", {"id": sid, "mode": "llm-agent" if mode == "llm" else "deterministic",
                                        "wall_s": round(time.time() - t0, 1), **out})
    print(json.dumps({"agent_trace_id": rec["id"], "mode": rec["mode"], "wall_s": rec["wall_s"]}))


if __name__ == "__main__":
    main()
