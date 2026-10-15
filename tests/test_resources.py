import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from ew import jobs, records


@pytest.fixture(autouse=True)
def queue(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "JOBS", tmp_path / "jobs")


def test_concurrent_idempotency():
    gate = threading.Barrier(8)
    def submit(_):
        gate.wait()
        return jobs.submit("evaluate", {"policy_id": "P-a", "suite_id": "val-target-v1"})
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))
    assert sum(created for _, created in results) == 1
    assert len({job["id"] for job, _ in results}) == 1


def test_concurrent_quota_and_rollout_reservation(monkeypatch):
    monkeypatch.setattr(jobs, "STEP_QUOTA", 4096)
    gate = threading.Barrier(8)
    def submit(seed):
        gate.wait()
        try:
            return jobs.submit("transfer_trial", {"budget": 2048, "seed": seed})[0]
        except jobs.QuotaExceeded:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(8)))
    assert sum(job is not None for job in results) == 2
    assert jobs.steps_used() == 4096
    with pytest.raises(jobs.QuotaExceeded):
        jobs.submit("transfer_trial", {"budget": 200000, "seed": 99})


def test_reserves_actual_rollout_cost(monkeypatch):
    monkeypatch.setattr(jobs, "STEP_QUOTA", 300000)
    job, _ = jobs.submit("transfer_trial", {"budget": 150000, "seed": 1})
    assert job["reserved_steps"] == 151552 == jobs.steps_used()


def test_second_worker_cannot_execute_in_parallel(monkeypatch):
    jobs.submit("evaluate", {"policy_id": "P-a", "suite_id": "val-target-v1"})
    entered, release = threading.Event(), threading.Event()
    def run(job):
        entered.set()
        assert release.wait(5)
        job["state"] = "completed"
    monkeypatch.setattr(jobs, "_run", run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(jobs.work_once)
        assert entered.wait(5)
        assert pool.submit(jobs.work_once).result() is None
        release.set()
        assert first.result()["state"] == "completed"


def test_queued_cancel_persists_unknown_trial():
    trial_id = records.new_id("trial")
    job, _ = jobs.submit("transfer_trial", {"parent_id": None, "child_id": "unused", "trial_id": trial_id,
        "target_family": "static_crossing", "threshold_id": "thr-target-1", "budget": 2048, "seed": 29,
        "recipe": "ppo-r1", "decision_id": None})
    jobs.cancel(job["id"])
    trial = records.read("trial", trial_id)
    assert trial["status"] == "cancelled" and trial["consumed_steps"] == 0
    assert trial["child_policy_id"] is None and trial["steps_to_threshold"] is None
    assert jobs.steps_used() == 0


def test_failed_and_interrupted_jobs_keep_conservative_reservations():
    # A crash can happen after the last progress callback. Do not refund unknown work.
    for seed, state in ((1, "failed"), (2, "interrupted")):
        job, _ = jobs.submit("transfer_trial", {"budget": 150000, "seed": seed})
        job.update(state=state, consumed_steps=2048)
        jobs._save(job)
    assert jobs.steps_used() == 2 * 151552


def test_agent_session_cannot_launch_a_second_training_job(monkeypatch):
    monkeypatch.setenv("EW_AGENT_TRAINING_LIMIT", "1")
    params = {"budget":2048,"seed":1}
    first, created = jobs.submit("transfer_trial", params, "agent-session-1")
    assert created
    assert jobs.submit("transfer_trial", params, "agent-session-1")[0]["id"] == first["id"]
    with pytest.raises(jobs.QuotaExceeded, match="one authorized"):
        jobs.submit("transfer_trial", {**params,"seed":2}, "agent-session-1")
    assert jobs.submit("transfer_trial", {**params,"seed":2}, "agent-session-2")[1]
