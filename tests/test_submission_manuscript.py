"""Regression tests for the evidence-bound submission manuscript builder."""

from __future__ import annotations

import importlib.util
import csv
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "77_build_submission_manuscript.py"
LITERATURE_COLUMNS = [
    "paper_id", "citation_key", "region", "period", "sensor", "geometry",
    "method", "validation", "mechanism_claim", "limitation", "manuscript_use",
]
CLAIM_COLUMNS = [
    "claim_id", "claim", "claim_type", "evidence_kind", "evidence_locator",
    "citation_key", "allowed_strength", "manuscript_section",
]


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


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def test_literature_matrix_schema_and_unique_ids(project_root):
    columns, rows = _read_csv(project_root / "manuscript" / "LITERATURE_MATRIX.csv")
    assert columns == LITERATURE_COLUMNS
    paper_ids = [row["paper_id"] for row in rows]
    assert len(rows) >= 14
    assert len(paper_ids) == len(set(paper_ids))
    assert all(row["citation_key"] for row in rows)


def test_claim_ledger_schema_unique_ids_and_locators(project_root):
    columns, rows = _read_csv(project_root / "manuscript" / "CLAIM_EVIDENCE_LEDGER.csv")
    assert columns == CLAIM_COLUMNS
    claim_ids = [row["claim_id"] for row in rows]
    assert len(rows) >= 12
    assert len(claim_ids) == len(set(claim_ids))
    assert all(row["evidence_locator"] for row in rows)


def test_paper_cards_cover_every_literature_record(project_root):
    _, rows = _read_csv(project_root / "manuscript" / "LITERATURE_MATRIX.csv")
    cards = (project_root / "manuscript" / "PAPER_CARDS.md").read_text()
    assert all(f"### {row['paper_id']} -" in cards for row in rows)
    assert "Claims this paper may not support:" in cards


def test_reference_library_contains_every_citation_key(project_root):
    _, rows = _read_csv(project_root / "manuscript" / "LITERATURE_MATRIX.csv")
    bibliography = (project_root / "manuscript" / "REFERENCE_LIBRARY.bib").read_text()
    assert all("{" + row["citation_key"] + "," in bibliography for row in rows)
