"""Engineering checks before measuring transfer; no checkpoint outcome tuning."""
import math
import numpy as np
import pytest

pytest.importorskip("mujoco")
from sim.mujoco.environment import MuJoCoNavEnv
from ew.env import EmbodiNavEnv


def layout(theta=0, statics=None, movers=None):
    return {"start": [2, 5, theta], "goal": [9, 5], "statics": statics or [], "movers": movers or []}


def test_observation_rays_history_and_command_semantics():
    lay = layout(statics=[[4, 5, .5]])
    physics, ideal = MuJoCoNavEnv(layout=lay), EmbodiNavEnv(layout=lay)
    obs, _ = physics.reset()
    ref, _ = ideal.reset()
    assert obs.shape == (51,) and obs.dtype == np.float32
    np.testing.assert_allclose(obs, ref, atol=1e-6)
    np.testing.assert_allclose(obs[:17], obs[17:34])
    old = obs[:17].copy()
    obs, *_ = physics.step([0, .25])
    np.testing.assert_allclose(obs[3:5], [.5, .25])
    np.testing.assert_allclose(obs[17:34], old)


def test_forward_drive_is_real_wheel_motion_and_yaw_sign():
    env = MuJoCoNavEnv(layout=layout())
    env.reset()
    for _ in range(15): env.step([0, 0])
    assert 2.4 < env.pose[0] < 2.9 and abs(env.pose[1]-5) < .03
    assert abs(env.data.qpos[7]) > 1  # actual wheel joint rotation
    env.reset()
    for _ in range(10): env.step([-1, .5])
    assert .25 < env.pose[2] < 1.3  # positive command produces CCW heading, with physical lag


def test_contacts_stop_the_robot_and_movers_follow_script():
    env = MuJoCoNavEnv(layout=layout(statics=[[2.8, 5, .35]]), record=True)
    env.reset()
    for _ in range(30):
        _, _, term, _, info = env.step([1, 0])
        if term: break
    assert info["outcome"] == "collision" and info["hit"] == "static"
    assert env.data.time < 3
    assert env.physics_trace[-1]["time"] == env.data.time
    with pytest.raises(RuntimeError): env.step([1, 0])
    env = MuJoCoNavEnv("crossing", layout=layout(movers=[[6, 5, 0, .8, .5]]))
    env.reset()
    env.step([-1, 0])
    np.testing.assert_allclose(env.data.mocap_pos[0, :2], [6, 5.08], atol=1e-8)


def test_sensor_rotation_tracks_body_frame():
    env = MuJoCoNavEnv(layout=layout(math.pi/2, statics=[[2, 7, .5]]))
    obs, _ = env.reset()
    assert obs[5] == pytest.approx(1.3/4)
