"""Learnability probe: scratch PPO on one family, then reload the saved artifact and evaluate it."""
import json, sys, os
from ew import rl
from ew.scenarios import SUITES, FAMILIES
pid, fam, steps, seed, suite = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
s = SUITES[suite]
r = rl.train(pid, family=fam, budget_steps=steps, seed=seed, validation=s, validation_every=steps // 5)
ev = rl.evaluate_policy(pid, s.family, s.seeds)
print(json.dumps({"policy": pid, "family": fam, "steps": r["consumed_steps"], "wall_s": round(r["wall_s"], 1),
  "weight_delta_l2": r["manifest"]["weight_delta_l2"], "artifact_hash": r["manifest"]["artifact_hash"],
  "schedule": r["validation_schedule"], "reloaded_eval": ev["summary"], "suite": suite}, indent=1))
