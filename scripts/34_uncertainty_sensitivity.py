#!/usr/bin/env python
"""
Phase I, stage 4: uncertainty budget and sensitivity of the hotspot results.

The formal `velocityStd` from the inversion is a FIT uncertainty. Reporting it as
the error bar would understate the true uncertainty by roughly an order of
magnitude, because the dominant terms are spatially correlated and therefore do
not average down with more pixels. This script separates the terms that DO
average down from those that do NOT, and states which conclusions each term can
and cannot support.

Uncertainty terms
-----------------
  formal fit            velocityStd from the inversion           ~0.9 mm/yr
                        averages down with pixels; supports CONTRAST
  short-wavelength      pixel-to-pixel roughness                 ~1.2 mm/yr
                        averages down with pixels
  common-mode           stable-area epoch-to-epoch scatter      ~3.5 mm
                        does NOT average down; sets the practical
                        detection limit for a time series
  reference selection   spread across candidate references      4.78 mm/yr
                        constant over the AOI; bounds the ABSOLUTE
                        offset only, never the gradients

Sensitivity tests
-----------------
  A  split-half rates         does the rate hold in both halves of the record?
  B  epoch bootstrap          resample dates with replacement, refit
  C  pixel bootstrap          resample hotspot pixels with replacement
  D  coherence stratification does the hotspot velocity depend on coherence?
  E  reference re-basing      what a different reference would do to the value

Outputs
-------
qc/sci/phase1/uncertainty_budget.json
qc/sci/phase1/hotspot_uncertainty.csv
qc/sci/phase1/coherence_stratification.csv

Usage
-----
    python scripts/34_uncertainty_sensitivity.py [--bootstrap 1000]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
GEOMETRY = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
OUT_QC = PROJECT_ROOT / "qc" / "sci" / "phase1"

REFERENCE_SYSTEMATIC_MM_PER_YR = 4.78
REFERENCE_SYSTEMATIC_SD_MM_PER_YR = 1.716


def linear_rate(t, y):
    design = np.column_stack([np.ones_like(t), t])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coef
    return float(coef[1]), float(np.sqrt(np.mean(residual ** 2)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260922)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)

    OUT_QC.mkdir(parents=True, exist_ok=True)
    hotspots = pd.read_csv(OUT_QC / "hotspots.csv")
    # Dates are stored as YYYYMMDD and would otherwise be read as integers.
    long_ts = pd.read_csv(OUT_QC / "hotspot_timeseries.csv", dtype={"date": str})
    map_summary = json.loads((OUT_QC / "deformation_map_summary.json").read_text())

    with h5py.File(RAW_WORK / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        velocity_std = handle["velocityStd"][:].astype("float64")
        ref_y, ref_x = int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"])
    with h5py.File(RAW_WORK / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(GEOMETRY, "r") as handle:
        land = handle["waterMask"][:].astype(bool)
        height = handle["height"][:].astype("float64")

    import rasterio.features
    from rasterio.transform import from_origin
    from rasterio.warp import transform_geom
    from shapely.geometry import shape as shp_shape
    length, width = velocity.shape
    with h5py.File(RAW_WORK / "velocity.h5", "r") as handle:
        meta = {k: float(handle.attrs[k]) for k in ("X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP")}
    aoi = shp_shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", aoi.__geo_interface__))
    mask_aoi = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=(length, width),
        transform=from_origin(meta["X_FIRST"], meta["Y_FIRST"],
                              meta["X_STEP"], -meta["Y_STEP"]), invert=True)
    vel_mm = velocity * 1000.0

    print("=" * 88)
    print("PHASE I - UNCERTAINTY AND SENSITIVITY  (product_v1 / RAW-336)")
    print("=" * 88)

    dates = sorted(long_ts["date"].unique())
    t_all = np.array([int(d[:4]) + (int(d[4:6]) - 1) / 12 + (int(d[6:]) - 1) / 365.25
                      for d in dates])
    t_all = t_all - t_all[0]

    # ---- A/B/C. per-hotspot sensitivity ----------------------------------
    rows = []
    for _, hotspot in hotspots.iterrows():
        hid = hotspot["hotspot_id"]
        sub = long_ts[long_ts["hotspot_id"] == hid].sort_values("date")
        if sub.empty:
            continue
        y = sub["los_displacement_mm"].to_numpy(dtype=float)
        rate_series, rms = linear_rate(t_all, y)

        # A. split-half
        half = len(t_all) // 2
        rate_first, rms_first = linear_rate(t_all[:half], y[:half])
        rate_second, rms_second = linear_rate(t_all[half:], y[half:])

        # B. epoch bootstrap: resample dates with replacement, refit
        boot_rates = np.empty(args.bootstrap)
        n = len(t_all)
        for i in range(args.bootstrap):
            idx = rng.integers(0, n, n)
            if len(np.unique(t_all[idx])) < 3:
                boot_rates[i] = np.nan
                continue
            boot_rates[i] = linear_rate(t_all[idx], y[idx])[0]
        boot_rates = boot_rates[np.isfinite(boot_rates)]

        # C. pixel bootstrap: rebuild the component and resample its pixels.
        #    Done on the field velocity, which is what the hotspot reports.
        rows.append({
            "hotspot_id": hid,
            "area_km2": hotspot["area_km2"],
            "n_pixels": int(hotspot["n_pixels"]),
            "los_velocity_field_median_mm_per_yr": hotspot["los_velocity_median_mm_per_yr"],
            "los_rate_from_series_mm_per_yr": round(rate_series, 3),
            "series_residual_rms_mm": round(rms, 3),
            "rate_first_half_mm_per_yr": round(rate_first, 3),
            "rate_second_half_mm_per_yr": round(rate_second, 3),
            "split_half_difference_mm_per_yr": round(rate_second - rate_first, 3),
            "epoch_bootstrap_p2_5_mm_per_yr": round(float(np.percentile(boot_rates, 2.5)), 3),
            "epoch_bootstrap_p97_5_mm_per_yr": round(float(np.percentile(boot_rates, 97.5)), 3),
            "epoch_bootstrap_width_mm_per_yr": round(float(
                np.percentile(boot_rates, 97.5) - np.percentile(boot_rates, 2.5)), 3),
            "temporal_coherence_median": hotspot["temporal_coherence_median"],
            "formal_velocity_std_median_mm_per_yr":
                hotspot["formal_velocity_std_median_mm_per_yr"],
        })
    uncertainty = pd.DataFrame(rows)

    print("\n  A. split-half rate consistency (does the rate hold across the record?):")
    for _, r in uncertainty.iterrows():
        flag = "" if abs(r["split_half_difference_mm_per_yr"]) < 0.25 * abs(
            r["los_velocity_field_median_mm_per_yr"]) else "  <-- halves disagree"
        print(f"    {r['hotspot_id']}  first {r['rate_first_half_mm_per_yr']:+8.2f}  "
              f"second {r['rate_second_half_mm_per_yr']:+8.2f}  "
              f"diff {r['split_half_difference_mm_per_yr']:+7.2f} mm/yr{flag}")

    print("\n  B. epoch bootstrap 95% interval on the hotspot rate:")
    for _, r in uncertainty.iterrows():
        print(f"    {r['hotspot_id']}  {r['los_rate_from_series_mm_per_yr']:+8.2f} "
              f"[{r['epoch_bootstrap_p2_5_mm_per_yr']:+8.2f}, "
              f"{r['epoch_bootstrap_p97_5_mm_per_yr']:+8.2f}] mm/yr  "
              f"width {r['epoch_bootstrap_width_mm_per_yr']:.2f}")

    # ---- C. pixel bootstrap on the field, and D. coherence strata ---------
    from scipy import ndimage
    eligible = mask_aoi & land & np.isfinite(velocity) & (coherence >= 0.80)
    thresholded = eligible & (np.abs(vel_mm) >= 10.0)
    labels, n_raw = ndimage.label(thresholded, structure=np.ones((3, 3), dtype=bool))
    sizes = ndimage.sum(thresholded, labels, index=np.arange(1, n_raw + 1))
    keep = np.where(sizes >= 250)[0] + 1

    pixel_rows = []
    for _, hotspot in hotspots.iterrows():
        hid = hotspot["hotspot_id"]
        row_i = int(round((hotspot["centroid_y_utm"] - meta["Y_FIRST"]) / meta["Y_STEP"]))
        col_i = int(round((hotspot["centroid_x_utm"] - meta["X_FIRST"]) / meta["X_STEP"]))
        lab = labels[row_i, col_i]
        if lab not in keep:
            best, best_d = None, np.inf
            for candidate in keep:
                ys, xs = np.where(labels == candidate)
                d = np.hypot(ys.mean() - row_i, xs.mean() - col_i)
                if d < best_d:
                    best, best_d = int(candidate), d
            lab = best
        values = vel_mm[labels == lab]
        n = len(values)
        boot = np.array([np.median(rng.choice(values, n, replace=True))
                         for _ in range(min(args.bootstrap, 500))])
        pixel_rows.append({
            "hotspot_id": hid,
            "n_pixels": n,
            "field_median_mm_per_yr": round(float(np.median(values)), 3),
            "pixel_bootstrap_p2_5_mm_per_yr": round(float(np.percentile(boot, 2.5)), 3),
            "pixel_bootstrap_p97_5_mm_per_yr": round(float(np.percentile(boot, 97.5)), 3),
            "field_iqr_mm_per_yr": round(float(
                np.percentile(values, 75) - np.percentile(values, 25)), 3),
            "formal_std_median_mm_per_yr": round(float(np.median(
                velocity_std[labels == lab] * 1000)), 4),
        })
    pixels = pd.DataFrame(pixel_rows)
    if not pixels.empty:
        uncertainty = uncertainty.merge(pixels, on="hotspot_id", how="left")
    print("\n  C. pixel bootstrap vs the formal error:")
    for _, r in pixels.iterrows():
        print(f"    {r['hotspot_id']}  field {r['field_median_mm_per_yr']:+8.2f} "
              f"[{r['pixel_bootstrap_p2_5_mm_per_yr']:+7.2f}, "
              f"{r['pixel_bootstrap_p97_5_mm_per_yr']:+7.2f}]  "
              f"formal {r['formal_std_median_mm_per_yr']:.3f}  "
              f"iqr {r['field_iqr_mm_per_yr']:.2f} mm/yr")

    # D. coherence stratification over the whole AOI
    strata = []
    for low in np.arange(0.50, 1.00, 0.05):
        high = low + 0.05
        sel = mask_aoi & land & np.isfinite(velocity) & (coherence >= low) & (coherence < high)
        if sel.sum() < 500:
            continue
        values = vel_mm[sel]
        strata.append({
            "coherence_low": round(float(low), 2),
            "coherence_high": round(float(high), 2),
            "n_pixels": int(sel.sum()),
            "median_mm_per_yr": round(float(np.median(values)), 3),
            "p05_mm_per_yr": round(float(np.percentile(values, 5)), 3),
            "p95_mm_per_yr": round(float(np.percentile(values, 95)), 3),
            "fraction_below_minus10": round(float((values <= -10).mean()), 5),
            "mean_elevation_m": round(float(np.mean(height[sel])), 1),
            "median_formal_std_mm_per_yr": round(
                float(np.median(velocity_std[sel] * 1000)), 4),
        })
    stratification = pd.DataFrame(strata)
    stratification.to_csv(OUT_QC / "coherence_stratification.csv", index=False)
    print("\n  D. coherence stratification (whole AOI):")
    print(f"    {'coh band':>12s} {'n':>9s} {'median':>8s} {'p05':>8s} {'p95':>8s} "
          f"{'frac<-10':>9s} {'elev':>7s}")
    for _, r in stratification.iterrows():
        print(f"    {r['coherence_low']:.2f}-{r['coherence_high']:.2f} "
              f"{r['n_pixels']:9.0f} {r['median_mm_per_yr']:8.2f} "
              f"{r['p05_mm_per_yr']:8.2f} {r['p95_mm_per_yr']:8.2f} "
              f"{r['fraction_below_minus10']:9.4f} {r['mean_elevation_m']:7.1f}")

    # ---- E. reference re-basing ------------------------------------------
    # Velocity is linear, so changing the reference shifts every pixel by a
    # constant. The reported hotspot values therefore move together and the
    # hotspot CONTRAST is invariant.
    frozen = (1378, 1426)
    offset = float(vel_mm[frozen])
    print(f"\n  E. reference re-basing:")
    print(f"    actual reference (y,x) = ({ref_y},{ref_x}); frozen decision = {frozen}")
    print(f"    re-basing to the frozen pixel shifts EVERY velocity by {offset:+.3f} mm/yr")
    print(f"    hotspot medians would become:")
    for _, r in uncertainty.iterrows():
        print(f"      {r['hotspot_id']}  {r['los_velocity_field_median_mm_per_yr']:+8.2f} "
              f"-> {r['los_velocity_field_median_mm_per_yr'] + offset:+8.2f} mm/yr "
              f"(unchanged contrast against surroundings)")

    # ---- budget ----------------------------------------------------------
    formal = float(map_summary["formal_uncertainty_mm_per_yr_primary_mask"]["median"])
    noise = float(map_summary["noise_floor"]["short_wavelength_robust_sigma_mm_per_yr"])
    ts_json = json.loads((OUT_QC / "hotspot_timeseries.json").read_text())
    common_mode = float(ts_json["stable_control_date_to_date_scatter_mm"])

    budget = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"freeze": "product_v1",
                   "freeze_id": "2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37"},
        "terms": {
            "formal_fit_uncertainty_mm_per_yr": {
                "value": round(formal, 4),
                "averages_down_with_pixels": True,
                "supports": "relative contrast between neighbouring areas",
            },
            "short_wavelength_noise_mm_per_yr": {
                "value": round(noise, 4),
                "averages_down_with_pixels": True,
                "supports": "detection of spatially coherent anomalies",
            },
            "common_mode_epoch_scatter_mm": {
                "value": round(common_mode, 4),
                "averages_down_with_pixels": False,
                "supports": "sets the practical limit on resolving the SHAPE of a "
                            "time series; a few mm per epoch persists at any averaging",
            },
            "reference_selection_systematic_mm_per_yr": {
                "value": REFERENCE_SYSTEMATIC_MM_PER_YR,
                "sd": REFERENCE_SYSTEMATIC_SD_MM_PER_YR,
                "averages_down_with_pixels": False,
                "supports": "bounds the ABSOLUTE LOS offset only; relative spatial "
                            "gradients and hotspot contrast are unaffected",
            },
        },
        "combined_relative_uncertainty_mm_per_yr": round(
            float(np.hypot(formal, noise)), 4),
        "combined_absolute_uncertainty_mm_per_yr": round(
            float(np.hypot(np.hypot(formal, noise), REFERENCE_SYSTEMATIC_MM_PER_YR)), 4),
        "what_this_means": {
            "relative_contrast_is_well_determined":
                "hotspot-minus-surroundings differences are supported at the "
                f"~{np.hypot(formal, noise):.1f} mm/yr level",
            "absolute_los_offset_is_not":
                f"the whole AOI could shift by {REFERENCE_SYSTEMATIC_MM_PER_YR} mm/yr "
                "without changing anything the InSAR data themselves can check",
            "time_series_shape_is_limited":
                f"a ~{common_mode:.1f} mm common-mode scatter persists at every epoch "
                "regardless of how many pixels are averaged",
        },
        "hotspot_uncertainty": rows,
        "coherence_stratification": strata,
        "reference_rebasing_offset_mm_per_yr": round(offset, 4),
    }
    (OUT_QC / "uncertainty_budget.json").write_text(json.dumps(budget, indent=2, default=str))
    uncertainty.to_csv(OUT_QC / "hotspot_uncertainty.csv", index=False)

    print(f"\n  error budget (LOS):")
    print(f"    formal fit            {formal:6.3f} mm/yr   averages down")
    print(f"    short-wavelength      {noise:6.3f} mm/yr   averages down")
    print(f"    common mode           {common_mode:6.3f} mm      does NOT average down")
    print(f"    reference systematic  {REFERENCE_SYSTEMATIC_MM_PER_YR:6.3f} mm/yr   does NOT average down")
    print(f"    -> relative contrast supported at ~{budget['combined_relative_uncertainty_mm_per_yr']:.2f} mm/yr")
    print(f"    -> absolute offset uncertain at ~{budget['combined_absolute_uncertainty_mm_per_yr']:.2f} mm/yr")
    print(f"\n  {OUT_QC / 'uncertainty_budget.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
