#!/usr/bin/env python
"""
Consolidated RAW-336 scientific report.

Assembles the frozen-input provenance, AOI QC table, RAW-336 baseline
diagnostics, candidate bad-pair table, unwrap-correction comparison,
reference-sensitivity results and the proposed curated network into one
human-readable report plus a machine-readable summary.

This is a STOPPING POINT: it does not produce a final deformation product, and
the tropospheric and DEM-residual branches are deliberately not run yet because
they belong after the network and reference are frozen.

Outputs
-------
qc/sci/RAW336_REPORT.md
qc/sci/raw336_summary.json

Usage
-----
    python scripts/21_report_raw336.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QC = PROJECT_ROOT / "qc" / "sci"


def load(name: str) -> dict:
    path = QC / name
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> int:
    qc_summary = load("ifgram_qc_summary.json")
    baseline = load("baseline_raw_diagnostics.json")
    unwrap = load("unwrap_comparison.json")
    reference = load("reference_sensitivity.json")
    network = load("network_comparison.json")

    qc_table = pd.read_csv(QC / "ifgram_qc_table.csv")
    candidates = pd.read_csv(QC / "bad_pair_candidates.csv")
    residuals = pd.read_csv(QC / "per_ifg_residuals.csv")

    v = baseline.get("raw_los_velocity_m_per_yr", {})
    tc = baseline.get("temporal_coherence", {})
    rms = baseline.get("residual_rms_rad", {})
    ref_sens = reference.get("sensitivity", {})
    rec = reference.get("recommended_reference", {})
    full = network.get("full", {})
    curated = network.get("curated", {})
    repaired = network.get("revised_proposal_to_restore_bridges", {})
    pruned = network.get("alternative_strategy_acquisition_pruning", {})
    verdict = unwrap.get("verdict", {})
    udiff = unwrap.get("difference_bridge_minus_raw", {})
    ures = unwrap.get("per_ifg_residual_comparison", {})

    md: list[str] = []
    add = md.append

    add("# Delhi-NCR SBAS - RAW-336 Scientific Report")
    add("")
    add(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    add("")
    add("**Status: stopping point. No final deformation product is declared, and the")
    add("tropospheric and DEM-residual branches are not run yet** (they belong after the")
    add("network and reference are frozen).")
    add("")
    add("## 1. Frozen input")
    add("")
    add("| item | value |")
    add("|---|---|")
    add("| freeze | `freeze/mintpy_input_v1` (hash-pinned, verified) |")
    add("| network | 336 interferograms / 119 acquisitions |")
    add("| grid | 2407 x 2939 px @ 40 m, EPSG:32643 |")
    add("| period | 2021-10-06 to 2025-09-27 |")
    add("| HyP3 corpus | unchanged; 2025-05-18 remains excluded (fail-closed) |")
    add("")
    add("**No pair was removed before the baseline inversion.** MintPy's `dropIfgram`")
    add("flag remains all-336-in-use afterwards (note: the flag is *inverted* relative")
    add("to its name - `True` means in use).")
    add("")

    add("## 2. AOI-centric interferogram QC (all 336 pairs)")
    add("")
    aoi = qc_summary.get("aoi", {})
    add(f"AOI polygon: **{aoi.get('aoi_px')} px = {aoi.get('aoi_area_km2')} km²**, "
        f"water fraction {aoi.get('water_fraction_of_aoi')}.")
    add("")
    add("| temporal baseline | n | median coherence | median largest component (AOI) |")
    add("|---|---|---|---|")
    for key, value in qc_summary.get("by_temporal_baseline", {}).items():
        add(f"| {key} d | {value['count']} | {value['median_coherence']:.4f} | "
            f"{value['median_largest_component_frac']:.4f} |")
    add("")
    d = qc_summary.get("distributions", {})
    add(f"Coherence degrades cleanly with temporal baseline "
        f"({d.get('coherence_median', {}).get('min')} to "
        f"{d.get('coherence_median', {}).get('max')} across pairs). "
        f"Unwrapped-phase validity over the AOI is uniform at "
        f"{d.get('unwrap_valid_frac_aoi', {}).get('median')} - the missing ~1.85% is water, "
        f"which the mask removes by design.")
    add("")

    add("## 3. RAW-336 baseline inversion (uncorrected)")
    add("")
    add("Corrections deliberately **disabled**: unwrap error, troposphere, deramp, DEM")
    add("residual. `keepMinSpanTree` forced off (MintPy defaults it to *yes* and would")
    add("have silently dropped pairs). Runtime 13m25s.")
    add("")
    add("| quantity | median | p05 | p95 | std |")
    add("|---|---|---|---|---|")
    add(f"| raw LOS velocity (m/yr) | {v.get('median')} | {v.get('p05')} | {v.get('p95')} | {v.get('std')} |")
    add(f"| velocity uncertainty (m/yr) | "
        f"{baseline.get('velocity_uncertainty_m_per_yr', {}).get('median')} | | | |")
    add(f"| temporal coherence | {tc.get('median')} | {tc.get('p05')} | {tc.get('p95')} | {tc.get('std')} |")
    add(f"| per-ifg residual RMS (rad) | {rms.get('median')} | | {rms.get('p95')} | |")
    add("")
    add(f"- {100 * baseline.get('temporal_coherence_fractions', {}).get('frac_gt_0.7', 0):.1f}% "
        f"of the AOI exceeds temporal coherence 0.7.")
    add(f"- The velocity field is skewed negative: p05 = {v.get('p05')} m/yr "
        f"(-{abs(v.get('p05', 0)) * 1000:.0f} mm/yr) versus p95 = {v.get('p95')} m/yr. "
        f"That asymmetry is the LOS subsidence signature, but it is **relative** to the "
        f"reference pixel and is not yet a deformation product.")
    add(f"- Residual model validated: Spearman(residual RMS, coherence) = "
        f"{baseline.get('residual_model_validation', {}).get('spearman_residual_vs_coherence')} "
        f"({baseline.get('residual_model_validation', {}).get('interpretation')}).")
    add("")

    add("## 4. Candidate bad-pair table (proposal only)")
    add("")
    add(f"**{len(candidates)} of 336 pairs ({100 * len(candidates) / 336:.1f}%)** are robust")
    add("outliers *within their own temporal-baseline class*. Absolute thresholds are")
    add("meaningless on an uncorrected baseline - an initial fixed 1 rad cut flagged")
    add("333/336 because unmodelled atmosphere and orbit ramps dominate the residual.")
    add("")
    if not candidates.empty:
        add("| pair | t (d) | coh median | largest comp | residual RMS (rad) | reasons |")
        add("|---|---|---|---|---|---|")
        for row in candidates.head(15).itertuples():
            add(f"| {row.date12} | {row.temporal_baseline_days} | {row.coherence_median} | "
                f"{row.largest_component_frac_aoi} | {row.residual_rms_rad} | {row.n_reasons} |")
        add("")
        by_tb = candidates["temporal_baseline_days"].value_counts().sort_index().to_dict()
        add(f"Distribution by temporal baseline: {by_tb}. "
            "The candidates **cluster in mid-2023**, which is itself diagnostic.")
    add("")

    add("## 5. Unwrap-correction comparison")
    add("")
    add("Bridging + phase closure, identical in every other respect. Runtime 23m33s.")
    add("")
    add("| metric | RAW | bridging+phase_closure |")
    add("|---|---|---|")
    add(f"| velocity median (m/yr) | {unwrap.get('velocity_m_per_yr', {}).get('raw', {}).get('median')} | "
        f"{unwrap.get('velocity_m_per_yr', {}).get('bridge_pc', {}).get('median')} |")
    add(f"| temporal coherence median | "
        f"{unwrap.get('temporal_coherence', {}).get('raw', {}).get('median')} | "
        f"{unwrap.get('temporal_coherence', {}).get('bridge_pc', {}).get('median')} |")
    add(f"| per-ifg residual RMS median (rad) | {ures.get('raw', {}).get('median')} | "
        f"{ures.get('bridge_pc', {}).get('median')} |")
    add(f"| pairs improved / worsened | - | {ures.get('n_improved')} / {ures.get('n_worsened')} |")
    add("")
    add(f"Velocity changes by **{1000 * udiff.get('velocity_rms', 0):.2f} mm/yr RMS** "
        f"(max |delta| {1000 * udiff.get('velocity_max_abs', 0):.1f} mm/yr), so the correction "
        "is materially changing ambiguities. However it **degrades** the fit: residual RMS "
        f"median rises {ures.get('raw', {}).get('median')} -> {ures.get('bridge_pc', {}).get('median')} rad, "
        f"only {ures.get('n_improved')} of 336 pairs improve, and temporal coherence falls "
        f"{udiff.get('temporal_coherence_median')} on median.")
    add("")
    add("**Recommendation: do not enable unwrap correction for production in this")
    add("configuration.** Its benefit is not demonstrated, and it may require parameter")
    add("tuning (`connCompMinArea`, `numSample`, `bridgePtsRadius`) for this 40 m")
    add("4-burst dataset before it can be reconsidered.")
    add("")

    add("## 6. Reference sensitivity")
    add("")
    add("Candidates were selected on coherence and velocity **uncertainty** only. Velocity")
    add("was deliberately **not** a selection criterion: choosing the reference because its")
    add("velocity is near zero is circular and would hide the systematic.")
    add("")
    add("| region | lon | lat | median tc | velocity (mm/yr) | uncertainty (mm/yr) |")
    add("|---|---|---|---|---|---|")
    for key, c in reference.get("candidates", {}).items():
        add(f"| {key} | {c['lon']} | {c['lat']} | | {c['shift_vs_baseline_mm_per_yr']:+.2f} "
            f"(vs baseline) | |")
    add("")
    add(f"**Velocity spread across candidates: {ref_sens.get('candidate_velocity_spread_mm_per_yr')} mm/yr "
        f"(sd {ref_sens.get('candidate_velocity_sd_mm_per_yr')}).**")
    add("")
    add("That spread is the systematic uncertainty the reference imposes on **absolute** LOS")
    add("velocity across the whole AOI. For a study whose signals are tens of mm/yr this is")
    add("material and must be reported. **Relative spatial gradients are unaffected** by the")
    add("reference choice, so hotspot *contrast* is robust even while the absolute offset is not.")
    add("")
    add(f"Recommended: **lon {rec.get('lon')}, lat {rec.get('lat')}** "
        f"(median tc {rec.get('median_temporal_coherence')}, "
        f"uncertainty-derived std {rec.get('median_velocity_m_per_yr')} m/yr). "
        "Geographic plausibility (bedrock/ridge versus floodplain) is for the owner to confirm.")
    add("")

    add("## 7. Proposed curated network and graph audit")
    add("")
    add("| network | pairs | components | bridges | articulation pts | min degree | accepted |")
    add("|---|---|---|---|---|---|---|")
    for label, s in (("FULL", full), ("CURATED (naive)", curated)):
        add(f"| {label} | {s.get('edges')} | {s.get('components')} | {s.get('bridges')} | "
            f"{s.get('articulation_points')} | {s.get('degree_min')} | {s.get('accepted')} |")
    add("")
    add("**Naive exclusion is rejected.** Removing all 39 candidates keeps the network")
    add("connected but introduces a bridge, two articulation points and a node of degree 1")
    add("(2023-08-09 falls from degree 4 to 1).")
    add("")
    add(f"- Greedy repair restoring the fewest pairs: {repaired.get('n_restored')} restored "
        f"-> {repaired.get('resulting_pairs')} pairs, still **not accepted**.")
    add(f"- Alternative (prune under-supported acquisitions): {pruned.get('n_pruned')} dates "
        f"dropped ({', '.join(pruned.get('pruned_acquisitions', []))}) -> "
        f"{pruned.get('pairs')} pairs / {pruned.get('dates')} dates, "
        f"**accepted = {pruned.get('accepted')}**.")
    add("")
    add("The candidates cluster in mid-2023, so removing them strips redundancy exactly where")
    add("the network is weakest. Combined with the unwrap result above, the defensible")
    add("position is: **retain all 336 pairs** and treat exclusion as unnecessary for now.")
    add("")

    add("## 8. What is deliberately NOT done")
    add("")
    add("- No final deformation product is declared.")
    add("- ERA5 tropospheric correction and DEM-residual correction are **not** run: the brief")
    add("  places them after the network and reference are frozen, and both are still open.")
    add("- Spatial deramping is not enabled by default and was not run; it remains a")
    add("  sensitivity experiment only, because broad subsidence gradients may be genuine.")
    add("- The production reference is not frozen.")
    add("")

    add("## 9. Decisions requested")
    add("")
    add("1. **Reference:** confirm or replace `lon 77.0950, lat 28.6426`; accept the ~5 mm/yr")
    add("   absolute-velocity systematic and interpret gradients.")
    add("2. **Network:** confirm retaining all 336 pairs, or choose a curation strategy with")
    add("   the graph consequences stated above.")
    add("3. **Unwrap correction:** confirm leaving it disabled.")
    add("4. Only then: authorise the ERA5 branch, then the DEM-residual branch.")
    add("")

    (QC / "RAW336_REPORT.md").write_text("\n".join(md) + "\n")

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "stopping point - no final deformation product",
        "frozen_input": "freeze/mintpy_input_v1",
        "pairs": 336,
        "dates": 119,
        "baseline_velocity_m_per_yr": v,
        "temporal_coherence": tc,
        "candidate_bad_pairs": int(len(candidates)),
        "unwrap_correction_verdict": verdict,
        "reference_sensitivity_mm_per_yr": ref_sens,
        "recommended_reference": rec,
        "network_full": full,
        "network_curated_naive": curated,
        "network_curated_pruned": pruned,
        "recommended_action": "retain all 336 pairs; freeze reference after owner review; "
                              "keep unwrap correction disabled; then run ERA5 then DEM-residual",
        "not_done": ["final deformation product", "ERA5 tropospheric branch",
                     "DEM-residual branch", "spatial deramp (sensitivity only)"],
    }
    (QC / "raw336_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("=" * 88)
    print("RAW-336 REPORT WRITTEN")
    print("=" * 88)
    print(f"  candidate bad pairs : {len(candidates)}/336")
    print(f"  unwrap correction   : {verdict.get('assessment')}")
    print(f"  reference spread    : {ref_sens.get('candidate_velocity_spread_mm_per_yr')} mm/yr")
    print(f"  curated accepted    : naive={curated.get('accepted')} pruned={pruned.get('accepted')}")
    print(f"\n  {QC / 'RAW336_REPORT.md'}")
    print(f"  {QC / 'raw336_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
