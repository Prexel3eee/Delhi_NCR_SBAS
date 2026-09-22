#!/usr/bin/env python
"""
Unwrap-correction comparison: RAW baseline vs bridging+phase_closure.

Both branches are identical except for `mintpy.unwrapError.method`, so any
difference is attributable to unwrap-error correction. Comparison is
AOI-restricted and includes a re-computation of per-interferogram residuals for
the corrected branch, which is the most direct test of whether the correction
actually improved the fit.

Outputs
-------
qc/sci/unwrap_comparison.json
qc/sci/per_ifg_residuals_bridge_pc.csv

Usage
-----
    python scripts/20_unwrap_comparison.py
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
RAW = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
BRIDGE = PROJECT_ROOT / "mintpy" / "bridge_pc_work"
OUT_DIR = PROJECT_ROOT / "qc" / "sci"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"

LAMBDA = 0.055465764662349676
PHASE2RANGE = -LAMBDA / (4.0 * np.pi)


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


def per_ifg_residuals(work: Path, window, mask) -> pd.DataFrame:
    row0, row1, col0, col1 = window
    with h5py.File(work / "timeseries.h5", "r") as handle:
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
            rows.append({
                "index": i,
                "date12": f"{ref}_{sec}",
                "residual_rms_rad": round(float(np.sqrt(np.mean(v ** 2))), 4) if v.size else None,
                "residual_frac_abs_gt_1rad": round(float(np.mean(np.abs(v) > 1.0)), 6) if v.size else None,
            })
    return pd.DataFrame(rows)


def main() -> int:
    for required in (RAW / "velocity.h5", BRIDGE / "velocity.h5"):
        if not required.exists():
            print(f"FAIL: missing {required}")
            return 1

    mask, window = grid_mask(RAW / "inputs" / "ifgramStack.h5")
    row0, row1, col0, col1 = window
    n_aoi = int(mask.sum())

    print("=" * 88)
    print("UNWRAP-CORRECTION COMPARISON: RAW baseline vs bridging+phase_closure")
    print("=" * 88)
    print(f"\n  AOI pixels: {n_aoi}")

    def load(work: Path):
        with h5py.File(work / "velocity.h5", "r") as h:
            vel = h["velocity"][row0:row1, col0:col1].astype("float64")
            vstd = h["velocityStd"][row0:row1, col0:col1].astype("float64")
        with h5py.File(work / "temporalCoherence.h5", "r") as h:
            tc = h["temporalCoherence"][row0:row1, col0:col1].astype("float64")
        return vel, vstd, tc

    v_raw, s_raw, tc_raw = load(RAW)
    v_bri, s_bri, tc_bri = load(BRIDGE)

    def stats(a, m):
        x = a[m]
        x = x[np.isfinite(x)]
        return {
            "median": round(float(np.median(x)), 6),
            "p05": round(float(np.percentile(x, 5)), 6),
            "p95": round(float(np.percentile(x, 95)), 6),
            "std": round(float(np.std(x)), 6),
        }

    dv = (v_bri - v_raw)[mask]
    dv = dv[np.isfinite(dv)]
    dtc = (tc_bri - tc_raw)[mask]
    dtc = dtc[np.isfinite(dtc)]

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "branches": {
            "raw": "mintpy/baseline_raw_work (unwrapError = no)",
            "bridge_pc": "mintpy/bridge_pc_work (unwrapError = bridging+phase_closure)",
        },
        "aoi_pixels": n_aoi,
        "velocity_m_per_yr": {"raw": stats(v_raw, mask), "bridge_pc": stats(v_bri, mask)},
        "velocity_uncertainty_m_per_yr": {"raw": stats(s_raw, mask), "bridge_pc": stats(s_bri, mask)},
        "temporal_coherence": {"raw": stats(tc_raw, mask), "bridge_pc": stats(tc_bri, mask)},
        "difference_bridge_minus_raw": {
            "velocity_median": round(float(np.median(dv)), 6),
            "velocity_p05": round(float(np.percentile(dv, 5)), 6),
            "velocity_p95": round(float(np.percentile(dv, 95)), 6),
            "velocity_rms": round(float(np.sqrt(np.mean(dv ** 2))), 6),
            "velocity_max_abs": round(float(np.max(np.abs(dv))), 6),
            "temporal_coherence_median": round(float(np.median(dtc)), 6),
            "fraction_of_aoi_coherence_improved": round(float(np.mean(dtc > 0)), 6),
        },
    }

    print("\n  raw LOS velocity (m/yr):")
    for k in ("raw", "bridge_pc"):
        s = report["velocity_m_per_yr"][k]
        print(f"    {k:10s} median={s['median']:+.4f}  p05={s['p05']:+.4f}  "
              f"p95={s['p95']:+.4f}  std={s['std']:.4f}")
    print("\n  temporal coherence:")
    for k in ("raw", "bridge_pc"):
        s = report["temporal_coherence"][k]
        print(f"    {k:10s} median={s['median']:.4f}  p05={s['p05']:.4f}  std={s['std']:.4f}")
    d = report["difference_bridge_minus_raw"]
    print(f"\n  velocity difference (bridge - raw): median {1000*d['velocity_median']:+.2f} mm/yr, "
          f"RMS {1000*d['velocity_rms']:.2f} mm/yr, max |d| {1000*d['velocity_max_abs']:.1f} mm/yr")
    print(f"  coherence change: median {d['temporal_coherence_median']:+.4f}, "
          f"improved over {100*d['fraction_of_aoi_coherence_improved']:.1f}% of the AOI")

    # ---- per-ifg residual comparison -------------------------------------
    print("\n  recomputing per-interferogram residuals for the corrected branch...")
    resid_bridge = per_ifg_residuals(BRIDGE, window, mask)
    resid_bridge.to_csv(OUT_DIR / "per_ifg_residuals_bridge_pc.csv", index=False)

    raw_resid = pd.read_csv(OUT_DIR / "per_ifg_residuals.csv")
    merged = raw_resid[["index", "date12", "residual_rms_rad"]].merge(
        resid_bridge[["index", "residual_rms_rad"]], on="index", suffixes=("_raw", "_bridge"))
    merged["delta"] = merged["residual_rms_rad_bridge"] - merged["residual_rms_rad_raw"]

    report["per_ifg_residual_comparison"] = {
        "raw": {
            "median": round(float(merged["residual_rms_rad_raw"].median()), 4),
            "p95": round(float(merged["residual_rms_rad_raw"].quantile(0.95)), 4),
        },
        "bridge_pc": {
            "median": round(float(merged["residual_rms_rad_bridge"].median()), 4),
            "p95": round(float(merged["residual_rms_rad_bridge"].quantile(0.95)), 4),
        },
        "n_improved": int((merged["delta"] < 0).sum()),
        "n_worsened": int((merged["delta"] > 0).sum()),
        "n_unchanged": int((merged["delta"] == 0).sum()),
        "largest_improvements": merged.nsmallest(10, "delta")[
            ["date12", "residual_rms_rad_raw", "residual_rms_rad_bridge", "delta"]
        ].to_dict(orient="records"),
    }

    pc = report["per_ifg_residual_comparison"]
    print(f"\n  per-ifg residual RMS (rad): raw median {pc['raw']['median']} | "
          f"bridge median {pc['bridge_pc']['median']}")
    print(f"  improved: {pc['n_improved']}  worsened: {pc['n_worsened']}  "
          f"unchanged: {pc['n_unchanged']}")

    # ---- verdict ---------------------------------------------------------
    vel_change = 1000 * d["velocity_rms"]
    coh_change = d["temporal_coherence_median"]
    resid_change = pc["bridge_pc"]["median"] - pc["raw"]["median"]
    report["verdict"] = {
        "velocity_rms_change_mm_per_yr": round(vel_change, 3),
        "coherence_median_change": round(coh_change, 4),
        "residual_median_change_rad": round(resid_change, 4),
        "assessment": (
            "unwrap correction materially changes the solution"
            if vel_change > 2.0 else
            "unwrap correction has a modest effect on velocity"
        ),
    }
    print(f"\n  verdict: {report['verdict']['assessment']}")

    (OUT_DIR / "unwrap_comparison.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"\n  {OUT_DIR / 'unwrap_comparison.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
