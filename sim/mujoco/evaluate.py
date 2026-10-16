"""Frozen transfer measurement. python -m sim.mujoco.evaluate (no training).

Fresh transfer seeds, all checkpoints, all four families. Resumes completed suite
files only when their protocol and artifact hashes match. No held-out access.
"""
from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path

import mujoco
import numpy as np

from ew.artifacts import verify_policy, sha256_file
from ew.contract import CONTRACT_V1
from ew.rl import load_policy
from ew.scenarios import FAMILIES, generate_layout
from sim.mujoco.environment import MuJoCoNavEnv, VERSION

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence/mujoco-v1"
POLICIES = {"deployed": "P-static-b", "original": "scratch~a7ee2c-s7",
            "rehearsal": "search-20261015185749-4a6581"}
FAMILIES_ORDER = ("open", "static", "crossing", "static_crossing")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")


def protocol():
    return {"version": VERSION, "role": "sim2sim", "physics": "mujoco", "mujoco": mujoco.__version__,
            "contract_id": CONTRACT_V1.contract_id, "deterministic_policy": True, "training": False,
            "policies": {name: {"id": pid, "artifact_hash": verify_policy(pid)} for name, pid in POLICIES.items()},
            "sources": {p: sha256_file(ROOT / p) for p in
                ("sim/mujoco/environment.py", "ew/contract.py", "ew/scenarios.py")},
            "suites": [{"id": f"sim2sim-mujoco-v1-{name}", "family": name,
                         "seeds": list(range(5_100_000 + i*1000, 5_100_040 + i*1000)), "episodes": 40}
                        for i, name in enumerate(FAMILIES_ORDER)],
            "selection": "No model selection or promotion uses transfer results. No retraining.",
            "film_selection": "Select a deployed collision in a pedestrian suite, preferring a paired rehearsal success; report full aggregates regardless."}


def save_trajectory(env, path, actions):
    frames = env.physics_trace
    np.savez_compressed(path, time=[f["time"] for f in frames], qpos=[f["qpos"] for f in frames],
                        mocap_pos=np.array([f["mocap_pos"] for f in frames]).reshape(len(frames), -1, 3),
                        mocap_quat=np.array([f["mocap_quat"] for f in frames]).reshape(len(frames), -1, 4),
                        ranges=[f["ranges"] for f in frames], actions=np.array(actions),
                        control_poses=[f["robot"] for f in env.trace])


def run(protocol_data=None, output=None):
    p = protocol_data if protocol_data is not None else protocol()
    out = Path(output) if output is not None else OUT
    out.mkdir(parents=True, exist_ok=True)
    if (out / "protocol.json").exists():
        if json.loads((out / "protocol.json").read_text()) != p:
            raise RuntimeError("Frozen transfer protocol differs. Do not overwrite evidence.")
    else:
        write_new(out / "protocol.json", p)
    ph = digest(p)
    results = []
    for label, policy_info in p["policies"].items():
        policy = policy_info["id"]
        model, vn, contract, manifest, artifact_hash = load_policy(policy)
        assert artifact_hash == policy_info["artifact_hash"]
        assert contract.contract_id == CONTRACT_V1.contract_id
        for suite in p["suites"]:
            path = out / f"{label}-{suite['family']}.json"
            if path.exists():
                result = json.loads(path.read_text())
                assert result["protocol_hash"] == ph and result["artifact_hash"] == artifact_hash
                results.append(result)
                continue
            episodes = []
            started = time.monotonic()
            for seed in suite["seeds"]:
                layout = generate_layout(FAMILIES[suite["family"]], np.random.default_rng(seed))
                env = MuJoCoNavEnv(suite["family"], record=True, layout=layout)
                obs, _ = env.reset()
                actions = []
                for _ in range(250):
                    normalized = vn.normalize_obs(obs[None, :]).astype(np.float32)
                    action = model.predict(normalized, deterministic=True)[0][0]
                    actions.append(action.tolist())
                    obs, _, term, trunc, info = env.step(action)
                    if term or trunc:
                        break
                relative = f"trajectories/{label}-{suite['family']}-{seed}.npz"
                target = out / relative
                target.parent.mkdir(exist_ok=True)
                # A crashed incomplete suite can be resumed from scratch; no completed result is replaced.
                save_trajectory(env, target, actions)
                episodes.append({"seed": seed, "layout": layout, "outcome": info["outcome"], "hit": info["hit"],
                                 "steps": info["t"], "seconds": float(env.data.time),
                                 "goal_distance": info["goal_dist"], "trajectory": relative,
                                 "trajectory_sha256": sha256_file(target),
                                 "model_xml_sha256": hashlib.sha256(env.xml.encode()).hexdigest()})
            counts = {k: sum(e["outcome"] == k for e in episodes) for k in ("success", "collision", "timeout")}
            summary = {"episodes": len(episodes), **counts,
                       **{f"{k}_rate": counts[k]/len(episodes) for k in counts},
                       "collisions_by_object": {k: sum(e["hit"] == k for e in episodes) for k in ("wall", "static", "mover")}}
            result = {"id": f"{p.get('record_prefix', 'mj1')}-{label}-{suite['family']}-{artifact_hash[:12]}", "policy_id": policy,
                      "label": label, "artifact_hash": artifact_hash, "contract_id": contract.contract_id,
                      "suite_id": suite["id"], "family": suite["family"], "role": p["role"], "physics": "mujoco",
                      "protocol_hash": ph, "suite_fingerprint": digest({"protocol": ph, "suite": suite}),
                      "summary": summary, "episodes": episodes, "wall_s": round(time.monotonic()-started, 3),
                      "runtime": {"mujoco": mujoco.__version__, "python": platform.python_version(), "machine": platform.machine()}}
            write_new(path, result)
            results.append(result)
            print(json.dumps({"policy": label, "suite": suite["family"], **summary, "wall_s": result["wall_s"]}), flush=True)
        vn.close()
    summary = {"protocol_hash": ph, "results": [{k: r[k] for k in
               ("id", "policy_id", "label", "artifact_hash", "suite_id", "family", "summary")} for r in results]}
    if not (out / "summary.json").exists(): write_new(out / "summary.json", summary)
    checksums = {str(f.relative_to(out)): sha256_file(f) for f in sorted(out.rglob("*"))
                 if f.is_file() and f.name != "checksums.json"}
    if not (out / "checksums.json").exists(): write_new(out / "checksums.json", checksums)
    print(f"Complete: {out}/summary.json", flush=True)


if __name__ == "__main__":
    run()
