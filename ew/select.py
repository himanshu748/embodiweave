"""Parent selection rule ew-select-1 (frozen 2026-10-15 at Gate 2, before any benchmark run).

Every input comes from FalkorDB read templates. The only non-graph check is the trusted artifact
check (files on disk must match the hash the graph holds).

Rule ew-select-1
  1. Eligible = same robot AND same semantic contract id AND policy status 'completed' AND artifact
     files present with the graph's hash. Everything else is rejected with explicit reasons.
  2. Every eligible candidate needs a matched evaluation of its exact artifact hash on the target
     validation suite. If any is missing the decision is 'evaluate_candidates' (no ranking from an
     incomplete set, no borrowing of scores from other suites).
  3. Conditioned transfer evidence: trials with the same parent, target family id, contract, recipe,
     threshold id and budget. Completed trials count; cancelled / interrupted / failed trials are
     shown but excluded from the estimate (their outcome is unknown).
       p_reach = (reached + 1) / (completed + 2)      Beta(1,1) prior; with no trials this is 0.5 and is
                                                       labelled as a prior, not evidence.
     A completed trial that did not reach the threshold counts only as "not reached within budget";
     no steps-to-threshold value is ever invented for it.
  4. Rank by: higher p_reach, then higher matched validation score (success_rate - collision_rate),
     then lower median observed steps-to-threshold (reached trials only; none = last), then policy id.
  5. With no eligible candidate the action is train_from_scratch.
Variant ew-select-1-nohist drops step 3 (p_reach fixed at the prior) for the no-history comparison.

Rule ew-select-2 (frozen 2026-10-15 10:10 IST, after exp-1, before exp-2; exp-1 used ew-select-1)
  Same as ew-select-1, plus "train from scratch" is an explicit option with its own conditioned
  trials in the graph ((:Trial)-[:FROM_ORIGIN]->(:Origin {id:'scratch'}), same target family,
  contract, recipe, threshold and budget). p_scratch = (reached + 1) / (completed + 2).
  If p_scratch is strictly greater than the best parent's p_reach the action is train_from_scratch;
  on a tie, reuse is kept. Motivation: exp-1 measured that warm starts from this library did not
  reach the threshold (0/9) while scratch did in 1/3, and ew-select-1 had no way to act on that.
"""
from __future__ import annotations

import statistics

from . import artifacts
from .criteria import THRESHOLDS
from .graph import queries as Q

RULE_VERSION = "ew-select-2"
RULES = ("ew-select-1", "ew-select-2")


