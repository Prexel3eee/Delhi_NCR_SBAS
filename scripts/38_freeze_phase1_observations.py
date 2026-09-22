#!/usr/bin/env python
"""
Phase II, stage 1: freeze the Phase-I observational conclusions.

Phase II introduces external data. Before it does, the Phase-I conclusions are
pinned so that anything external is compared against a fixed statement rather
than a moving one, and so that any later revision of a Phase-I number is visible
as a change rather than a silent drift.

These are OBSERVATIONS, not mechanisms. Nothing in this file asserts a cause.

Outputs
-------
freeze/phase1_observations/OBSERVATIONS.json
freeze/phase1_observations/PHASE1_OBSERVATIONS.md
freeze/phase1_observations/README.md
freeze/phase1_observations/<copied source artefacts>
(whole directory marked read-only)

Usage
-----
    python scripts/38_freeze_phase1_observations.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DIR = PROJECT_ROOT / "freeze" / "phase1_observations"
QC_PHASE1 = PROJECT_ROOT / "qc" / "sci" / "phase1"

FREEZE_VERSION = "phase1_observations_v1"

SOURCE_ARTEFACTS = [
    "qc/sci/phase1/hotspots.csv",
    "qc/sci/phase1/hotspots.json",
    "qc/sci/phase1/hotspot_persistence.json",
    "qc/sci/phase1/hotspot_persistence.csv",
    "qc/sci/phase1/hotspot_timeseries.json",
    "qc/sci/phase1/hotspot_timeseries_summary.csv",
    "qc/sci/phase1/hotspot_uncertainty.csv",
    "qc/sci/phase1/uncertainty_budget.json",
    "qc/sci/phase1/oscillation_diagnostics.json",
    "qc/sci/phase1/coherence_stratification.csv",
    "qc/sci/phase1/deformation_map_summary.json",
    "qc/sci/phase1/evidence_grades.json",
    "qc/sci/PHASE1_REPORT.md",
]

#: The exact phrase required for the mapped area. The true extent is unresolved.
AREA_LABEL = "robustly supported mapped deformation area under the selected quality criterion"

GRADE_BASIS = {
    "H001": ("A", 14, 14),
    "H002": ("B", 11, 14),
    "H003": ("B", 10, 14),
    "H004": ("B", 10, 14),
    "H005": ("C", 8, 14),
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_observations() -> dict:
    hotspots = pd.read_csv(QC_PHASE1 / "hotspots.csv")
    ts = pd.read_csv(QC_PHASE1 / "hotspot_timeseries_summary.csv")
    unc = pd.read_csv(QC_PHASE1 / "hotspot_uncertainty.csv")
    persistence = json.loads((QC_PHASE1 / "hotspot_persistence.json").read_text())
    budget = json.loads((QC_PHASE1 / "uncertainty_budget.json").read_text())
    oscillation = json.loads((QC_PHASE1 / "oscillation_diagnostics.json").read_text())
    summary = json.loads((QC_PHASE1 / "deformation_map_summary.json").read_text())
    sensitivity = pd.read_csv(QC_PHASE1 / "hotspot_threshold_sensitivity.csv")

    merged = hotspots.merge(
        ts[["hotspot_id", "los_rate_from_series_mm_per_yr", "total_los_displacement_mm",
            "temporal_form"]], on="hotspot_id", how="left").merge(
        unc[["hotspot_id", "rate_first_half_mm_per_yr", "rate_second_half_mm_per_yr"]],
        on="hotspot_id", how="left")

    zones = []
    for _, row in merged.iterrows():
        hid = row["hotspot_id"]
        grade, survived, total = GRADE_BASIS[hid]
        reported = persistence["persistence"][hid]
        assert reported["scenarios_survived"] == survived, (
            f"{hid}: frozen expectation {survived} != current {reported['scenarios_survived']}")
        zones.append({
            "zone_id": hid,
            "centroid_lon": row["centroid_lon"],
            "centroid_lat": row["centroid_lat"],
            "area_km2": row["area_km2"],
            "los_velocity_median_mm_per_yr": row["los_velocity_median_mm_per_yr"],
            "los_velocity_peak_mm_per_yr": row["los_velocity_peak_abs_mm_per_yr"],
            "los_sign": "negative" if row["los_velocity_median_mm_per_yr"] < 0 else "positive",
            "temporal_coherence_median": row["temporal_coherence_median"],
            "cumulative_los_displacement_mm": row["total_los_displacement_mm"],
            "rate_from_series_mm_per_yr": row["los_rate_from_series_mm_per_yr"],
            "split_half_first_mm_per_yr": row["rate_first_half_mm_per_yr"],
            "split_half_second_mm_per_yr": row["rate_second_half_mm_per_yr"],
            "split_half_difference_mm_per_yr": round(
                row["rate_second_half_mm_per_yr"] - row["rate_first_half_mm_per_yr"], 3),
            "temporal_form": row["temporal_form"],
            "grade": grade,
            "persistence_scenarios_survived": survived,
            "persistence_scenarios_total": total,
        })

    mapped_area = round(float(hotspots["area_km2"].sum()), 2)
    median_rate = float(merged.loc[merged["hotspot_id"] == "H001",
                                   "los_velocity_median_mm_per_yr"].iloc[0])
    peak = float(hotspots["los_velocity_peak_abs_mm_per_yr"].min())
    totals = hotspots["area_km2"].sum() if len(hotspots) else 0.0
    cumulative = float(ts["total_los_displacement_mm"].min()), float(
        ts["total_los_displacement_mm"].max())
    split_diffs = (merged["rate_second_half_mm_per_yr"]
                   - merged["rate_first_half_mm_per_yr"]).abs()

    return {
        "freeze_version": FREEZE_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_product": {
            "freeze": "product_v1",
            "freeze_id":
                "2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37",
            "principal_solution": "RAW-336",
            "velocity_reference":
                "AUTHORITATIVE PRODUCT REFERENCE (y=1384, x=1451); see "
                "provenance/errata/INC-007.json",
        },
        "status": "OBSERVATIONS_ONLY - no mechanism is asserted anywhere in this file",

        "deformation_zones": zones,
        "zone_count": len(zones),

        "mapped_area": {
            "label": AREA_LABEL,
            "value_km2": mapped_area,
            "quality_criterion": {
                "absolute_velocity_threshold_mm_per_yr": 10.0,
                "temporal_coherence_min": 0.80,
                "minimum_area_km2": 0.4,
                "connectivity": 8,
            },
            "explicit_warning":
                "This is NOT the true deformation extent. Deformation magnitude and "
                "temporal coherence are strongly associated in this stack, so a "
                "coherence-based criterion systematically excludes part of the signal. "
                "The true extent is UNRESOLVED.",
            "extent_sensitivity_km2": {
                f"threshold_{row.threshold_mm_per_yr:g}_coherence_{row.coherence_min:g}":
                    row.area_km2
                for row in sensitivity.itertuples()
                if row.threshold_mm_per_yr in (5.0, 10.0, 15.0)
            },
        },

        "observational_findings": {
            "all_zones_negative_los": all(z["los_velocity_median_mm_per_yr"] < 0
                                          for z in zones),
            "sign_convention": "negative LOS = ground moving away from the satellite along "
                               "the line of sight; this is NOT a subsidence claim",
            "H001_median_los_mm_per_yr": round(median_rate, 3),
            "supported_local_extremes_reach_mm_per_yr": round(peak, 3),
            "cumulative_los_range_mm": [round(cumulative[0], 2), round(cumulative[1], 2)],
            "rates_are_non_stationary": True,
            "split_half_difference_range_mm_per_yr": [
                round(float(split_diffs.min()), 3), round(float(split_diffs.max()), 3)],
            "northern_group": {
                "zones": ["H002", "H003", "H005"],
                "behaviour": "accumulate most displacement in the first half, then plateau",
            },
            "southern_group": {
                "zones": ["H001", "H004"],
                "behaviour": "faster in the second half",
            },
            "north_south_distinct_temporal_behaviour": True,
            "within_group_mutual_correlation": {
                "northern_r_range": [0.82, 0.99],
                "southern_r": 0.82,
                "between_groups_r_range": [-0.46, -0.34],
                "survives_change_of_detrend_order": True,
            },
            "reference_choice_zero_level_range_mm_per_yr": 4.78,
            "relative_contrast_uncertainty_mm_per_yr":
                budget["combined_relative_uncertainty_mm_per_yr"],
            "absolute_zero_level_uncertainty_mm_per_yr":
                budget["combined_absolute_uncertainty_mm_per_yr"],
            "relative_contrast_materially_smaller_than_absolute":
                budget["combined_relative_uncertainty_mm_per_yr"]
                < budget["combined_absolute_uncertainty_mm_per_yr"],
            "coherence_velocity_association": {
                "present": True,
                "description": "lower temporal coherence is associated with much stronger "
                               "negative LOS velocity across the AOI",
                "status": "UNRESOLVED - the highest-priority open question for Phase II",
            },
            "noise_floor_mm_per_yr":
                summary["noise_floor"]["short_wavelength_robust_sigma_mm_per_yr"],
        },

        "not_established": [
            "no mechanism", "no vertical rate", "no absolute rate",
            "no validated total extent", "no volume or storage change",
        ],
        "not_a_mechanism_statement": (
            "Every entry above is a statement about the InSAR observations. "
            "Groundwater, tectonics, compaction, construction and metro loading, "
            "lithology and fault motion are untested hypotheses and appear nowhere "
            "in this freeze."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if FREEZE_DIR.exists() and not args.force:
        print(f"ERROR: {FREEZE_DIR} exists. Use --force to rebuild.", file=sys.stderr)
        return 1

    missing = [rel for rel in SOURCE_ARTEFACTS if not (PROJECT_ROOT / rel).exists()]
    if missing:
        print("ERROR: missing Phase I artefacts:", file=sys.stderr)
        for rel in missing:
            print(f"  - {rel}", file=sys.stderr)
        return 1

    if FREEZE_DIR.exists():
        for path in sorted(FREEZE_DIR.rglob("*"), reverse=True):
            path.chmod(0o755) if path.is_dir() else path.chmod(0o644)
        FREEZE_DIR.chmod(0o755)
        shutil.rmtree(FREEZE_DIR)
    FREEZE_DIR.mkdir(parents=True)

    observations = build_observations()

    print("=" * 88)
    print("FREEZE PHASE I OBSERVATIONS")
    print("=" * 88)

    copied = []
    for rel in SOURCE_ARTEFACTS:
        src = PROJECT_ROOT / rel
        dst = FREEZE_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append({"path": rel, "sha256": sha256_of(dst),
                       "bytes": dst.stat().st_size})
    print(f"\n  copied {len(copied)} source artefacts")

    observations["source_artefacts"] = copied

    payload = json.dumps({
        "version": FREEZE_VERSION,
        "zones": [[z["zone_id"], z["area_km2"], z["los_velocity_median_mm_per_yr"],
                   z["grade"]] for z in observations["deformation_zones"]],
        "mapped_area_km2": observations["mapped_area"]["value_km2"],
        "findings": observations["observational_findings"],
        "sources": [[c["path"], c["sha256"]] for c in copied],
    }, sort_keys=True).encode()
    freeze_id = hashlib.sha256(payload).hexdigest()
    observations["freeze_id"] = freeze_id

    json_path = FREEZE_DIR / "OBSERVATIONS.json"
    json_path.write_text(json.dumps(observations, indent=2, default=str))

    f = observations["observational_findings"]
    md = f"""# Phase I Observations — frozen

