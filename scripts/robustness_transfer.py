"""Post-selection physics check on fresh seeds. Never feeds model selection."""
import json

from ew import artifacts
from ew.robustness import protocol_hash
from sim.mujoco import evaluate


if __name__ == "__main__":
    selection = json.loads((artifacts.ROOT / "robustness-v2-selected.json").read_text())
    if not selection["selection_stopped"] or selection["protocol_sha256"] != protocol_hash():
        raise PermissionError("Requires a frozen candidate from the registered protocol")
    p = evaluate.protocol()
    p.update({"record_prefix": "mj2", "study": "robustness-v2", "selection":
              "Candidate frozen using canonical validation before this transfer study. No MuJoCo retraining or selection.",
              "film_selection": "No episode selected for a new film before recording the complete aggregate results."})
    p["policies"] = {name: {"id": pid, "artifact_hash": artifacts.verify_policy(pid)} for name, pid in
                     {"deployed": "P-static-b", "robust": selection["policy_id"]}.items()}
    p["suites"] = [{"id": f"sim2sim-mujoco-v2-{family}", "family": family,
                    "seeds": list(range(5_200_000+i*1000, 5_200_040+i*1000)), "episodes": 40}
                   for i, family in enumerate(evaluate.FAMILIES_ORDER)]
    evaluate.run(p, evaluate.ROOT / "evidence/mujoco-v2")
