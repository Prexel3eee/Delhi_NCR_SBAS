"""
Regression tests for production retrieval (`scripts/13_download_production.py`).

These exist because the first production retrieval run died part-way through on
a transient ASF DNS outage: `hyp3-api.asf.alaska.edu` and `cumulus.asf.alaska.edu`
stopped resolving, authentication raised, and the whole run exited with a
traceback after 47 of 336 products had downloaded.

Two defects are pinned here:

1. Connection and job listing were not retried, so a network blip was fatal.
2. `hyp3.refresh(Batch)` issues one HTTP request PER JOB (336 per poll cycle
   here). Listing the batch once is both faster and far less fragile.

All tests are offline: time.sleep is neutralised and the client is faked.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("hyp3_sdk", reason="script 13 imports hyp3_sdk at call time")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "13_download_production.py"
PREFIX = "delhi_ncr_sbas_a27_v1_prod"


@pytest.fixture(scope="module")
def retrieval():
    spec = importlib.util.spec_from_file_location("prod_retrieval_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Neutralise backoff so the tests stay fast."""
    import time

    monkeypatch.setattr(time, "sleep", lambda *_: None)


class FakeJob:
    def __init__(self, name, job_id, status_code="RUNNING"):
        self.name = name
        self.job_id = job_id
        self.status_code = status_code

    def succeeded(self) -> bool:  # a METHOD on the real object
        return self.status_code == "SUCCEEDED"

    def failed(self) -> bool:
        return self.status_code == "FAILED"


class FlakyHyp3:
    """Fails the first `fail_times` calls, then succeeds."""

    def __init__(self, jobs, fail_times=0, fail_on=("job_type", "plain")):
        self.jobs = jobs
        self.fail_times = fail_times
        self.calls: list[dict] = []
        self.attempts = 0

    def find_jobs(self, **kwargs):
        self.calls.append(kwargs)
        if self.attempts < self.fail_times:
            self.attempts += 1
            raise ConnectionError("Failed to resolve 'hyp3-api.asf.alaska.edu'")
        return list(self.jobs)


# ---------------------------------------------------------------------------
# Connection / listing resilience
# ---------------------------------------------------------------------------


def test_fetch_jobs_retries_a_transient_outage(retrieval):
    hyp3 = FlakyHyp3([FakeJob(f"{PREFIX}_a", "id-a")], fail_times=3)
    jobs = retrieval.fetch_jobs(hyp3, tries=6, base_delay=0)
    assert [j.job_id for j in jobs] == ["id-a"]


def test_fetch_jobs_raises_network_unavailable_when_it_never_recovers(retrieval):
    hyp3 = FlakyHyp3([], fail_times=999)
    with pytest.raises(retrieval.NetworkUnavailable):
        retrieval.fetch_jobs(hyp3, tries=3, base_delay=0)


def test_fetch_jobs_never_filters_by_name(retrieval):
    """`find_jobs(name=...)` is an exact match; a prefix silently returns nothing."""
    hyp3 = FlakyHyp3([FakeJob(f"{PREFIX}_a", "id-a")])
    retrieval.fetch_jobs(hyp3, tries=2, base_delay=0)
    assert hyp3.calls, "find_jobs must be called"
    for call in hyp3.calls:
        assert "name" not in call


def test_fetch_jobs_lists_the_batch_once_not_per_job(retrieval):
    """Guards against reintroducing hyp3.refresh(Batch), which is 1 call per job."""
    many = [FakeJob(f"{PREFIX}_{i}", f"id-{i}") for i in range(50)]
    hyp3 = FlakyHyp3(many)
    jobs = retrieval.fetch_jobs(hyp3, tries=2, base_delay=0)
    assert len(jobs) == 50
    assert len(hyp3.calls) == 1, "the whole batch must be listed in a single call"


def test_fetch_jobs_filters_to_the_production_prefix(retrieval):
    mixed = [
        FakeJob(f"{PREFIX}_a", "id-a"),
        FakeJob("delhi_ncr_sbas_a27_v1_pilot_b", "id-b"),
        FakeJob("Delhi_NCR_Subsidence", "id-c"),
        FakeJob(None, "id-d"),
    ]
    hyp3 = FlakyHyp3(mixed)
    jobs = retrieval.fetch_jobs(hyp3, tries=2, base_delay=0)
    assert [j.job_id for j in jobs] == ["id-a"]


def test_connect_hyp3_retries_then_raises(retrieval, monkeypatch):
    import hyp3_sdk

    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ConnectionError("Failed to resolve 'cumulus.asf.alaska.edu'")

    monkeypatch.setattr(hyp3_sdk, "HyP3", boom)

    with pytest.raises(retrieval.NetworkUnavailable) as excinfo:
        retrieval.connect_hyp3(tries=3, base_delay=0)
    assert calls["n"] == 3
    assert "could not authenticate" in str(excinfo.value)


def test_connect_hyp3_returns_a_client_when_reachable(retrieval, monkeypatch):
    import hyp3_sdk

    sentinel = object()
    monkeypatch.setattr(hyp3_sdk, "HyP3", lambda: sentinel)
    assert retrieval.connect_hyp3(tries=3, base_delay=0) is sentinel


# ---------------------------------------------------------------------------
# State handling (the method-not-property trap)
# ---------------------------------------------------------------------------


def test_job_state_must_come_from_status_code(retrieval):
    running = FakeJob(f"{PREFIX}_a", "id-a", "RUNNING")
    assert bool(running.succeeded) is True, "bound method is truthy"
    assert running.succeeded() is False
    assert running.status_code not in retrieval.TERMINAL


def test_terminal_states_exclude_in_progress(retrieval):
    assert retrieval.TERMINAL == {"SUCCEEDED", "FAILED", "EXPIRED"}
    assert "RUNNING" not in retrieval.TERMINAL
    assert "PENDING" not in retrieval.TERMINAL
