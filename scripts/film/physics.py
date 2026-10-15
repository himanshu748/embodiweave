"""Offscreen MuJoCo renders from recorded physics states, never interpolated poses."""
from __future__ import annotations

import json
import math
from pathlib import Path

import mujoco
import numpy as np

from sim.mujoco.environment import MuJoCoNavEnv

ROOT = Path(__file__).resolve().parents[2]


class Replay:
    def __init__(self, episode, family, width=1920, height=1080):
        self.episode = episode
        self.env = MuJoCoNavEnv(family, layout=episode["layout"])
        self.env.reset()
        # Lighting changes are render-only. The frozen physics and sensor model
        # are untouched during evaluation; these do not move any simulated body.
        self.env.model.light_diffuse[:] *= .55
        self.env.model.vis.headlight.diffuse[:] = .20
        self.env.model.vis.headlight.ambient[:] = .15
        self.env.model.mat_texrepeat[self.env.model.material("floor").id] = [.5, .5]
        self.states = np.load(ROOT / "evidence/mujoco-v1" / episode["trajectory"], allow_pickle=False)
        self.renderer = mujoco.Renderer(self.env.model, width=width, height=height, max_geom=10000)
        self.camera = mujoco.MjvCamera()
        self.camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.options = mujoco.MjvOption()
        self.options.flags[mujoco.mjtVisFlag.mjVIS_RANGEFINDER] = False

    def connector(self, start, end, width, color):
        scene = self.renderer.scene
        geom = scene.geoms[scene.ngeom]
        mujoco.mjv_initGeom(geom, mujoco.mjtGeom.mjGEOM_CAPSULE, np.zeros(3), np.zeros(3), np.eye(3).ravel(), np.array(color, dtype=np.float32))
        mujoco.mjv_connector(geom, mujoco.mjtGeom.mjGEOM_CAPSULE, width, np.array(start), np.array(end))
        scene.ngeom += 1

    def frame(self, seconds, view="wide", camera_phase=0.):
        # Sample-and-hold actual recorded states. Never interpolate robot joints.
        index = max(0, min(len(self.states["time"])-1, int(np.searchsorted(self.states["time"], seconds, side="right")-1)))
        env = self.env
        env.data.qpos[:] = self.states["qpos"][index]
        env.data.mocap_pos[:] = self.states["mocap_pos"][index]
        env.data.mocap_quat[:] = self.states["mocap_quat"][index]
        env.data.time = self.states["time"][index]
        mujoco.mj_forward(env.model, env.data)
        env._sync_pose()
        x, y, theta = env.pose
        if view == "chase":
            self.camera.lookat[:] = [x+.25*math.cos(theta), y+.25*math.sin(theta), .15]
            self.camera.distance = 3.8
            self.camera.azimuth = math.degrees(theta)+180
            self.camera.elevation = -42
        elif view == "tactical":
            self.camera.lookat[:] = [5, 5, 0]
            self.camera.distance, self.camera.azimuth, self.camera.elevation = 13.6, 90, -89
        else:
            self.camera.lookat[:] = [5, 5, .10]
            self.camera.distance = 13.5-.6*(1-math.cos(math.pi*min(1, camera_phase)))/2
            self.camera.azimuth, self.camera.elevation = 125, -49
        self.renderer.update_scene(env.data, camera=self.camera, scene_option=self.options)
        for k in range(11):
            self.connector([k,0,.009],[k,10,.009],.003,[.28,.34,.35,.3])
            self.connector([0,k,.009],[10,k,.009],.003,[.28,.34,.35,.3])
        # Render-only rays and trails do not enter physics or sensor calculations.
        ranges = env._ray_ranges()
        for i, distance in enumerate(ranges):
            site = env.model.site(f"ray{i}").id
            start = env.data.site_xpos[site]
            direction = env.data.site_xmat[site].reshape(3,3)[:,2]
            end = start + direction*(distance+.20)
            color = [.92,.12,.05,.70] if distance < .4 else [.12,.65,.36,.20]
            self.connector(start, end, .006, color)
        start_index = max(0, index-100)
        for j in range(start_index+3, index+1, 3):
            start, end = self.states["qpos"][j-3,:3].copy(), self.states["qpos"][j,:3].copy()
            start[2] = end[2] = .012
            alpha = .05+.65*(j-start_index)/max(1,index-start_index)
            self.connector(start, end, .018, [1,.28,.035,alpha])
        return self.renderer.render().copy(), float(env.data.time)

    def close(self):
        self.renderer.close()
        self.states.close()


def smoke():
    from PIL import Image
    pair = json.loads((ROOT / "evidence/film/filmed-pair.json").read_text())
    replay = Replay(pair["deployed"], "static_crossing" if "static_crossing" in pair["suite"] else "crossing")
    image, _ = replay.frame(max(0, pair["deployed"]["seconds"]-1), "chase")
    Image.fromarray(image).save(ROOT / "docs/demo/physics-preview.png")
    replay.close()


if __name__ == "__main__":
    smoke()
