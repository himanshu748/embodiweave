import json

import numpy as np

from ew.env import EmbodiNavEnv
from ew.live_frames import FrameWriter


def test_observation_does_not_change_simulator_results_or_hide_terminal_state():
    samples = []
    observed = EmbodiNavEnv('open', record=True, on_frame=samples.append)
    plain = EmbodiNavEnv('open', record=True)
    a, _ = observed.reset(seed=27)
    b, _ = plain.reset(seed=27)
    assert np.array_equal(a, b)
    for _ in range(250):
        action = np.array([.7, .15], dtype=np.float32)
        a, ar, at, ax, ai = observed.step(action)
        b, br, bt, bx, bi = plain.step(action)
        assert np.array_equal(a, b) and (ar, at, ax, ai) == (br, bt, bx, bi)
        assert samples[-1]['frame'] == observed.trace[-1]
        if at or ax:
            break
    assert samples[-1]['frame']['outcome'] is not None
    terminal = samples[-1]
    observed.reset(seed=28)
    assert samples[-1]['episode'] == terminal['episode']+1
    assert samples[-1]['frame']['t'] == 0
    assert terminal['frame']['outcome'] is not None


def test_live_frame_writer_is_bounded_copies_states_and_keeps_phase_changes(tmp_path):
    now = [0.0]
    writer = FrameWriter(tmp_path/'frames.json', clock=lambda:now[0])
    sample = {'layout': {'start':[1,2,3]}, 'frame': {'t':1,'robot':[1,2,3]}, 'episode':0}
    emit = writer.observer('train')
    emit(sample)
    sample['frame']['robot'][0] = 999
    emit(sample)
    data = json.loads((tmp_path/'frames.json').read_text())
    assert data['latest']==1 and data['frames'][0]['frame']['robot'][0]==1
    writer.observer('validate','val-target-v1')(sample)
    assert json.loads((tmp_path/'frames.json').read_text())['latest']==2
    for i in range(50):
        now[0] += .2
        emit({**sample,'episode':i})
    data = json.loads((tmp_path/'frames.json').read_text())
    assert len(data['frames'])==32 and data['latest']==52
    assert all(a['seq']<b['seq'] for a,b in zip(data['frames'],data['frames'][1:]))


def test_final_frame_is_flushed_even_when_interval_has_not_elapsed(tmp_path):
    writer=FrameWriter(tmp_path/'frames.json',clock=lambda:0)
    emit=writer.observer('validate','val-target-v1')
    emit({'frame':{'t':0,'outcome':None},'episode':0})
    emit({'frame':{'t':99,'outcome':'success'},'episode':0})
    writer.flush()
    data=json.loads((tmp_path/'frames.json').read_text())
    assert data['latest']==2 and data['frames'][-1]['frame']=={'t':99,'outcome':'success'}
