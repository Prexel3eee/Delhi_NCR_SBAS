#!/usr/bin/env python
"""
Three-way branch comparison: RAW vs ERA5 vs ERA5+DEM-residual.

Compares whatever branches exist, AOI-restricted, on:
  * raw LOS velocity and its uncertainty
  * temporal coherence
  * per-interferogram residual RMS (the direct fit-quality test)

Also reports the pairwise differences, so it is clear whether each correction
helped, hurt, or merely shifted the solution.

Deramping is NOT applied in any branch; it remains a sensitivity experiment.

Usage
-----
    python scripts/25_branch_comparison.py
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
from shapely.geometry import shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "qc" / "sci"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
LAMBDA = 0.055465764662349676
PHASE2RANGE = -LAMBDA / (4.0 * np.pi)

# (label, work dir, velocity/ts filename prefix)
BRANCHES = [
    ("RAW", PROJECT_ROOT / "mintpy" / "baseline_raw_work", ""),
    ("ERA5", PROJECT_ROOT / "mintpy" / "era5_work", "ERA5"),
    ("ERA5+DEM", PROJECT_ROOT / "mintpy" / "dem_work", "ERA5"),
]


def grid_mask(stack: Path):
    with h5py.File(stack, "r") as handle:
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
    return mask, (row0, row1, col0, col1)


def per_ifg_residuals(work: Path, window, mask, ts_name: str) -> pd.DataFrame:
    row0, row1, col0, col1 = window
    with h5py.File(work / ts_name, "r") as handle:
        ts_dates = np.array(handle["date"]).astype(str)
        ts = handle["timeseries"][:, row0:row1, col0:col1]
    idx = {d: i for i, d in enumerate(ts_dates)}
    rows = []
    with h5py.File(work / "inputs" / "ifgramStack.h5", "r") as handle:
        dates = np.array(handle["date"]).astype(str)
        unw = handle["unwrapPhase"]
        for i in range(len(dates)):
            ref, sec = dates[i]
            obs = unw[i, row0:row1, col0:col1].astype("float64")
            model = (ts[idx[sec]] - ts[idx[ref]]) / PHASE2RANGE
            r = (obs - model)[mask]
            o = obs[mask]
            v = r[np.isfinite(r) & np.isfinite(o) & (o != 0)]
            rows.append({"index": i, "date12": f"{ref}_{sec}",
                         "residual_rms_rad": round(float(np.sqrt(np.mean(v ** 2))), 4)
                         if v.size else None})
    return pd.DataFrame(rows)


def main() -> int:
    mask, window = grid_mask(PROJECT_ROOT / "mintpy" / "baseline_raw_work" / "inputs" / "ifgramStack.h5")
    row0, row1, col0, col1 = window

    results: dict = {}
    residuals: dict[str, pd.DataFrame] = {}

    print("=" * 88)
    print("BRANCH COMPARISON (AOI-restricted)")
    print("=" * 88)

    for label, work, prefix in BRANCHES:
        vel_path = work / f"velocity{prefix}.h5" if prefix else work / "velocity.h5"
        ts_name = f"timeseries_{prefix}.h5" if prefix else "timeseries.h5"
        if not vel_path.exists() or not (work / ts_name).exists():
            print(f"\n  {label:10s} SKIPPED (missing {vel_path.name} or {ts_name})")
            continue
        with h5py.File(vel_path, "r") as h:
            vel = h["velocity"][row0:row1, col0:col1].astype("float64")
            vstd = h["velocityStd"][row0:row1, col0:col1].astype("float64")
        with h5py.File(work / "temporalCoherence.h5", "r") as h:
            tc = h["temporalCoherence"][row0:row1, col0:col1].astype("float64")

        def st(a):
            x = a[mask]
            x = x[np.isfinite(x)]
            return {"median": round(float(np.median(x)), 6),
                    "p05": round(float(np.percentile(x, 5)), 6),
                    "p95": round(float(np.percentile(x, 95)), 6),
                    "std": round(float(np.std(x)), 6)}

        res = per_ifg_residuals(work, window, mask, ts_name)
        residuals[label] = res
        results[label] = {
            "work_dir": str(work.relative_to(PROJECT_ROOT)),
            "velocity_file": vel_path.name,
            "velocity_m_per_yr": st(vel),
            "velocity_uncertainty_m_per_yr": {"median": st(vstd)["median"]},
            "temporal_coherence": st(tc),
            "residual_rms_rad_median": round(float(res["residual_rms_rad"].median()), 4),
        }
        print(f"\n  {label:10s} velocity median {results[label]['velocity_m_per_yr']['median']:+.4f} m/yr | "
              f"coherence {results[label]['temporal_coherence']['median']:.4f} | "
              f"residual RMS {results[label]['residual_rms_rad_median']} rad")

    # pairwise differences
    labels = [l for l, _, _ in BRANCHES if l in results]
    pairwise = {}
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            wa = next(w for l, w, p in BRANCHES if l == a)
            wb = next(w for l, w, p in BRANCHES if l == b)
            pa = next(p for l, w, p in BRANCHES if l == a)
            pb = next(p for l, w, p in BRANCHES if l == b)
            with h5py.File(wa / (f"velocity{pa}.h5" if pa else "velocity.h5"), "r") as h:
                va = h["velocity"][row0:row1, col0:col1].astype("float64")
            with h5py.File(wb / (f"velocity{pb}.h5" if pb else "velocity.h5"), "r") as h:
                vb = h["velocity"][row0:row1, col0:col1].astype("float64")
            d = (vb - va)[mask]
            d = d[np.isfinite(d)]
            key = f"{b}_minus_{a}"
            pairwise[key] = {
                "median_mm_per_yr": round(1000 * float(np.median(d)), 3),
                "rms_mm_per_yr": round(1000 * float(np.sqrt(np.mean(d ** 2))), 3),
                "max_abs_mm_per_yr": round(1000 * float(np.max(np.abs(d))), 2),
            }
            # residual improvement
            if a in residuals and b in residuals:
                m = residuals[a][["index", "residual_rms_rad"]].merge(
                    residuals[b][["index", "residual_rms_rad"]], on="index",
                    suffixes=("_a", "_b"))
                delta = m["residual_rms_rad_b"] - m["residual_rms_rad_a"]
                pairwise[key]["residual_improved"] = int((delta < 0).sum())
                pairwise[key]["residual_worsened"] = int((delta > 0).sum())
                pairwise[key]["residual_median_change_rad"] = round(float(delta.median()), 4)

    print("\n  pairwise velocity differences:")
    for key, val in pairwise.items():
        extra = ""
        if "residual_improved" in val:
            extra = (f" | residual improved {val['residual_improved']}"
                     f" / worsened {val['residual_worsened']}"
                     f" (median {val['residual_median_change_rad']:+.3f} rad)")
        print(f"    {key:24s} median {val['median_mm_per_yr']:+8.2f} mm/yr  "
              f"RMS {val['rms_mm_per_yr']:7.2f}  max {val['max_abs_mm_per_yr']:7.2f}{extra}")

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "branches": results,
        "pairwise": pairwise,
        "deramp": "disabled in every branch (sensitivity experiment only)",
        "note": "No deformation product declared. The DEM branch is ERA5 + pixel-wise "
                "DEM residual, so ERA5+DEM minus ERA5 isolates the DEM-residual effect.",
    }
    (OUT_DIR / "branch_comparison.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"\n  {OUT_DIR / 'branch_comparison.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
