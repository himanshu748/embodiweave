"""Domain MCP over stdio and Streamable HTTP. Historical tools: mcp_legacy.py."""
from __future__ import annotations

import argparse
import os
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

from . import mcp_domain as D

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True)
Hops = Annotated[int, Field(strict=True, ge=1, le=8)]
_stdio_workflow = None


def _workflow(ctx):
    request = ctx.request_context.request
    if request is not None:
        return D.lookup(request.headers.get("x-ew-agent-capability"))
    return _stdio_workflow


def create_server():
    server = MCPServer("EmbodiWeave", version="agent-mcp-v1", log_level="ERROR", instructions=
        "Bounded robotics domain tools. All graph reads use GRAPH.RO_QUERY. No arbitrary Cypher, paths or final tests. "
        "Training needs separate consent, diagnosis, origin evidence and the graph algorithm. The guardrail can veto your origin. "
        "A validation pass does not deploy weights.")

    @server.tool(annotations=READ)
    def diagnose_policy(policy_id: str, ctx: Context) -> dict:
        """Read an exact checkpoint's canonical validation and collision failures."""
        return D.dispatch("diagnose_policy", {"policy_id": policy_id}, _workflow(ctx))

    @server.tool(annotations=READ)
    def explain_decision(decision_id: str, ctx: Context) -> dict:
        """Read the Decision node: model, tool calls, Cypher, candidates and guardrail."""
        return D.dispatch("explain_decision", {"decision_id": decision_id}, _workflow(ctx))

    @server.tool(annotations=READ)
    def lineage(policy_id: str, ctx: Context, max_hops: Hops = 8) -> dict:
        """Read multi-hop DERIVED_FROM paths, bounded to one through eight hops."""
        return D.dispatch("lineage", {"policy_id": policy_id, "max_hops": max_hops}, _workflow(ctx))

    @server.tool(annotations=READ)
    def find_training_origins(target_policy: str, ctx: Context) -> dict:
        """Find origins with compatible semantics, verified artifacts and four complete validation suites. You may choose any eligible origin."""
        return D.dispatch("find_training_origins", {"target_policy": target_policy}, _workflow(ctx))

    @server.tool(annotations=READ)
    def nearest_passing_ancestor(policy_id: str, ctx: Context, suite_id: str = "val-target-v1", max_hops: Hops = 8) -> dict:
        """Run FalkorDB shortestPath to the nearest same-contract ancestor passing a canonical suite. Minimum unweighted hops, not a safety prediction."""
        return D.dispatch("nearest_passing_ancestor", {"policy_id": policy_id, "suite_id": suite_id, "max_hops": max_hops}, _workflow(ctx))

    @server.tool(annotations=WRITE)
    def start_training(origin_id: str, reason: str, ctx: Context, budget: Annotated[int, Field(strict=True)] = 60000) -> dict:
        """Propose an origin, citing the algorithm and evidence in reason. Guardrail writes an allowed/vetoed Decision BEFORE one real 60000-step PPO run (seed29), 180 validation episodes and the gate. Consent required; returns a pending session."""
        return D.dispatch("start_training", {"origin_id": origin_id, "budget": budget, "reason": reason}, _workflow(ctx))

    @server.tool(annotations=READ)
    def check_gate(policy_id: str, ctx: Context) -> dict:
        """Preview unchanged promo-1 for the saved artifact. No evaluation or deployment."""
        return D.dispatch("check_gate", {"policy_id": policy_id}, _workflow(ctx))
    return server


def http_app(server):
    from urllib.parse import urlparse
    public = urlparse(os.environ.get("EW_PUBLIC_URL", "https://embodiweave.52.202.25.181.sslip.io")).netloc
    security = TransportSecuritySettings(allowed_hosts=["127.0.0.1:*", "localhost:*", "testserver", public],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "https://"+public])
    return server.streamable_http_app(streamable_http_path="/", stateless_http=True,
        json_response=True, max_request_body_size=32768, transport_security=security)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    mcp = create_server()
    if args.transport == "stdio":
        if os.environ.get("EW_MCP_ALLOW_TRAINING") == "1":
            _stdio_workflow = D.Workflow("stdio-"+D.secrets.token_hex(8), D.secrets.token_hex(32),
                training_consent=True, training_requested=True, mode="external_mcp_client", transport="stdio")
        mcp.run("stdio")
    else:
        import uvicorn
        uvicorn.run(http_app(mcp), host="127.0.0.1", port=args.port)
