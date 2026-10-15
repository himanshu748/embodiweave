"""EmbodiNavEnv: CPU-only Gymnasium environment for a simulated unicycle robot.

Step order (frozen in reward/dynamics version ew-dyn-1 / ew-reward-1):
  1. clip action, map to (v, w) via the contract
  2. integrate robot pose for dt (exact unicycle arc)
  3. move each dynamic obstacle for dt, reflect off arena walls
  4. check collision (robot disc vs obstacles or walls), then success (goal_dist < 0.3 m)
  5. build the frame, push it into the history (newest first)
"""
from __future__ import annotations

import math

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .contract import CONTRACT_V1, PolicyContract
from .scenarios import FAMILIES, WORLD, Family, generate_layout

DYNAMICS_VERSION = "ew-dyn-1"
REWARD_VERSION = "ew-reward-1"
GOAL_TOL = 0.3
REWARD = {"progress": 1.0, "time": -0.005, "success": 10.0, "collision": -10.0,
          "proximity": -0.05, "proximity_band_m": 0.4}


class EmbodiNavEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, family: Family | str = "open", contract: PolicyContract = CONTRACT_V1,
                 record: bool = False, layout: dict | None = None):
        self.family = FAMILIES[family] if isinstance(family, str) else family
        self.c = contract
        self.record = record
        self.fixed_layout = layout
        self._angles = np.array(contract.ray_angles())
        self.observation_space = spaces.Box(-1.5, 1.5, shape=(contract.obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)
        self.trace: list = []
        self._hist: np.ndarray | None = None

    # ---------- geometry ----------
    def _ray_ranges(self) -> np.ndarray:
        x, y, th = self.pose
        ang = th + self._angles
        dx, dy = np.cos(ang), np.sin(ang)
        # walls
        with np.errstate(divide="ignore", invalid="ignore"):
            tx = np.where(dx > 0, (WORLD - x) / dx, np.where(dx < 0, -x / dx, np.inf))
            ty = np.where(dy > 0, (WORLD - y) / dy, np.where(dy < 0, -y / dy, np.inf))
        hit = np.minimum(tx, ty)
        obs = self._obstacles()
        if len(obs):
            ox = obs[:, 0][None, :] - x
            oy = obs[:, 1][None, :] - y
            r = obs[:, 2][None, :]
            b = ox * dx[:, None] + oy * dy[:, None]
            cc = ox ** 2 + oy ** 2 - r ** 2
            disc = b ** 2 - cc
            t = b - np.sqrt(np.maximum(disc, 0))
            t = np.where((disc >= 0) & (t > 0), t, np.where(cc <= 0, 0.0, np.inf))
            hit = np.minimum(hit, t.min(axis=1))
        free = np.clip(hit - self.c.robot.radius_m, 0.0, self.c.ray_max_m)
        return free

    def _obstacles(self) -> np.ndarray:
        rows = [s for s in self.statics] + [[m[0], m[1], m[4]] for m in self.movers]
        return np.array(rows, dtype=np.float64).reshape(-1, 3)

    def _goal_polar(self):
        x, y, th = self.pose
        gx, gy = self.goal
        d = math.hypot(gx - x, gy - y)
        bearing = math.atan2(gy - y, gx - x) - th
        return d, bearing

    def _frame(self) -> np.ndarray:
        d, b = self._goal_polar()
        rays = self._ray_ranges() / self.c.ray_max_m
        f = np.empty(self.c.frame_dim, dtype=np.float32)
        f[0] = min(d / 10.0, 1.5)
        f[1] = math.cos(b)
        f[2] = math.sin(b)
        f[3] = self.last_cmd[0] / self.c.robot.v_max_mps
        f[4] = self.last_cmd[1] / self.c.robot.w_max_radps
        f[5:] = rays
        return f

    def _collided(self) -> str | None:
        """Return what the robot hit (wall | static | mover) or None."""
        x, y, _ = self.pose
        R = self.c.robot.radius_m
        if not (R <= x <= WORLD - R and R <= y <= WORLD - R):
            return "wall"
        obs = self._obstacles()
        if len(obs) == 0:
            return None
        d = np.hypot(obs[:, 0] - x, obs[:, 1] - y)
        hit = np.nonzero(d < obs[:, 2] + R)[0]
        if len(hit) == 0:
            return None
        return "static" if hit[0] < len(self.statics) else "mover"

    def _obs(self) -> np.ndarray:
        return self._hist.reshape(-1).copy()

    # ---------- gym API ----------
    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        lay = (options or {}).get("layout") or self.fixed_layout or generate_layout(self.family, self.np_random)
        self.layout = lay
        self.pose = np.array(lay["start"], dtype=np.float64)
        self.goal = np.array(lay["goal"], dtype=np.float64)
        self.statics = [list(s) for s in lay["statics"]]
        self.movers = [list(m) for m in lay["movers"]]
        self.last_cmd = (0.0, 0.0)
        self.t = 0
        self.prev_dist = self._goal_polar()[0]
        f = self._frame()
        # history reset: every slot holds the first frame of THIS episode
        self._hist = np.tile(f, (self.c.history, 1))
        self.trace = [self._state(None)] if self.record else []
        return self._obs(), {"layout": lay}

    def step(self, action):
        a = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        v = (a[0] + 1.0) / 2.0 * self.c.robot.v_max_mps
        w = a[1] * self.c.robot.w_max_radps
        dt = self.c.dt_s
        x, y, th = self.pose
        if abs(w) < 1e-6:
            x += v * dt * math.cos(th)
            y += v * dt * math.sin(th)
        else:
            x += v / w * (math.sin(th + w * dt) - math.sin(th))
            y -= v / w * (math.cos(th + w * dt) - math.cos(th))
        th = (th + w * dt + math.pi) % (2 * math.pi) - math.pi
        self.pose = np.array([x, y, th])
        for m in self.movers:
            m[0] += m[2] * dt
            m[1] += m[3] * dt
            r = m[4]
            if m[0] < r or m[0] > WORLD - r:
                m[2] = -m[2]
                m[0] = min(max(m[0], r), WORLD - r)
            if m[1] < r or m[1] > WORLD - r:
                m[3] = -m[3]
                m[1] = min(max(m[1], r), WORLD - r)
        self.last_cmd = (v, w)
        self.t += 1

        d, _ = self._goal_polar()
        hit = self._collided()
        collided = hit is not None
        success = (not collided) and d < GOAL_TOL
        f = self._frame()
        self._hist = np.roll(self._hist, 1, axis=0)
        self._hist[0] = f

        min_free = float(f[5:].min()) * self.c.ray_max_m
        r = REWARD["progress"] * (self.prev_dist - d) + REWARD["time"]
        if min_free < REWARD["proximity_band_m"]:
            r += REWARD["proximity"] * (1 - min_free / REWARD["proximity_band_m"])
        self.prev_dist = d
        terminated = collided or success
        if collided:
            r += REWARD["collision"]
        if success:
            r += REWARD["success"]
        truncated = (not terminated) and self.t >= self.family.max_steps
        outcome = "collision" if collided else "success" if success else "timeout" if truncated else None
        info = {"outcome": outcome, "t": self.t, "goal_dist": d, "hit": hit}
        if self.record:
            self.trace.append(self._state(outcome))
        return self._obs(), float(r), terminated, truncated, info

    def _state(self, outcome):
        return {"t": self.t, "robot": [round(float(v), 4) for v in self.pose],
                "movers": [[round(m[0], 4), round(m[1], 4)] for m in self.movers],
                "cmd": [round(self.last_cmd[0], 4), round(self.last_cmd[1], 4)], "outcome": outcome}
