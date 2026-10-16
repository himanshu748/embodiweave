import io
import struct
import wave
from pathlib import Path
import json

import numpy as np
import pytest

from scripts.film.voice import pcm_wav, tokens
from scripts.film.mcp_update import normalized_tokens, validate_transcript


def test_streamed_wav_header_is_finalized_without_changing_pcm():
    pcm = np.arange(2400, dtype=np.int16).tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(48000); wav.writeframes(pcm)
    streamed = bytearray(buffer.getvalue())
    streamed[4:8] = struct.pack("<I", 0xffffffff)
    streamed[40:44] = struct.pack("<I", 0xffffffff)
    with wave.open(io.BytesIO(pcm_wav(bytes(streamed)))) as wav:
        assert wav.getnframes() == 2400
        assert wav.readframes(2400) == pcm


def test_transcript_comparison_keeps_claim_numbers():
    assert tokens("Falkor-D-B, thirteen collisions in forty episodes.") == tokens("FalkorDB: 13 collisions in 40 episodes.")
    assert tokens("13 collisions") != tokens("3 collisions")


def test_mcp_film_transcript_accepts_spoken_rollout_count():
    script = 'Sixty-one thousand, four hundred forty P-P-O steps. One hundred eighty episodes.'
    transcript = '61,440 PPO steps. 180 episodes.'
    assert normalized_tokens(script) == normalized_tokens(transcript)
    assert validate_transcript(script, transcript) == 1


def test_mcp_film_refuses_a_changed_spoken_collision_count():
    with pytest.raises(ValueError, match='numbers differ'):
        validate_transcript('Three collisions in sixty episodes.', 'Six collisions in 60 episodes.')
    with pytest.raises(ValueError, match='numbers differ'):
        validate_transcript('Zero collisions in forty episodes.', 'Collisions in 40 episodes.')


def test_recorded_transfer_motion_reproduces_from_actions():
    pytest.importorskip("mujoco")
    from sim.mujoco.environment import MuJoCoNavEnv
    root = Path(__file__).resolve().parents[1] / "evidence/mujoco-v1"
    episode = json.loads((root/"deployed-open.json").read_text())["episodes"][0]
    with np.load(root/episode["trajectory"], allow_pickle=False) as trace:
        env=MuJoCoNavEnv("open",layout=episode["layout"],record=True)
        env.reset()
        for action in trace["actions"][:5]:env.step(action)
        actual=np.array([f["qpos"] for f in env.physics_trace])
        np.testing.assert_allclose(actual,trace["qpos"][:len(actual)],atol=1e-6,rtol=1e-6)


def test_film_table_uses_recorded_checks_and_actual_gate_floors():
    pytest.importorskip("mujoco")
    pytest.importorskip("PIL")
    from scripts.film.render import gate_table_rows
    rows,criteria=gate_table_rows()
    assert [c['min_success'] for c in criteria]==[.8,.9,.75,.75]
    assert rows[1][1:5]==('≤10%','≤5%','≤10%','≤15%')
    assert [r[-1] for r in rows[2:]]==['1 / 4','3 / 4','4 / 4']
    assert rows[-1][1]=='95 / 5'
