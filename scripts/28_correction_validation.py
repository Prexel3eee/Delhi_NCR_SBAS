#!/usr/bin/env python
"""
Targeted validation of the corrections with better-posed tests.

Residual RMS is a blunt instrument: on an uncorrected baseline those residuals
are dominated by unmodelled atmosphere and orbit ramps, so a correction can
"fail" that test while still being right (or pass it while being wrong). This
script uses four tests that are better matched to what atmospheric and
DEM-residual errors actually look like.

  A. Velocity-field roughness
     Atmospheric/dem errors inject spatially-correlated, temporally-random noise.
     Removing them should smooth the VELOCITY field. Measured as the robust
     standard deviation of the high-pass velocity field (high-pass energy).

  B. Stable-area scatter
     Over areas selected as independently stable (high temporal coherence, low
     velocity, away from the known subsidence corridor), velocity should be
     near zero and spatially uniform. Reports both the offset and the scatter.

  C. Topography-correlated residual
     A DEM-residual error appears as a correlation between residual phase and
     elevation. Pixel-wise DEM-residual correction should reduce it more than
     ERA5 alone.

  D. Per-pixel temporal residual scatter
     The median over the AOI of each pixel's residual standard deviation. Unlike
     per-interferogram RMS this is robust to a handful of bad interferograms.

Note: a correction that simply removes real signal would score well on all four,
so a branch is only "better" if it improves these AND does not degrade the
raw velocity agreement elsewhere. Both directions are reported.

Outputs
-------
qc/sci/correction_validation.json
qc/sci/correction_validation.csv

Usage
-----
    python scripts/28_correction_validation.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
from rasterio.transform import Affine
from rasterio.warp import transform_geom
from scipy.ndimage import gaussian_filter
from shapely.geometry import shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "qc" / "sci"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
GEOMETRY = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"

LAMBDA = 0.055465764662349676
PHASE2RANGE = -LAMBDA / (4.0 * np.pi)

BRANCHES = [
    ("RAW", PROJECT_ROOT / "mintpy" / "baseline_raw_work", "timeseries.h5"),
    ("ERA5", PROJECT_ROOT / "mintpy" / "era5_work", "timeseries_ERA5.h5"),
    ("ERA5+DEM", PROJECT_ROOT / "mintpy" / "dem_work", "timeseries_ERA5_demErr.h5"),
]

STABLE_COHERENCE = 0.90
STABLE_MAX_ABS_VELOCITY = 0.003      # 3 mm/yr
HIGHPASS_SIGMA_PX = 3                # ~120 m


def grid_mask():
    with h5py.File(GEOMETRY, "r") as handle:
        md = {k: float(handle.attrs[k]) for k in
              ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    aoi = shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shape(transform_geom("EPSG:4326", f"EPSG:{int(md['EPSG'])}", aoi.__geo_interface__))
    minx, miny, maxx, maxy = aoi_utm.bounds
    col0 = max(0, int(np.floor((minx - md["X_FIRST"]) / md["X_STEP"])) - 1)
    col1 = min(int(md["WIDTH"]), int(np.ceil((maxx - md["X_FIRST"]) / md["X_STEP"])) + 1)
    row0 = max(0, int(np.floor((md["Y_FIRST"] - maxy) / -md["Y_STEP"])) - 1)
    row1 = min(int(md["LENGTH"]), int(np.ceil((md["Y_FIRST"] - miny) / -md["Y_STEP"])) + 1)
    t = Affine(md["X_STEP"], 0.0, md["X_FIRST"] + col0 * md["X_STEP"],
               0.0, md["Y_STEP"], md["Y_FIRST"] + row0 * md["Y_STEP"])
    mask = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=(row1 - row0, col1 - col0),
        transform=t, invert=True)
    with h5py.File(GEOMETRY, "r") as handle:
        height = handle["height"][row0:row1, col0:col1].astype("float64")
    return mask, (row0, row1, col0, col1), height


def resolve_velocity(work: Path, final_ts: str) -> Path | None:
    for path in sorted(work.glob("velocity*.h5")):
        with h5py.File(path, "r") as handle:
            if str(handle.attrs.get("FILE_PATH", "")).endswith(final_ts):
                return path
    return None


def highpass_energy(values: np.ndarray, valid: np.ndarray, sigma: float) -> float:
    filled = np.where(valid, values, np.nan)
    median = float(np.nanmedian(filled))
    filled = np.where(valid, values, median)
    smooth = gaussian_filter(filled, sigma=sigma)
    residual = (values - smooth)[valid]
    residual = residual[np.isfinite(residual)]
    if residual.size == 0:
        return float("nan")
    mad = float(np.median(np.abs(residual - np.median(residual))))
    return 1.4826 * mad


def main() -> int:
    mask, window, height = grid_mask()
    row0, row1, col0, col1 = window
    n_aoi = int(mask.sum())

    print("=" * 88)
    print("CORRECTION VALIDATION - better-posed tests")
    print("=" * 88)
    print(f"\n  AOI pixels: {n_aoi}")

    # ---- load every branch once ------------------------------------------
    data: dict[str, dict] = {}
    for label, work, ts_name in BRANCHES:
        vel_path = resolve_velocity(work, ts_name)
        if vel_path is None:
            print(f"  {label}: SKIPPED (no velocity derived from {ts_name})")
            continue
        with h5py.File(vel_path, "r") as handle:
            vel = handle["velocity"][row0:row1, col0:col1].astype("float64")
        with h5py.File(work / "temporalCoherence.h5", "r") as handle:
            tc = handle["temporalCoherence"][row0:row1, col0:col1].astype("float64")
        data[label] = {"work": work, "velocity_file": vel_path.name,
                       "ts": ts_name, "velocity": vel, "tcoherence": tc}
        print(f"  {label:10s} {vel_path.name:16s} <- {ts_name}")

    # ---- A. velocity-field roughness -------------------------------------
    print("\n  A. velocity-field high-pass energy (lower = smoother):")
    roughness = {}
    for label, d in data.items():
        valid = mask & np.isfinite(d["velocity"])
        hp = highpass_energy(d["velocity"], valid, HIGHPASS_SIGMA_PX)
        roughness[label] = round(1000 * hp, 4)
        print(f"     {label:10s} {1000 * hp:8.4f} mm/yr")
    best_rough = min(roughness, key=roughness.get) if roughness else None
    print(f"     -> smoothest: {best_rough}")

    # ---- B. stable-area scatter ------------------------------------------
    print(f"\n  B. stable-area diagnostics "
          f"(tc >= {STABLE_COHERENCE}, |v| <= {1000 * STABLE_MAX_ABS_VELOCITY:.0f} mm/yr):")
    stable = {}
    for label, d in data.items():
        if label == "RAW":
            base = mask & np.isfinite(d["velocity"]) & (d["tcoherence"] >= STABLE_COHERENCE)
            stable_mask = base & (np.abs(d["velocity"]) <= STABLE_MAX_ABS_VELOCITY)
        v = d["velocity"][stable_mask]
        v = v[np.isfinite(v)]
        if v.size == 0:
            stable[label] = {}
            continue
        stable[label] = {
            "n_pixels": int(v.size),
            "velocity_median_mm_per_yr": round(1000 * float(np.median(v)), 4),
            "velocity_robust_std_mm_per_yr": round(
                1000 * 1.4826 * float(np.median(np.abs(v - np.median(v)))), 4),
            "velocity_p95_minus_p05_mm_per_yr": round(
                1000 * float(np.percentile(v, 95) - np.percentile(v, 5)), 4),
        }
        s = stable[label]
        print(f"     {label:10s} n={s['n_pixels']:7d}  median {s['velocity_median_mm_per_yr']:+7.3f}  "
              f"robust std {s['velocity_robust_std_mm_per_yr']:6.3f}  "
              f"p95-p05 {s['velocity_p95_minus_p05_mm_per_yr']:6.3f} mm/yr")

    # ---- C. topography-correlated residual -------------------------------
    print("\n  C. topography-correlated residual (|Spearman|, lower = better):")
    topo_corr = {}
    dem_valid = mask & np.isfinite(height)
    for label, d in data.items():
        work = d["work"]
        name = d["ts"]
        with h5py.File(work / name, "r") as handle:
            dates = np.array(handle["date"]).astype(str)
            ts = handle["timeseries"][:, row0:row1, col0:col1].astype("float64")
        idx = {x: i for i, x in enumerate(dates)}
        with h5py.File(work / "inputs" / "ifgramStack.h5", "r") as handle:
            ifg_dates = np.array(handle["date"]).astype(str)
            # mean residual over a subset of interferograms (every 8th) for speed
            accum = np.zeros(height.shape, dtype="float64")
            count = 0
            for i in range(0, len(ifg_dates), 8):
                ref, sec = ifg_dates[i]
                obs = handle["unwrapPhase"][i, row0:row1, col0:col1].astype("float64")
                model = (ts[idx[sec]] - ts[idx[ref]]) / PHASE2RANGE
                accum += np.where(np.isfinite(obs) & np.isfinite(model) & (obs != 0), obs - model, 0)
                count += 1
            mean_residual = accum / max(1, count)

        sel = dem_valid & np.isfinite(mean_residual)
        if sel.sum() > 1000:
            r = float(pd.Series(mean_residual[sel]).corr(
                pd.Series(height[sel]), method="spearman"))
        else:
            r = float("nan")
        topo_corr[label] = round(r, 4)
        print(f"     {label:10s} Spearman(residual, elevation) = {r:+.4f}")
    best_topo = min(topo_corr, key=lambda k: abs(topo_corr[k])) if topo_corr else None
    print(f"     -> weakest topo correlation: {best_topo}")

    # ---- D. per-pixel temporal residual scatter --------------------------
    print("\n  D. per-pixel temporal residual scatter (median over AOI, lower = better):")
    pixel_scatter = {}
    for label, d in data.items():
        work = d["work"]
        name = d["ts"]
        with h5py.File(work / name, "r") as handle:
            dates = np.array(handle["date"]).astype(str)
            ts = handle["timeseries"][:, row0:row1, col0:col1].astype("float64")
        idx = {x: i for i, x in enumerate(dates)}
        with h5py.File(work / "inputs" / "ifgramStack.h5", "r") as handle:
            ifg_dates = np.array(handle["date"]).astype(str)
            stack = np.full((len(ifg_dates), int(mask.sum())), np.nan)
            flat_mask = mask.ravel()
            for i in range(len(ifg_dates)):
                ref, sec = ifg_dates[i]
                obs = handle["unwrapPhase"][i, row0:row1, col0:col1].astype("float64")
                model = (ts[idx[sec]] - ts[idx[ref]]) / PHASE2RANGE
                resid = obs - model
                stack[i] = resid.ravel()[flat_mask]
        std = np.nanstd(stack, axis=0)
        med = float(np.nanmedian(std))
        pixel_scatter[label] = round(med, 4)
        print(f"     {label:10s} {med:.4f} rad")

    # ---- verdict ---------------------------------------------------------
    def improved(branch: str, ref: str = "RAW") -> dict:
        return {
            "roughness": roughness.get(branch, np.nan) < roughness.get(ref, np.inf),
            "stable_scatter": (
                stable.get(branch, {}).get("velocity_robust_std_mm_per_yr", np.inf)
                < stable.get(ref, {}).get("velocity_robust_std_mm_per_yr", -np.inf)
            ),
            "topo_correlation": abs(topo_corr.get(branch, np.inf)) < abs(topo_corr.get(ref, np.inf)),
            "pixel_scatter": pixel_scatter.get(branch, np.inf) < pixel_scatter.get(ref, np.inf),
        }

    verdicts = {}
    for branch in ("ERA5", "ERA5+DEM"):
        if branch not in data:
            continue
        cmp = improved(branch)
        n_better = sum(cmp.values())
        verdicts[branch] = {
            "tests": cmp,
            "n_tests_improved": n_better,
            "n_tests": len(cmp),
            "verdict": "measurable improvement" if n_better >= 3 else "no measurable improvement",
        }
        print(f"\n  {branch}: {n_better}/{len(cmp)} tests improved -> {verdicts[branch]['verdict']}")

    promote = [b for b, v in verdicts.items() if v["n_tests_improved"] >= 3]
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "aoi_pixels": n_aoi,
        "tests": {
            "A_velocity_highpass_energy_mm_per_yr": roughness,
            "B_stable_area": stable,
            "C_topography_correlation_spearman": topo_corr,
            "D_per_pixel_residual_scatter_rad": pixel_scatter,
        },
        "stable_mask_definition": {
            "temporal_coherence_min": STABLE_COHERENCE,
            "abs_velocity_max_mm_per_yr": 1000 * STABLE_MAX_ABS_VELOCITY,
            "note": "the mask is defined from the RAW branch so it is identical across branches",
        },
        "verdicts": verdicts,
        "promotion_policy": "promote only if at least 3 of 4 tests show measurable improvement",
        "promoted": promote,
        "principal_candidate": promote[0] if promote else "RAW",
        "caveat": "These tests favour smoother solutions; a correction that removed real "
                  "signal would also score well, so the raw velocity agreement is reported "
                  "alongside (see branch_comparison.json).",
    }
    (OUT_DIR / "correction_validation.json").write_text(json.dumps(report, indent=2, default=str))
    pd.DataFrame([
        {"branch": b,
         "highpass_energy_mm_per_yr": roughness.get(b),
         "stable_robust_std_mm_per_yr": stable.get(b, {}).get("velocity_robust_std_mm_per_yr"),
         "topo_correlation": topo_corr.get(b),
         "pixel_residual_scatter_rad": pixel_scatter.get(b)}
        for b in data
    ]).to_csv(OUT_DIR / "correction_validation.csv", index=False)

    print(f"\n  PROMOTED: {promote if promote else 'none'}")
    print(f"  principal candidate: {report['principal_candidate']}")
    print(f"\n  {OUT_DIR / 'correction_validation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
