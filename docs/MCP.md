# EmbodiWeave domain MCP

The live agent discovers schemas with `tools/list` and executes `tools/call` through the [Python MCP SDK client](../ew/mcp_client.py). The [domain server](../ew/mcp_server.py) supports stdio and Streamable HTTP. The historical Sonnet tool set remains in [mcp_legacy.py](../ew/mcp_legacy.py); frozen runs were not converted into new MCP evidence.

## Tools

| Tool | Purpose |
|---|---|
| `diagnose_policy(policy_id)` | Exact-artifact canonical validation and collision failures |
| `explain_decision(decision_id)` | Decision node, model, actual tool calls, candidates, query receipts and guardrail |
| `get_evidence_record(record_type, record_id)` | Full Policy, Decision, DecisionOutcome or canonical-validation Evaluation properties by exact ID; bounded model-facing view |
| `lineage_path(from_policy, to_policy)` | Native `algo.SPpaths`, resolved IDs, at most eight unit-weight lineage edges |
| `rank_origins_excluding_regressed(target_policy, max_hops=8)` | Graph-ranked origins, exclusion outcomes and actual ancestry paths |
| `lineage(policy_id, max_hops=8)` | Bounded `DERIVED_FROM` paths |
| `find_training_origins(target_policy)` | Verified, compatible origins with all four complete validation suites |
| `nearest_passing_ancestor(policy_id, suite_id, max_hops=8)` | FalkorDB shortest-path algorithm, minimum unweighted lineage distance to a passing ancestor |
| `get_decision_outcomes(target_policy)` | Connected Decisions, selected origins, child runs and measured parent comparisons |
| `rank_regression_origins(target_policy)` | Native Cypher weighted incoming degree from observed child collision-rate deltas, with support counts |
| `start_training(origin_id, reason, budget=60000)` | Record the model proposal, check guardrails, then queue one consented PPO run |
| `check_gate(policy_id)` | Read the unchanged promo-1 preview; no evaluation or deployment |

All reads execute [parameterized `GRAPH.RO_QUERY` templates](../ew/graph/queries.py). There is no arbitrary Cypher or protected-suite tool. The server appends Decisions through trusted ingestion and launches the existing bounded CPU worker. Anonymous HTTP clients cannot train. Model credentials stay in the API; the MCP capability is never included in model context, tool arguments, public receipts or the training environment.

## The lineage graph algorithm

`shortestPath` executes in FalkorDB, in a `WITH` clause as required by the pinned runtime. It traverses only `DERIVED_FROM`, at most eight hops, then filters same-contract ancestors by complete, exact-hash, fingerprint-matched validation on the requested canonical suite. Results sort by hop count, collision rate and ID. No eligible ancestor produces an explicit empty result.

This is an **unweighted shortest-path query**, not PageRank or a learned safety score. The model must read its output and cite the returned ancestor ID when proposing training. The guardrail accepts any eligible origin; it does not substitute the first-ranked one. [Implementation](../ew/mcp_domain.py) · [Algorithm and veto tests](../tests/test_mcp_agent.py).

## Claude Desktop and Cursor

Start the local app with the README's `docker compose up --build` command first. In Claude Desktop's `claude_desktop_config.json`, or Cursor's project `.cursor/mcp.json`, add the following. Replace the absolute Compose path with your checkout. This runs inside the existing app container, where the graph and evidence volume are available; it does not assume the container's private database port is exposed on your host.

```json
{
  "mcpServers": {
    "embodiweave": {
      "command": "docker",
      "args": ["compose", "-f", "/absolute/path/embodiweave/compose.yaml", "exec", "-T", "embodiweave", "/app/.venv/bin/python", "-m", "ew.mcp_server"]
    }
  }
}
```

The stdio connection defaults to read-only. To authorize its bounded local training tool, insert `"-e", "EW_MCP_ALLOW_TRAINING=1"` after `"-T"` in the Compose arguments. It still requires the diagnosis, origin and algorithm reads, exactly 60,000 requested steps, seed 29, the origin guardrail and the shared worker quotas. External clients do not attest their model, so those Decisions say `external_mcp_client`, with model unknown. A direct Python launch is also supported when you separately configure a local FalkorDB connection and the evidence directory.

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

### Model routing and credits