`freeze_version` **{FREEZE_VERSION}**
`freeze_id` **{freeze_id}**

Source: `product_v1` / RAW-336. Velocities are relative to the
**AUTHORITATIVE PRODUCT REFERENCE** (y=1384, x=1451) — see
`provenance/errata/INC-007.json`.

**These are observations, not mechanisms.** No causal statement appears here.

## Deformation zones

| Zone | Area km² | Median LOS mm/yr | Coherence | Cumulative LOS mm | Grade | Persistence |
|---|---:|---:|---:|---:|---|---|
"""
    for z in observations["deformation_zones"]:
        md += (f"| {z['zone_id']} | {z['area_km2']:.2f} | "
               f"{z['los_velocity_median_mm_per_yr']:+.2f} | "
               f"{z['temporal_coherence_median']:.3f} | "
               f"{z['cumulative_los_displacement_mm']:+.1f} | {z['grade']} | "
               f"{z['persistence_scenarios_survived']}/{z['persistence_scenarios_total']} |\n")

    md += f"""
## Mapped area

**{AREA_LABEL}: {observations['mapped_area']['value_km2']:.1f} km²**

Criterion: |LOS velocity| ≥ 10 mm/yr, temporal coherence ≥ 0.80, area ≥ 0.4 km²,
8-connectivity.

