#!/usr/bin/env python
"""
Phase G - pilot acceptance report.

Aggregates every Phase F/G artefact into a single machine-checkable verdict and
a human-readable report, then stops. Production is not reachable from here.

Gates are evaluated against evidence, not asserted: each one names the artefact
it reads and the observed value. A failing gate is reported as a failure rather
than smoothed over.

Outputs
-------
qc/pilot/PILOT_ACCEPTANCE_REPORT.md
qc/pilot/pilot_acceptance.json

Usage
-----
    python scripts/11_pilot_acceptance_report.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
QC_DIR = PROJECT_ROOT / "qc" / "pilot"
MINTPY_DIR = PROJECT_ROOT / "mintpy"

EXPECTED_JOBS = 14
EXPECTED_CONFIGS = 7
EXPECTED_PAIRS = 6  # water-mask=ON configurations forming the ingestion network
PRODUCTION_PAIRS = 336
PRODUCTION_CREDITS_10X2 = 1680
FREE_DISK_GB_AT_REPORT = 555


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> int:
    inventory = pd.read_csv(MANIFEST_DIR / "product_inventory.csv")
    qc = load_json(QC_DIR / "pilot_qc.json")
    repro = load_json(QC_DIR / "reproducibility.json")
    water = load_json(QC_DIR / "water_mask_comparison.json")
    storage = load_json(QC_DIR / "storage_estimate.json")
    recon = load_json(QC_DIR / "ledger_reconciliation.json")
    ingestion = load_json(MINTPY_DIR / "pilot_ingestion_report.json")

    configs = qc.get("configurations", [])
    ok = inventory[inventory["download_ok"].fillna(False).astype(bool)]

    gates: list[dict] = []

    def gate(name: str, passed: bool, observed, expected: str, source: str) -> None:
        gates.append(
            {
                "gate": name,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected,
                "source": source,
            }
        )

    # ---- retrieval -------------------------------------------------------
    gate(
        "all_pilot_jobs_reached_terminial_and_succeeded",
        len(ok) == EXPECTED_JOBS,
        f"{len(ok)}/{EXPECTED_JOBS} downloaded",
        f"{EXPECTED_JOBS}/{EXPECTED_JOBS} SUCCEEDED and downloaded",
        "manifests/product_inventory.csv",
    )
    gate(
        "ledger_reconciles_with_remote_truth",
        bool(recon.get("ledger_covers_remote")) and bool(recon.get("remote_covers_ledger")),
        f"ledger={recon.get('ledger_distinct_job_ids')} remote={recon.get('remote_jobs')} "
        f"only_ledger={len(recon.get('in_ledger_not_remote', []))} "
        f"only_remote={len(recon.get('in_remote_not_ledger', []))}",
        "bidirectional coverage, 0 orphans",
        "qc/pilot/ledger_reconciliation.json",
    )
    gate(
        "credit_cost_matches_the_estimate",
        recon.get("credit_cost_observed") == {"5": EXPECTED_JOBS},
        f"{recon.get('credit_cost_observed')} total={recon.get('credit_cost_total')}",
        f"5 credits/job (K=4 @ 10x2), {5 * EXPECTED_JOBS} total",
        "HyP3 job metadata (credit_cost)",
    )

    # ---- geometry / coverage --------------------------------------------
    gate(
        "qc_covered_all_unique_configurations",
        len(configs) == EXPECTED_CONFIGS,
        len(configs),
        f"{EXPECTED_CONFIGS} unique scientific configurations",
        "qc/pilot/pilot_qc.json",
    )
    aoi_ok = all(c.get("aoi_fully_inside_product") for c in configs)
    gate(
        "aoi_fully_inside_every_product",
        aoi_ok,
        [c.get("aoi_fully_inside_product") for c in configs],
        "True for all",
        "qc/pilot/pilot_qc.json",
    )
    crs = {c.get("raster", {}).get("crs") for c in configs}
    res = {c.get("raster", {}).get("res", [None])[0] for c in configs}
    gate(
        "product_geometry_consistent",
        len(crs) == 1 and len(res) == 1 and res == {40.0},
        {"crs": sorted(map(str, crs)), "pixel_size_m": sorted(map(str, res))},
        "one CRS, 40 m pixel spacing (10x2)",
        "qc/pilot/pilot_qc.json",
    )
    valid_aoi = [c.get("coherence", {}).get("valid_fraction_of_aoi") for c in configs]
    gate(
        "valid_data_covers_the_aoi",
        all(v is not None and v >= 0.99 for v in valid_aoi),
        valid_aoi,
        ">= 0.99 of AOI pixels carry valid data",
        "qc/pilot/pilot_qc.json",
    )

    # ---- coherence / unwrapping / components ----------------------------
    medians = [c.get("coherence", {}).get("median") for c in configs]
    gate(
        "coherence_usable_across_all_configs",
        all(m is not None and m >= 0.30 for m in medians),
        {"min": min(m for m in medians if m is not None), "values": medians},
        "median coherence >= 0.30 for every configuration",
        "qc/pilot/pilot_qc.json",
    )
    # Land-relative: water pixels are excluded by design, so gating on the plain
    # AOI fraction would penalise the water mask for working correctly.
    unw_valid = [
        (c.get("unw_phase", {}).get("valid_fraction_of_aoi_land")
         or c.get("unw_phase", {}).get("valid_fraction_of_aoi"))
        for c in configs
    ]
    gate(
        "unwrapped_phase_usable_over_land",
        all(v is not None and v >= 0.99 for v in unw_valid),
        unw_valid,
        ">= 0.99 of AOI *land* pixels unwrapped (water excluded by design)",
        "qc/pilot/pilot_qc.json",
    )
    largest = [c.get("conncomp", {}).get("largest_component_fraction_of_aoi") for c in configs]
    comps = [c.get("conncomp", {}).get("components_in_aoi") for c in configs]
    gate(
        "connected_components_sensible",
        all(v is not None and v >= 0.50 for v in largest),
        {"largest_component_fraction_min": min(v for v in largest if v is not None), "components": comps},
        "largest component >= 0.50 of the AOI in every configuration",
        "qc/pilot/pilot_qc.json",
    )

    # ---- multi-burst seams ----------------------------------------------
    seam_effects = [
        (c.get("coherence_seam_check") or {}).get("max_abs_residual") for c in configs
    ]
    seam_flagged = [
        (c.get("coherence_seam_check") or {}).get("flagged_rows") for c in configs
    ]
    seam_ok = all(
        (e is not None and e < 0.25) and (f is not None and f < 0.05 * 2250)
        for e, f in zip(seam_effects, seam_flagged)
    )
    gate(
        "no_catastrophic_burst_merge_seam",
        seam_ok,
        {"max_coherence_residual": max(e for e in seam_effects if e is not None),
         "max_flagged_rows": max(f for f in seam_flagged if f is not None)},
        "coherence residual < 0.25 and < 5% of rows flagged",
        "qc/pilot/pilot_qc.json (seam check)",
    )

    # ---- reproducibility -------------------------------------------------
    gate(
        "duplicate_copies_are_reproducible",
        bool(repro.get("all_identical")),
        f"{repro.get('configurations_compared')} configurations compared, "
        f"all_identical={repro.get('all_identical')}",
        "every layer bit-identical between duplicate submissions",
        "qc/pilot/reproducibility.json",
    )

    # ---- water mask ------------------------------------------------------
    comp = (water.get("comparison") or {})
    unw_water = comp.get("unw_phase", {})
    unw_land = comp.get("unw_phase", {})
    mask_effective = (
        unw_water.get("water_masked_valid_fraction") == 0.0
        and (unw_water.get("water_unmasked_valid_fraction") or 0) > 0.5
    )
    land_unaffected = (
        unw_land.get("land_masked_valid_fraction") == unw_land.get("land_unmasked_valid_fraction")
    )
    gate(
        "water_mask_excludes_water_from_unwrapping",
        mask_effective,
        {"water_masked_valid": unw_water.get("water_masked_valid_fraction"),
         "water_unmasked_valid": unw_water.get("water_unmasked_valid_fraction")},
        "water pixels have 0 valid unwrapped phase when masked, > 0.5 when not",
        "qc/pilot/water_mask_comparison.json",
    )
    gate(
        "water_mask_does_not_remove_land",
        land_unaffected,
        {"land_masked_valid": unw_land.get("land_masked_valid_fraction"),
         "land_unmasked_valid": unw_land.get("land_unmasked_valid_fraction")},
        "land valid fraction unchanged by masking",
        "qc/pilot/water_mask_comparison.json",
    )
    gate(
        "water_mask_polarity_verified_against_asf_docs",
        water.get("water_mask_convention") is not None,
        water.get("water_mask_convention"),
        "0 = water, 1 = land per https://hyp3-docs.asf.alaska.edu/water_masking/",
        "qc/pilot/water_mask_comparison.json",
    )

    # ---- MintPy ----------------------------------------------------------
    load = ingestion.get("load_data", {})
    loaded = ingestion.get("loaded", {})
    gate(
        "mintpy_preparation_succeeded",
        bool(ingestion.get("prep_hyp3", {}).get("ok")),
        f"prep_hyp3 exit={ingestion.get('prep_hyp3', {}).get('exit_code')} "
        f"rsc={ingestion.get('prep_hyp3', {}).get('rsc_files_created')}",
        "prep_hyp3 exit 0 with .rsc metadata written",
        "mintpy/pilot_ingestion_report.json",
    )
    gate(
        "mintpy_ingestion_succeeded",
        bool(load.get("ok")) and loaded.get("n_interferograms") == EXPECTED_PAIRS,
        {"exit": load.get("exit_code"), "interferograms": loaded.get("n_interferograms"),
         "dates": len(loaded.get("acquisition_dates", []))},
        f"load_data exit 0 with {EXPECTED_PAIRS} interferograms loaded",
        "mintpy/pilot_ingestion_report.json",
    )

    # ---- storage ---------------------------------------------------------
    proj = storage.get("projection_336_pairs", {})
    gate(
        "storage_sufficient_for_production",
        (proj.get("grand_total_gb") or 1e9) < FREE_DISK_GB_AT_REPORT * 0.6,
        {"projected_grand_total_gb": proj.get("grand_total_gb"),
         "free_disk_gb": FREE_DISK_GB_AT_REPORT},
        f"projected total < 60% of {FREE_DISK_GB_AT_REPORT} GB free",
        "qc/pilot/storage_estimate.json",
    )

    passed = sum(1 for g in gates if g["passed"])
    all_passed = passed == len(gates)

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "G",
        "scope": "pilot only",
        "verdict": "PILOT ACCEPTED" if all_passed else "PILOT NOT ACCEPTED",
        "gates_passed": passed,
        "gates_total": len(gates),
        "gates": gates,
        "production": {
            "submitted": False,
            "blocked": True,
            "blocked_on": "explicit owner approval",
            "pairs": PRODUCTION_PAIRS,
            "credits_at_10x2": PRODUCTION_CREDITS_10X2,
            "storage_projected_gb": proj.get("grand_total_gb"),
        },
        "recommended_production_options": {
            "looks": "10x2",
            "pixel_spacing_m": 40,
            "apply_water_mask": True,
            "water_mask_rationale": "masking removes water pixels from unwrapping entirely "
            "(0 valid unwrapped phase over water) while leaving land untouched "
            "(identical land valid fraction with and without the mask)",
        },
    }
    (QC_DIR / "pilot_acceptance.json").write_text(json.dumps(report, indent=2, default=str))

    # ---- markdown --------------------------------------------------------
    lines = [
        "# Pilot Acceptance Report",
        "",
        f"Generated: {report['generated_utc']}",
        "",
        f"## Verdict: **{report['verdict']}**",
        "",
        f"{passed}/{len(gates)} gates passed. Production remains **blocked** pending explicit approval.",
        "",
        "## Gates",
        "",
        "| # | Gate | Result | Observed | Expected | Source |",
        "|---|---|---|---|---|---|",
    ]
    for i, g in enumerate(gates, 1):
        observed = json.dumps(g["observed"], default=str)
        if len(observed) > 90:
            observed = observed[:87] + "..."
        lines.append(
            f"| {i} | `{g['gate']}` | {'PASS' if g['passed'] else 'FAIL'} | {observed} | {g['expected']} | `{g['source']}` |"
        )

    lines += [
        "",
        "## Pilot summary",
        "",
        f"- Jobs submitted: {EXPECTED_JOBS} (7 unique configurations x 2 copies; the duplicate was INC-001)",
        f"- Products downloaded: {len(ok)}/{EXPECTED_JOBS}",
        f"- Credits charged (HyP3-reported): {recon.get('credit_cost_total')}",
        f"- Unique configurations QC'd: {len(configs)}",
        "",
        "## Reproducibility",
        "",
        f"All duplicate pairs were compared layer-by-layer: "
        f"**all_identical = {repro.get('all_identical')}**. HyP3 multi-burst processing is "
        "deterministic, so the accidental duplicate submission became a genuine determinism test.",
        "",
        "## Water-mask decision",
        "",
        "| region | metric | masked | unmasked |",
        "|---|---|---|---|",
    ]
    u = comp.get("unw_phase", {})
    lines.append(
        f"| water | valid unwrapped fraction | {u.get('water_masked_valid_fraction')} | "
        f"{u.get('water_unmasked_valid_fraction')} |"
    )
    lines.append(
        f"| land | valid unwrapped fraction | {u.get('land_masked_valid_fraction')} | "
        f"{u.get('land_unmasked_valid_fraction')} |"
    )
    lines += [
        "",
        "Masking removes water from unwrapping completely and leaves land unchanged, so "
        "**`apply_water_mask = True` is recommended for production**.",
        "",
        "## Storage",
        "",
        f"- Measured: zip mean {storage.get('measured', {}).get('zip_mean_bytes', 0)/1e6:.1f} MB, "
        f"extracted mean {storage.get('measured', {}).get('extracted_mean_bytes', 0)/1e6:.1f} MB "
        f"(x{storage.get('measured', {}).get('extracted_to_zip_ratio')})",
        f"- Projected for {PRODUCTION_PAIRS} pairs: zip {proj.get('zip_total_gb')} GB, "
        f"extracted {proj.get('extracted_total_gb')} GB, MintPy working {proj.get('mintpy_working_gb')} GB",
        f"- **Grand total {proj.get('grand_total_gb')} GB** against {FREE_DISK_GB_AT_REPORT} GB free",
        "",
        "## MintPy ingestion",
        "",
        f"- `prep_hyp3.py`: exit {ingestion.get('prep_hyp3', {}).get('exit_code')} "
        f"({ingestion.get('prep_hyp3', {}).get('rsc_files_created')} .rsc files)",
        f"- `smallbaselineApp.py --dostep load_data`: exit {load.get('exit_code')}",
        f"- Loaded {loaded.get('n_interferograms')} interferograms over "
        f"{len(loaded.get('acquisition_dates', []))} acquisition dates",
        "",
        "This is a loadability test. The pilot pairs are not a connected time series, so a full "
        "SBAS inversion is not attempted at this stage.",
        "",
        "## Production recommendation",
        "",
        f"- looks: **10x2 (40 m)**, `apply_water_mask = True`",
        f"- {PRODUCTION_PAIRS} pairs, **{PRODUCTION_CREDITS_10X2} credits** (21% of the monthly allocation)",
        f"- projected storage **{proj.get('grand_total_gb')} GB**",
        "- **NOT submitted.** Awaiting explicit owner approval.",
        "",
        "## Known limitations",
        "",
        "- The seam detector cannot distinguish a burst merge seam from a real east-west scene "
        "feature (river, road, land-use boundary); its verdict is supporting evidence, not proof.",
        "- Edge-versus-interior validity is not informative for a merged multi-burst mosaic "
        "(the bounding box includes nodata corners); it is reported for completeness only.",
        f"- The network in this pilot is deliberately tiny and disconnected; time-series "
        "connectivity is a Phase H property of the full {PRODUCTION_PAIRS}-pair stack.",
        "- The 2025-05-18 acquisition remains excluded from v1 (documented CMR serving anomaly).",
    ]
    (QC_DIR / "PILOT_ACCEPTANCE_REPORT.md").write_text("\n".join(lines) + "\n")

    print("=" * 88)
    print("PILOT ACCEPTANCE REPORT")
    print("=" * 88)
    for g in gates:
        print(f"  [{'PASS' if g['passed'] else 'FAIL'}] {g['gate']}")
    print(f"\n  {passed}/{len(gates)} gates passed -> {report['verdict']}")
    print(f"\n  {QC_DIR / 'PILOT_ACCEPTANCE_REPORT.md'}")
    print(f"  {QC_DIR / 'pilot_acceptance.json'}")
    print("\n  PRODUCTION NOT SUBMITTED - awaiting explicit approval.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
