"""Read-only UI projections, with no model or worker entry point."""
from . import mcp_domain as D, agent_tools


def depth_ranking(max_hops):
    if type(max_hops) is not int or max_hops not in (1,8):
        raise ValueError('Choose lineage depth 1 or 8')
    result=D.rank_origins_excluding_regressed(agent_tools.DEPLOYED_POLICY,max_hops)
    return {**result,'max_hops':max_hops,'target_policy':agent_tools.DEPLOYED_POLICY,
            'source':'live FalkorDB, current graph', 'read_only':True}
