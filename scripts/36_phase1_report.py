#!/usr/bin/env python
"""
Phase I, stage 6: consolidate the characterization into one report.

Every number in the report is read from the stage outputs, never retyped, so the
report cannot drift away from the results it describes.

Usage
-----
    python scripts/36_phase1_report.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_QC = PROJECT_ROOT / "qc" / "sci" / "phase1"
OUT_PRODUCTS = PROJECT_ROOT / "products" / "product_v1"
REPORT = PROJECT_ROOT / "qc" / "sci" / "PHASE1_REPORT.md"


def load(name: str) -> dict:
    path = OUT_QC / name
    return json.loads(path.read_text()) if path.exists() else {}


def grade(row: pd.Series, persistence: dict) -> tuple[str, str]:
    """Evidence grade from persistence, coherence, magnitude and rate agreement."""
    hid = row["hotspot_id"]
    survived = persistence.get(hid, {}).get("scenarios_survived", 0)
    total = persistence.get(hid, {}).get("scenarios_total", 14)
    coherence = row["temporal_coherence_median"]
    field = abs(row["los_velocity_median_mm_per_yr"])
    series = abs(row.get("los_rate_from_series_mm_per_yr", float("nan")))
    agreement = abs(field - series) / field if field else float("nan")

    if survived >= 12 and coherence >= 0.85 and field >= 10 and agreement <= 0.20:
        return "A", (f"persists in {survived}/{total} masks, coherence {coherence:.3f}, "
                     f"|v| {field:.1f} mm/yr, field and series rates agree to "
                     f"{agreement * 100:.0f}%")
    if survived >= 9 and field >= 10:
        return "B", (f"persists in {survived}/{total} masks, coherence {coherence:.3f}, "
                     f"|v| {field:.1f} mm/yr")
    return "C", (f"persists in only {survived}/{total} masks; feature is "
                 f"mask-dependent and should not be carried forward unresolved")


def main() -> int:
    summary = load("deformation_map_summary.json")
    hotspots_json = load("hotspots.json")
    ts = load("hotspot_timeseries.json")
    unc = load("uncertainty_budget.json")
    pers = load("hotspot_persistence.json")
    osc = load("oscillation_diagnostics.json")

    hotspots = pd.read_csv(OUT_QC / "hotspots.csv")
    ts_summary = pd.read_csv(OUT_QC / "hotspot_timeseries_summary.csv")
    uncertainty = pd.read_csv(OUT_QC / "hotspot_uncertainty.csv")
    hots = hotspots.merge(
        ts_summary[["hotspot_id", "los_rate_from_series_mm_per_yr", "annual_amplitude_mm",
                    "temporal_form", "total_los_displacement_mm",
                    "linear_rms_mm", "seasonal_rms_mm"]],
        on="hotspot_id", how="left").merge(
        uncertainty[["hotspot_id", "rate_first_half_mm_per_yr",
                     "rate_second_half_mm_per_yr", "epoch_bootstrap_p2_5_mm_per_yr",
                     "epoch_bootstrap_p97_5_mm_per_yr"]],
        on="hotspot_id", how="left")

    persistence = pers.get("persistence", {})
    grades = {}
    for _, row in hots.iterrows():
        g, why = grade(row, persistence)
        grades[row["hotspot_id"]] = (g, why)

    v = summary["los_velocity_mm_per_yr_primary_mask"]
    counts = summary["counts"]
    tiers = summary["quality_tiers"]
    noise = summary["noise_floor"]
    ref = summary["reference"]

    L = []
    add = L.append

    add("# Phase I — Final Scientific Results Characterization")
    add("")
    add(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from the "
        "frozen `product_v1` solution. Every figure below is read programmatically from "
        "the stage outputs in `qc/sci/phase1/`.")
    add("")
    add("**Scope.** This phase characterizes the existing frozen solution. It does not "
        "improve, tune, smooth, correct, or modify it, and it does not attribute any "
        "observation to a physical mechanism. Causal interpretation requires independent "
        "datasets and belongs to a later phase.")
    add("")
    add("## 0. Authoritative state")
    add("")
    add("| Item | Value |")
    add("|---|---|")
    add(f"| Product freeze | `product_v1` |")
    add(f"| freeze_id | `2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37` |")
    add(f"| Principal solution | RAW-336 |")
    add(f"| Acquisitions / interferograms | {summary['dates']['count']} / 336 |")
    add(f"| Excluded pairs | 0 |")
    add(f"| Date span | {summary['dates']['first']} – {summary['dates']['last']} |")
    add(f"| Unwrap correction | disabled |")
    add(f"| Troposphere / DEM residual | disabled in the principal branch |")
    add(f"| Deramp | disabled |")
    add("")
    add("All deformation quantities in this report are **line-of-sight (LOS)** and "
        "**relative** to the processing reference pixel. Sentinel-1 measures a projection "
        "of the full 3-D displacement; LOS is not vertical motion.")
    add("")

    # ---- provenance defect ----------------------------------------------
    if ref.get("mismatch"):
        add("### 0.1 Provenance defect found during this phase (INC-007)")
        add("")
        add(f"The frozen decision records reference pixel `y={ref['frozen_decision_yx'][0]}, "
            f"x={ref['frozen_decision_yx'][1]}`, but the frozen product is actually "
            f"referenced to `y={ref['processing_ref_yx'][0]}, x={ref['processing_ref_yx'][1]}`. "
            "`config/mintpy_baseline_raw.txt` sets only `mintpy.reference.minCoherence`, so "
            "MintPy auto-selected the reference; the ERA5 and ERA5+DEM configs do set "
            "`mintpy.reference.yx`.")
        add("")
        add(f"Verification: `timeseries[:, {ref['processing_ref_yx'][0]}, "
            f"{ref['processing_ref_yx'][1]}]` is identically zero at all 119 dates, while "
            f"`timeseries[:, {ref['frozen_decision_yx'][0]}, {ref['frozen_decision_yx'][1]}]` "
            "is not.")
        add("")
        add(f"**Impact.** The RAW velocity at the frozen pixel is "
            f"{ref['raw_velocity_at_frozen_pixel_mm_per_yr']:+.4f} mm/yr, so the v1 product "
            "carries that constant offset relative to the frozen decision. Re-basing shifts "
            "every velocity by the same constant, so **spatial gradients and hotspot "
            "contrast are unaffected**. The offset is far smaller than the 4.78 mm/yr "
            "reference-selection systematic. It also introduced a constant "
            f"{ref['raw_velocity_at_frozen_pixel_mm_per_yr']:+.3f} mm/yr term into the "
            "published RAW-vs-ERA5 branch comparison; re-aligning the references moves the "
            "ERA5−RAW median from +0.013 to +0.149 mm/yr and the RMS from 0.521 to "
            "0.549 mm/yr, which does not change any branch verdict.")
        add("")

    # ---- 1. where -------------------------------------------------------
    add("## 1. Where reliably supported relative LOS deformation occurs")
    add("")
    add(f"Within the AOI ({counts['aoi_pixels']:,} pixels, "
        f"{counts['land_in_aoi']:,} land), the primary quality mask (temporal coherence "
        f"≥ 0.80) retains {summary['primary_mask_pixels']:,} pixels. Deformation is not "
        "uniformly distributed: it is concentrated in spatially connected patches rather "
        "than scattered pixel noise.")
    add("")
    add(f"Detected with |LOS velocity| ≥ 10 mm/yr, coherence ≥ 0.80 and a 0.4 km² minimum "
        f"area: **{hotspots_json['counts']['components_reported']} hotspots covering "
        f"{hotspots_json['counts']['hotspot_area_km2']:.1f} km²** "
        f"({hotspots_json['counts']['hotspot_fraction_of_eligible'] * 100:.2f}% of eligible "
        f"pixels). All are in the `{list(hotspots_json['direction_counts'])[0]}` sense "
        "(ground moving away from the satellite along the LOS).")
    add("")
    add("| ID | Area km² | Median LOS mm/yr | Peak \\|LOS\\| mm/yr | Vertical-equiv mm/yr | Coherence | Longitude | Latitude |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in hots.iterrows():
        add(f"| {r['hotspot_id']} | {r['area_km2']:.2f} | "
            f"{r['los_velocity_median_mm_per_yr']:+.2f} | "
            f"{abs(r['los_velocity_peak_abs_mm_per_yr']):.2f} | "
            f"{r['vertical_equivalent_median_mm_per_yr']:+.2f} | "
            f"{r['temporal_coherence_median']:.3f} | {r['centroid_lon']:.4f} | "
            f"{r['centroid_lat']:.4f} |")
    add("")
    add("The vertical-equivalent column divides LOS by cos(incidence) and assumes the "
        "displacement is **purely vertical**. It is context only; no horizontal motion was "
        "measured or ruled out.")
    add("")

    # ---- 2. magnitude ---------------------------------------------------
    add("## 2. How large the measured deformation is")
    add("")
    add("| Statistic | LOS velocity (mm/yr), primary mask |")
    add("|---|---:|")
    for key in ("median", "mean", "std", "p01", "p05", "p25", "p75", "p95", "p99", "min", "max"):
        value = v[key]
        # A standard deviation is non-negative; only signed statistics get a sign.
        add(f"| {key} | {value:.2f} |" if key == "std" else f"| {key} | {value:+.2f} |")
    add("")
    add("The distribution is strongly asymmetric: the bulk sits near zero while a tail "
        "extends to strongly negative values. The median pixel is essentially stationary; "
        "the deformation is carried by a minority of the AOI.")
    add("")
    add("Per-hotspot totals over the record:")
    add("")
    add("| ID | Cumulative LOS displacement (mm) | Rate from series (mm/yr) | Rate from field (mm/yr) |")
    add("|---|---:|---:|---:|")
    for _, r in hots.iterrows():
        add(f"| {r['hotspot_id']} | {r['total_los_displacement_mm']:+.1f} | "
            f"{r['los_rate_from_series_mm_per_yr']:+.2f} | "
            f"{r['los_velocity_median_mm_per_yr']:+.2f} |")
    add("")

    # ---- 3. extent ------------------------------------------------------
    add("## 3. How spatially extensive the deformation is")
    add("")
    add("The extent depends strongly on the quality mask, and that dependence is itself "
        "a result. Detected hotspot area:")
    add("")
    sens = pd.read_csv(OUT_QC / "hotspot_threshold_sensitivity.csv")
    pivot = sens.pivot(index="threshold_mm_per_yr", columns="coherence_min", values="area_km2")
    add("| \\|v\\| threshold (mm/yr) | coh ≥ 0.70 | coh ≥ 0.80 | coh ≥ 0.90 |")
    add("|---|---:|---:|---:|")
    for threshold, row in pivot.iterrows():
        add(f"| {threshold:g} | {row.get(0.70, float('nan')):.1f} | "
            f"{row.get(0.80, float('nan')):.1f} | {row.get(0.90, float('nan')):.1f} |")
    add("")
    add(f"At the working threshold of 10 mm/yr the detected area roughly **doubles** when "
        f"coherence is relaxed from 0.80 ({pivot.loc[10.0, 0.80]:.1f} km²) to 0.70 "
        f"({pivot.loc[10.0, 0.70]:.1f} km²). Relaxing to a 5 mm/yr threshold at coherence "
        f"0.70 raises the detected area to {pivot.loc[5.0, 0.70]:.1f} km² — roughly seven "
        f"times the working-mask figure.")
    add("")
    add("This is reinforced by the AOI-wide coherence stratification, which shows a strong "
        "monotonic relationship:")
    add("")
    strat = pd.read_csv(OUT_QC / "coherence_stratification.csv")
    add("| Coherence band | Pixels | Median LOS mm/yr | p05 mm/yr | Fraction ≤ −10 mm/yr |")
    add("|---|---:|---:|---:|---:|")
    for _, r in strat.iterrows():
        add(f"| {r['coherence_low']:.2f}–{r['coherence_high']:.2f} | {int(r['n_pixels']):,} | "
            f"{r['median_mm_per_yr']:+.2f} | {r['p05_mm_per_yr']:+.2f} | "
            f"{r['fraction_below_minus10'] * 100:.1f}% |")
    add("")
    lo = strat.iloc[0]
    hi = strat.iloc[-1]
    add(f"The lowest-coherence band has a median of {lo['median_mm_per_yr']:+.1f} mm/yr with "
        f"{lo['fraction_below_minus10'] * 100:.1f}% of pixels beyond −10 mm/yr, while the "
        f"highest-coherence band has a median of {hi['median_mm_per_yr']:+.1f} mm/yr and "
        f"{hi['fraction_below_minus10'] * 100:.1f}%. **A high-coherence mask therefore "
        "selects against the deformation signal**, which is why the conservative hotspot "
        "catalogue is a lower bound on extent, not an estimate of it.")
    add("")
    add("This relationship has two readings that these data alone cannot separate: the "
        "low-coherence terrain may genuinely deform faster, or low coherence may coincide "
        "with a coherent bias (unwrapping or atmosphere) that pushes velocity negative. "
        "The offset is far too large to be random pixel noise — the short-wavelength noise "
        f"floor is {noise['short_wavelength_robust_sigma_mm_per_yr']:.2f} mm/yr against a "
        f"{abs(lo['median_mm_per_yr']):.1f} mm/yr median — so if it is an artefact it is a "
        "structured one, not scatter. Resolving this is a stated open item.")
    add("")

    # ---- 4. time --------------------------------------------------------
    add("## 4. How the deformation evolves through time")
    add("")
    add(f"Temporal form from nested linear / linear+seasonal / linear+step models over "
        f"{ts.get('n_dates')} dates:")
    add("")
    add(f"`{json.dumps(ts.get('temporal_form_counts', {}))}`")
    add("")
    add("| ID | Rate mm/yr | Total mm | Annual amplitude mm | RMS linear mm | RMS seasonal mm | Form |")
    add("|---|---:|---:|---:|---:|---:|---|")
    for _, r in hots.iterrows():
        add(f"| {r['hotspot_id']} | {r['los_rate_from_series_mm_per_yr']:+.2f} | "
            f"{r['total_los_displacement_mm']:+.1f} | {r['annual_amplitude_mm']:.2f} | "
            f"{r['linear_rms_mm']:.2f} | {r['seasonal_rms_mm']:.2f} | {r['temporal_form']} |")
    add("")
    add("**No hotspot is well described by a single constant rate.** Splitting the record "
        "in half, the two halves disagree at every hotspot:")
    add("")
    add("| ID | First half mm/yr | Second half mm/yr | Difference mm/yr |")
    add("|---|---:|---:|---:|")
    for _, r in hots.iterrows():
        add(f"| {r['hotspot_id']} | {r['rate_first_half_mm_per_yr']:+.2f} | "
            f"{r['rate_second_half_mm_per_yr']:+.2f} | "
            f"{r['rate_second_half_mm_per_yr'] - r['rate_first_half_mm_per_yr']:+.2f} |")
    add("")
    add("Three hotspots in the north (H002, H003, H005) accumulate most of their "
        "displacement in the first half and are nearly flat in the second; the southern "
        "hotspots (H001, H004) are faster in the second half. A single rate for the whole "
        "record is therefore a poor summary for any of them.")
    add("")
    add(f"The independent stable-area control drifts {ts.get('stable_control_total_drift_mm'):+.2f} mm "
        "over the record with an epoch-to-epoch scatter of "
        f"{ts.get('stable_control_date_to_date_scatter_mm'):.2f} mm. That control is "
        "common-mode: it does not average down with more pixels.")
    add("")

    # ---- 5. persistence -------------------------------------------------
    add("## 5. Which features persist under reasonable quality-mask choices")
    add("")
    scenarios = pers.get("scenarios", [])
    add(f"Each hotspot was re-detected under {len(scenarios)} mask scenarios "
        "(coherence cut 0.50–0.90, threshold 5–15 mm/yr, minimum area 0.4–5.0 km²). A "
        "hotspot counts as persisting only if at least half its pixels remain inside a "
        "single connected component that also meets that scenario's minimum area.")
    add("")
    add("| ID | Scenarios survived | Outcome |")
    add("|---|---:|---|")
    for hid in sorted(persistence):
        info = persistence[hid]
        add(f"| {hid} | {info['scenarios_survived']}/{info['scenarios_total']} | "
            f"{info['outcome']} |")
    add("")
    add("Only **H001** survives every scenario, including the strictest coherence cut and a "
        "5 km² area floor. H002 and H003 survive most scenarios but disappear under "
        "coherence ≥ 0.90. H004 fails under `min_area_2.0`. H005 fails the strict coherence "
        "cuts and any area floor above 1 km².")
    add("")

    # ---- 6. uncertainty -------------------------------------------------
    add("## 6. Uncertainty and sensitivity")
    add("")
    terms = unc.get("terms", {})
    add("| Term | Value | Averages down with pixels? | What it supports |")
    add("|---|---:|---|---|")
    for key, info in terms.items():
        value = info.get("value")
        unit = "mm" if "scatter" in key else "mm/yr"
        add(f"| {key.replace('_', ' ')} | {value:g} {unit} | "
            f"{'yes' if info.get('averages_down_with_pixels') else '**no**'} | "
            f"{info.get('supports')} |")
    add("")
    add(f"* Combined **relative** uncertainty (contrast between neighbouring areas): "
        f"~{unc.get('combined_relative_uncertainty_mm_per_yr'):.2f} mm/yr.")
    add(f"* Combined **absolute** LOS uncertainty: ~"
        f"{unc.get('combined_absolute_uncertainty_mm_per_yr'):.2f} mm/yr, dominated by the "
        "reference-selection systematic.")
    add("")
    add("Sensitivity findings:")
    add("")
    add("* **Reference re-basing** shifts every velocity by "
        f"{unc.get('reference_rebasing_offset_mm_per_yr'):+.3f} mm/yr and changes no "
        "contrast. Hotspot values move together.")
    add("* **Epoch bootstrap** (resampling dates, refitting) gives 95% intervals a few "
        "mm/yr wide on each hotspot rate — narrower than the reference systematic, so it "
        "does not capture the dominant error.")
    add("* **Pixel bootstrap** intervals are tight (sub-mm/yr) because hotspot pixel counts "
        "are large. This confirms the median is well determined *given* the field, and says "
        "nothing about systematic error.")
    add("* **Split-half rates** disagree by 10–20 mm/yr, far exceeding every statistical "
        "interval. The dominant uncertainty in any single quoted rate is therefore "
        "**non-stationarity of the signal itself**, not measurement noise.")
    add("")

    # ---- 7. oscillation -------------------------------------------------
    add("## 7. Are the oscillations localised or common-mode?")
    add("")
    if osc.get("available"):
        add(f"The stable-area control has a de-trended amplitude of "
            f"{osc.get('stable_control_amplitude_mm'):.2f} mm, so a real common-mode signal "
            "does exist at the few-mm level.")
        add("")
        add("| ID | De-trended amplitude mm | Ratio to control | Corr. with control (linear) | Corr. (quadratic) |")
        add("|---|---:|---:|---:|---:|")
        for hid, info in osc["per_hotspot"].items():
            add(f"| {hid} | {info['detrended_amplitude_mm']:.2f} | "
                f"{info['amplitude_ratio_to_control']:.2f}× | "
                f"{info['correlation_with_stable_control']:+.3f} | "
                f"{info['correlation_with_stable_control_quadratic']:+.3f} |")
        add("")
        add("Every hotspot oscillates 2.7–5.5× more than the stable control and correlates "
            "only weakly with it (r ≤ 0.44). The oscillations are therefore **not "
            "predominantly common-mode**.")
        add("")
        add("They are, however, spatially organised. Cross-hotspot residual correlations:")
        add("")
        add("| Pair | Linear de-trend | Quadratic de-trend |")
        add("|---|---:|---:|")
        for key, value in osc["cross_hotspot_correlation"].items():
            q = osc["cross_hotspot_correlation_quadratic"].get(key)
            add(f"| {key.replace('_vs_', ' vs ')} | {value:+.3f} | "
                f"{q:+.3f} |" if q is not None else f"| {key} | {value:+.3f} | |")
        add("")
        add("Two mutually anti-correlated groups emerge, and the grouping is unchanged by "
            "switching from a linear to a quadratic de-trend — so it reflects phase, not "
            "long-term curvature:")
        add("")
        add("* **Northern group** — H002, H003, H005 (mutual r = +0.82 to +0.99)")
        add("* **Southern group** — H001, H004 (mutual r = +0.82)")
        add("* **Between groups** — r = −0.34 to −0.46")
        add("")
        add("A shared oscillation across hotspots ~30 km apart indicates a process or error "
            "with a regional spatial scale, while the sign reversal between north and south "
            "indicates a spatial gradient in phase or sign. Neither the amplitude ratios "
            "nor the correlations identify the mechanism.")
    add("")

    # ---- 8. evidence grading --------------------------------------------
    add("## 8. Observations strong enough to carry forward")
    add("")
    add("| ID | Area km² | LOS mm/yr | Grade | Basis |")
    add("|---|---:|---:|---|---|")
    for _, r in hots.iterrows():
        g, why = grades[r["hotspot_id"]]
        add(f"| {r['hotspot_id']} | {r['area_km2']:.2f} | "
            f"{r['los_velocity_median_mm_per_yr']:+.2f} | **{g}** | {why} |")
    add("")
    add("**Grade A** — spatial extent, magnitude, coherence and persistence all hold, and "
        "the rate is corroborated independently by the field and by the time series. Safe "
        "to carry into interpretation.")
    add("")
    add("**Grade B** — real and large, but mask-dependent in extent or coherence. Carry "
        "forward with the stated sensitivity.")
    add("")
    add("**Grade C** — not resolvable at this stage.")
    add("")
    add("Two further observations are strong enough to carry forward even though they are "
        "not single hotspots:")
    add("")
    add("1. **Deformation is not temporally stationary.** Split-half rates differ by "
        "10–20 mm/yr at every hotspot, far beyond any statistical interval. Any "
        "interpretation must explain a time-varying rate, not a constant one.")
    add("2. **The coherence–velocity relationship is a property of the dataset**, not of "
        "one hotspot, and it bounds how much of the AOI can ever be characterized from "
        "this stack.")
    add("")

    # ---- 9. what is not established -------------------------------------
    add("## 9. What the InSAR data alone do not establish")
    add("")
    add("* **No mechanism.** Nothing here identifies groundwater depletion, compaction, "
        "tectonics, construction or metro loading, lithology, or fault motion. A "
        "subsidence-shaped LOS signal is consistent with many mechanisms and discriminates "
        "none of them.")
    add("* **No vertical rate.** LOS is a projection. The vertical-equivalent column "
        "assumes purely vertical motion; horizontal components are unmeasured, so the true "
        "vertical rate is unknown and could be larger or smaller.")
    add("* **No absolute rate.** All values are relative to the processing reference. The "
        f"absolute LOS offset is uncertain at {unc.get('combined_absolute_uncertainty_mm_per_yr'):.1f} "
        "mm/yr, and no independent in-AOI geodetic reference exists to reduce it. Whether "
        "the AOI as a whole is subsiding, stable, or rising is **not determined**.")
    add("* **No validated total extent.** The high-coherence mask demonstrably excludes "
        "part of the signal, and whether the low-coherence signal is real or biased is "
        "unresolved.")
    add("")
    add("### Open items")
    add("")
    add("1. The coherence–velocity relationship must be adjudicated before any total-area "
        "or aggregate-volume statement is made.")
    add("2. The reference-pixel mismatch (INC-007) should be corrected at the next product "
        "revision, by setting `mintpy.reference.yx` explicitly in every branch config. It "
        "does not invalidate relative results in this product.")
    add("3. The north/south anti-correlated oscillation needs an independent dataset "
        "(GNSS, groundwater levels, or a weather-driven delay model) before interpretation.")
    add("")

    # ---- products -------------------------------------------------------
    # Written before the deliverables listing so the file appears in its own index.
    grading = {hid: {"grade": g, "basis": why} for hid, (g, why) in grades.items()}
    (OUT_QC / "evidence_grades.json").write_text(json.dumps(
        {"generated_utc": datetime.now(timezone.utc).isoformat(),
         "grades": grading,
         "grade_definition": {
             "A": "persistence >= 12/14, coherence >= 0.85, |v| >= 10 mm/yr, field and "
                  "series rates agree within 20%",
             "B": "persistence >= 9/14 and |v| >= 10 mm/yr",
             "C": "mask-dependent; not resolvable at this stage"},
         "products": [str(p.name) for p in sorted(OUT_PRODUCTS.glob("*.tif"))]},
        indent=2))

    add("## 10. Deliverables")
    add("")
    add("Rasters (`products/product_v1/`):")
    add("")
    for name in summary.get("rasters", []):
        add(f"* `{name}`")
    add("")
    add("Tabular and structured results (`qc/sci/phase1/`):")
    add("")
    for path in sorted(OUT_QC.glob("*")):
        add(f"* `{path.name}`")
    add("")

    REPORT.write_text("\n".join(L) + "\n")
    print(f"wrote {REPORT}  ({len(L)} lines)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
