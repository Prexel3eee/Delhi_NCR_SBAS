"""Regression tests for the evidence-bound submission manuscript builder."""

from __future__ import annotations

import importlib.util
import csv
import re
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "77_build_submission_manuscript.py"
AUDIT_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "78_submission_audit.py"
LITERATURE_COLUMNS = [
    "paper_id", "citation_key", "region", "period", "sensor", "geometry",
    "method", "validation", "mechanism_claim", "limitation", "manuscript_use",
]
CLAIM_COLUMNS = [
    "claim_id", "claim", "claim_type", "evidence_kind", "evidence_locator",
    "citation_key", "allowed_strength", "manuscript_section",
]
FIGURE_REGISTRY_COLUMNS = [
    "submission_id", "source_figure", "placement", "scientific_question",
    "claim_ids", "source_paths", "limitations", "caption_file",
]


def load_submission_module():
    spec = importlib.util.spec_from_file_location("submission_under_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load submission builder from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_audit_module():
    spec = importlib.util.spec_from_file_location("submission_audit_under_test", AUDIT_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load submission audit from {AUDIT_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def submission():
    return load_submission_module()


@pytest.fixture(scope="module")
def audit():
    return load_audit_module()


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


def test_submission_front_matter_and_methods_architecture(submission, project_root):
    manuscript = submission.build_submission(project_root)["manuscript"]
    assert manuscript.startswith(
        "# Selective reproduction of localized line-of-sight deformation in Delhi-NCR "
        "using independent Sentinel-1 geometries"
    )
    required_headings = [
        "## Abstract",
        "## 1. Introduction",
        "## 2. Data and methods",
        "### 2.1 Study design and observation period",
        "### 2.2 Ascending stack and time-series processing",
        "### 2.3 Frozen observations and hotspot definition",
        "### 2.4 Independent descending experiment",
        "### 2.5 Cross-geometry comparison",
        "### 2.6 Preregistered mechanism tests",
        "### 2.7 Uncertainty and evidence states",
    ]
    assert all(heading in manuscript for heading in required_headings)


def test_abstract_contains_required_design_and_outcomes(submission, project_root):
    manuscript = submission.build_submission(project_root)["manuscript"]
    abstract = manuscript.split("## Abstract\n", 1)[1].split("## 1. Introduction", 1)[0]
    abstract = abstract.split("**Keywords:**", 1)[0]
    assert 150 <= len(abstract.split()) <= 250
    for phrase in (
        "119 acquisitions",
        "336 interferograms",
        "91 acquisitions",
        "219 interferograms",
        "Five zones",
        "H001 and H004",
        "H002 and H003",
        "H005",
        "mean-rate",
        "time histories",
    ):
        assert phrase in abstract


def test_submission_uses_protected_measurement_language(submission, project_root):
    manuscript = submission.build_submission(project_root)["manuscript"]
    assert "relative LOS" in manuscript
    assert "measured vertical displacement" not in manuscript.lower()
    assert "independently validated" not in manuscript.lower()


def test_results_architecture_is_complete(submission, project_root):
    manuscript = submission.build_submission(project_root)["manuscript"]
    required_headings = [
        "### 3.1 Ascending field and frozen detections",
        "### 3.2 Descending reliability and correction decision",
        "### 3.3 Common-domain agreement",
        "### 3.4 Independently supported zones: H001 and H004",
        "### 3.5 Negative controls: H002 and H003",
        "### 3.6 Unresolved contradiction: H005",
        "### 3.7 Temporal behavior and uncertainty",
        "### 3.8 Mechanism-test outcomes",
    ]
    assert all(heading in manuscript for heading in required_headings)


def test_generated_hotspot_table_matches_frozen_rates(submission, project_root):
    evidence = submission.load_frozen_evidence(project_root)
    manuscript = submission.build_submission(project_root)["manuscript"]
    for hotspot, row in evidence.hotspots.items():
        expected = (
            f"| {hotspot} | {row.ascending_rate:+.2f} | "
            f"{row.descending_rate:+.2f} | {row.area_km2:.2f} | {row.status} |"
        )
        assert expected in manuscript


def test_results_reproduce_every_frozen_evidence_state(submission, project_root):
    evidence = submission.load_frozen_evidence(project_root)
    manuscript = submission.build_submission(project_root)["manuscript"]
    for state in evidence.evidence_states.values():
        assert state in manuscript
    assert "H005 was excluded from all causal-test samples" in manuscript


def test_discussion_and_limitations_cover_approved_arguments(submission, project_root):
    manuscript = submission.build_submission(project_root)["manuscript"]
    discussion_headings = [
        "### 4.1 What H001/H004 reproduction establishes",
        "### 4.2 Why rate support is not vertical or temporal validation",
        "### 4.3 Negative controls as scientific evidence",
        "### 4.4 H005 and the cost of unresolved contradiction",
        "### 4.5 Comparison with prior Delhi-NCR studies",
        "### 4.6 Why tested candidates fail causal selectivity",
        "### 4.7 Remaining alternatives are not conclusions",
        "### 4.8 Implications for urban InSAR inference",
    ]
    assert all(heading in manuscript for heading in discussion_headings)
    assert manuscript.count("<!-- Claims: C") >= 8
    for limitation in (
        "Local geodetic reference",
        "LOS projection",
        "Partial descending coverage",
        "Temporal mismatch",
        "Coherence ambiguity",
        "Aquifer-depth specificity",
        "Construction chronology",
        "H005 contradiction",
    ):
        assert f"**{limitation}.**" in manuscript


def test_conclusion_is_supported_and_avoids_overclaiming(submission, project_root):
    manuscript = submission.build_submission(project_root)["manuscript"]
    before, conclusion = manuscript.split("## 6. Conclusions", 1)
    repeated_claims = [
        "spatial and mean-rate level",
        "H002 and H003 were not reproduced",
        "H005 remained an unresolved cross-geometry contradiction",
        "physical mechanism remains unresolved",
    ]
    assert all(claim in conclusion and claim in before for claim in repeated_claims)
    for prohibited in (
        "caused by groundwater",
        "confirmed subsidence",
        "validated vertical displacement",
    ):
        assert prohibited not in manuscript.lower()


def test_supplement_has_complete_reproducibility_architecture(submission, project_root):
    supplement = submission.build_submission(project_root)["supplement"]
    required_sections = [
        "## S1. Study area and reference frame",
        "## S2. Ascending network",
        "## S3. Descending network",
        "## S4. Processing and correction branches",
        "## S5. Hotspot definition and freeze",
        "## S6. Common-domain alignment and comparison",
        "## S7. Groundwater protocol",
        "## S8. Geology and urban evidence",
        "## S9. Uncertainty and evidence states",
        "## S10. Supplementary tables",
        "## S11. Scientific incidents",
        "## S12. Figure captions",
        "## S13. Data and code availability",
    ]
    assert all(section in supplement for section in required_sections)
    for incident in ("INC-001", "INC-002", "INC-005", "INC-006", "INC-007", "INC-008", "INC-009"):
        card = supplement.split(f"### {incident}", 1)[1].split("### ", 1)[0]
        for field in ("Problem:", "Consequence:", "Detection:", "Correction:", "Regression protection:"):
            assert field in card


def test_supplementary_callouts_resolve(submission, project_root):
    texts = submission.build_submission(project_root)
    callouts = set(re.findall(r"Supplementary Section (S\d+)", texts["manuscript"]))
    assert callouts == {f"S{number}" for number in range(1, 10)}
    headings = set(re.findall(r"^## (S\d+)\.", texts["supplement"], flags=re.MULTILINE))
    assert callouts <= headings


def test_author_input_boundary_contains_no_guessed_identity(project_root):
    text = (project_root / "manuscript" / "AUTHOR_INPUT_REQUIRED.md").read_text()
    placeholder = "Not supplied; must be confirmed by the human authors before submission."
    fields = [
        "Author names and order",
        "Affiliations",
        "Corresponding author and email",
        "CRediT roles",
        "Funding",
        "Acknowledgements",
        "Conflicts of interest",
        "Ethics requirement",
        "Selected journal",
        "Journal-specific AI disclosure",
    ]
    assert all(f"**{field}:** {placeholder}" in text for field in fields)
    assert text.count(placeholder) == len(fields)
    assert "@" not in text


def test_figure_registry_links_provenance_and_claims(project_root):
    columns, rows = _read_csv(project_root / "manuscript" / "FIGURE_CLAIM_REGISTRY.csv")
    assert columns == FIGURE_REGISTRY_COLUMNS
    assert len(rows) == 12
    provenance = __import__("json").loads(
        (project_root / "manuscript" / "FIGURE_PROVENANCE.json").read_text()
    )
    figures = {figure["figure_id"]: figure for figure in provenance["figures"]}
    _, claim_rows = _read_csv(project_root / "manuscript" / "CLAIM_EVIDENCE_LEDGER.csv")
    claim_ids = {row["claim_id"] for row in claim_rows}
    main_rows = [row for row in rows if row["placement"] == "main"]
    assert 6 <= len(main_rows) <= 8
    assert len(main_rows) == 8
    assert {row["source_figure"] for row in rows} == set(figures)
    for row in rows:
        assert set(row["claim_ids"].split(";")) <= claim_ids
        provenance_outputs = {item["path"] for item in figures[row["source_figure"]]["outputs"]}
        assert set(row["source_paths"].split(";")) == provenance_outputs
        assert row["limitations"]
        assert row["caption_file"] == "manuscript/FIGURE_CAPTIONS.md"


def test_main_figure_callouts_follow_submission_registry(submission, project_root):
    _, rows = _read_csv(project_root / "manuscript" / "FIGURE_CLAIM_REGISTRY.csv")
    manuscript = submission.build_submission(project_root)["manuscript"]
    main_ids = [row["submission_id"] for row in rows if row["placement"] == "main"]
    assert all(f"(Figure {figure_id})" in manuscript for figure_id in main_ids)
    assert all(manuscript.count(f"(Figure {figure_id})") == 1 for figure_id in main_ids)


def test_audit_rejects_hotspot_value_mutation(audit, submission, project_root):
    texts = submission.build_submission(project_root)
    mutated = texts["manuscript"].replace("-30.95", "-31.95", 1)
    report = audit.run_audit(project_root, manuscript_override=mutated)
    assert not report.scientific_pass
    assert "numerical_consistency" in report.failed_gates


def test_audit_rejects_relative_los_changed_to_vertical(audit, submission, project_root):
    texts = submission.build_submission(project_root)
    mutated = texts["manuscript"].replace("relative LOS", "vertical displacement", 1)
    report = audit.run_audit(project_root, manuscript_override=mutated)
    assert not report.scientific_pass
    assert "terminology" in report.failed_gates


def test_audit_rejects_unknown_citation(audit, submission, project_root):
    texts = submission.build_submission(project_root)
    mutated = texts["manuscript"] + "\nUnsupported citation [@unknown2026].\n"
    report = audit.run_audit(project_root, manuscript_override=mutated)
    assert not report.scientific_pass
    assert "citations" in report.failed_gates


def test_audit_rejects_removed_negative_or_contradictory_zones(
    audit, submission, project_root
):
    texts = submission.build_submission(project_root)
    mutated = texts["manuscript"].replace("H002", "REMOVED").replace("H005", "REMOVED")
    report = audit.run_audit(project_root, manuscript_override=mutated)
    assert not report.scientific_pass
    assert "numerical_consistency" in report.failed_gates


def test_audit_rejects_nondeterministic_second_build(audit, submission, project_root):
    texts = submission.build_submission(project_root)
    second = {**texts, "manuscript": texts["manuscript"] + "\nBUILD DRIFT\n"}
    report = audit.run_audit(project_root, second_build_override=second)
    assert not report.scientific_pass
    assert "determinism" in report.failed_gates


def test_target_journal_abstract_keywords_and_highlights(submission, project_root):
    texts = submission.build_submission(project_root)
    manuscript = texts["manuscript"]
    abstract = manuscript.split("## Abstract\n", 1)[1].split("\n\n", 1)[0].strip()
    assert 150 <= len(abstract.split()) <= 250

    keyword_line = manuscript.split("**Keywords:**", 1)[1].splitlines()[0].strip()
    keywords = [item.strip() for item in keyword_line.split(";")]
    assert 1 <= len(keywords) <= 7

    highlights = [
        line.removeprefix("- ")
        for line in texts["highlights"].splitlines()
        if line.startswith("- ")
    ]
    assert 3 <= len(highlights) <= 5
    assert all(len(item) <= 85 for item in highlights)


def test_journal_selection_uses_declared_weighting_and_official_sources(project_root):
    selection = (project_root / "manuscript" / "JOURNAL_SELECTION.md").read_text()
    for journal in (
        "International Journal of Applied Earth Observation and Geoinformation",
        "Remote Sensing of Environment",
        "IEEE Journal of Selected Topics in Applied Earth Observations and Remote Sensing",
    ):
        assert journal in selection
    for weight in ("40%", "25%", "15%", "10%"):
        assert weight in selection
    assert "Selected target" in selection
    assert "Retrieved 23 September 2026" in selection
    assert selection.count("https://") >= 6


def test_journal_compliance_has_only_actionable_statuses(project_root):
    compliance = (project_root / "manuscript" / "JOURNAL_COMPLIANCE.md").read_text()
    assert "International Journal of Applied Earth Observation and Geoinformation" in compliance
    assert "PASS" in compliance
    assert "AWAITING AUTHOR CONFIRMATION" in compliance
    assert "Declaration of generative AI" in compliance
    assert "Data repository" in compliance
    statuses = re.findall(r"\| (PASS|AWAITING AUTHOR CONFIRMATION) \|", compliance)
    assert len(statuses) >= 10


def test_cover_letter_is_factual_and_preserves_author_boundary(project_root):
    letter = (project_root / "manuscript" / "COVER_LETTER.md").read_text()
    assert "Research paper" in letter
    assert "Selective reproduction" in letter
    assert "exclusive submission" in letter.lower()
    assert "data and code" in letter.lower()
    assert "AWAITING AUTHOR CONFIRMATION" in letter
    assert not re.search(r"\bfirst\b", letter, flags=re.IGNORECASE)
