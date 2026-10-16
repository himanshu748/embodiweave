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


@pytest.mark.parametrize("followup",[False,True])
def test_physics_selection_cannot_resume_after_freeze(tmp_path,monkeypatch,followup):
    from ew import artifacts
    monkeypatch.setattr(artifacts,"ROOT",tmp_path)
    (tmp_path/"physics-adapt-v1-selected.json").write_text('{}')
    with pytest.raises(PermissionError,match="frozen"):
        if followup:
            from ew.physics_followup import run
            run()
        else:physics_study.run_next()


def test_training_cost_changes_no_contact_dynamics():
    from ew.physics_train import PhysicsTrainingEnv
    base=MuJoCoNavEnv("open")
    trained=PhysicsTrainingEnv("open",CONTRACT_V1,RECIPES["ppo-mixed-mujoco-v1"])
    layout={"start":[.21,5,np.pi],"goal":[8.5,5],"statics":[],"movers":[]}
    np.testing.assert_array_equal(base.reset(options={"layout":layout})[0],trained.reset(options={"layout":layout})[0])
    a,b=base.step([1.,0.]),trained.step([1.,0.])
    np.testing.assert_array_equal(a[0],b[0])
    np.testing.assert_array_equal(base.data.qpos,trained.data.qpos)
    assert a[2:]==b[2:] and a[4]["hit"]=="wall"
    assert b[1]<a[1]-9.9


@pytest.mark.parametrize("field,value,message",[("role","final_test","protected"),("artifact_hash","0"*64,"protected"),("success_rate",.123,"rates")])
def test_physics_ingester_rejects_protected_or_inconsistent_evidence(tmp_path,monkeypatch,field,value,message):
    import shutil
    from ew import artifacts
    pid="robust-20261016140226-352fd7"
    monkeypatch.setattr(artifacts,"POLICIES",physics_study.ROOT/"artifacts/policies")
    original=physics_study.OUT
    shutil.copyfile(original/"protocol.json",tmp_path/"protocol.json")
    folder=tmp_path/"development"/pid
    shutil.copytree(original/"development"/pid,folder)
    target=folder/"candidate-open.json"
    e=json.loads(target.read_text())
    (e["summary"] if field=="success_rate" else e)[field]=value
    target.write_text(json.dumps(e))
    hashes=json.loads((folder/"checksums.json").read_text())
    hashes[target.name]=artifacts.sha256_file(target)
    (folder/"checksums.json").write_text(json.dumps(hashes))
    monkeypatch.setattr(physics_study,"OUT",tmp_path)
    with pytest.raises(ValueError,match=message):physics_study.ingest_development(pid)


def test_recovery_restores_physics_decision_evidence_without_confirmation(monkeypatch):
    import sys
    from ew import artifacts, records
    from ew.graph import db, ingest, queries
    root=physics_study.ROOT/"artifacts"
    monkeypatch.setattr(artifacts,"ROOT",root)
    monkeypatch.setattr(artifacts,"POLICIES",root/"policies")
    monkeypatch.setattr(records,"RECORDS",root/"records")
    # Hosted recovery must work without the optional MuJoCo training dependency.
    monkeypatch.setitem(sys.modules,"mujoco",None)
    graph="ew_test_physics_recovery"
    try:
        ingest.rebuild(graph)
        rows=queries.run("search_lineage",{"rule":"physics-adapt-v1"},graph).dicts()
        assert rows
        for decision in {r["decision"] for r in rows}:
            selected=[r for r in rows if r["decision"]==decision]
            assert len(selected)==8
            assert len([r for r in selected if r["evidence_suite"].startswith("val-physics-adapt-v1-")])==4
        assert db.ro("MATCH (e:Evaluation) WHERE e.id STARTS WITH 'pft1-' RETURN count(e)",graph_name=graph)[1]==[[0]]
    finally:db.delete_graph(graph)