Free NVIDIA endpoints remain the default. The owner can explicitly set `EW_AGENT_MODEL=openai/gpt-4.1-mini` for paid OpenRouter inference through **Azure only**, with no provider fallback. The MCP agent limits each serialized request to 28,000 bytes (within the paid route's existing 32,000-byte ceiling), each response to 1,200 tokens and each investigation to six model turns. OpenRouter's `max_price` caps input at $0.40 and output at $1.60 per million tokens, with no per-request surcharge. The existing daily and per-browser quotas still apply; actual provider usage is saved in the agent receipt. No model or billing option is accepted from a public request.

The first public [v1 attempt](../evidence/mcp-agent-v1/agent-receipt.json) exhausted the account's daily free-model quota and used the labelled deterministic fallback. The owner then authorized paid credits for a separately registered [v2 demonstration](../evidence/mcp-agent-v2/protocol.json). Ongoing judge runs use the [public protocol](../evidence/mcp-agent/protocol.json), rather than being counted as additional attempts in either one-run study.

The completed [v2 record](../evidence/mcp-agent-v2/) contains the actual model choice, four MCP calls, shortest-path output, guardrail Decision and 180-episode gate. The independent [public SDK check](../evidence/mcp-agent-v2/public-client-verification.json) also reads all six read tools, including the saved Decision and new checkpoint's gate. CI runs the README's exact Docker Compose stdio command and the HTTP client against a fresh Compose launch. Reproduce those read-only checks with `python -m scripts.check_mcp --stdio docker compose -f "$PWD/compose.yaml" exec -T embodiweave /app/.venv/bin/python -m ew.mcp_server` or `python -m scripts.check_mcp --url http://127.0.0.1:8000/mcp/`.


## Connected outcomes and weighted regression degree

`get_decision_outcomes(target_policy)` follows recorded Decisions through selected origins, launched runs, produced children and exact-artifact validation comparisons. Trusted worker completion writes a separate append-only DecisionOutcome and parent comparison edges; it never overwrites the pre-training Decision or changes promo-1.

`rank_regression_origins(target_policy)` computes weighted incoming degree in FalkorDB using Cypher over measured COMPARED_AGAINST edges. Each edge weighs the sum of positive per-suite collision-rate deltas. The output includes observed-child support; no observations means null. It is descriptive and can grow with more trials, not a probability of safety. Current output is restricted to eligible origins to keep the bounded model context small.

[The one preregistered v3 attempt](../evidence/mcp-agent-v3/) called both tools but exceeded the model-context cap before choosing an origin. Its original receipt is retained. A separately authorized [v3-retry](../evidence/mcp-agent-v3-retry/) was preregistered and completed once: six MCP calls, prior-outcome citation, the same origin, 61,440 steps and 180 validation episodes. All four gates passed, but target and crossing regressed against the parent; the child was not released. Both one-attempt studies disable deterministic fallback. No further retry was made.

## Bounded model context

The [current graph snapshot and budget tests](../evidence/mcp-agent-v3-retry/context-fix.json) retain full query records in the Decision audit while sending top-k rows, exact IDs and per-suite deltas to the model. Each tool reply is at most 2,000 UTF-8 bytes, retained tool text at most 12,000 bytes, history at most six whole exchanges and a provider request at most 28,000 bytes. UTF-8 byte counts conservatively upper-bound byte-BPE text tokens, rather than estimating tokenizer usage. Required first reads and the latest exchange stay together with their call/response IDs. Oversized required evidence fails closed before sending another request.

`get_evidence_record` gives read-only clients full properties by ID; the live model receives a bounded view. Only canonical validation Evaluation records are exposed. Summaries mark omitted candidates; this limited model view is not the full candidate set. The retry's largest actual serialized request was 17,926 bytes, and the original receipt was preserved.

## Native procedure verified on the pinned image

The Dockerfile, Compose and CI use `falkordb/falkordb@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6`. On October 17, 2026, `redis-cli MODULE LIST` reported `graph ver 60002` (FalkorDB 6.0.2) both in the isolated local container and the existing AWS API container.

Read-only procedure probes on that digest confirmed registration of `algo.SPpaths`, `algo.SSpaths`, `algo.BFS`, `algo.pageRank`, `algo.MSF`, `algo.WCC`, `algo.betweenness` and `algo.maxFlow`. Empty-argument probes returned argument-count validation for procedures requiring arguments; MSF, WCC and betweenness ran on an isolated two-node fixture. `db.procedures()`, `algo.CDLP` and `algo.allShortestPaths` returned unknown-function errors. This is the tested procedure set, not a claim that those are the only procedures. The runtime itself, not a latest-version documentation assumption, determined the new tool.

`lineage_path(from_policy, to_policy)` executes the [exact `CALL algo.SPpaths` template](../ew/graph/cypher/lineage_path.cypher) through `GRAPH.RO_QUERY`. Both strings are capped at 160 characters and first resolved with a parameterized Policy lookup. An unknown ID returns `outcome: unknown_policy`; only resolution reads run, never the algorithm query. A known but disconnected pair returns `no_path_within_bound`. The procedure follows at most eight outgoing `DERIVED_FROM` edges and returns one path as policy IDs plus `pathWeight`. Equal-cost path choice is unspecified.

[Trusted ingestion](../ew/graph/ingest.py) assigns a missing `DERIVED_FROM.weight` the value 1. No read tool adds weights. These unit weights represent **unweighted lineage distance**, not a safety signal. The existing shortestPath and weighted-degree tools are unchanged. [Native procedure and unknown-ID tests](../tests/test_mcp_agent.py). [Official SPpaths documentation](https://docs.falkordb.com/algorithms/sppath).

## Checked sentences and depth contrast

[accepts(sentence, answer)](../ew/rationale.py) validates identifier membership against returned tool fields, rejects unsupported comparison words unless the same sentence contains a returned measurement, and rejects improvement claims from empty or excluded origin rankings. Rejected wording is replaced by a flat rendering of returned ranking rows with a visible rejection reason. This is a conservative lexical check, not proof that a comparison is scientifically justified. A number alone does not establish safety, improvement or causation. The original raw audit remains unchanged.

The public response boundary applies this check to proposal rationales and final model wording. The [saved v4 fixture test](../tests/test_rationale.py) demonstrates rejection of its unsupported “safest” sentence. The page can repeat that display check without an LLM request or a new Decision.

[The depth comparison](https://embodiweave.52.202.25.181.sslip.io/live.html#graph-tools) runs `rank_origins_excluding_regressed` with depths 1 and 8 against the live graph. The [exact Cypher](../ew/graph/cypher/rank_origins_excluding_regressed.cypher) now includes the actual policy path for every exclusion reason and outcome ID. A boundary path identifies the next unexamined ancestor, with no fabricated outcome ID. Such lineage is excluded, never called safe. The caption is computed from returned rows; it does not assume that eligibility changes between depths. [Frozen projection tests](../tests/test_regression_exclusion.py) check path adjacency and conservative exclusion. These additions create no new training, agent run or evaluation evidence.
