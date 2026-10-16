import json
import numpy as np
import pytest

from ew import rl, physics_study
from ew.contract import CONTRACT_V1
from ew.recipes import RECIPES
from ew.scenarios import SUITES
from sim.mujoco.environment import MuJoCoNavEnv


def test_mixed_recipe_uses_real_physics_with_identical_observation_contract():
    vec=rl.make_vec(rl.FAMILIES["open"],CONTRACT_V1,2,23,recipe_params=RECIPES["ppo-mixed-mujoco-v1"])
    assert isinstance(vec.envs[0].unwrapped,MuJoCoNavEnv)
    assert not isinstance(vec.envs[1].unwrapped,MuJoCoNavEnv)
    obs=vec.reset();assert obs.shape==(2,51) and obs.dtype==np.float32
    obs,reward,done,info=vec.step(np.array([[0.,.2],[0.,.2]],dtype=np.float32))
    assert vec.envs[0].unwrapped.data.time==pytest.approx(.1)
    assert vec.envs[0].unwrapped.model.opt.gravity[2]==-9.81
    assert obs.shape==(2,51)
    vec.close()


def test_physics_confirmation_is_disjoint_and_never_a_planning_suite():
    p=physics_study.protocol()
    dev={s for suite in p["development"] for s in suite["seeds"]}
    final={s for suite in p["confirmation"] for s in suite["seeds"]}
    canonical={s for suite in SUITES.values() for s in suite.seeds}
    old=json.loads((physics_study.ROOT/"evidence/robustness-v2/protocol.json").read_text())
    spent={s for suite in old["confirmation"]["suites"] for s in suite["seeds"]}
    assert len(dev)==160 and len(final)==400
    assert not dev&final and not (dev|final)&(canonical|spent)
    assert set(physics_study.physical_ids())=={s["id"] for s in p["development"]}


def test_physics_selection_cannot_resume_after_freeze(tmp_path,monkeypatch):
    from ew import artifacts
    monkeypatch.setattr(artifacts,"ROOT",tmp_path)
    (tmp_path/"physics-adapt-v1-selected.json").write_text('{}')
    with pytest.raises(PermissionError,match="frozen"):
        physics_study.run_next()