> This is **NOT the true deformation extent.** Deformation magnitude and temporal
> coherence are strongly associated in this stack, so a coherence-based criterion
> systematically excludes part of the signal. The true extent is **UNRESOLVED**.

## Observational findings

* All five principal zones have **negative LOS velocity** in the frozen sign
  convention (movement away from the satellite along the line of sight). This is
  **not** a subsidence claim.
* H001 approximate median velocity **{f['H001_median_los_mm_per_yr']:+.1f} mm/yr**.
* Supported local extremes reach substantially larger negative values
  (magnitude up to **{abs(f['supported_local_extremes_reach_mm_per_yr']):.1f} mm/yr**).
* Major hotspot cumulative LOS displacement approximately
  **{f['cumulative_los_range_mm'][0]:.0f} to {f['cumulative_los_range_mm'][1]:.0f} mm**.
* **Rates are non-stationary.** Split-half differences reach
  **{f['split_half_difference_range_mm_per_yr'][0]:.1f}–{f['split_half_difference_range_mm_per_yr'][1]:.1f} mm/yr**.
* Northern ({', '.join(f['northern_group']['zones'])}) and southern
  ({', '.join(f['southern_group']['zones'])}) groups show **distinct temporal
  behaviour**.
* Reference-choice zero-level range: **{f['reference_choice_zero_level_range_mm_per_yr']:.2f} mm/yr**.
* Relative contrast uncertainty (**{f['relative_contrast_uncertainty_mm_per_yr']:.2f} mm/yr**)
  is materially smaller than absolute zero-level uncertainty
  (**{f['absolute_zero_level_uncertainty_mm_per_yr']:.2f} mm/yr**).
