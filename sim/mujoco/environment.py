"""A torque-limited, gravity/contact-driven differential-drive transfer test.

Only pedestrians are kinematic. No robot pose is written after reset. The adapter
preserves the *interface*, not the original ideal unicycle dynamics.
"""
from __future__ import annotations

import math
import mujoco
import numpy as np

from ew.contract import CONTRACT_V1
from ew.env import EmbodiNavEnv, GOAL_TOL, REWARD
from ew.scenarios import WORLD, generate_layout

VERSION = "ew-mujoco-1"
PHYSICS_DT = 0.005
WHEEL_RADIUS = 0.09
TRACK = 0.30


def model_xml(layout: dict) -> str:
    statics = "".join(
        f'<geom name="static{i}" type="cylinder" pos="{x} {y} .45" '
        f'size="{r} .45" material="obstacle"/>'
        for i, (x, y, r) in enumerate(layout["statics"]))
    movers = "".join(
        f'<body name="pedestrian{i}" mocap="true" pos="{m[0]} {m[1]} .60">'
        f'<geom name="mover{i}" type="capsule" size="{m[4]} .40" material="pedestrian"/>'
        '</body>' for i, m in enumerate(layout["movers"]))
    sites = []
    for i, angle in enumerate(CONTRACT_V1.ray_angles()):
        # MuJoCo rangefinders cast along the site's local +Z axis.
        sites.append(f'<site name="ray{i}" pos="0 0 .30" zaxis="{math.cos(angle)} {math.sin(angle)} 0" size=".003" rgba="0 0 0 0"/>')
    sensors = ''.join(f'<rangefinder name="range{i}" site="ray{i}" cutoff="4.2"/>' for i in range(12))
    return f'''<mujoco model="EmbodiWeave real physics transfer">
      <compiler angle="radian"/>
      <option timestep="{PHYSICS_DT}" gravity="0 0 -9.81" integrator="implicitfast" iterations="50"/>
      <visual><global offwidth="1920" offheight="1080"/><quality shadowsize="2048"/>
        <headlight ambient=".25 .25 .25" diffuse=".4 .4 .4" specular=".2 .2 .2"/>
        <map znear=".01" zfar="80"/><rgba haze=".86 .88 .89 1"/></visual>
      <default><geom friction="1 .005 .0001" condim="4" solref=".01 1" solimp=".95 .99 .001"/>
        <joint damping=".02" armature=".002"/></default>
      <asset>
        <texture name="sky" type="skybox" builtin="gradient" rgb1=".34 .43 .51" rgb2=".93 .94 .92" width="512" height="3072"/>
        <texture name="tiles" type="2d" builtin="checker" rgb1=".76 .78 .77" rgb2=".82 .84 .82" width="512" height="512" mark="edge" markrgb=".65 .69 .68"/>
        <material name="floor" texture="tiles" texrepeat="10 10" texuniform="true" reflectance=".1"/>
        <material name="shell" rgba=".14 .18 .20 1" shininess=".65" specular=".5"/>
        <material name="accent" rgba="1 .26 .035 1" shininess=".4"/>
        <material name="rubber" rgba=".035 .045 .05 1"/>
        <material name="obstacle" rgba=".39 .46 .48 1" shininess=".25"/>
        <material name="pedestrian" rgba=".91 .42 .13 1" shininess=".3"/>
      </asset>
      <worldbody>
        <light pos="3 1 9" dir=".2 .3 -1" diffuse=".8 .8 .76" directional="true" castshadow="true"/>
        <light pos="8 9 6" dir="-.4 -.4 -1" diffuse=".35 .4 .45" castshadow="false"/>
        <geom name="floor" type="plane" size="20 20 .1" material="floor"/>
        <geom name="wall0" type="box" pos="-.1 5 .5" size=".1 5.2 .5" rgba=".57 .63 .64 1"/>
        <geom name="wall1" type="box" pos="10.1 5 .5" size=".1 5.2 .5" rgba=".57 .63 .64 1"/>
        <geom name="wall2" type="box" pos="5 -.1 .5" size="5 .1 .5" rgba=".57 .63 .64 1"/>
        <geom name="wall3" type="box" pos="5 10.1 .5" size="5 .1 .5" rgba=".57 .63 .64 1"/>
        <geom name="goal" type="cylinder" pos="{layout['goal'][0]} {layout['goal'][1]} .004" size=".3 .004" rgba=".20 .67 .41 .75" contype="0" conaffinity="0"/>
        {statics}{movers}
        <body name="robot" pos="0 0 .12">
          <freejoint name="base"/>
          <geom name="chassis" type="cylinder" size=".20 .04" mass="3" material="shell"/>
          <geom type="box" pos=".10 0 .055" size=".07 .11 .015" material="accent" mass=".1"/>
          <geom type="cylinder" pos="0 0 .12" size=".07 .07" material="shell" mass=".15"/>
          <geom type="cylinder" pos="0 0 .20" size=".075 .015" material="accent" mass=".05"/>
          <geom name="caster_front" type="sphere" pos=".15 0 -.085" size=".035" mass=".02" friction=".01 .001 .0001" priority="1" condim="3"/>
          <geom name="caster_back" type="sphere" pos="-.15 0 -.085" size=".035" mass=".02" friction=".01 .001 .0001" priority="1" condim="3"/>
          <body name="left" pos="0 .15 -.03"><joint name="left_axle" type="hinge" axis="0 1 0"/>
            <geom name="left_wheel" type="cylinder" size=".09 .025" quat=".7071067812 .7071067812 0 0" mass=".25" material="rubber"/>
            <geom type="box" size=".065 .026 .008" rgba=".6 .65 .67 1" mass=".01"/>
          </body>
          <body name="right" pos="0 -.15 -.03"><joint name="right_axle" type="hinge" axis="0 1 0"/>
            <geom name="right_wheel" type="cylinder" size=".09 .025" quat=".7071067812 .7071067812 0 0" mass=".25" material="rubber"/>
            <geom type="box" size=".065 .026 .008" rgba=".6 .65 .67 1" mass=".01"/>
          </body>{''.join(sites)}
        </body>
      </worldbody>
      <actuator><velocity name="left_motor" joint="left_axle" kv=".5" forcelimited="true" forcerange="-3 3"/>
        <velocity name="right_motor" joint="right_axle" kv=".5" forcelimited="true" forcerange="-3 3"/></actuator>
      <sensor>{sensors}</sensor>
    </mujoco>'''


