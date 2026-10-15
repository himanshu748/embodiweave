"""Measure raw env and PPO throughput on this host."""
import json, sys, time, os
import numpy as np
os.environ.setdefault("EW_ARTIFACTS", "/tmp/claude-0/ew-throughput")
from ew.env import EmbodiNavEnv
from ew import rl
out = {}
for fam in ("open", "static_crossing"):
    e = EmbodiNavEnv(fam); e.reset(seed=0); rng = np.random.default_rng(0); n = 0; t0 = time.time()
    while time.time() - t0 < 3:
        _, _, te, tr, _ = e.step(rng.uniform(-1, 1, 2)); n += 1
        if te or tr: e.reset()
    out[f"env_steps_per_s_{fam}"] = round(n / (time.time() - t0))
r = rl.train("throughput-probe", family="static_crossing", budget_steps=20480, seed=0)
out["ppo_steps"] = r["consumed_steps"]; out["ppo_wall_s"] = round(r["wall_s"], 2)
out["ppo_steps_per_s"] = round(r["consumed_steps"] / r["wall_s"])
out["weight_delta_l2"] = r["manifest"]["weight_delta_l2"]
out["runtime"] = r["manifest"]["runtime"]
print(json.dumps(out, indent=2))
