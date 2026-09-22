#!/usr/bin/env python
"""
Phase I, stage 3: displacement time series at each hotspot.

For every hotspot the per-date spatial MEDIAN of the LOS displacement is taken
over its pixels. The median rather than the mean, because a hotspot edge can
contain a few unwrapping outliers that a mean would propagate into the whole
series.

Each series is then described, not explained, by three nested models:

  M1  linear                    displacement = a + b*t
  M2  linear + seasonal         adds annual and semi-annual sinusoids
  M3  linear + one step         adds a single offset at the best-fitting date

The purpose is to say whether a hotspot is best described as steady motion, a
seasonal oscillation, or an episodic offset. It is NOT to attribute a cause.
Nothing here identifies groundwater, tectonics, or any other mechanism.

Outputs
-------
qc/sci/phase1/hotspot_timeseries.csv        long format, every hotspot x date
qc/sci/phase1/hotspot_timeseries_summary.csv
qc/sci/phase1/hotspot_timeseries.json

Usage
-----
    python scripts/33_time_series.py [--top 25]
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
OUT_QC = PROJECT_ROOT / "qc" / "sci" / "phase1"

# Descriptive classification thresholds (mm/yr for rates, mm for amplitudes).
SEASONAL_DOMINANT_MM = 3.0
SEASONAL_FRACTION_OF_RATE = 0.30
MIN_RATE_MM_PER_YR = 3.0


def design_linear(t):
    return np.column_stack([np.ones_like(t), t])


def design_seasonal(t):
    w = 2 * np.pi * t
    return np.column_stack([np.ones_like(t), t, np.sin(w), np.cos(w),
                            np.sin(2 * w), np.cos(2 * w)])


def design_step(t, index):
    step = (np.arange(len(t)) >= index).astype(float)
    return np.column_stack([np.ones_like(t), t, step])


def fit(design, y, sigma):
    w = 1.0 / np.maximum(sigma, 1e-9) ** 2
    a = design * np.sqrt(w)[:, None]
    b = y * np.sqrt(w)
    coef, *_ = np.linalg.lstsq(a, b, rcond=None)
    residual = y - design @ coef
    dof = max(1, len(y) - design.shape[1])
    chi2 = float(np.sum(residual ** 2 * w))
    return coef, residual, chi2 / dof


def best_step(t, y, sigma):
    best = None
    for index in range(4, len(t) - 4):
        try:
            coef, residual, red = fit(design_step(t, index), y, sigma)
        except np.linalg.LinAlgError:
            continue
        rss = float(np.sum(residual ** 2))
        if best is None or rss < best[0]:
            best = (rss, index, coef, residual, red)
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    OUT_QC.mkdir(parents=True, exist_ok=True)
    hotspots = pd.read_csv(OUT_QC / "hotspots.csv").head(args.top)
    if hotspots.empty:
        print("No hotspots found; run scripts/32_hotspots.py first.")
        return 1

    with h5py.File(RAW_WORK / "timeseries.h5", "r") as handle:
        dates = np.array(handle["date"]).astype(str)
        length, width = handle["timeseries"].shape[1:]
    with h5py.File(RAW_WORK / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:]
    with h5py.File(GEOMETRY, "r") as handle:
        incidence = handle["incidenceAngle"][:]

    n_dates = len(dates)
    t_years = np.array([int(d[:4]) + (int(d[4:6]) - 1) / 12 + (int(d[6:]) - 1) / 365.25
                        for d in dates])
    t_years = t_years - t_years[0]

    # Rebuild each hotspot's pixel mask from its bounding box and properties by
    # re-reading the detection masks deterministically instead of storing them.
    # The hotspot geometry is reproduced from velocity + coherence + threshold.
    with h5py.File(RAW_WORK / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:]
        ref_y, ref_x = int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"])

    print("=" * 88)
    print("PHASE I - HOTSPOT DISPLACEMENT TIME SERIES  (product_v1 / RAW-336)")
    print("=" * 88)
    print(f"\n  {len(hotspots)} hotspots, {n_dates} dates "
          f"({dates[0]} .. {dates[-1]})")

    # Pixel membership: recompute the connected components exactly as stage 2 did
    # so the masks cannot drift from the reported hotspot table.
    import rasterio.features
    from rasterio.transform import from_origin
    from rasterio.warp import transform_geom
    from shapely.geometry import shape as shp_shape
    from scipy import ndimage

    with h5py.File(GEOMETRY, "r") as handle:
        land = handle["waterMask"][:].astype(bool)
    aoi = shp_shape(json.loads((PROJECT_ROOT / "geometry" / "aoi.geojson").read_text()
                               )["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", aoi.__geo_interface__))
    meta = {}
    with h5py.File(RAW_WORK / "velocity.h5", "r") as handle:
        meta = {k: float(handle.attrs[k]) for k in ("X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP")}
    mask_aoi = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=(length, width),
        transform=from_origin(meta["X_FIRST"], meta["Y_FIRST"],
                              meta["X_STEP"], -meta["Y_STEP"]), invert=True)
    eligible = mask_aoi & land & np.isfinite(velocity) & (coherence >= 0.80)
    thresholded = eligible & (np.abs(velocity.astype("float64") * 1000) >= 10.0)
    labels, n_raw = ndimage.label(thresholded, structure=np.ones((3, 3), dtype=bool))
    sizes = ndimage.sum(thresholded, labels, index=np.arange(1, n_raw + 1))
    keep = np.where(sizes >= 250)[0] + 1

    # Map each hotspot to its component label using the stored centroid.
    label_of = {}
    for _, row in hotspots.iterrows():
        row_i = int(round((row["centroid_y_utm"] - meta["Y_FIRST"]) / meta["Y_STEP"]))
        col_i = int(round((row["centroid_x_utm"] - meta["X_FIRST"]) / meta["X_STEP"]))
        candidate = labels[row_i, col_i]
        if candidate in keep:
            label_of[row["hotspot_id"]] = int(candidate)
        else:
            # Fall back to the nearest kept component centroid.
            best, best_d = None, np.inf
            for lab in keep:
                ys, xs = np.where(labels == lab)
                d = np.hypot(ys.mean() - row_i, xs.mean() - col_i)
                if d < best_d:
                    best, best_d = int(lab), d
            label_of[row["hotspot_id"]] = best
            print(f"  note: {row['hotspot_id']} centroid not inside a kept component; "
                  f"mapped to nearest (distance {best_d * 40 / 1000:.2f} km)")
    for hid, lab in label_of.items():
        membership = int((labels == lab).sum())
        expected = int(hotspots.loc[hotspots["hotspot_id"] == hid, "n_pixels"].iloc[0])
        if membership != expected:
            print(f"  WARNING: {hid} membership {membership} != reported {expected}; skipping")
            label_of[hid] = None

    # ---- one pass over the cube, sampling every hotspot pixel -------------
    pix = {}
    for hid, lab in label_of.items():
        if lab is None:
            continue
        rows, cols = np.where(labels == lab)
        pix[hid] = (rows, cols)
    # Stable control: the highest-coherence, slowest pixels in the AOI.
    stable = eligible & (np.abs(velocity.astype("float64") * 1000) <= 2.0) & (coherence >= 0.97)
    srows, scols = np.where(stable)
    print(f"  stable control pixels (|v|<=2 mm/yr, tc>=0.97): {len(srows):,}")
    if len(srows) > 20000:
        step = len(srows) // 20000
        srows, scols = srows[::step], scols[::step]

    series = {hid: np.full(n_dates, np.nan) for hid in pix}
    spread = {hid: np.full(n_dates, np.nan) for hid in pix}
    control = np.full(n_dates, np.nan)
    print("\n  reading the 119-date cube once ...")
    with h5py.File(RAW_WORK / "timeseries.h5", "r") as handle:
        for i in range(n_dates):
            slab = handle["timeseries"][i, :, :].astype("float32")
            for hid, (rows, cols) in pix.items():
                values = slab[rows, cols] * 1000.0        # mm
                series[hid][i] = np.median(values)
                spread[hid][i] = (np.percentile(values, 75)
                                  - np.percentile(values, 25)) / 2.0
            control[i] = np.median(slab[srows, scols] * 1000.0)
            if (i + 1) % 40 == 0:
                print(f"    {i + 1}/{n_dates} dates")

    # ---- describe each series --------------------------------------------
    control_sigma = float(1.4826 * np.median(np.abs(np.diff(control)
                                                    - np.median(np.diff(control)))))
    print(f"\n  stable-control date-to-date scatter (robust sigma): "
          f"{control_sigma:.3f} mm")

    long_rows, summaries = [], []
    for _, row in hotspots.iterrows():
        hid = row["hotspot_id"]
        if hid not in series or not np.isfinite(series[hid]).all():
            continue
        y = series[hid]
        sigma = np.maximum(spread[hid], control_sigma)
        coef1, res1, red1 = fit(design_linear(t_years), y, sigma)
        coef2, res2, red2 = fit(design_seasonal(t_years), y, sigma)
        step = best_step(t_years, y, sigma)
        rms1 = float(np.sqrt(np.mean(res1 ** 2)))
        rms2 = float(np.sqrt(np.mean(res2 ** 2)))
        rate = float(coef1[1])
        annual = float(np.hypot(coef2[2], coef2[3]))
        semiannual = float(np.hypot(coef2[4], coef2[5]))

        step_mm = step_date = None
        rms3 = np.nan
        if step is not None:
            _, index, coef3, res3, _ = step
            rms3 = float(np.sqrt(np.mean(res3 ** 2)))
            step_mm = float(coef3[2])
            step_date = dates[index]

        # Descriptive classification of the temporal FORM only.
        if rms3 < 0.8 * rms1 and step_mm is not None and abs(step_mm) > 3 * rms1:
            form = "episodic_offset"
        elif abs(rate) < MIN_RATE_MM_PER_YR and annual > SEASONAL_DOMINANT_MM:
            form = "seasonal_dominated"
        elif annual > SEASONAL_FRACTION_OF_RATE * abs(rate):
            form = "linear_with_seasonal"
        else:
            form = "approximately_linear"

        inc = float(np.nanmedian(incidence[labels == label_of[hid]]))
        cos_inc = float(np.cos(np.radians(inc)))
        for i in range(n_dates):
            long_rows.append({"hotspot_id": hid, "date": dates[i],
                              "los_displacement_mm": round(float(y[i]), 3),
                              "los_interquartile_halfwidth_mm": round(float(spread[hid][i]), 3)})
        summaries.append({
            "hotspot_id": hid,
            "area_km2": row["area_km2"],
            "centroid_lon": row["centroid_lon"],
            "centroid_lat": row["centroid_lat"],
            "n_pixels": int(row["n_pixels"]),
            "temporal_coherence_median": row["temporal_coherence_median"],
            "los_velocity_median_field_mm_per_yr": row["los_velocity_median_mm_per_yr"],
            "los_rate_from_series_mm_per_yr": round(rate, 3),
            "los_rate_std_mm_per_yr": round(float(np.sqrt(red1 / max(1e-9, np.sum(
                (t_years - t_years.mean()) ** 2)))), 4),
            "vertical_equivalent_rate_mm_per_yr": round(rate / cos_inc, 3),
            "total_los_displacement_mm": round(float(y[-1] - y[0]), 3),
            "annual_amplitude_mm": round(annual, 3),
            "semiannual_amplitude_mm": round(semiannual, 3),
            "linear_rms_mm": round(rms1, 3),
            "seasonal_rms_mm": round(rms2, 3),
            "step_rms_mm": round(float(rms3), 3) if np.isfinite(rms3) else None,
            "best_step_date": step_date,
            "best_step_mm": round(step_mm, 3) if step_mm is not None else None,
            "temporal_form": form,
            "rms_reduction_seasonal": round(float(1 - rms2 / rms1), 4),
            "rms_reduction_step": round(float(1 - rms3 / rms1), 4) if np.isfinite(rms3) else None,
        })

    frame = pd.DataFrame(summaries)
    pd.DataFrame(long_rows).to_csv(OUT_QC / "hotspot_timeseries.csv", index=False)
    frame.to_csv(OUT_QC / "hotspot_timeseries_summary.csv", index=False)
    # The stable-area control is the common-mode reference: a regional oscillation
    # that appears here as well as at a hotspot is not localised deformation.
    pd.DataFrame({"date": dates, "los_displacement_mm": np.round(control, 4),
                  "n_pixels": len(srows)}).to_csv(
        OUT_QC / "stable_control_timeseries.csv", index=False)

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"freeze": "product_v1",
                   "freeze_id": "2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37"},
        "method": "per-date spatial median over hotspot pixels; nested linear / "
                  "linear+seasonal / linear+step models",
        "date_span": [dates[0], dates[-1]],
        "n_dates": int(n_dates),
        "stable_control_date_to_date_scatter_mm": round(control_sigma, 4),
        "stable_control_total_drift_mm": round(float(control[-1] - control[0]), 3),
        "classification_thresholds": {
            "seasonal_dominant_mm": SEASONAL_DOMINANT_MM,
            "seasonal_fraction_of_rate": SEASONAL_FRACTION_OF_RATE,
            "min_rate_mm_per_yr": MIN_RATE_MM_PER_YR,
        },
        "temporal_form_counts": frame["temporal_form"].value_counts().to_dict(),
        "hotspots": summaries,
        "caveat": "The temporal form is descriptive. A seasonal or episodic shape is "
                  "consistent with many mechanisms and identifies none of them.",
    }
    (OUT_QC / "hotspot_timeseries.json").write_text(json.dumps(payload, indent=2, default=str))

    print(f"\n  temporal form: {payload['temporal_form_counts']}")
    print(f"  stable control drift over the record: "
          f"{payload['stable_control_total_drift_mm']:+.2f} mm")
    print(f"\n  {'id':5s} {'area':>7s} {'rate':>8s} {'std':>6s} {'total':>8s} "
          f"{'annual':>7s} {'rms1':>6s} {'rms2':>6s} {'rms3':>6s}  form")
    for s in summaries:
        print(f"  {s['hotspot_id']:5s} {s['area_km2']:7.2f} "
              f"{s['los_rate_from_series_mm_per_yr']:8.2f} "
              f"{s['los_rate_std_mm_per_yr']:6.2f} "
              f"{s['total_los_displacement_mm']:8.2f} "
              f"{s['annual_amplitude_mm']:7.2f} {s['linear_rms_mm']:6.2f} "
              f"{s['seasonal_rms_mm']:6.2f} "
              f"{(s['step_rms_mm'] if s['step_rms_mm'] is not None else float('nan')):6.2f}  "
              f"{s['temporal_form']}")

    print(f"\n  {OUT_QC / 'hotspot_timeseries.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
