"""Training recipe and exact rollout reservations, importable without torch."""
import math

RECIPES = {
    "ppo-r1": dict(n_envs=8, n_steps=256, batch_size=256, n_epochs=5, learning_rate=3e-4,
                   gamma=0.99, gae_lambda=0.95, clip_range=0.2, ent_coef=0.0,
                   net_arch=[64, 64]),
}

# Search recipes change training only. Canonical evaluation always uses ew-reward-1
# and the unchanged suite families. Keep identifiers immutable once measured.
RECIPES["ppo-rehearsal-v1"] = {**RECIPES["ppo-r1"],
    "training_families": ["open", "static", "crossing", "static_crossing"]}
RECIPES["ppo-collision20-v1"] = {**RECIPES["ppo-r1"], "collision_penalty": -20.0}
RECIPES["ppo-entropy-v1"] = {**RECIPES["ppo-r1"], "ent_coef": 0.005}
RECIPES["ppo-lr-v1"] = {**RECIPES["ppo-r1"], "learning_rate": 1e-4}


def reserved_steps(budget: int, recipe: str = "ppo-r1") -> int:
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise ValueError("budget must be a positive integer")
    rc = RECIPES[recipe]
    rollout = rc["n_envs"] * rc["n_steps"]
    return math.ceil(budget / rollout) * rollout
