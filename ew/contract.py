"""Semantic observation/action contract for the EmbodiWeave mobile robot.

The contract is frozen before any reusable checkpoint is trained. Two contracts with the
same array shape are NOT compatible unless every semantic field matches; the contract id is
a hash over the full semantic description, so changing ray ordering (for example) produces a
different id even though the observation length is unchanged.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class RobotConfig:
    name: str = "ew-unicycle-r20"
    body: str = "unicycle (differential-drive kinematics), disc body"
    radius_m: float = 0.20
    v_max_mps: float = 1.0          # forward speed limit; no reverse
    w_max_radps: float = 2.0        # yaw-rate limit


@dataclass(frozen=True)
class PolicyContract:
    version: str = "ew-contract-1"
    robot: RobotConfig = field(default_factory=RobotConfig)
    dt_s: float = 0.1               # control timestep, no action repeat
    n_rays: int = 12
    ray_max_m: float = 4.0
    # Rays start at robot heading (0 rad) and proceed counter-clockwise in 30 degree steps.
    ray_order: str = "ccw-from-heading"
    history: int = 3                # frames stacked, newest first
    history_reset: str = "fill-with-first-frame"
    frame_features: tuple = (
        "goal_dist / 10 m, clipped to [0, 1.5]",
        "cos(goal bearing in robot frame)",
        "sin(goal bearing in robot frame)",
        "previous v command / v_max, in [0, 1]",
        "previous w command / w_max, in [-1, 1]",
        "ray_i free range / ray_max, in [0, 1], 1 = nothing within ray_max (i = 0..n_rays-1)",
    )
    frame: str = "robot body frame, x forward, y left, angles radians CCW positive"
    units: str = "metres, seconds, radians"
    action_order: str = "[a_v, a_w]"
    action_bounds: tuple = (-1.0, 1.0)
    action_clip: str = "clip each component to [-1, 1] before mapping"
    action_map: str = "v = (a_v + 1) / 2 * v_max ; w = a_w * w_max"
    wrappers: tuple = ("EmbodiNavEnv(history inside env)", "Monitor", "DummyVecEnv", "VecNormalize(norm_obs, norm_reward, clip_obs=10)")
    normalization: str = "VecNormalize running obs mean/var saved per checkpoint as vecnormalize.pkl; eval uses training=False, norm_reward=False"

    @property
    def frame_dim(self) -> int:
        return 5 + self.n_rays

    @property
    def obs_dim(self) -> int:
        return self.frame_dim * self.history

    def ray_angles(self) -> list[float]:
        step = 2 * math.pi / self.n_rays
        angles = [i * step for i in range(self.n_rays)]
        if self.ray_order == "cw-from-heading":
            angles = [-a for a in angles]
        return angles

    def describe(self) -> dict:
        d = asdict(self)
        d["frame_dim"] = self.frame_dim
        d["obs_dim"] = self.obs_dim
        return d

    @property
    def contract_id(self) -> str:
        blob = json.dumps(self.describe(), sort_keys=True, default=list).encode()
        return f"{self.version}:{hashlib.sha256(blob).hexdigest()[:12]}"


CONTRACT_V1 = PolicyContract()
# Same shape, different semantics (ray order mirrored). Used only to build a checkpoint that
# must be rejected by the compatibility check even though its tensors line up.
CONTRACT_MIRRORED = PolicyContract(version="ew-contract-1m", ray_order="cw-from-heading")

CONTRACTS = {c.contract_id: c for c in (CONTRACT_V1, CONTRACT_MIRRORED)}


def get_contract(contract_id: str) -> PolicyContract:
    return CONTRACTS[contract_id]
