"""Read-only SDK smoke check for the documented stdio command or HTTP URL."""
import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ew import agent_tools, mcp_client as C

EXPECTED = {"lineage_path", "diagnose_policy", "explain_decision", "lineage", "find_training_origins",
            "nearest_passing_ancestor", "start_training", "check_gate", "get_decision_outcomes", "rank_regression_origins", "get_evidence_record", "rank_origins_excluding_regressed"}


@asynccontextmanager
async def connection(args):
    if args.stdio:
        params = StdioServerParameters(command=args.stdio[0], args=args.stdio[1:])
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                yield session, [t.name for t in tools.tools], initialized.model_dump(by_alias=True)
    else:
        async with C.connect(url=args.url) as (session, tools, initialized):
            yield session, [t["function"]["name"] for t in tools], initialized


async def check(args):
    async with connection(args) as (client, tools, initialized):
        assert set(tools) == EXPECTED
        calls = [("lineage_path", {"from_policy":args.policy,"to_policy":args.policy}), ("rank_origins_excluding_regressed", {"target_policy":args.policy}), ("get_evidence_record", {"record_type":"Policy", "record_id":args.policy}),
                 ("diagnose_policy", {"policy_id": args.policy}),
                 ("lineage", {"policy_id": args.policy, "max_hops": 8}),
                 ("find_training_origins", {"target_policy": args.policy}),
                 ("nearest_passing_ancestor", {"policy_id": args.policy}),
                 ("get_decision_outcomes", {"target_policy": args.policy}),
                 ("rank_regression_origins", {"target_policy": args.policy}),
                 ("check_gate", {"policy_id": args.child or args.policy})]
        if args.decision:
            calls.append(("explain_decision", {"decision_id": args.decision}))
        results = []
        for tool, params in calls:
            result = C.unpack(await client.call_tool(tool, params))
            assert not result.get("error"), (tool, result.get("error"))
            results.append({"tool": tool, "args": params, "result": result})
        receipt = {"transport": "stdio" if args.stdio else "streamable-http", "endpoint": args.url,
                   "initialization": initialized, "tools": tools, "calls": results, "read_only": True}
        if args.output:
            Path(args.output).write_text(json.dumps(receipt, indent=2)+"\n")
        print(json.dumps({"transport": receipt["transport"], "tools": tools,
                          "verified_reads": [c["tool"] for c in results], "training_started": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp/")
    parser.add_argument("--policy", default=agent_tools.DEPLOYED_POLICY)
    parser.add_argument("--child")
    parser.add_argument("--decision")
    parser.add_argument("--output")
    parser.add_argument("--stdio", nargs=argparse.REMAINDER)
    asyncio.run(check(parser.parse_args()))