* The coherence–velocity association is **UNRESOLVED** and is the highest-priority
  question for Phase II.

## Not established

{chr(10).join('* ' + item for item in observations['not_established'])}

## Source artefact hashes

| File | sha256 |
|---|---|
"""
    for c in copied:
        md += f"| `{c['path']}` | `{c['sha256']}` |\n"

    md_path = FREEZE_DIR / "PHASE1_OBSERVATIONS.md"
    md_path.write_text(md)

    readme = FREEZE_DIR / "README.md"
    readme.write_text(
        f"# freeze/{FREEZE_VERSION}\n\n"
        f"Immutable. `freeze_id = {freeze_id}`\n\n"
        "Phase-I observational conclusions, pinned before Phase II introduces "
        "external data. Observations only; no mechanism is asserted.\n\n"
        "Verify with `python scripts/verify_phase1_observations.py`.\n")

    for path in sorted(FREEZE_DIR.rglob("*"), reverse=True):
        if path in (json_path, md_path, readme):
            continue
        path.chmod(path.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    for path in (json_path, md_path, readme):
        path.chmod(0o444)
    FREEZE_DIR.chmod(0o555)

    print(f"  freeze_id {freeze_id}")
    print(f"  zones {observations['zone_count']}, "
          f"mapped area {observations['mapped_area']['value_km2']:.1f} km2")
    print(f"  marked read-only: {FREEZE_DIR}")
    print(f"\n  {json_path}")
    print(f"  {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
