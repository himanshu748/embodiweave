"""Real PPO training and evaluation of saved artifacts (Stable-Baselines3)."""
from __future__ import annotations

import json
import platform
import tempfile
import time
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from . import artifacts
from .contract import CONTRACT_V1, PolicyContract, get_contract
from .env import DYNAMICS_VERSION, REWARD_VERSION, EmbodiNavEnv
from .scenarios import FAMILIES, Family, Suite, generate_layout
from .recipes import RECIPES, reserved_steps
from .provenance import source_snapshot

torch.set_num_threads(1)


class TrainingEnv(EmbodiNavEnv):
    """Training-only interventions; never used by the evaluation path.

    Rehearsal cycles authored families at episode boundaries. It never uses a
    validation layout or seed. Reward shaping adds a terminal collision penalty.
    """
    def __init__(self, family, contract, recipe_params, **kwargs):
        super().__init__(family, contract, **kwargs)
        self.training_families = recipe_params.get("training_families", [])
        self.family_index = 0
        self.collision_penalty = recipe_params.get("collision_penalty", -10.0)

    def reset(self, **kwargs):
        if self.training_families:
            self.family = FAMILIES[self.training_families[self.family_index % len(self.training_families)]]
            self.family_index += 1
        return super().reset(**kwargs)

    def step(self, action):
        obs, reward, term, trunc, info = super().step(action)
        if info.get("outcome") == "collision":
            reward += self.collision_penalty + 10.0
        return obs, reward, term, trunc, info



def runtime_versions() -> dict:
    import gymnasium, stable_baselines3
    return {"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__,
            "gymnasium": gymnasium.__version__, "stable_baselines3": stable_baselines3.__version__,
            "dynamics": DYNAMICS_VERSION, "reward": REWARD_VERSION, "machine": platform.machine()}


def make_vec(family: Family, contract: PolicyContract, n_envs: int, seed: int, on_frame=None,
             recipe_params=None) -> DummyVecEnv:
    def mk(i):
        def _f():
            params = recipe_params or {}
            if params.get("physics") == "mixed-mujoco" and i % 2 == 0:
                from .physics_train import PhysicsTrainingEnv
                base = PhysicsTrainingEnv(family, contract, params)
            else:
                base = TrainingEnv(family, contract, params, on_frame=on_frame if i == 0 else None)
            e = Monitor(base)
            e.reset(seed=seed * 1000 + i)
            return e
        return _f
    v = DummyVecEnv([mk(i) for i in range(n_envs)])
    v.seed(seed * 1000)
    return v


class _Progress(BaseCallback):
    def __init__(self, every: int, on_progress, should_cancel, evaluator):
        super().__init__()
        self.every, self.on_progress, self.should_cancel, self.evaluator = every, on_progress, should_cancel, evaluator
        self.next_mark = every
        self.cancelled = False
        self.ep_outcomes: list = []

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            if info.get("outcome"):
                self.ep_outcomes.append(info["outcome"])
        if self.num_timesteps >= self.next_mark:
            self.next_mark += self.every
            recent = self.ep_outcomes[-200:]
            sr = recent.count("success") / len(recent) if recent else None
            if self.evaluator:
                self.evaluator(self.num_timesteps, self.model)
            if self.on_progress:
                self.on_progress({"steps": self.num_timesteps, "train_success_recent": sr,
                                  "episodes": len(self.ep_outcomes)})
        if self.should_cancel and self.should_cancel():
            self.cancelled = True
            return False
        return True