class MuJoCoNavEnv(EmbodiNavEnv):
    def __init__(self, family="open", *, record=False, layout=None):
        super().__init__(family, CONTRACT_V1, record=record, layout=layout)
        self.model = self.data = None
        self.physics_trace = []
        self._next_sample = 0

    def _sync_pose(self):
        rot = self.data.xmat[self.robot_body].reshape(3, 3)
        self.pose = np.array([*self.data.xpos[self.robot_body, :2], math.atan2(rot[1, 0], rot[0, 0])])

    def _ray_ranges(self):
        # No-hit is -1. Max measured centre distance is 4.2 m, yielding 4 m free space.
        distances = self.data.sensordata[:12]
        return np.clip(np.where(distances < 0, 4.2, distances) - .20, 0, 4)

    def reset(self, *, seed=None, options=None):
        # Initialize Gym's RNG without invoking the kinematic environment reset.
        import gymnasium as gym
        gym.Env.reset(self, seed=seed)
        lay = (options or {}).get("layout") or self.fixed_layout or generate_layout(self.family, self.np_random)
        self.layout = lay
        self.xml = model_xml(lay)
        self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.data = mujoco.MjData(self.model)
        x, y, theta = lay["start"]
        self.data.qpos[:7] = [x, y, .12, math.cos(theta/2), 0, 0, math.sin(theta/2)]
        self.robot_body = self.model.body("robot").id
        self.robot_bodies = {self.robot_body, self.model.body("left").id, self.model.body("right").id}
        self.goal = np.array(lay["goal"], dtype=float)
        self.statics = [list(v) for v in lay["statics"]]
        self.movers = [list(v) for v in lay["movers"]]
        self.t, self.last_cmd, self._contact_hit = 0, (0., 0.), None
        mujoco.mj_forward(self.model, self.data)
        self._sync_pose()
        self.prev_dist = self._goal_polar()[0]
        self._hist = np.tile(self._frame(), (3, 1))
        self.trace = [self._state(None)] if self.record else []
        self.physics_trace, self._next_sample = [], 0
        self._sample()
        return self._obs(), {"layout": lay}

    def _sample(self):
        if self.record:
            self.physics_trace.append({"time": float(self.data.time), "qpos": self.data.qpos.tolist(),
                                       "mocap_pos": self.data.mocap_pos.tolist(),
                                       "mocap_quat": self.data.mocap_quat.tolist(),
                                       "ranges": self._ray_ranges().tolist()})
        self._next_sample += 1 / 30

    def _contact(self):
        for contact in self.data.contact:
            g1, g2 = contact.geom1, contact.geom2
            b1, b2 = self.model.geom_bodyid[[g1, g2]]
            if (b1 in self.robot_bodies) == (b2 in self.robot_bodies):
                continue
            other = g2 if b1 in self.robot_bodies else g1
            name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, int(other)) or ""
            if contact.dist <= 0:
                for kind in ("wall", "static", "mover"):
                    if name.startswith(kind):
                        return kind
        return None

    def step(self, action):
        if self._contact_hit:
            raise RuntimeError("episode ended in collision; reset before stepping")
        a = np.clip(np.asarray(action, dtype=float), -1, 1)
        v, w = (a[0]+1)/2, a[1]*2
        self.data.ctrl[:] = [(v-w*TRACK/2)/WHEEL_RADIUS, (v+w*TRACK/2)/WHEEL_RADIUS]
        self.last_cmd = (float(v), float(w))
        # Simultaneous continuous contact dynamics; movers reflect each 5ms physics tick.
        for _ in range(round(self.c.dt_s / PHYSICS_DT)):
            for i, m in enumerate(self.movers):
                for axis in (0, 1):
                    m[axis] += m[axis+2]*PHYSICS_DT
                    if m[axis] < m[4] or m[axis] > WORLD-m[4]:
                        m[axis+2] *= -1
                        m[axis] = float(np.clip(m[axis], m[4], WORLD-m[4]))
                self.data.mocap_pos[i, :2] = m[:2]
            mujoco.mj_step(self.model, self.data)
            self._contact_hit = self._contact()
            if self.data.time + 1e-9 >= self._next_sample or self._contact_hit:
                self._sample()
            if self._contact_hit:
                break
        mujoco.mj_forward(self.model, self.data)
        self._sync_pose()
        self.t += 1
        d, _ = self._goal_polar()
        success = not self._contact_hit and d < GOAL_TOL
        term = bool(self._contact_hit or success)
        trunc = not term and self.t >= self.family.max_steps
        outcome = "collision" if self._contact_hit else "success" if success else "timeout" if trunc else None
        self._hist = np.roll(self._hist, 1, axis=0)
        self._hist[0] = self._frame()
        reward = REWARD["progress"]*(self.prev_dist-d) + REWARD["time"]
        if outcome == "collision": reward += REWARD["collision"]
        if outcome == "success": reward += REWARD["success"]
        self.prev_dist = d
        if self.record:
            self.trace.append(self._state(outcome))
            if term or trunc:
                # Preserve the actual terminal state even if it falls between video samples.
                self.physics_trace.append({"time": float(self.data.time), "qpos": self.data.qpos.tolist(),
                    "mocap_pos": self.data.mocap_pos.tolist(), "mocap_quat": self.data.mocap_quat.tolist(),
                    "ranges": self._ray_ranges().tolist()})
        return self._obs(), float(reward), term, trunc, {"outcome": outcome, "hit": self._contact_hit, "t": self.t, "goal_dist": d}
