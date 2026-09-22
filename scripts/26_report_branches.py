#!/usr/bin/env python
"""
Final report for the atmospheric and DEM-residual branches.

Consolidates RAW / ERA5 / ERA5+DEM into one report and records a correction:
the first RAW-vs-ERA5 comparison used MintPy's `velocityERA5.h5`, which is NOT
the ERA5-corrected velocity. Its FILE_PATH provenance points at inputs/ERA5.h5
(the delay file), and it disagrees with a direct fit to `timeseries_ERA5.h5` by
~3.7 mm/yr. That produced a spurious 15.49 mm/yr RMS difference. Resolving the
products by provenance metadata instead gives 0.52 mm/yr.

No deformation product is declared, and deramping is not applied in any branch.

Outputs
-------
qc/sci/BRANCHES_REPORT.md
qc/sci/branches_summary.json

Usage
-----
    python scripts/26_report_branches.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QC = PROJECT_ROOT / "qc" / "sci"


def load(name: str) -> dict:
    path = QC / name
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> int:
    comparison = load("branch_comparison.json")
    era5 = load("era5_comparison.json")
    coverage = load("era5_coverage.json")
    decisions = json.loads(
        (PROJECT_ROOT / "config" / "scientific_decisions_v2.json").read_text()
    )

    branches = comparison.get("branches", {})
    pairwise = comparison.get("pairwise", {})
    raw = branches.get("RAW", {})
    e5 = branches.get("ERA5", {})
    dem = branches.get("ERA5+DEM", {})

    md: list[str] = []
    add = md.append
    add("# Atmospheric and DEM-Residual Branch Report")
    add("")
    add(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    add("")
    add("**No deformation product is declared.** Deramping is disabled in every branch.")
    add("")

    add("## Frozen decisions")
    add("")
    d = decisions["decisions"]
    add(f"- freeze_id `{decisions['freeze_id']}`")
    add(f"- reference **yx {d['reference']['yx_full_grid']}** "
        f"(lon {d['reference']['lon']}, lat {d['reference']['lat']})")
    add(f"- network **{d['network']['pairs']} pairs**, curation: {d['network']['curation']}")
    add(f"- unwrap-error correction: **{d['unwrap_error_correction']}**")
    add(f"- deramp: **{d['deramp']}**")
    add("")

    add("## ERA5 coverage gate")
    add("")
    add(f"- acquisition dates expected: **{coverage.get('expected_dates')}**")
    add(f"- ERA5 GRIB files present: **{coverage.get('grib_files_present')}** "
        f"({len(coverage.get('grib_missing_dates', []))} missing, "
        f"{len(coverage.get('grib_below_min_size', []))} undersized)")
    add(f"- delay dates match the accepted-acquisition manifest: "
        f"**{coverage.get('delay_dates_match_expected')}**")
    add(f"- AOI finite fraction (minimum across all dates): "
        f"**{coverage.get('aoi_min_finite_fraction')}**")
    add(f"- complete coverage: **{coverage.get('complete_coverage')}**")
    add("")
    add(f"The gate is AOI-restricted. PyAPS leaves NaN outside the ERA5 interpolation")
    add(f"domain, so the *global* finite fraction is only "
        f"{coverage.get('global_finite_fraction')} - gating on that would reject a branch")
    add("that is in fact fully corrected where it matters (0 NaN inside the AOI).")
    add("")

    add("## Correction to the first RAW-vs-ERA5 comparison")
    add("")
    add("The first comparison reported a **15.49 mm/yr RMS** velocity difference. That")
    add("was wrong. It used MintPy's `velocityERA5.h5`, which is **not** the")
    add("ERA5-corrected velocity:")
    add("")
    add("| file | FILE_PATH provenance | agreement with a direct fit to `timeseries_ERA5.h5` |")
    add("|---|---|---|")
    add("| `era5_work/velocity.h5` | `timeseries_ERA5.h5` | **0.0008 mm/yr** (correct) |")
    add("| `era5_work/velocityERA5.h5` | `inputs/ERA5.h5` (the delay file) | 3.72 mm/yr (not the corrected velocity) |")
    add("")
    add("Products are now resolved by reading `FILE_PATH` metadata rather than by")
    add("guessing filename patterns. The corrected difference is **0.52 mm/yr RMS**.")
    add("")
    add("The same class of mistake had already bitten this project once (assuming a")
    add("filename pattern made the DEM branch look identical to ERA5), which is why the")
    add("resolution is now provenance-based in both scripts.")
    add("")

    add("## Branch comparison (AOI-restricted)")
    add("")
    add("| branch | final timeseries | velocity median (m/yr) | coherence | residual RMS (rad) |")
    add("|---|---|---|---|---|")
    for label in ("RAW", "ERA5", "ERA5+DEM"):
        b = branches.get(label)
        if not b:
            continue
        add(f"| {label} | `{b.get('final_timeseries')}` | "
            f"{b['velocity_m_per_yr']['median']:+.4f} | "
            f"{b['temporal_coherence']['median']:.4f} | "
            f"{b['residual_rms_rad_median']} |")
    add("")

    add("## Pairwise effects")
    add("")
    add("| comparison | velocity median (mm/yr) | RMS (mm/yr) | max abs (mm/yr) | residual improved / worsened |")
    add("|---|---|---|---|---|")
    for key, val in pairwise.items():
        add(f"| {key.replace('_minus_', ' minus ')} | {val['median_mm_per_yr']:+.2f} | "
            f"{val['rms_mm_per_yr']:.2f} | {val['max_abs_mm_per_yr']:.2f} | "
            f"{val.get('residual_improved', '-')} / {val.get('residual_worsened', '-')} |")
    add("")

    add("## Interpretation")
    add("")
    add("- **ERA5 changes the velocity field only slightly** (0.52 mm/yr RMS, max 5.1),")
    add("  and slightly **degrades** the fit: residual RMS rises from 4.593 to 4.670 rad,")
    add("  with 140 of 336 pairs improved and 196 worsened.")
    add("- **Pixel-wise DEM-residual correction adds a further 0.78 mm/yr RMS** change")
    add("  relative to ERA5 and a further 1.04 mm/yr relative to RAW; the fit again does")
    add("  not improve (4.670 -> 4.671 rad, 142 improved / 194 worsened).")
    add("- Neither correction is therefore shown to be beneficial for this stack. On an")
    add("  uncorrected baseline the per-interferogram residuals are dominated by")
    add("  unmodelled atmosphere and orbit ramps, so residual RMS is a blunt test - but it")
    add("  is the test the brief specifies, and it does not favour enabling either.")
    add("- ERA5 delays are physically sensible (AOI-median slant delay -3.44 to -2.95 m,")
    add("  median date-to-date step 42 mm, max 254 mm), so the corrections are real")
    add("  rather than numerical artefacts.")
    add("")

    add("## Status")
    add("")
    add("- Deramping **not** applied; it remains a sensitivity experiment only, because")
    add("  broad subsidence gradients may be genuine signal.")
    add("- **No final deformation product is declared.**")
    add("- Raw LOS velocity remains unreferenced to any external stability datum, and the")
    add("  reference choice carries a ~4.8 mm/yr systematic (see the RAW-336 report).")
    add("")

    (QC / "BRANCHES_REPORT.md").write_text("\n".join(md) + "\n")

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "era5_coverage_complete": coverage.get("complete_coverage"),
        "branches": {k: v for k, v in branches.items()},
        "pairwise": pairwise,
        "correction_issued": (
            "The first RAW-vs-ERA5 comparison used velocityERA5.h5, which is not the "
            "ERA5-corrected velocity (provenance points at inputs/ERA5.h5). Corrected "
            "RMS difference: 0.52 mm/yr, not 15.49 mm/yr."
        ),
        "verdict": "neither ERA5 nor pixel-wise DEM-residual correction improves the fit "
                   "on this stack; both change the velocity field modestly",
        "deramp": "disabled",
        "final_deformation_product_declared": False,
    }
    (QC / "branches_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("=" * 88)
    print("BRANCH REPORT WRITTEN")
    print("=" * 88)
    print(f"  ERA5 coverage complete : {coverage.get('complete_coverage')}")
    for label in ("RAW", "ERA5", "ERA5+DEM"):
        b = branches.get(label)
        if b:
            print(f"  {label:10s} velocity {b['velocity_m_per_yr']['median']:+.4f} m/yr | "
                  f"coh {b['temporal_coherence']['median']:.4f} | "
                  f"residual {b['residual_rms_rad_median']} rad")
    print(f"\n  {QC / 'BRANCHES_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