def train(policy_id: str, *, family: Family | str, budget_steps: int, seed: int,
          parent_id: str | None = None, recipe: str = "ppo-r1", contract: PolicyContract | None = None,
          on_progress: Callable | None = None, should_cancel: Callable | None = None,
          validation: Suite | None = None, validation_every: int | None = None,
          run_id: str | None = None, on_frame=None) -> dict:
    """Train PPO for budget_steps environment steps. Parent artifacts are read, never modified.

    Returns a result dict with status completed|cancelled, consumed steps, the new policy manifest
    and the validation schedule results (if a validation suite was given).
    """
    fam = FAMILIES[family] if isinstance(family, str) else family
    training_source = source_snapshot()
    rc = RECIPES[recipe]
    reservation = reserved_steps(budget_steps, recipe)
    if parent_id:
        pm = artifacts.load_manifest(parent_id)
        artifacts.verify_policy(parent_id)
        pc = get_contract(pm["contract_id"])
        if contract is not None and contract.contract_id != pc.contract_id:
            raise ValueError("contract mismatch between requested contract and parent")
        contract = pc
    contract = contract or CONTRACT_V1
    venv = make_vec(fam, contract, rc["n_envs"], seed, on_frame=on_frame, recipe_params=rc)
    pdir = artifacts.policy_dir(parent_id) if parent_id else None
    if parent_id:
        venv = VecNormalize.load(str(pdir / "vecnormalize.pkl"), venv)
        venv.training, venv.norm_reward = True, True
        # PPO.load otherwise silently keeps the parent's optimizer hyperparameters.
        # Pass the recorded recipe explicitly, preserving parent weights and stats.
        model = PPO.load(str(pdir / "model.zip"), env=venv, device="cpu", seed=seed,
                         **{k: rc[k] for k in ("n_steps", "batch_size", "n_epochs", "learning_rate",
                                               "gamma", "gae_lambda", "clip_range", "ent_coef")})
    else:
        venv = VecNormalize(venv, norm_obs=True, norm_reward=True, clip_obs=10.0, gamma=rc["gamma"])
        model = PPO("MlpPolicy", venv, device="cpu", seed=seed, verbose=0,
                    n_steps=rc["n_steps"], batch_size=rc["batch_size"], n_epochs=rc["n_epochs"],
                    learning_rate=rc["learning_rate"], gamma=rc["gamma"], gae_lambda=rc["gae_lambda"],
                    clip_range=rc["clip_range"], ent_coef=rc["ent_coef"],
                    policy_kwargs={"net_arch": rc["net_arch"]})
    w0 = torch.nn.utils.parameters_to_vector(model.policy.parameters()).detach().clone()

    schedule: list = []

    def evaluator(steps, mdl):
        if validation is None:
            return
        res = evaluate_live(mdl, venv, contract, validation)
        schedule.append({"steps": int(steps), "suite_id": validation.suite_id, **res["summary"]})

    every = validation_every or max(budget_steps // 4, rc["n_envs"] * rc["n_steps"])
    cb = _Progress(every, on_progress, should_cancel, evaluator if validation else None)
    t0 = time.time()
    model.learn(total_timesteps=budget_steps, callback=cb, reset_num_timesteps=True, progress_bar=False)
    wall = time.time() - t0
    consumed = int(model.num_timesteps)
    if consumed > reservation:
        raise RuntimeError("optimizer exceeded its reserved rollout budget")
    w1 = torch.nn.utils.parameters_to_vector(model.policy.parameters()).detach()
    if validation and (not schedule or schedule[-1]["steps"] != consumed):
        evaluator(consumed, model)

    tmp = Path(tempfile.mkdtemp(prefix="ew-ckpt-"))
    model.save(str(tmp / "model.zip"))
    venv.save(str(tmp / "vecnormalize.pkl"))
    manifest = artifacts.write_policy(policy_id, tmp, {
        "parent_id": parent_id, "run_id": run_id, "contract_id": contract.contract_id,
        "robot": contract.robot.name, "family": fam.name, "family_id": fam.fid(), "recipe": recipe,
        "recipe_params": rc, "seed": seed, "budget_steps": budget_steps, "consumed_steps": consumed,
        "reserved_steps": reservation, "source": training_source,
        "status": "cancelled" if cb.cancelled else "completed", "wall_s": round(wall, 2),
        "weight_delta_l2": float(torch.norm(w1 - w0)), "runtime": runtime_versions(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    })
    venv.close()
    return {"status": manifest["status"], "consumed_steps": consumed, "wall_s": wall,
            "manifest": manifest, "validation_schedule": schedule,
            "train_episodes": len(cb.ep_outcomes)}


# ---------------- evaluation ----------------

def suite_layouts(suite_or_family, seeds) -> list[dict]:
    fam = suite_or_family
    return [generate_layout(fam, np.random.default_rng(s)) for s in seeds]


def _run_episodes(policy_fn, contract, family, layouts, record, on_frame=None, should_cancel=None):
    eps = []
    for episode_index, lay in enumerate(layouts):
        observer = (lambda sample, i=episode_index: on_frame({**sample, "episode": i})) if on_frame else None
        env = EmbodiNavEnv(family, contract, record=record, on_frame=observer)
        obs, _ = env.reset(options={"layout": lay})
        done, ret = False, 0.0
        while not done:
            if should_cancel and should_cancel():
                raise InterruptedError("Evaluation cancelled")
            a = policy_fn(obs)
            obs, r, term, trunc, info = env.step(a)
            ret += r
            done = term or trunc
        ep = {"outcome": info["outcome"], "steps": info["t"], "return": round(ret, 3),
              "final_goal_dist": round(info["goal_dist"], 3), "hit": info["hit"]}
        if record:
            ep["trace"] = env.trace
            ep["layout"] = lay
        eps.append(ep)
    return eps


def summarize(eps: list) -> dict:
    n = len(eps)
    oc = [e["outcome"] for e in eps]
    succ = [e["steps"] for e in eps if e["outcome"] == "success"]
    return {"episodes": n, "success_rate": round(oc.count("success") / n, 4),
            "collision_rate": round(oc.count("collision") / n, 4),
            "timeout_rate": round(oc.count("timeout") / n, 4),
            "mean_success_steps": round(float(np.mean(succ)), 1) if succ else None,
            "collisions_by_object": {k: sum(1 for e in eps if e.get("hit") == k) for k in ("wall", "static", "mover")}}


def evaluate_live(model, venv: VecNormalize, contract, suite: Suite) -> dict:
    """Evaluate an in-memory model with frozen normalization (used for validation schedules)."""
    def fn(o):
        on = np.clip((o - venv.obs_rms.mean) / np.sqrt(venv.obs_rms.var + venv.epsilon), -venv.clip_obs, venv.clip_obs)
        return model.predict(on.astype(np.float32), deterministic=True)[0]
    eps = _run_episodes(fn, contract, suite.family, suite_layouts(suite.family, suite.seeds), False)
    return {"summary": summarize(eps)}


def load_policy(policy_id: str, expected_hash: str | None = None, policy_path: Path | None = None):
    d = Path(policy_path) if policy_path else artifacts.policy_dir(policy_id)
    h = artifacts.verify_directory(d, expected_hash)
    m = json.loads((d / "manifest.json").read_text())
    contract = get_contract(m["contract_id"])
    dummy = DummyVecEnv([lambda: EmbodiNavEnv("open", contract)])
    vn = VecNormalize.load(str(d / "vecnormalize.pkl"), dummy)
    vn.training, vn.norm_reward = False, False
    model = PPO.load(str(d / "model.zip"), device="cpu")
    return model, vn, contract, m, h


def evaluate_policy(policy_id: str, family: Family, seeds, record: bool = False,
                    expected_hash: str | None = None, eval_contract: PolicyContract | None = None,
                    policy_path: Path | None = None, on_frame=None, should_cancel=None) -> dict:
    """Reload the saved artifact from disk and evaluate it on fixed layouts.

    eval_contract defaults to the policy's own contract. Passing a different one runs the policy
    in an environment with other semantics (used only to demonstrate why mismatches are rejected).
    """
    model, vn, contract, m, h = load_policy(policy_id, expected_hash, policy_path)
    env_contract = eval_contract or contract

    def fn(o):
        return model.predict(vn.normalize_obs(o[None, :]).astype(np.float32), deterministic=True)[0][0]
    t0 = time.time()
    eps = _run_episodes(fn, env_contract, family, suite_layouts(family, seeds), record, on_frame=on_frame, should_cancel=should_cancel)
    return {"policy_id": policy_id, "artifact_hash": h, "contract_id": env_contract.contract_id,
            "family_id": family.fid(), "seeds": list(seeds), "summary": summarize(eps),
            "episodes": eps, "wall_s": round(time.time() - t0, 2)}
