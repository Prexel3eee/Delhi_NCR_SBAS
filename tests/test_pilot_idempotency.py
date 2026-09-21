"""
Regression tests for pilot-submission idempotency.

These exist because the guard was wrong in a way that cost real credits.

`HyP3.find_jobs(name=...)` performs an **exact** name match. The original
idempotency check passed the project *prefix*
(``delhi_ncr_sbas_a27_v1_pilot``), so it always returned zero jobs even with
seven matching jobs on the account. A re-run therefore resubmitted all seven
pairs, doubling the pilot to 14 jobs / 70 credits instead of 7 / 35.

Verified against the live API at the time:
    find_jobs(name='delhi_ncr_sbas_a27_v1_pilot')                    -> 0
    find_jobs(name='delhi_ncr_sbas_a27_v1_pilot_20250211_20250223')  -> 2

The fix lists jobs and matches exact names locally. These tests pin both the
matching behaviour and the fact that no `name=` filter is ever passed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PILOT_SCRIPT = PROJECT_ROOT / "scripts" / "07_submit_pilot.py"


@pytest.fixture(scope="module")
def pilot():
    """Load `07_submit_pilot.py` (its filename is not a valid module name)."""
    spec = importlib.util.spec_from_file_location("submit_pilot_under_test", PILOT_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeJob:
    def __init__(self, name, job_id, status_code="PENDING"):
        self.name = name
        self.job_id = job_id
        self.status_code = status_code


class FakeHyp3:
    """Emulates the real exact-match semantics of `find_jobs(name=...)`."""

    def __init__(self, jobs):
        self._jobs = list(jobs)
        self.calls: list[dict] = []

    def find_jobs(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("name"):
            # Exact match only - this is the behaviour that caused the incident.
            return [j for j in self._jobs if j.name == kwargs["name"]]
        return list(self._jobs)


PREFIX = "delhi_ncr_sbas_a27_v1_pilot"
PAIR_IDS = [
    "20250211_20250223",
    "20211205_20211229",
    "20250331_20250506",
    "20250623_20250705",
    "20250307_20250319",
    "20250530_20250705",
    "20250211_20250223_nomask",
]
EXPECTED_NAMES = [f"{PREFIX}_{p}" for p in PAIR_IDS]


def make_fake(names=None):
    names = EXPECTED_NAMES if names is None else names
    jobs = [FakeJob(n, f"id-{i}") for i, n in enumerate(names)]
    return FakeHyp3(jobs)


def test_prefix_query_returns_nothing_which_is_why_the_old_check_failed(pilot):
    """Document the trap explicitly: a prefix query matches nothing."""
    fake = make_fake()
    assert fake.find_jobs(name=PREFIX) == []
    # ...while an exact name matches.
    assert len(fake.find_jobs(name=EXPECTED_NAMES[0])) == 1


def test_find_existing_matches_all_submitted_jobs(pilot):
    fake = make_fake()
    existing = pilot.find_existing(fake)
    assert sorted(existing) == sorted(EXPECTED_NAMES)
    assert all(len(v) == 1 for v in existing.values())


def test_find_existing_never_passes_a_name_filter(pilot):
    """The regression guard: matching must not rely on `name=` at all."""
    fake = make_fake()
    pilot.find_existing(fake)
    assert fake.calls, "find_existing must query the API"
    for call in fake.calls:
        assert "name" not in call, (
            "find_existing must not pass name= to find_jobs: it is an exact match, "
            "so a prefix silently returns nothing and idempotency breaks"
        )


def test_find_existing_groups_duplicate_submissions(pilot):
    """Duplicates must be visible, not collapsed - they cost credits."""
    doubled = EXPECTED_NAMES + EXPECTED_NAMES
    fake = make_fake(doubled)
    existing = pilot.find_existing(fake)
    assert sorted(existing) == sorted(EXPECTED_NAMES)
    assert all(len(v) == 2 for v in existing.values())


def test_find_existing_ignores_unrelated_jobs(pilot):
    """Pre-existing jobs from other work must not be mistaken for pilot jobs."""
    unrelated = ["Delhi_NCR_Subsidence", "some_other_project_2020"]
    fake = make_fake(EXPECTED_NAMES + unrelated)
    existing = pilot.find_existing(fake)
    assert sorted(existing) == sorted(EXPECTED_NAMES)
    assert "Delhi_NCR_Subsidence" not in existing


def test_all_frozen_pilot_names_are_detected_so_nothing_is_resubmitted(pilot):
    """End-to-end: given a fully submitted pilot, nothing remains to submit."""
    fake = make_fake()
    existing = pilot.find_existing(fake)
    to_submit = [n for n in EXPECTED_NAMES if n not in existing]
    assert to_submit == [], "a fully submitted pilot must produce an empty work list"


def test_nomask_control_has_a_distinct_job_name(pilot):
    """The water-mask control must not collide with its water-mask-on twin."""
    assert f"{PREFIX}_20250211_20250223" in EXPECTED_NAMES
    assert f"{PREFIX}_20250211_20250223_nomask" in EXPECTED_NAMES
    assert len(set(EXPECTED_NAMES)) == len(EXPECTED_NAMES)


def test_frozen_pilot_definition_still_has_seven_jobs(pilot):
    """The pilot ceiling is part of the freeze; guard against drift."""
    assert pilot.MAX_PILOT_JOBS == 7
    assert pilot.LOOKS == "10x2"
    assert pilot.JOB_NAME_PREFIX == PREFIX
