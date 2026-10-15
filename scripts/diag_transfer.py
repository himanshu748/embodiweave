"""Validation-only diagnostic: why do warm starts plateau? (does not touch any final-test suite)"""
import json, sys, tempfile, time, os
os.environ["EW_ARTIFACTS"] = "/tmp/claude-0/ew-diag"
import numpy as np, torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import VecNormalize
sys.path.insert(0, ".")
from ew import rl
from ew.scenarios import SUITES
SRC = "/home/claude/embodiweave/artifacts/policies/P-open-a"
variant, seed = sys.argv[1], int(sys.argv[2])
venv = rl.make_vec(rl.FAMILIES["static_crossing"], rl.CONTRACT_V1, 8, seed)
if variant == "fresh_norm":
    venv = VecNormalize(venv, norm_obs=True, norm_reward=True, clip_obs=10.0, gamma=0.99)
else:
    venv = VecNormalize.load(f"{SRC}/vecnormalize.pkl", venv); venv.training = True
model = PPO.load(f"{SRC}/model.zip", env=venv, device="cpu", seed=seed)
if variant == "reset_std":
    with torch.no_grad(): model.policy.log_std.fill_(0.0)
if variant == "reset_value":
    for m in model.policy.mlp_extractor.value_net.modules():
        if hasattr(m, "reset_parameters"): m.reset_parameters()
    model.policy.value_net.reset_parameters()
val = SUITES["val-target-v1"]; sched = []
class CB(rl.BaseCallback):
    def _on_step(self):
        if self.num_timesteps % 37_500 < 8:
            sched.append((self.num_timesteps, rl.evaluate_live(self.model, venv, rl.CONTRACT_V1, val)["summary"]["success_rate"]))
        return True
t0 = time.time(); model.learn(150_000, callback=CB()); 
sched.append((model.num_timesteps, rl.evaluate_live(model, venv, rl.CONTRACT_V1, val)["summary"]["success_rate"]))
print(json.dumps({"variant": variant, "seed": seed, "schedule": sched, "wall_s": round(time.time() - t0, 1),
                  "final_log_std": model.policy.log_std.detach().numpy().round(2).tolist()}))