def decide(request: dict, graph_name: str | None = None, use_history: bool = True,
           extra_exclude: set | None = None, rule: str = RULE_VERSION) -> dict:
    """request keys: mission, robot, contract, target_family_id, threshold_id, recipe, budget."""
    thr = THRESHOLDS[request["threshold_id"]]
    suite = thr["suite_id"]
    log = []

    def q(name, params):
        r = Q.run(name, params, graph_name)
        log.append(r.to_log())
        return r

    req = q("mission_requirements", {"mission": request["mission"]})
    elig = q("candidate_eligibility", {"contract": request["contract"], "robot": request["robot"]})
    rejected, eligible = [], []
    for row in elig.dicts():
        reasons = []
        if not row["robot_match"]:
            reasons.append(f"robot {row['robot_id']} != {request['robot']}")
        if not row["contract_match"]:
            diff = ", ".join(row["differing_fields"]) or "contract id"
            reasons.append(f"semantic contract mismatch ({row['contract_id']} vs {request['contract']}; differs in {diff})")
        if row["status"] != "completed":
            reasons.append(f"checkpoint status {row['status']}")
        if extra_exclude and row["policy_id"] in extra_exclude:
            reasons.append("excluded by request")
        kinds = request.get("candidate_run_kinds")
        if kinds and row["run_kind"] not in kinds:
            reasons.append(f"outside requested catalog (run kind {row['run_kind']})")
        if not reasons:
            try:
                artifacts.verify_policy(row["policy_id"], row["artifact_hash"])
            except Exception as e:  # noqa: BLE001
                reasons.append(f"artifact check failed: {e}")
        (rejected if reasons else eligible).append({**row, "reasons": reasons})
    ids = [c["policy_id"] for c in eligible]
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule}")
    base = {"rule_version": rule + ("" if use_history else "-nohist"), "request": request,
            "suite_id": suite, "graph": graph_name or "ew", "graph_revision": elig.graph_revision,
            "requirements": req.dicts(),
            "rejected": [{"policy_id": r["policy_id"], "reasons": r["reasons"]} for r in rejected],
            "queries": log}
    if not ids:
        return {**base, "action": "train_from_scratch", "selected": None, "ranking": [],
                "explanation": "No eligible compatible checkpoint; train from scratch."}

    anc = q("candidate_ancestry", {"ids": ids})
    mv = q("matched_validation", {"suite": suite, "ids": ids})
    latest_eval = {}
    for row in mv.dicts():
        if row["evaluation_id"]:
            latest_eval[row["policy_id"]] = row  # ordered by time; keep newest of same hash
    missing = [i for i in ids if i not in latest_eval]
    lineage = {}
    for row in anc.dicts():
        lineage.setdefault(row["policy_id"], []).append(
            {"depth": row["depth"], "policy": row["ancestor_id"], "trained_on": row["trained_on"], "steps": row["steps"]})
    if missing:
        return {**base, "action": "evaluate_candidates", "selected": None, "ranking": [],
                "needs_evaluation": missing, "lineage": lineage,
                "explanation": f"{len(missing)} eligible candidate(s) lack a matched {suite} evaluation of their "
                               f"exact artifact: {', '.join(missing)}. Evaluate before ranking."}

    params = {"ids": ids, "threshold": request["threshold_id"], "recipe": request["recipe"],
              "budget": request["budget"], "family": request["target_family_id"], "contract": request["contract"]}
    tr = q("relevant_trials", params)
    na = q("non_applicable_trials", {k: params[k] for k in ("ids", "threshold", "recipe", "budget", "family")})
    trials = {i: [] for i in ids}
    for row in tr.dicts():
        if row["trial_id"]:
            trials[row["policy_id"]].append(row)

    ranking = []
    for pid in ids:
        ts = trials[pid]
        done = [t for t in ts if t["status"] == "completed"]
        reached = [t for t in done if t["reached"]]
        if use_history:
            p = (len(reached) + 1) / (len(done) + 2)
            basis = "prior Beta(1,1) (no applicable trials)" if not done else f"{len(reached)}/{len(done)} applicable trials reached threshold"
            n_hyp = sum(1 for t in done if t.get("hypothetical"))
            if n_hyp:
                basis += f" (WHAT-IF: {n_hyp} hypothetical, not measured)"
        else:
            p, basis = 0.5, "history not used (nohist variant)"
        ev = latest_eval[pid]
        vs = round(ev["success_rate"] - ev["collision_rate"], 4)
        stt = [t["steps_to_threshold"] for t in reached if t["steps_to_threshold"] is not None]
        med = statistics.median(stt) if stt else None
        ranking.append({
            "policy_id": pid, "p_reach": round(p, 4), "p_basis": basis, "trials": ts,
            "n_completed": len(done), "n_reached": len(reached),
            "n_not_reached_within_budget": len(done) - len(reached),
            "n_unknown_outcome": len(ts) - len(done),
            "validation": {"evaluation_id": ev["evaluation_id"], "success_rate": ev["success_rate"],
                           "collision_rate": ev["collision_rate"], "episodes": ev["episodes"], "score": vs},
            "median_steps_to_threshold": med, "lineage": lineage.get(pid, []),
            "sort_key": [-round(p, 4), -vs, med if med is not None else 1e12, pid],
        })
    ranking.sort(key=lambda c: c["sort_key"])
    for i, c in enumerate(ranking):
        c["rank"] = i + 1
    best = ranking[0]
    tie = len(ranking) > 1 and ranking[1]["sort_key"][:3] == best["sort_key"][:3]
    second = ranking[1] if len(ranking) > 1 else None
    why = (f"Selected {best['policy_id']}: p_reach {best['p_reach']} ({best['p_basis']}), matched {suite} "
           f"success {best['validation']['success_rate']:.2f} / collision {best['validation']['collision_rate']:.2f}.")
    if second:
        if second["sort_key"][0] != best["sort_key"][0]:
            why += f" Beats {second['policy_id']} on transfer evidence ({best['p_reach']} vs {second['p_reach']})."
        elif second["sort_key"][1] != best["sort_key"][1]:
            why += f" Same transfer estimate as {second['policy_id']}; wins on matched validation ({best['validation']['score']} vs {second['validation']['score']})."
        else:
            why += f" Tie with {second['policy_id']} broken by {'steps-to-threshold' if not tie else 'policy id'}."
    scratch = None
    if rule == "ew-select-2" and use_history:
        st = q("scratch_trials", {k: params[k] for k in ("threshold", "recipe", "budget", "family", "contract")})
        sts = [r for r in st.dicts() if r["trial_id"]]
        sdone = [t for t in sts if t["status"] == "completed"]
        sreach = [t for t in sdone if t["reached"]]
        ps = (len(sreach) + 1) / (len(sdone) + 2)
        scratch = {"p_reach": round(ps, 4), "trials": sts, "n_completed": len(sdone), "n_reached": len(sreach),
                   "p_basis": "prior Beta(1,1) (no applicable scratch trials)" if not sdone else
                   f"{len(sreach)}/{len(sdone)} applicable scratch trials reached threshold"}
        n_hyp = sum(1 for t in sdone if t.get("hypothetical"))
        if n_hyp:
            scratch["p_basis"] += f" (WHAT-IF: {n_hyp} hypothetical, not measured)"
        if round(ps, 4) > best["p_reach"]:
            return {**base, "action": "train_from_scratch", "selected": None, "ranking": ranking, "scratch_option": scratch,
                    "non_applicable_trials": na.dicts(), "tie_broken_by_id": False,
                    "evidence_trial_ids": [t["trial_id"] for c in ranking for t in c["trials"]] + [t["trial_id"] for t in sts],
                    "evidence_eval_ids": [c["validation"]["evaluation_id"] for c in ranking],
                    "explanation": f"Train from scratch: p_reach {scratch['p_reach']} ({scratch['p_basis']}) beats the best "
                                   f"parent {best['policy_id']} at {best['p_reach']} ({best['p_basis']}). Reuse is not supported "
                                   f"by the measured transfer history for this target, recipe and budget."}
        why += f" Scratch option p_reach {scratch['p_reach']} ({scratch['p_basis']}) does not beat it."
    return {**base, "action": "train_from_parent", "selected": best["policy_id"], "ranking": ranking,
            "scratch_option": scratch, "non_applicable_trials": na.dicts(), "tie_broken_by_id": tie,
            "evidence_trial_ids": [t["trial_id"] for c in ranking for t in c["trials"]] + [t["trial_id"] for t in (scratch or {}).get("trials", [])],
            "evidence_eval_ids": [c["validation"]["evaluation_id"] for c in ranking],
            "explanation": why}
