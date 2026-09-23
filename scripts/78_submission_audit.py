#!/usr/bin/env python
"""Fail-closed scientific and submission audit for the Delhi-NCR manuscript."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT_DIR = PROJECT_ROOT / "manuscript"


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    details: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditReport:
    gates: list[GateResult]
    metrics: dict[str, Any]
    terminology_allowances: list[dict[str, str]]
    author_status: str

    @property
    def scientific_pass(self) -> bool:
        return all(gate.passed for gate in self.gates)

    @property
    def failed_gates(self) -> list[str]:
        return [gate.name for gate in self.gates if not gate.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "submission_audit_v2",
            "scientific_pass": self.scientific_pass,
            "failed_gates": self.failed_gates,
            "author_status": self.author_status,
            "metrics": self.metrics,
            "terminology_allowances": self.terminology_allowances,
            "gates": [asdict(gate) for gate in self.gates],
        }


def _load_builder(root: Path):
    path = root / "scripts" / "77_build_submission_manuscript.py"
    spec = importlib.util.spec_from_file_location("submission_builder_for_audit", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load manuscript builder from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def _result(name: str, problems: list[str], success: str) -> GateResult:
    return GateResult(name=name, passed=not problems, details=problems or [success])


def _scientific_freeze_gate(root: Path, builder: Any) -> GateResult:
    problems: list[str] = []
    required = [
        *builder.evidence_paths(root),
        root / "freeze" / "v1" / "FREEZE_v1.json",
        root / "freeze" / "product_v1" / "FREEZE.json",
        root / "freeze" / "mintpy_input_v1" / "FREEZE.json",
    ]
    for path in required:
        if not path.is_file():
            problems.append(f"missing authoritative freeze record: {path.relative_to(root)}")
    targets = [str(path.relative_to(root)) for path in builder.output_paths(root)]
    if any("publication_v1" in target or "MANUSCRIPT_FINAL_JOURNAL_NEUTRAL" in target for target in targets):
        problems.append("submission builder targets a protected publication-v1 artefact")
    return _result(
        "scientific_freeze",
        problems,
        "authoritative evidence and freeze records are present; publication v1 is not targeted",
    )


def _numerical_gate(manuscript: str, evidence: Any, builder: Any) -> GateResult:
    problems: list[str] = []
    expected_rows: list[str] = []
    for hotspot in ("H001", "H004", "H002", "H003", "H005"):
        row = evidence.hotspots[hotspot]
        expected = (
            f"| {hotspot} | {row.ascending_rate:+.2f} | {row.descending_rate:+.2f} | "
            f"{row.area_km2:.2f} | {row.status} |"
        )
        expected_rows.append(expected)
        if expected not in manuscript:
            problems.append(f"missing or altered frozen hotspot row: {hotspot}")
        if hotspot not in manuscript:
            problems.append(f"required frozen zone absent: {hotspot}")

    required_literals = {
        "supported polygon sum": "6.66 km2",
        "operating extent": "22.6 km2",
        "ascending acquisitions": "119 acquisitions",
        "ascending interferograms": "336 interferograms",
        "descending acquisitions": "91 acquisitions",
        "descending interferograms": "219 interferograms",
        "H001 abstract rate pair": "-30.95/-36.02",
        "H004 abstract rate pair": "-14.31/-12.46",
        "H005 abstract contradiction": "-14.21 versus +61.39",
        "formal uncertainty": "0.866 mm yr-1",
        "reference systematic": "4.78 mm yr-1",
        "processing sensitivity range": "0.521-1.036 mm yr-1",
        "temporal sensitivity lower bound": "10.44-20.24 mm yr-1",
        "field correlation before correction": "r = 0.175",
        "field correlation after correction": "r = 0.363",
    }
    for label, literal in required_literals.items():
        if literal not in manuscript:
            problems.append(f"missing frozen numeric statement ({label}): {literal}")

    for state in evidence.evidence_states.values():
        if state not in manuscript:
            problems.append(f"missing frozen evidence state: {state}")

    if "H005 was excluded from all causal-test samples" not in manuscript:
        problems.append("H005 exclusion from causal tests is absent")
    if "H002 and H003" not in manuscript:
        problems.append("negative-control pair H002/H003 is absent")
    if builder._hotspot_table(evidence).splitlines()[2:] != expected_rows:
        problems.append("builder hotspot ordering or formatting drifted from the frozen audit contract")
    return _result(
        "numerical_consistency",
        problems,
        "all protected values, zones, exclusions, and evidence states are reproduced",
    )


def _sentence_units(text: str) -> list[tuple[int, str]]:
    units: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", stripped):
            if sentence:
                units.append((line_number, sentence))
    return units


def _allowed_term(term: str, sentence: str) -> tuple[bool, str, str]:
    lowered = sentence.casefold()
    if term == "validated":
        allowed = any(
            phrase in lowered
            for phrase in (
                "not a validated",
                "not a continuous validated",
                "rather than a continuous validated",
                "not an extrapolated or continuous validated",
            )
        )
        return allowed, "explicitly negates a continuous validated footprint", "C005;C006"
    if term == "vertical":
        allowed = any(
            phrase in lowered
            for phrase in (
                "does not establish vertical",
                "do not by themselves establish vertical",
                "does not establish an absolute rate, vertical",
                "not vertical",
                "no vertical/east decomposition",
                "relative los and vertical motion",
                "vertical-equivalent expectation",
                "vertical equivalence is a reference calculation",
                "not a vertical solution",
                "cannot claim vertical",
                "licenses the phrase vertical displacement",
                "vertical components, and absolute rates are different claims",
            )
        )
        return allowed, "bounds vertical inference or labels a diagnostic expectation", "C014;C021"
    return False, "", ""


def _terminology_gate(manuscript: str) -> tuple[GateResult, list[dict[str, str]]]:
    problems: list[str] = []
    allowances: list[dict[str, str]] = []
    terms = ("vertical", "validated", "confirmed", "proved", "caused by", "groundwater-induced", "subsidence")
    patterns = {
        term: re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.IGNORECASE)
        for term in terms
    }
    for line_number, sentence in _sentence_units(manuscript):
        for term, pattern in patterns.items():
            if not pattern.search(sentence):
                continue
            allowed, reason, claim_id = _allowed_term(term, sentence)
            if not allowed:
                problems.append(f"unqualified term '{term}' at manuscript line {line_number}: {sentence[:180]}")
                continue
            allowances.append(
                {
                    "term": term,
                    "line": str(line_number),
                    "line_sha256": hashlib.sha256(sentence.encode()).hexdigest(),
                    "reason": reason,
                    "claim_id": claim_id,
                }
            )
    return (
        _result(
            "terminology",
            problems,
            f"{len(allowances)} bounded uses logged; no prohibited unqualified terminology",
        ),
        allowances,
    )


def _bib_entries(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"(?m)^@\w+\s*\{\s*([^,\s]+)\s*,", text))
    entries: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        entries[match.group(1)] = text[match.start():end]
    return entries


def _citation_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for group in re.findall(r"\[([^\]]*@[A-Za-z0-9_:-]+[^\]]*)\]", text):
        keys.update(re.findall(r"@([A-Za-z0-9_:-]+)", group))
    return keys


def _citation_gate(root: Path, manuscript: str, supplement: str) -> GateResult:
    problems: list[str] = []
    bibliography = (root / "manuscript" / "REFERENCE_LIBRARY.bib").read_text()
    entries = _bib_entries(bibliography)
    cited = _citation_keys(manuscript + "\n" + supplement)
    unknown = sorted(cited - set(entries))
    if unknown:
        problems.append("unknown citation keys: " + ", ".join(unknown))
    dois: dict[str, str] = {}
    for key, entry in entries.items():
        doi_match = re.search(r"(?im)^\s*doi\s*=\s*[\{\"]([^\}\"]+)", entry)
        url_match = re.search(r"(?im)^\s*url\s*=\s*[\{\"]([^\}\"]+)", entry)
        if not doi_match and not url_match:
            problems.append(f"bibliography entry {key} has neither DOI nor URL")
        if doi_match:
            doi = doi_match.group(1).strip().casefold().removeprefix("https://doi.org/")
            if not doi:
                problems.append(f"bibliography entry {key} has an empty DOI")
            elif doi in dois:
                problems.append(f"duplicate DOI in {dois[doi]} and {key}: {doi}")
            else:
                dois[doi] = key
        elif url_match and not url_match.group(1).strip():
            problems.append(f"bibliography entry {key} has an empty URL")
    return _result(
        "citations",
        problems,
        f"{len(cited)} cited keys resolve against {len(entries)} bibliography entries with unique locators",
    )


def _claim_gate(root: Path, manuscript: str) -> tuple[GateResult, set[str]]:
    problems: list[str] = []
    expected_columns = [
        "claim_id", "claim", "claim_type", "evidence_kind", "evidence_locator",
        "citation_key", "allowed_strength", "manuscript_section",
    ]
    columns, rows = _read_csv(root / "manuscript" / "CLAIM_EVIDENCE_LEDGER.csv")
    if columns != expected_columns:
        problems.append(f"claim ledger schema mismatch: {columns}")
    claim_ids = {row.get("claim_id", "") for row in rows}
    if len(claim_ids) != len(rows):
        problems.append("claim ledger contains duplicate IDs")
    for row in rows:
        if not row.get("evidence_locator", "").strip():
            problems.append(f"claim {row.get('claim_id', '<unknown>')} has no evidence locator")

    annotated = set(re.findall(r"<!--\s*Claims:\s*([^>]+?)\s*-->", manuscript))
    used_claim_ids: set[str] = set()
    for group in annotated:
        used_claim_ids.update(re.findall(r"C\d{3}", group))
    unknown = sorted(used_claim_ids - claim_ids)
    if unknown:
        problems.append("unknown manuscript claim IDs: " + ", ".join(unknown))

    material = manuscript.split("## 4. Discussion", 1)
    if len(material) == 2:
        material_text = material[1].split("## 6. Conclusions", 1)[0]
        for paragraph in re.split(r"\n\s*\n", material_text):
            clean = paragraph.strip()
            if not clean or clean.startswith("#") or clean.startswith("|") or len(clean.split()) < 40:
                continue
            if "<!-- Claims:" not in clean and "[@" not in clean:
                digest = hashlib.sha256(clean.encode()).hexdigest()[:12]
                problems.append(f"material paragraph lacks claim ID or citation: sha256:{digest}")
    else:
        problems.append("Discussion section unavailable for material-claim audit")
    return (
        _result(
            "claim_coverage",
            problems,
            f"{len(rows)} ledger claims have locators and all material paragraphs are annotated",
        ),
        claim_ids,
    )


def _figure_gate(root: Path, manuscript: str, claim_ids: set[str]) -> tuple[GateResult, dict[str, int]]:
    problems: list[str] = []
    expected_columns = [
        "submission_id", "source_figure", "placement", "scientific_question",
        "claim_ids", "source_paths", "limitations", "caption_file",
    ]
    columns, rows = _read_csv(root / "manuscript" / "FIGURE_CLAIM_REGISTRY.csv")
    if columns != expected_columns:
        problems.append(f"figure registry schema mismatch: {columns}")
    provenance = json.loads((root / "manuscript" / "FIGURE_PROVENANCE.json").read_text())
    figures = {item["figure_id"]: item for item in provenance.get("figures", [])}
    main_rows = [row for row in rows if row.get("placement") == "main"]
    supplementary_rows = [row for row in rows if row.get("placement") == "supplement"]
    if not 6 <= len(main_rows) <= 8:
        problems.append(f"main figure count outside 6-8: {len(main_rows)}")
    if len(rows) != 12:
        problems.append(f"figure registry must contain 12 entries, found {len(rows)}")
    if {row.get("source_figure") for row in rows} != set(figures):
        problems.append("figure registry and provenance membership differ")
    for row in rows:
        submission_id = row.get("submission_id", "<unknown>")
        source = row.get("source_figure", "")
        referenced_claims = set(filter(None, row.get("claim_ids", "").split(";")))
        if not referenced_claims <= claim_ids:
            problems.append(f"figure {submission_id} references unknown claim IDs")
        if not row.get("limitations", "").strip():
            problems.append(f"figure {submission_id} has no limitation")
        if source in figures:
            outputs = {item["path"] for item in figures[source].get("outputs", [])}
            registered = set(filter(None, row.get("source_paths", "").split(";")))
            if outputs != registered:
                problems.append(f"figure {submission_id} output paths do not match provenance")
        if row.get("placement") == "main":
            callout = f"(Figure {submission_id})"
            if manuscript.count(callout) != 1:
                problems.append(f"main figure callout must occur exactly once: {callout}")
    return (
        _result("figures", problems, f"{len(main_rows)} main and {len(supplementary_rows)} supplementary figures resolve to provenance"),
        {"main_figures": len(main_rows), "supplementary_figures": len(supplementary_rows)},
    )


def _structure_gate(manuscript: str, supplement: str) -> tuple[GateResult, dict[str, int]]:
    problems: list[str] = []
    required_main = [
        "## Abstract", "## 1. Introduction", "## 2. Data and methods", "## 3. Results",
        "## 4. Discussion", "## 5. Limitations", "## 6. Conclusions",
    ]
    for heading in required_main:
        if heading not in manuscript:
            problems.append(f"missing manuscript heading: {heading}")
    required_supplement = [f"## S{number}." for number in range(1, 14)]
    for heading in required_supplement:
        if heading not in supplement:
            problems.append(f"missing supplement heading prefix: {heading}")

    word_count = len(manuscript.split())
    if not 5500 <= word_count <= 7000:
        problems.append(f"manuscript word count outside 5,500-7,000: {word_count}")
    table_count = len(re.findall(r"(?m)^\|---", manuscript))
    if not 2 <= table_count <= 3:
        problems.append(f"main manuscript table count outside 2-3: {table_count}")
    callouts = set(re.findall(r"Supplementary Section (S\d+)", manuscript))
    supplement_headings = set(re.findall(r"(?m)^## (S\d+)\.", supplement))
    expected_callouts = {f"S{number}" for number in range(1, 10)}
    if callouts != expected_callouts:
        problems.append(f"supplement callouts differ from S1-S9: {sorted(callouts)}")
    if not callouts <= supplement_headings:
        problems.append("one or more supplement callouts do not resolve")
    metrics = {"manuscript_words": word_count, "main_tables": table_count}
    return _result("structure", problems, "required architecture, length, tables, and supplement links pass"), metrics


def _reproducibility_gate(root: Path, supplement: str, builder: Any) -> GateResult:
    problems: list[str] = []
    targets = [str(path.relative_to(root)) for path in builder.output_paths(root)]
    if any("publication_v1" in target for target in targets):
        problems.append("builder writes into protected publication_v1")
    for incident in ("INC-001", "INC-002", "INC-005", "INC-006", "INC-007", "INC-008", "INC-009"):
        if incident not in supplement:
            problems.append(f"missing scientific incident: {incident}")
    for heading in ("## S13. Data and code availability", "## Code", "## Processed products", "## External datasets"):
        if heading not in supplement:
            problems.append(f"missing availability component: {heading}")
    return _result(
        "reproducibility",
        problems,
        "submission outputs are isolated and the supplement records incidents and availability",
    )


def _determinism_gate(builder: Any, root: Path, second_build_override: dict[str, str] | None) -> GateResult:
    first = builder.build_submission(root)
    second = second_build_override if second_build_override is not None else builder.build_submission(root)
    problems: list[str] = []
    if set(first) != set(second):
        problems.append(f"build output keys differ: {sorted(first)} versus {sorted(second)}")
    for key in sorted(set(first) & set(second)):
        if first[key] != second[key]:
            problems.append(f"second build differs for {key}")
    return _result("determinism", problems, "two independent in-memory builds are byte-identical")


def _author_status(root: Path) -> str:
    path = root / "manuscript" / "AUTHOR_INPUT_REQUIRED.md"
    if not path.is_file():
        return "AUTHOR INPUT FILE MISSING"
    placeholder = "Not supplied; must be confirmed by the human authors before submission."
    return "AWAITING AUTHOR CONFIRMATION" if placeholder in path.read_text() else "AUTHOR INPUT RECORDED"


def run_audit(
    root: Path = PROJECT_ROOT,
    manuscript_override: str | None = None,
    supplement_override: str | None = None,
    second_build_override: dict[str, str] | None = None,
) -> AuditReport:
    root = Path(root)
    builder = _load_builder(root)
    built = builder.build_submission(root)
    manuscript = manuscript_override if manuscript_override is not None else built["manuscript"]
    supplement = supplement_override if supplement_override is not None else built["supplement"]
    evidence = builder.load_frozen_evidence(root)

    gates: list[GateResult] = []
    gates.append(_scientific_freeze_gate(root, builder))
    gates.append(_numerical_gate(manuscript, evidence, builder))
    terminology, allowances = _terminology_gate(manuscript)
    gates.append(terminology)
    claim_gate, claim_ids = _claim_gate(root, manuscript)
    gates.append(claim_gate)
    gates.append(_citation_gate(root, manuscript, supplement))
    figure_gate, figure_metrics = _figure_gate(root, manuscript, claim_ids)
    gates.append(figure_gate)
    structure_gate, structure_metrics = _structure_gate(manuscript, supplement)
    gates.append(structure_gate)
    gates.append(_reproducibility_gate(root, supplement, builder))
    gates.append(_determinism_gate(builder, root, second_build_override))

    metrics = {
        **structure_metrics,
        **figure_metrics,
        "claim_ledger_entries": len(claim_ids),
        "terminology_allowances": len(allowances),
    }
    return AuditReport(
        gates=gates,
        metrics=metrics,
        terminology_allowances=allowances,
        author_status=_author_status(root),
    )


def _readiness_markdown(report: AuditReport) -> str:
    rows = [
        "# Submission readiness v2",
        "",
        f"**Scientific status:** {'PASS' if report.scientific_pass else 'FAIL'}",
        "",
        f"**Author status:** {report.author_status}",
        "",
        "The author-status boundary is administrative and does not weaken or override a failed scientific gate.",
        "",
        "| Gate | Status | Detail |",
        "|---|---|---|",
    ]
    for gate in report.gates:
        detail = "; ".join(gate.details).replace("|", "\\|")
        rows.append(f"| {gate.name} | {'PASS' if gate.passed else 'FAIL'} | {detail} |")
    rows.extend(
        [
            "",
            "## Metrics",
            "",
            *[f"- **{key}:** {value}" for key, value in sorted(report.metrics.items())],
            "",
            "## Required human completion",
            "",
            "Complete `manuscript/AUTHOR_INPUT_REQUIRED.md` and journal-specific formatting only after all scientific gates pass.",
            "",
        ]
    )
    return "\n".join(rows)


def main() -> int:
    report = run_audit(PROJECT_ROOT)
    audit_path = MANUSCRIPT_DIR / "SUBMISSION_AUDIT.json"
    readiness_path = MANUSCRIPT_DIR / "SUBMISSION_READINESS_V2.md"
    audit_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
    readiness_path.write_text(_readiness_markdown(report))
    print(f"scientific_status={'PASS' if report.scientific_pass else 'FAIL'}")
    print(f"author_status={report.author_status}")
    for gate in report.gates:
        print(f"{gate.name}: {'PASS' if gate.passed else 'FAIL'}")
        if not gate.passed:
            for detail in gate.details:
                print(f"  - {detail}")
    print(audit_path.relative_to(PROJECT_ROOT))
    print(readiness_path.relative_to(PROJECT_ROOT))
    return 0 if report.scientific_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
