"""EmbodiWeave MCP server (stdio). Exposes only the bounded tools in ew.agent_tools."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import agent_tools as T
from .select import RULE_VERSION

mcp = MCPServer("embodiweave", instructions=(
    "Tools for a graph-guided RL studio. FalkorDB holds checkpoint lineage, semantic contracts, matched "
    "validation, conditioned transfer trials and decisions. You choose which bounded operation to run; trusted "
    "code enforces compatibility, budgets and promotion. You cannot run shell, write the graph, or see final-test results."))

def _template_help() -> str:
    """Each allowed template with the parameters its Cypher needs, so a model can fill them first time."""
    import re
    from .graph.queries import TEMPLATES as ALL
    out = []
    for name in sorted(T.AGENT_TEMPLATES):
        ps = sorted(set(re.findall(r"\$(\w+)", str(ALL[name]))))
        out.append(f"{name}({', '.join(ps)})")
    return "; ".join(out)


TEMPLATES = _template_help()


@mcp.tool(description="Mission requirements (prerequisite closure), deployed policy and its measured failure evidence with authored hypotheses labelled.")
def inspect_mission() -> dict:
    return T.inspect_mission()


@mcp.tool(description=f"Run one named read-only Cypher template on FalkorDB. Pass the bare name as template and its parameters "
                      f"in params. Templates and their params: {TEMPLATES}. "
                      "Every listed param is required. ids is a list of policy ids, contract is the contract_id and robot the robot "
                      "name from inspect_mission, suite a validation suite id, evaluation an evaluation id.")
def query_graph(template: str, params: dict) -> dict:
    return T.query_graph(template=template, params=params)


@mcp.tool(description=f"Apply the frozen parent-selection rule {RULE_VERSION} to current graph evidence for the static_crossing "
                      "mission and record a decision. budget is 60000 or 150000 PPO steps. Returns action, ranking, rejections.")
def propose_adaptation(budget: int = 150000) -> dict:
    return T.propose_adaptation(budget=budget)


@mcp.tool(description="Queue matched validation evaluations for candidates a decision listed in needs_evaluation.")
def evaluate_candidates(decision_id: str) -> dict:
    return T.evaluate_candidates(decision_id=decision_id)


@mcp.tool(description="Launch real PPO adaptation from the parent a recorded decision selected. Revalidated before launch; idempotent per (decision, seed).")
def start_training(decision_id: str, seed: int) -> dict:
    return T.start_training(decision_id=decision_id, seed=seed)


@mcp.tool(description="Current worker state of a job.")
def job_status(job_id: str) -> dict:
    return T.job_status(job_id=job_id)


@mcp.tool(description="Wait (up to 240 s) for a job to finish, then return its status.")
def wait_for_job(job_id: str, timeout_s: int = 180) -> dict:
    return T.wait_for_job(job_id=job_id, timeout_s=timeout_s)


@mcp.tool(description="Request cancellation of a queued or running job.")
def cancel_job(job_id: str) -> dict:
    return T.cancel_job(job_id=job_id)


@mcp.tool(description="Queue evaluation of a saved checkpoint on a validation suite: val-open-v1, val-static-v1, val-crossing-v1, val-target-v1.")
def evaluate_checkpoint(policy_id: str, suite_id: str) -> dict:
    return T.evaluate_checkpoint(policy_id=policy_id, suite_id=suite_id)


@mcp.tool(description="Ask the trusted promotion gate promo-1 to promote or reject this exact artifact (target + retained behaviours on the same hash).")
def request_promotion(policy_id: str) -> dict:
    return T.request_promotion(policy_id=policy_id)


@mcp.tool(description="Build the reproducibility bundle for a checkpoint and return its checksums.")
def export_evidence(policy_id: str) -> dict:
    return T.export_evidence(policy_id=policy_id)


if __name__ == "__main__":
    mcp.run("stdio")
