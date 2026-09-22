#!/usr/bin/env python
"""
ERA5 coverage verification and RAW-vs-ERA5 comparison.

Two separate obligations, deliberately kept apart:

1. **Coverage gate first.** An ERA5-corrected time series is only trustworthy if
   *every* acquisition date has an atmospheric model profile. A partial download
   would silently produce a time series whose later dates lack correction, which
   can masquerade as a temporal deformation signal. So coverage is verified
   before any comparison is reported, and a gap is a hard failure.

2. **Comparison second.** Only once coverage is complete: quantify what ERA5
   changed, per-pixel and per-interferogram, and whether it improved the fit.

Nothing here declares a deformation product, and deramping is not applied.

Outputs
-------
qc/sci/era5_coverage.json
qc/sci/era5_comparison.json
qc/sci/per_ifg_residuals_era5.csv

Usage
-----
    python scripts/24_era5_coverage_and_comparison.py
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
ERA5 = PROJECT_ROOT / "mintpy" / "era5_work"
WEATHER = ERA5 / "mintpy" / "weather" / "ERA5"
OUT_DIR = PROJECT_ROOT / "qc" / "sci"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
ACC_CSV = PROJECT_ROOT / "manifests" / "accepted_acquisitions.csv"

LAMBDA = 0.055465764662349676
PHASE2RANGE = -LAMBDA / (4.0 * np.pi)
MIN_GRIB_BYTES = 1024


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


def aoi_mask_for(stack: Path):
    """AOI mask on the full stack grid (used for AOI-restricted coverage)."""
    with h5py.File(stack, "r") as handle:
        md = {k: float(handle.attrs[k]) for k in
              ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    aoi = shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shape(transform_geom("EPSG:4326", f"EPSG:{int(md['EPSG'])}", aoi.__geo_interface__))
    t = Affine(md["X_STEP"], 0.0, md["X_FIRST"], 0.0, md["Y_STEP"], md["Y_FIRST"])
    return rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__],
        out_shape=(int(md["LENGTH"]), int(md["WIDTH"])),
        transform=t, invert=True,
    )


def verify_coverage() -> tuple[bool, dict]:
    """Every acquisition date must carry a usable ERA5 profile over the AOI.

    The gate is AOI-restricted on purpose. PyAPS leaves NaN outside the valid
    ERA5 interpolation domain, which here covers a large fraction of the full
    clipped grid (global finite fraction ~0.64) while leaving ZERO NaN inside
    the AOI. Gating on the global fraction would halt a branch that is in fact
    fully corrected where it matters.
    """
    acc = pd.read_csv(ACC_CSV)
    dates = sorted(acc["date"].str.replace("-", "", regex=False))
    grbs = sorted(WEATHER.glob("ERA5_*.grb")) if WEATHER.exists() else []

    present: dict[str, int] = {}
    for g in grbs:
        # ERA5_<area>_<YYYYMMDD>_<hour>.grb
        parts = g.stem.split("_")
        if len(parts) >= 3 and parts[-2].isdigit() and len(parts[-2]) == 8:
            present[parts[-2]] = g.stat().st_size

    missing = [d for d in dates if d not in present]
    too_small = [d for d, s in present.items() if s < MIN_GRIB_BYTES]

    # MintPy's delay file
    era5_h5 = ERA5 / "inputs" / "ERA5.h5"
    h5_info: dict = {"exists": era5_h5.exists()}
    if era5_h5.exists():
        with h5py.File(era5_h5, "r") as handle:
            h5_info["keys"] = list(handle.keys())
            delay_dates = None
            if "date" in handle:
                delay_dates = sorted(np.array(handle["date"]).astype(str).tolist())
                h5_info["delay_dates"] = len(delay_dates)
                h5_info["delay_dates_match_expected"] = delay_dates == dates
            for key in handle.keys():
                dset = handle[key]
                if not hasattr(dset, "shape") or not dset.shape:
                    continue
                # skip the string `date` array: isfinite() is undefined for it
                if not np.issubdtype(dset.dtype, np.number):
                    continue
                h5_info[f"{key}_shape"] = list(dset.shape)
                h5_info[f"{key}_dtype"] = str(dset.dtype)
                if dset.shape[0] == len(dates):
                    vals = np.array(dset)
                    finite = np.isfinite(vals)
                    h5_info[f"{key}_finite_fraction"] = round(float(finite.mean()), 6)
                    h5_info[f"{key}_min"] = round(float(np.nanmin(vals)), 4)
                    h5_info[f"{key}_median"] = round(float(np.nanmedian(vals)), 4)
                    h5_info[f"{key}_max"] = round(float(np.nanmax(vals)), 4)

    dates_match = h5_info.get("delay_dates_match_expected", False)
    finite_ok = all(
        v >= 0.999 for k, v in h5_info.items() if k.endswith("_finite_fraction")
    ) if any(k.endswith("_finite_fraction") for k in h5_info) else False
    # AOI-restricted, per-date finiteness across ALL dates
    aoi_min_finite = None
    aoi_worst_dates: list[dict] = []
    if era5_h5.exists():
        try:
            mask = aoi_mask_for(RAW / "inputs" / "ifgramStack.h5")
            with h5py.File(era5_h5, "r") as handle:
                ts = handle["timeseries"]
                n = ts.shape[0]
                fractions = []
                for i in range(n):
                    block = ts[i]
                    frac = float(np.isfinite(block[mask]).mean())
                    fractions.append(frac)
                    if frac < 0.999:
                        aoi_worst_dates.append({"index": i, "finite_fraction": round(frac, 6)})
            aoi_min_finite = round(min(fractions), 6)
            h5_info["aoi_min_finite_fraction"] = aoi_min_finite
            h5_info["aoi_mean_finite_fraction"] = round(float(np.mean(fractions)), 6)
        except Exception as exc:  # noqa: BLE001
            h5_info["aoi_coverage_error"] = f"{type(exc).__name__}: {exc}"

    aoi_ok = aoi_min_finite is not None and aoi_min_finite >= 0.999
    complete = (
        (not missing) and (not too_small) and era5_h5.exists()
        and dates_match and aoi_ok
    )
    report_extra = {
        "delay_dates_match_expected": dates_match,
        "global_finite_fraction": h5_info.get("timeseries_finite_fraction"),
        "aoi_min_finite_fraction": aoi_min_finite,
        "aoi_coverage_ok": aoi_ok,
        "dates_with_incomplete_aoi_coverage": aoi_worst_dates[:20],
        "note": "coverage is gated on the AOI, not the full clipped grid; PyAPS leaves "
                "NaN outside the ERA5 interpolation domain, which does not affect the AOI",
    }
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "expected_dates": len(dates),
        "first_date": dates[0],
        "last_date": dates[-1],
        "grib_files_present": len(present),
        "grib_missing_dates": missing,
        "grib_below_min_size": too_small,
        "total_grib_bytes": int(sum(present.values())),
        "weather_dir": str(WEATHER.relative_to(PROJECT_ROOT)),
        "era5_delay_file": h5_info,
        "complete_coverage": bool(complete),
        **report_extra,
    }
    return complete, report


def per_ifg_residuals(work: Path, window, mask, ts_name: str = "timeseries.h5") -> pd.DataFrame:
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
            rows.append({
                "index": i,
                "date12": f"{ref}_{sec}",
                "residual_rms_rad": round(float(np.sqrt(np.mean(v ** 2))), 4) if v.size else None,
            })
    return pd.DataFrame(rows)


def main() -> int:
    print("=" * 88)
    print("ERA5 COVERAGE GATE AND RAW-vs-ERA5 COMPARISON")
    print("=" * 88)

    complete, coverage = verify_coverage()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "era5_coverage.json").write_text(json.dumps(coverage, indent=2, default=str))

    print(f"\n  1. COVERAGE GATE")
    print(f"     expected acquisition dates : {coverage['expected_dates']}")
    print(f"     ERA5 GRIB files present    : {coverage['grib_files_present']}")
    print(f"     missing                    : {len(coverage['grib_missing_dates'])}")
    print(f"     undersized (< {MIN_GRIB_BYTES} B)     : {len(coverage['grib_below_min_size'])}")
    print(f"     delay file                 : {coverage['era5_delay_file']}")
    print(f"     global finite fraction     : {coverage.get('global_finite_fraction')} "
          f"(grid outside the AOI contains NaN by design)")
    print(f"     AOI finite fraction (min)  : {coverage.get('aoi_min_finite_fraction')}")
    print(f"     AOI coverage OK            : {coverage.get('aoi_coverage_ok')}")
    print(f"     COMPLETE COVERAGE          : {complete}")

    if not complete:
        print("\n  HALTING: ERA5 coverage is incomplete.")
        print("  A partial correction would make uncorrected dates look like a temporal")
        print("  deformation signal, so no comparison is reported.")
        if coverage["grib_missing_dates"]:
            print(f"  missing dates: {coverage['grib_missing_dates'][:20]}")
        return 1

    print("\n  [PASS] every acquisition date carries an ERA5 profile")

    # ---- comparison ------------------------------------------------------
    mask, window = grid_mask(RAW / "inputs" / "ifgramStack.h5")
    row0, row1, col0, col1 = window

    def load(work: Path, suffix: str = ""):
        """Load a branch's velocity/coherence.

        MintPy writes the troposphere-corrected products with an ERA5 suffix
        (`velocityERA5.h5`, `timeseries_ERA5.h5`); the unsuffixed `velocity.h5`
        in the ERA5 work dir is the PRE-correction inversion and must not be
        used for the corrected side of the comparison.
        """
        vel_path = work / f"velocity{suffix}.h5"
        if not vel_path.exists():
            print(f"FAIL: missing {vel_path}")
            raise SystemExit(1)
        with h5py.File(vel_path, "r") as h:
            vel = h["velocity"][row0:row1, col0:col1].astype("float64")
            vstd = h["velocityStd"][row0:row1, col0:col1].astype("float64")
        with h5py.File(work / "temporalCoherence.h5", "r") as h:
            tc = h["temporalCoherence"][row0:row1, col0:col1].astype("float64")
        return vel, vstd, tc

    v_raw, s_raw, tc_raw = load(RAW, "")
    v_e, s_e, tc_e = load(ERA5, "ERA5")
    print("  using velocityERA5.h5 / timeseries_ERA5.h5 for the corrected branch")

    def stats(a, m):
        x = a[m]
        x = x[np.isfinite(x)]
        return {
            "median": round(float(np.median(x)), 6),
            "p05": round(float(np.percentile(x, 5)), 6),
            "p95": round(float(np.percentile(x, 95)), 6),
            "std": round(float(np.std(x)), 6),
        }

    dv = (v_e - v_raw)[mask]
    dv = dv[np.isfinite(dv)]
    dtc = (tc_e - tc_raw)[mask]
    dtc = dtc[np.isfinite(dtc)]

    residual = per_ifg_residuals(ERA5, window, mask, ts_name="timeseries_ERA5.h5")
    residual.to_csv(OUT_DIR / "per_ifg_residuals_era5.csv", index=False)
    raw_resid = pd.read_csv(OUT_DIR / "per_ifg_residuals.csv")
    merged = raw_resid[["index", "date12", "residual_rms_rad"]].merge(
        residual[["index", "residual_rms_rad"]], on="index", suffixes=("_raw", "_era5"))
    merged["delta"] = merged["residual_rms_rad_era5"] - merged["residual_rms_rad_raw"]

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "branches": {"raw": "baseline_raw_work", "era5": "era5_work"},
        "coverage_verified": True,
        "velocity_m_per_yr": {"raw": stats(v_raw, mask), "era5": stats(v_e, mask)},
        "velocity_uncertainty_m_per_yr": {"raw": stats(s_raw, mask), "era5": stats(s_e, mask)},
        "temporal_coherence": {"raw": stats(tc_raw, mask), "era5": stats(tc_e, mask)},
        "difference_era5_minus_raw": {
            "velocity_median": round(float(np.median(dv)), 6),
            "velocity_p05": round(float(np.percentile(dv, 5)), 6),
            "velocity_p95": round(float(np.percentile(dv, 95)), 6),
            "velocity_rms": round(float(np.sqrt(np.mean(dv ** 2))), 6),
            "velocity_max_abs": round(float(np.max(np.abs(dv))), 6),
            "temporal_coherence_median": round(float(np.median(dtc)), 6),
            "fraction_of_aoi_coherence_improved": round(float(np.mean(dtc > 0)), 6),
        },
        "per_ifg_residual_comparison": {
            "raw_median_rad": round(float(merged["residual_rms_rad_raw"].median()), 4),
            "era5_median_rad": round(float(merged["residual_rms_rad_era5"].median()), 4),
            "n_improved": int((merged["delta"] < 0).sum()),
            "n_worsened": int((merged["delta"] > 0).sum()),
            "largest_improvements": merged.nsmallest(8, "delta")[
                ["date12", "residual_rms_rad_raw", "residual_rms_rad_era5", "delta"]
            ].to_dict(orient="records"),
        },
        "note": "Deramping NOT applied. No deformation product declared.",
    }
    (OUT_DIR / "era5_comparison.json").write_text(json.dumps(report, indent=2, default=str))

    d = report["difference_era5_minus_raw"]
    pc = report["per_ifg_residual_comparison"]
    print("\n  2. RAW vs ERA5 (AOI-restricted)")
    print(f"     velocity  raw median {report['velocity_m_per_yr']['raw']['median']:+.4f} | "
          f"era5 {report['velocity_m_per_yr']['era5']['median']:+.4f} m/yr")
    print(f"     coherence raw median {report['temporal_coherence']['raw']['median']:.4f} | "
          f"era5 {report['temporal_coherence']['era5']['median']:.4f}")
    print(f"     velocity difference: median {1000*d['velocity_median']:+.2f} mm/yr, "
          f"RMS {1000*d['velocity_rms']:.2f} mm/yr, max |d| {1000*d['velocity_max_abs']:.1f} mm/yr")
    print(f"     coherence improved over {100*d['fraction_of_aoi_coherence_improved']:.1f}% of the AOI")
    print(f"     residual RMS: raw {pc['raw_median_rad']} -> era5 {pc['era5_median_rad']} rad; "
          f"improved {pc['n_improved']}, worsened {pc['n_worsened']}")
    print(f"\n     {OUT_DIR / 'era5_coverage.json'}")
    print(f"     {OUT_DIR / 'era5_comparison.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
