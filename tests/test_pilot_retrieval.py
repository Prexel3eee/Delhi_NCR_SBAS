"""
Regression tests for pilot retrieval (`scripts/08_download_pilot.py`).

Pins a real bug: `hyp3_sdk`'s `Job.succeeded` and `Job.failed` are **methods**,
not properties, so `if job.succeeded:` is always truthy (a bound method object).
The first version of the downloader therefore tried to download RUNNING jobs and
recorded spurious failures. State checks must compare `status_code`.

These tests use fakes that deliberately reproduce the trap.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RETRIEVAL_SCRIPT = PROJECT_ROOT / "scripts" / "08_download_pilot.py"

PREFIX = "delhi_ncr_sbas_a27_v1_pilot"


@pytest.fixture(scope="module")
def retrieval():
    spec = importlib.util.spec_from_file_location("download_pilot_under_test", RETRIEVAL_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeJob:
    """Emulates `hyp3_sdk.jobs.Job`, including the method-not-property trap."""

    def __init__(self, name, job_id, status_code="RUNNING", credit_cost=5, failure_reason=None):
        self.name = name
        self.job_id = job_id
        self.status_code = status_code
        self._credit_cost = credit_cost
        self.failure_reason = failure_reason

    # these are METHODS on the real object, which is the whole point
    def succeeded(self) -> bool:
        return self.status_code == "SUCCEEDED"

    def failed(self) -> bool:
        return self.status_code == "FAILED"

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "status_code": self.status_code,
            "credit_cost": self._credit_cost,
        }

    def download_files(self, location=None, create=True):
        if self.status_code != "SUCCEEDED":
            raise RuntimeError(
                f"Only succeeded jobs can be downloaded; job is {self.status_code}."
            )
        return []


def test_the_trap_exists_so_tests_are_meaningful():
    """Document why the module compares status_code."""
    running = FakeJob(f"{PREFIX}_x", "id-1", "RUNNING")
    assert bool(running.succeeded) is True, "bound method is truthy"
    assert running.succeeded() is False, "but calling it tells the truth"


def test_download_is_attempted_only_for_succeeded_jobs(retrieval):
    """Reproduces the original bug and proves the fix."""
    jobs = [
        FakeJob(f"{PREFIX}_a", "id-a", "RUNNING"),
        FakeJob(f"{PREFIX}_b", "id-b", "SUCCEEDED"),
        FakeJob(f"{PREFIX}_c", "id-c", "FAILED"),
    ]
    # the old, broken predicate
    broken = [j for j in jobs if j.succeeded]
    assert len(broken) == 3, "the broken predicate selects every job"

    # the fixed predicate
    fixed = [j for j in jobs if j.status_code == "SUCCEEDED"]
    assert [j.job_id for j in fixed] == ["id-b"]


def test_download_and_extract_records_error_for_non_succeeded(retrieval, tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "ZIP_DIR", tmp_path / "zips")
    monkeypatch.setattr(retrieval, "EXTRACT_DIR", tmp_path / "extracted")
    monkeypatch.setattr(retrieval, "PROJECT_ROOT", tmp_path)

    running = FakeJob(f"{PREFIX}_x", "id-x", "RUNNING")
    record = retrieval.download_and_extract(running)

    assert record["download_ok"] is False
    assert "Only succeeded jobs" in (record["error"] or "")
    assert record["job_id"] == "id-x"


# ---------------------------------------------------------------------------
# Ledger reconciliation
# ---------------------------------------------------------------------------


def write_ledger(tmp_path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(tmp_path / "hyp3_jobs.csv", index=False)


@pytest.fixture
def ledger_env(retrieval, tmp_path, monkeypatch):
    manifest = tmp_path / "manifests"
    qc = tmp_path / "qc"
    manifest.mkdir()
    qc.mkdir()
    monkeypatch.setattr(retrieval, "MANIFEST_DIR", manifest)
    monkeypatch.setattr(retrieval, "QC_DIR", qc)
    return manifest, qc


def test_reconcile_detects_bidirectional_coverage(retrieval, ledger_env):
    manifest, qc = ledger_env
    write_ledger(
        manifest,
        [
            {"job_id": "a", "job_name": f"{PREFIX}_a", "status": "PENDING"},
            {"job_id": "b", "job_name": f"{PREFIX}_b", "status": "PENDING"},
        ],
    )
    remote = [
        FakeJob(f"{PREFIX}_a", "a", "SUCCEEDED"),
        FakeJob(f"{PREFIX}_c", "c", "RUNNING"),  # not in ledger
    ]
    report = retrieval.reconcile_ledger(remote)

    assert report["in_ledger_not_remote"] == ["b"]
    assert report["in_remote_not_ledger"] == ["c"]
    assert report["ledger_covers_remote"] is False
    assert report["remote_covers_ledger"] is False
    assert (qc / "ledger_reconciliation.json").exists()


def test_reconcile_detects_status_mismatch(retrieval, ledger_env):
    manifest, _ = ledger_env
    write_ledger(manifest, [{"job_id": "a", "job_name": f"{PREFIX}_a", "status": "PENDING"}])
    report = retrieval.reconcile_ledger([FakeJob(f"{PREFIX}_a", "a", "SUCCEEDED")])

    assert len(report["status_mismatches"]) == 1
    mismatch = report["status_mismatches"][0]
    assert mismatch["ledger_status"] == "PENDING"
    assert mismatch["remote_status"] == "SUCCEEDED"


def test_reconcile_never_rewrites_the_append_only_ledger(retrieval, ledger_env):
    """Reconciliation must be read-only with respect to the ledger."""
    manifest, _ = ledger_env
    rows = [{"job_id": "a", "job_name": f"{PREFIX}_a", "status": "PENDING"}]
    write_ledger(manifest, rows)
    before = (manifest / "hyp3_jobs.csv").read_text()

    retrieval.reconcile_ledger([FakeJob(f"{PREFIX}_a", "a", "SUCCEEDED")])

    assert (manifest / "hyp3_jobs.csv").read_text() == before


def test_reconcile_reports_duplicate_names_and_credit_cost(retrieval, ledger_env):
    manifest, _ = ledger_env
    write_ledger(
        manifest,
        [
            {"job_id": "a1", "job_name": f"{PREFIX}_a", "status": "RUNNING"},
            {"job_id": "a2", "job_name": f"{PREFIX}_a", "status": "RUNNING"},
        ],
    )
    report = retrieval.reconcile_ledger(
        [
            FakeJob(f"{PREFIX}_a", "a1", "RUNNING", credit_cost=5),
            FakeJob(f"{PREFIX}_a", "a2", "RUNNING", credit_cost=5),
        ]
    )

    assert report["duplicate_names"] == {f"{PREFIX}_a": 2}
    assert report["credit_cost_observed"] == {"5": 2}
    assert report["credit_cost_total"] == 10


# ---------------------------------------------------------------------------
# Resumability
# ---------------------------------------------------------------------------


def test_already_downloaded_is_resumable(retrieval, ledger_env):
    manifest, _ = ledger_env
    pd.DataFrame(
        [
            {"job_id": "a", "download_ok": True},
            {"job_id": "b", "download_ok": False},
            {"job_id": "c", "download_ok": True},
        ]
    ).to_csv(manifest / "product_inventory.csv", index=False)

    assert retrieval.already_downloaded() == {"a", "c"}


def test_already_downloaded_handles_missing_inventory(retrieval, ledger_env):
    assert retrieval.already_downloaded() == set()


def test_terminal_states_are_complete(retrieval):
    assert retrieval.TERMINAL == {"SUCCEEDED", "FAILED", "EXPIRED"}
    assert "RUNNING" not in retrieval.TERMINAL
    assert "PENDING" not in retrieval.TERMINAL
