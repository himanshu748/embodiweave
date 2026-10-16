"""Training-only MuJoCo wrapper. The measured contact environment is unchanged."""
from .contract import CONTRACT_V1
from .env import REWARD
from .scenarios import FAMILIES
from sim.mujoco.environment import MuJoCoNavEnv


class PhysicsTrainingEnv(MuJoCoNavEnv):
    def __init__(self, family, contract, recipe_params):
        if contract.contract_id != CONTRACT_V1.contract_id:
            raise ValueError("Physics adaptation requires the recorded sensor/action semantics")
        super().__init__(family)
        self.training_families = recipe_params["training_families"]
        self.family_index = 0
        self.collision_penalty = recipe_params.get("collision_penalty", -10.)

    def reset(self, **kwargs):
        self.family = FAMILIES[self.training_families[self.family_index % len(self.training_families)]]
        self.family_index += 1
        return super().reset(**kwargs)

    def step(self, action):
        obs, reward, term, trunc, info = super().step(action)
        # Match the 2D training reward, including its proximity cost. No shaping
        # is applied to validation, transfer or confirmation environments.
        minimum = float(self._ray_ranges().min())
        if minimum < REWARD["proximity_band_m"]:
            reward += REWARD["proximity"] * (1-minimum/REWARD["proximity_band_m"])
        if info["outcome"] == "collision":
            reward += self.collision_penalty - REWARD["collision"]
        return obs, reward, term, trunc, info
