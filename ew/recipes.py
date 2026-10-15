"""Training recipe and exact rollout reservations, importable without torch."""
import math

RECIPES = {
    "ppo-r1": dict(n_envs=8, n_steps=256, batch_size=256, n_epochs=5, learning_rate=3e-4,
                   gamma=0.99, gae_lambda=0.95, clip_range=0.2, ent_coef=0.0,
                   net_arch=[64, 64]),
}


def reserved_steps(budget: int, recipe: str = "ppo-r1") -> int:
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise ValueError("budget must be a positive integer")
    rc = RECIPES[recipe]
    rollout = rc["n_envs"] * rc["n_steps"]
    return math.ceil(budget / rollout) * rollout
