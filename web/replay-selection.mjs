// Presentation-only selection: never create evaluations or substitute an unrelated child.
export function selectReplayPair(evaluations, requestedPolicy, deployedPolicy) {
  const policy = requestedPolicy || deployedPolicy;
  const target = evaluations.filter(row => row.suite_id === "val-target-v1");
  return {
    policy,
    before: target.filter(row => row.policy_id === "P-static-b").at(-1) || null,
    after: target.filter(row => row.policy_id === policy).at(-1) || null,
  };
}

export function decisionMode(mode) {
  if (mode === 'llm' || mode === 'llm-agent') return {label:'LLM agent', cls:'measured'};
  if (mode === 'deterministic_fallback') return {label:'Deterministic fallback', cls:'authored'};
  if (mode === 'deterministic') return {label:'Deterministic rule run', cls:'authored'};
  if (mode === 'what-if') return {label:'What-if (hypothetical)', cls:'hyp'};
  return {label:`Recorded decision (${mode || 'mode unavailable'})`, cls:'authored'};
}

export function candidateLayout(decision) {
  if (['search-v1','robustness-v2','physics-adapt-v1','physics-followup-v1'].includes(decision.rule_version)) return 'study';
  if (Array.isArray(decision.mcp_tool_calls)) return 'mcp';
  return 'legacy';
}
