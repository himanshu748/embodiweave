import math

import numpy as np
import pytest
from stable_baselines3.common.env_checker import check_env

from ew.contract import CONTRACT_MIRRORED, CONTRACT_V1
from ew.env import EmbodiNavEnv
from ew.scenarios import FAMILIES, SUITES, generate_layout


@pytest.mark.parametrize("fam", list(FAMILIES))
def test_sb3_checker(fam):
    check_env(EmbodiNavEnv(fam), warn=True, skip_render_check=True)


def test_seeded_reset_is_deterministic():
    a, b = EmbodiNavEnv("static_crossing"), EmbodiNavEnv("static_crossing")
    oa, ia = a.reset(seed=7)
    ob, ib = b.reset(seed=7)
    assert np.array_equal(oa, ob) and ia["layout"] == ib["layout"]
    oc, ic = a.reset(seed=8)
    assert ic["layout"] != ia["layout"]


def test_suite_layouts_fixed():
    s = SUITES["val-target-v1"]
    l1 = [generate_layout(s.family, np.random.default_rng(x)) for x in s.seeds[:5]]
    l2 = [generate_layout(s.family, np.random.default_rng(x)) for x in s.seeds[:5]]
    assert l1 == l2


def test_motion_straight_and_turn():
    e = EmbodiNavEnv("open")
    e.reset(seed=0, options={"layout": {"start": [5, 5, 0.0], "goal": [9, 9], "statics": [], "movers": []}})
    e.step([1.0, 0.0])  # v = v_max, w = 0
    assert e.pose[0] == pytest.approx(5.1) and e.pose[1] == pytest.approx(5.0)
    e.step([-1.0, 1.0])  # v = 0, w = w_max -> pure rotation
    assert e.pose[0] == pytest.approx(5.1) and e.pose[2] == pytest.approx(0.2)


def test_collision_with_static_terminates():
    e = EmbodiNavEnv("static")
    e.reset(options={"layout": {"start": [5, 5, 0.0], "goal": [9, 5], "statics": [[5.75, 5, 0.5]], "movers": []}})
    out = None
    for _ in range(10):
        _, _, term, trunc, info = e.step([1.0, 0.0])
        if term:
            out = info["outcome"]
            break
    assert out == "collision"


def test_wall_collision_and_timeout():
    e = EmbodiNavEnv("open")
    e.reset(options={"layout": {"start": [0.5, 5, math.pi], "goal": [9, 5], "statics": [], "movers": []}})
    _, _, term, _, info = e.step([1.0, 0.0])
    _, _, term, _, info = e.step([1.0, 0.0])
    _, _, term, _, info = e.step([1.0, 0.0])
    _, _, term, _, info = e.step([1.0, 0.0])
    assert term and info["outcome"] == "collision"
    e.reset(options={"layout": {"start": [5, 5, 0.0], "goal": [9, 9], "statics": [], "movers": []}})
    for i in range(400):
        _, _, term, trunc, info = e.step([-1.0, 0.0])  # stand still
        if term or trunc:
            break
    assert trunc and not term and info["outcome"] == "timeout" and info["t"] == FAMILIES["open"].max_steps


def test_success_when_reaching_goal():
    e = EmbodiNavEnv("open")
    e.reset(options={"layout": {"start": [5, 5, 0.0], "goal": [6, 5], "statics": [], "movers": []}})
    for _ in range(20):
        _, r, term, _, info = e.step([1.0, 0.0])
        if term:
            break
    assert info["outcome"] == "success" and r > 5


def test_mover_moves_and_bounces():
    e = EmbodiNavEnv("crossing")
    e.reset(options={"layout": {"start": [1, 1, 0.0], "goal": [9, 1], "statics": [], "movers": [[5, 9.4, 0, 1.0, 0.5]]}})
    e.step([-1, 0])
    assert e.movers[0][1] == pytest.approx(9.5)
    e.step([-1, 0])
    assert e.movers[0][3] < 0  # reflected


def test_ray_semantics_ccw():
    """Ray 3 points to the robot's left (90 deg CCW) under contract v1, to the right when mirrored."""
    lay = {"start": [5, 5, 0.0], "goal": [9, 9], "statics": [[5, 6.5, 0.5]], "movers": []}
    e = EmbodiNavEnv("static", CONTRACT_V1)
    o, _ = e.reset(options={"layout": lay})
    rays = o[5:5 + 12]
    assert rays[3] == pytest.approx((1.0 - 0.2) / 4.0, abs=1e-5)
    assert rays[9] > 0.9
    m = EmbodiNavEnv("static", CONTRACT_MIRRORED)
    om, _ = m.reset(options={"layout": lay})
    assert om.shape == o.shape
    assert om[5 + 9] == pytest.approx(rays[3]) and om[5 + 3] > 0.9


def test_frame_history_newest_first_and_reset():
    e = EmbodiNavEnv("open")
    fd = CONTRACT_V1.frame_dim
    o0, _ = e.reset(seed=1)
    frames = o0.reshape(CONTRACT_V1.history, fd)
    assert all(np.array_equal(frames[0], frames[k]) for k in range(1, CONTRACT_V1.history))
    o1, *_ = e.step([1.0, 0.5])
    f1 = o1.reshape(CONTRACT_V1.history, fd)
    assert np.array_equal(f1[1], frames[0]) and not np.array_equal(f1[0], f1[1])
    assert f1[0][3] == pytest.approx(1.0) and f1[0][4] == pytest.approx(0.5)
    for _ in range(5):
        e.step([1.0, -0.3])
    # new episode: no frame (and no previous command) may carry over
    o2, _ = e.reset(seed=2)
    f2 = o2.reshape(CONTRACT_V1.history, fd)
    assert all(np.array_equal(f2[0], f2[k]) for k in range(CONTRACT_V1.history))
    assert f2[0][3] == 0.0 and f2[0][4] == 0.0
    fresh, _ = EmbodiNavEnv("open").reset(seed=2)
    assert np.array_equal(o2, fresh)


def test_contract_ids_differ_with_same_shape():
    assert CONTRACT_V1.obs_dim == CONTRACT_MIRRORED.obs_dim
    assert CONTRACT_V1.contract_id != CONTRACT_MIRRORED.contract_id


def test_replay_trace_records_real_state():
    e = EmbodiNavEnv("crossing", record=True)
    e.reset(seed=3)
    for _ in range(5):
        e.step([0.5, 0.0])
    assert len(e.trace) == 6 and e.trace[-1]["t"] == 5
    assert e.trace[-1]["robot"] == [round(float(v), 4) for v in e.pose]


def test_protected_suites_disjoint_seeds():
    val = set().union(*[set(s.seeds) for s in SUITES.values() if s.role == "validation"])
    test = set().union(*[set(s.seeds) for s in SUITES.values() if s.role == "final_test"])
    assert not (val & test)
