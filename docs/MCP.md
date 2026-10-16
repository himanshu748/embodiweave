# EmbodiWeave domain MCP

The live agent discovers schemas with `tools/list` and executes `tools/call` through the [Python MCP SDK client](../ew/mcp_client.py). The [domain server](../ew/mcp_server.py) supports stdio and Streamable HTTP. The historical Sonnet tool set remains in [mcp_legacy.py](../ew/mcp_legacy.py); frozen runs were not converted into new MCP evidence.

## Tools

| Tool | Purpose |
|---|---|
| `diagnose_policy(policy_id)` | Exact-artifact canonical validation and collision failures |
| `explain_decision(decision_id)` | Decision node, model, actual tool calls, candidates, query receipts and guardrail |
| `lineage(policy_id, max_hops=8)` | Bounded `DERIVED_FROM` paths |
| `find_training_origins(target_policy)` | Verified, compatible origins with all four complete validation suites |
| `nearest_passing_ancestor(policy_id, suite_id, max_hops=8)` | FalkorDB shortest-path algorithm, minimum unweighted lineage distance to a passing ancestor |
| `start_training(origin_id, reason, budget=60000)` | Record the model proposal, check guardrails, then queue one consented PPO run |
| `check_gate(policy_id)` | Read the unchanged promo-1 preview; no evaluation or deployment |

All reads execute [parameterized `GRAPH.RO_QUERY` templates](../ew/graph/queries.py). There is no arbitrary Cypher or protected-suite tool. The server appends Decisions through trusted ingestion and launches the existing bounded CPU worker. Anonymous HTTP clients cannot train. Model credentials stay in the API; the MCP capability is never included in model context, tool arguments, public receipts or the training environment.

## The graph algorithm

`shortestPath` executes in FalkorDB, in a `WITH` clause as required by the pinned runtime. It traverses only `DERIVED_FROM`, at most eight hops, then filters same-contract ancestors by complete, exact-hash, fingerprint-matched validation on the requested canonical suite. Results sort by hop count, collision rate and ID. No eligible ancestor produces an explicit empty result.

This is an **unweighted shortest-path query**, not PageRank or a learned safety score. The model must read its output and cite the returned ancestor ID when proposing training. The guardrail accepts any eligible origin; it does not substitute the first-ranked one. [Implementation](../ew/mcp_domain.py) · [Algorithm and veto tests](../tests/test_mcp_agent.py).

## Claude Desktop and Cursor

Start the local app with the README command first. In Claude Desktop's `claude_desktop_config.json`, or Cursor's project `.cursor/mcp.json`, add the following. Replace the two absolute paths with your checkout and Python environment:

```json
{
  "mcpServers": {
    "embodiweave": {
      "command": "/absolute/path/embodiweave/.venv/bin/python",
      "args": ["-m", "ew.mcp_server"],
      "env": {
        "PYTHONPATH": "/absolute/path/embodiweave",
        "EW_ARTIFACTS": "/absolute/path/embodiweave/artifacts",
        "EW_FALKOR_HOST": "127.0.0.1",
        "EW_FALKOR_PORT": "6379"
      }
    }
  }
}
```

The stdio connection defaults to read-only. To authorize its bounded local training tool, add `EW_MCP_ALLOW_TRAINING=1` to that server's environment. It still requires the diagnosis, origin and algorithm reads, exactly 60,000 requested steps, seed 29, the origin guardrail and the shared worker quotas. External clients do not attest their model, so those Decisions say `external_mcp_client`, with model unknown.

Cursor can also use the public read-only HTTP endpoint:

```json
{"mcpServers":{"embodiweave":{"url":"https://embodiweave.52.202.25.181.sslip.io/mcp/"}}}
```

For Claude Desktop remote connectors, use the same URL if your client supports custom Streamable HTTP connectors. Otherwise use the stdio configuration. Training from a public HTTP connection is restricted to the webpage's consent-scoped agent. No API token needs to be pasted into a client configuration.

For a standalone local read-only HTTP server:

```sh
python -m ew.mcp_server --transport http --port 8001
```

Connect to `http://127.0.0.1:8001/`. The app itself mounts the transport at `/mcp/`, and owns the SDK session-manager lifespan. [Official Python SDK ASGI guidance](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/asgi.md).

## Official FalkorDB MCP alongside the domain tools

[FalkorDB's read-only MCP server](https://github.com/FalkorDB/falkordb-mcp) is useful for local schema inspection and query plans. After following its installation guide, an optional second entry is:

```json
{"mcpServers":{"falkordb-inspection":{"command":"/absolute/path/falkordb-mcp","env":{"FALKORDB_URL":"falkor://127.0.0.1:6379","FALKORDB_MCP_ALLOW_WRITES":"0"}}}}
```

It is optional and was not deployed or used for the recorded domain decision. EmbodiWeave's own tools enforce the robotics contracts, evidence completeness, budgets, consent and promotion boundaries.

## Verification boundary

The test suite exercises discovery and calls with the pinned Python SDK over stdio and HTTP, real FalkorDB traversal, vetoes, anonymous-action denial, model-chosen non-first origins and provider-down fallback. Synthetic unit fixtures are labelled in the test file and are not run evidence. Claude Desktop and Cursor configuration is provided, but those two client UIs have not been manually tested. The public demonstration has its own [prospective protocol](../evidence/mcp-agent-v1/protocol.json); results and receipts are recorded separately from frozen studies.
