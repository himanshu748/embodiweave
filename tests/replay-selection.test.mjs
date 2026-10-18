import test from 'node:test';
import assert from 'node:assert/strict';
import {selectReplayPair} from '../web/replay-selection.mjs';
const rows = [
  {id:'baseline', policy_id:'P-static-b', suite_id:'val-target-v1'},
  {id:'confirmed', policy_id:'current', suite_id:'val-target-v1'},
  {id:'old-child', policy_id:'scratch~old', suite_id:'val-target-v1'},
  {id:'other-suite', policy_id:'current', suite_id:'val-open-v1'},
  {id:'selected', policy_id:'requested', suite_id:'val-target-v1'},
];
test('a direct Studio visit compares the deployed policy with the historical baseline',()=>{
  const p=selectReplayPair(rows,null,'current');
  assert.equal(p.before.id,'baseline'); assert.equal(p.after.id,'confirmed');
});
test('an explicit policy link takes precedence over the current default',()=>{
  assert.equal(selectReplayPair(rows,'requested','current').after.id,'selected');
});
test('an unknown policy never silently substitutes an unrelated child',()=>{
  assert.equal(selectReplayPair(rows,'missing','current').after,null);
});
test('a missing current target replay does not substitute a different suite or child',()=>{
  assert.equal(selectReplayPair(rows.filter(r=>r.id!=='confirmed'),null,'current').after,null);
});

import {readFileSync} from 'node:fs';
import {decisionMode, candidateLayout} from '../web/replay-selection.mjs';
test('recorded v4 uses the MCP candidate table and an LLM label',()=>{
  const decision=JSON.parse(readFileSync(new URL('../evidence/mcp-agent-v4/decision.json',import.meta.url),'utf8'));
  assert.equal(candidateLayout(decision),'mcp'); assert.equal(decisionMode(decision.mode).label,'LLM agent');
  assert.ok(decision.ranking.every(row=>row.p_reach===undefined));
});
test('fallback and unknown modes are not labelled as LLM decisions',()=>{
  assert.equal(decisionMode('deterministic_fallback').label,'Deterministic fallback');
  assert.equal(decisionMode('new_mode').label,'Recorded decision (new_mode)');
});
