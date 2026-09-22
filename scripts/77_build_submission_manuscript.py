#!/usr/bin/env python
"""Build the evidence-bound submission manuscript without altering publication v1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class HotspotEvidence:
    hotspot: str
    ascending_rate: float
    descending_rate: float
    area_km2: float
    status: str
    final_interpretation: str


@dataclass(frozen=True)
class FrozenEvidence:
    hotspots: dict[str, HotspotEvidence]
    evidence_states: dict[str, str]
    uncertainty: dict
    source_paths: tuple[Path, ...]


def evidence_paths(root: Path) -> tuple[Path, Path, Path]:
    phase4 = root / "qc" / "sci" / "phase4"
    return (
        phase4 / "final_hotspot_table.csv",
        phase4 / "final_evidence_matrix.csv",
        phase4 / "uncertainty_table.json",
    )


def load_frozen_evidence(root: Path = PROJECT_ROOT) -> FrozenEvidence:
    hotspot_path, matrix_path, uncertainty_path = evidence_paths(root)
    hotspot_frame = pd.read_csv(hotspot_path)
    matrix_frame = pd.read_csv(matrix_path)

    hotspots = {
        str(row.hotspot): HotspotEvidence(
            hotspot=str(row.hotspot),
            ascending_rate=float(row.ascending_rate_mm_per_yr),
            descending_rate=float(row.descending_rate_mm_per_yr),
            area_km2=float(row.area_km2),
            status=str(row.cross_geometry_status),
            final_interpretation=str(row.final_interpretation),
        )
        for row in hotspot_frame.itertuples(index=False)
    }
    evidence_states = {
        str(row.hypothesis): str(row.evidence_state)
        for row in matrix_frame.itertuples(index=False)
    }
    uncertainty = json.loads(uncertainty_path.read_text())
    return FrozenEvidence(
        hotspots=hotspots,
        evidence_states=evidence_states,
        uncertainty=uncertainty,
        source_paths=(hotspot_path, matrix_path, uncertainty_path),
    )


def output_paths(root: Path = PROJECT_ROOT) -> tuple[Path, Path]:
    output = root / "manuscript"
    return (
        output / "SUBMISSION_MANUSCRIPT.md",
        output / "SUBMISSION_SUPPLEMENT.md",
    )


def _hotspot_table(evidence: FrozenEvidence) -> str:
    lines = [
        "| Zone | Ascending rate (mm/yr) | Descending rate (mm/yr) | Area (km2) | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for hotspot in ("H001", "H004", "H002", "H003", "H005"):
        row = evidence.hotspots[hotspot]
        lines.append(
            f"| {hotspot} | {row.ascending_rate:+.2f} | {row.descending_rate:+.2f} | "
            f"{row.area_km2:.2f} | {row.status} |"
        )
    return "\n".join(lines)


def build_submission(root: Path = PROJECT_ROOT) -> dict[str, str]:
    evidence = load_frozen_evidence(root)
    manuscript = "\n".join(
        [
            "# Selective reproducibility of localized LOS deformation in Delhi-NCR from ascending and descending Sentinel-1 InSAR",
            "",
            "## Abstract",
            "",
            "## 1. Introduction",
            "",
            "## 2. Data and methods",
            "",
            "## 3. Results",
            "",
            _hotspot_table(evidence),
            "",
            "## 4. Discussion",
            "",
            "## 5. Limitations",
            "",
            "## 6. Conclusions",
            "",
        ]
    )
    supplement = "# Supplementary material\n"
    return {"manuscript": manuscript, "supplement": supplement}


def write_submission(root: Path = PROJECT_ROOT) -> list[Path]:
    texts = build_submission(root)
    manuscript_path, supplement_path = output_paths(root)
    manuscript_path.parent.mkdir(parents=True, exist_ok=True)
    manuscript_path.write_text(texts["manuscript"])
    supplement_path.write_text(texts["supplement"])
    return [manuscript_path, supplement_path]


def main() -> int:
    for path in write_submission(PROJECT_ROOT):
        print(path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
