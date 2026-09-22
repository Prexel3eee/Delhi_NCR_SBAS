"""Regression tests for the evidence-bound submission manuscript builder."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "77_build_submission_manuscript.py"


def load_submission_module():
    spec = importlib.util.spec_from_file_location("submission_under_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load submission builder from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def submission():
    return load_submission_module()


@pytest.fixture(scope="module")
def project_root() -> Path:
    return PROJECT_ROOT


def test_load_frozen_evidence_preserves_authoritative_hotspots(submission, project_root):
    evidence = submission.load_frozen_evidence(project_root)
    assert evidence.hotspots["H001"].ascending_rate == -30.95
    assert evidence.hotspots["H001"].descending_rate == -36.02
    assert evidence.hotspots["H004"].area_km2 == 1.07
    assert sum(evidence.hotspots[h].area_km2 for h in ("H001", "H004")) == 6.66


def test_builder_never_targets_publication_v1(submission, project_root):
    paths = submission.output_paths(project_root)
    assert all("freeze/publication_v1" not in str(path) for path in paths)
    assert all("MANUSCRIPT_FINAL_JOURNAL_NEUTRAL.md" not in str(path) for path in paths)


def test_build_is_deterministic(submission, project_root):
    assert submission.build_submission(project_root) == submission.build_submission(project_root)
