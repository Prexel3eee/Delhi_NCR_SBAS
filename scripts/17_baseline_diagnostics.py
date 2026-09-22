#!/usr/bin/env python
"""
RAW-336 baseline diagnostics (uncorrected, all 336 pairs retained).

Reads the baseline branch outputs and produces:

  * AOI-restricted statistics for raw LOS velocity, its uncertainty, the
    linear-fit residue and temporal coherence;
  * **per-interferogram residual diagnostics** - MintPy's own residual_RMS step
    is skipped when every correction is disabled (it needs a residual phase
    file), so the residual is computed directly:

        residual = unwrapPhase - (timeseries[secondary] - timeseries[reference]) * (-4*pi/lambda)

    with the phase convention taken from mintpy/ifgram_inversion.py:
    phase2range = -WAVELENGTH / (4*pi);
  * a **candidate bad-pair table**. This is a *proposal* only: nothing is
    excluded, and every row carries the objective reason that would justify
    exclusion if it were accepted.

Outputs
-------
qc/sci/baseline_raw_diagnostics.json
qc/sci/per_ifg_residuals.csv
qc/sci/bad_pair_candidates.csv

Usage
-----
    python scripts/17_baseline_diagnostics.py
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
from shapely.geometry import shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
STACK = WORK / "inputs" / "ifgramStack.h5"
OUT_DIR = PROJECT_ROOT / "qc" / "sci"
QC_TABLE = OUT_DIR / "ifgram_qc_table.csv"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"

RESIDUAL_BAD_RAD = 1.0          # |residual| above this counts as a large misfit
RESIDUAL_BAD_FRACTION = 0.05    # ... in more than this fraction of the AOI
COHERENCE_LOW = 0.30
COMPONENT_LOW = 0.70


def aoi_mask_and_window(stack_path: Path):
    from rasterio.warp import transform_geom

    with h5py.File(stack_path, "r") as handle:
        md = {k: float(handle.attrs[k]) for k in
              ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    transform = Affine(md["X_STEP"], 0.0, md["X_FIRST"], 0.0, md["Y_STEP"], md["Y_FIRST"])
    aoi = shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shape(transform_geom("EPSG:4326", f"EPSG:{int(md['EPSG'])}", aoi.__geo_interface__))

    minx, miny, maxx, maxy = aoi_utm.bounds
    col0 = max(0, int(np.floor((minx - md["X_FIRST"]) / md["X_STEP"])) - 1)
    col1 = min(int(md["WIDTH"]), int(np.ceil((maxx - md["X_FIRST"]) / md["X_STEP"])) + 1)
    row0 = max(0, int(np.floor((md["Y_FIRST"] - maxy) / -md["Y_STEP"])) - 1)
    row1 = min(int(md["LENGTH"]), int(np.ceil((md["Y_FIRST"] - miny) / -md["Y_STEP"])) + 1)

    win_transform = Affine(md["X_STEP"], 0.0, md["X_FIRST"] + col0 * md["X_STEP"],
                           0.0, md["Y_STEP"], md["Y_FIRST"] + row0 * md["Y_STEP"])
    mask = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__],
        out_shape=(row1 - row0, col1 - col0),
        transform=win_transform, invert=True,
    )
    return mask, (row0, row1, col0, col1), md


def aoi_stats(values: np.ndarray, mask: np.ndarray) -> dict:
    v = values[mask]
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"n": 0}
    return {
        "n": int(v.size),
        "min": round(float(np.min(v)), 4),
        "p05": round(float(np.percentile(v, 5)), 4),
        "p25": round(float(np.percentile(v, 25)), 4),
        "median": round(float(np.median(v)), 4),
        "p75": round(float(np.percentile(v, 75)), 4),
        "p95": round(float(np.percentile(v, 95)), 4),
        "max": round(float(np.max(v)), 4),
        "mean": round(float(np.mean(v)), 4),
        "std": round(float(np.std(v)), 4),
    }


def main() -> int:
    for required in (STACK, WORK / "velocity.h5", WORK / "timeseries.h5"):
        if not required.exists():
            print(f"FAIL: missing {required}")
            return 1

    mask, (row0, row1, col0, col1), md = aoi_mask_and_window(STACK)
    n_aoi = int(mask.sum())
    lam = 0.055465764662349676
    phase2range = -lam / (4.0 * np.pi)

    print("=" * 88)
    print("RAW-336 BASELINE DIAGNOSTICS")
    print("=" * 88)
    print(f"\n  AOI pixels: {n_aoi}")
    print(f"  phase convention: phase2range = -lambda/(4pi) = {phase2range:.6e} m/rad")

    report: dict = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "branch": "baseline_raw (uncorrected, all 336 pairs)",
        "corrections": {"unwrap_error": "no", "troposphere": "no", "deramp": "no",
                        "dem_residual": "no"},
        "pairs_in_inversion": 336,
        "aoi_pixels": n_aoi,
        "phase2range": phase2range,
        "wavelength_m": lam,
    }

    # ---- velocity / coherence maps ---------------------------------------
    print("\n  velocity / coherence maps:")
    with h5py.File(WORK / "velocity.h5", "r") as handle:
        datasets = {k: handle[k][row0:row1, col0:col1] for k in handle.keys()
                    if hasattr(handle[k], "shape") and handle[k].shape == (md["LENGTH"], md["WIDTH"])}
        ref_y, ref_x = int(handle.attrs.get("REF_Y", -1)), int(handle.attrs.get("REF_X", -1))
    with h5py.File(WORK / "temporalCoherence.h5", "r") as handle:
        temp_coh = handle["temporalCoherence"][row0:row1, col0:col1]
    # This file holds a single `mask` layer in this MintPy version, not a count
    # map, so read whichever dataset is present rather than assuming a name.
    closure_path = WORK / "numTriNonzeroIntAmbiguity.h5"
    closure_name, closure = None, None
    if closure_path.exists():
        with h5py.File(closure_path, "r") as handle:
            closure_name = next(iter(handle.keys()))
            closure = handle[closure_name][row0:row1, col0:col1]

    report["reference_pixel_full_grid_yx"] = [ref_y, ref_x]
    report["raw_los_velocity_m_per_yr"] = aoi_stats(datasets["velocity"], mask)
    report["velocity_uncertainty_m_per_yr"] = aoi_stats(datasets["velocityStd"], mask)
    report["linear_fit_residue"] = aoi_stats(datasets["residue"], mask)
    report["temporal_coherence"] = aoi_stats(temp_coh, mask)
    if closure is not None:
        report["phase_closure"] = {
            "source_dataset": closure_name,
            "dtype": str(closure.dtype),
            "stats_over_aoi": aoi_stats(closure.astype("float64"), mask),
        }
        # a boolean mask flags pixels the closure diagnostic considers unreliable
        if closure.dtype == bool or set(np.unique(closure)).issubset({0, 1}):
            frac = float(np.mean(closure[mask].astype(bool)))
            report["phase_closure"]["flagged_fraction_of_aoi"] = round(frac, 6)
            print(f"    phase-closure flagged fraction of AOI: {frac:.4f}")
    else:
        report["phase_closure"] = {"available": False}

    for name in ("raw_los_velocity_m_per_yr", "velocity_uncertainty_m_per_yr",
                 "linear_fit_residue", "temporal_coherence"):
        s = report[name]
        print(f"    {name:34s} median={s.get('median')}  p05={s.get('p05')}  "
              f"p95={s.get('p95')}  std={s.get('std')}")

    # temporal coherence masks
    tc = temp_coh[mask]
    tc = tc[np.isfinite(tc)]
    report["temporal_coherence_fractions"] = {
        f"frac_gt_{t}": round(float(np.mean(tc > t)), 6) for t in (0.5, 0.6, 0.7, 0.8, 0.9)
    }
    print(f"    temporal coherence > 0.7: {report['temporal_coherence_fractions']['frac_gt_0.7']}")

    # ---- per-interferogram residuals -------------------------------------
    print("\n  per-interferogram residuals (model minus observation):")
    with h5py.File(WORK / "timeseries.h5", "r") as handle:
        ts_dates = np.array(handle["date"]).astype(str)
        ts = handle["timeseries"][:, row0:row1, col0:col1]      # (119, h, w) metres
    date_index = {d: i for i, d in enumerate(ts_dates)}

    with h5py.File(STACK, "r") as handle:
        ifg_dates = np.array(handle["date"]).astype(str)
        bperp = np.array(handle["bperp"])
        unw_ds = handle["unwrapPhase"]

        rows = []
        for i in range(len(ifg_dates)):
            ref, sec = ifg_dates[i]
            obs = unw_ds[i, row0:row1, col0:col1].astype("float64")
            model = (ts[date_index[sec]] - ts[date_index[ref]]) / phase2range  # rad
            resid = obs - model

            r = resid[mask]
            o = obs[mask]
            valid = np.isfinite(r) & np.isfinite(o) & (o != 0)
            rv = r[valid]
            if rv.size:
                rms = float(np.sqrt(np.mean(rv ** 2)))
                frac_bad = float(np.mean(np.abs(rv) > RESIDUAL_BAD_RAD))
                med = float(np.median(rv))
            else:
                rms = frac_bad = med = None
            rows.append({
                "index": i,
                "date12": f"{ref}_{sec}",
                "reference_date": ref,
                "secondary_date": sec,
                "perpendicular_baseline_m": round(float(bperp[i]), 1),
                "residual_px": int(rv.size),
                "residual_rms_rad": round(rms, 4) if rms is not None else None,
                "residual_median_rad": round(med, 4) if med is not None else None,
                "residual_frac_abs_gt_1rad": round(frac_bad, 6) if frac_bad is not None else None,
            })
            if (i + 1) % 84 == 0:
                print(f"    {i + 1}/{len(ifg_dates)}")

    resid_df = pd.DataFrame(rows)
    resid_df.to_csv(OUT_DIR / "per_ifg_residuals.csv", index=False)
    report["residual_rms_rad"] = {
        "min": round(float(resid_df["residual_rms_rad"].min()), 4),
        "p25": round(float(resid_df["residual_rms_rad"].quantile(0.25)), 4),
        "median": round(float(resid_df["residual_rms_rad"].median()), 4),
        "p75": round(float(resid_df["residual_rms_rad"].quantile(0.75)), 4),
        "p95": round(float(resid_df["residual_rms_rad"].quantile(0.95)), 4),
        "max": round(float(resid_df["residual_rms_rad"].max()), 4),
    }
    print(f"    residual RMS (rad): median={report['residual_rms_rad']['median']} "
          f"p95={report['residual_rms_rad']['p95']} max={report['residual_rms_rad']['max']}")

    # ---- validate the residual model -------------------------------------
    # A correct model must anti-correlate with coherence: high-coherence pairs
    # should fit better. A sign or scale error would destroy this relationship.
    qc = pd.read_csv(QC_TABLE)
    check = qc.merge(resid_df[["index", "residual_rms_rad"]], on="index", how="left")
    valid = check.dropna(subset=["residual_rms_rad", "coherence_median"])
    r = float(valid["residual_rms_rad"].corr(valid["coherence_median"], method="spearman"))
    report["residual_model_validation"] = {
        "spearman_residual_vs_coherence": round(r, 4),
        "expected": "negative (better coherence -> smaller residual)",
        "interpretation": (
            "consistent" if r < -0.3 else
            "WEAK/INCONSISTENT - residual model may be mis-scaled"
        ),
    }
    print(f"\n  residual model check: Spearman(residual RMS, coherence) = {r:.3f} "
          f"-> {report['residual_model_validation']['interpretation']}")

    # ---- candidate bad pairs (proposal only) -----------------------------
    # UNCORRECTED baselines carry unmodelled atmosphere and orbit ramps, so
    # absolute thresholds are meaningless: a fixed 1 rad cut flagged 333/336
    # pairs. Candidates are therefore identified as ROBUST OUTLIERS of the
    # network's own distribution (median +/- k * 1.4826 * MAD).
    merged = qc.merge(resid_df[["index", "residual_rms_rad", "residual_frac_abs_gt_1rad"]],
                      on="index", how="left")

    K = 3.5  # robust z threshold

    def robust_bounds(series: pd.Series) -> tuple[float, float, float, float]:
        s = series.dropna().astype(float)
        med = float(s.median())
        mad = float((s - med).abs().median())
        scale = 1.4826 * mad if mad > 0 else float(s.std() or 1e-9)
        return med - K * scale, med + K * scale, med, scale

    # Bounds are computed WITHIN EACH TEMPORAL-BASELINE CLASS. Coherence falls
    # systematically with temporal baseline (0.75 / 0.57 / 0.45 at 12/24/36 d
    # here), so comparing a 36-day pair against 12-day pairs would flag the whole
    # 36-day class as anomalous. Each pair is judged against its own class.
    bounds: dict[int, dict] = {}
    for tb, group in merged.groupby("temporal_baseline_days"):
        b = {}
        for key, direction in (("coherence_median", "lower"),
                               ("largest_component_frac_aoi", "lower"),
                               ("residual_rms_rad", "upper")):
            lo, hi, med, scale = robust_bounds(group[key])
            b[key] = {"lower": lo, "upper": hi, "median": med, "scale": scale,
                      "direction": direction, "n": int(len(group))}
        bounds[int(tb)] = b

    report["robust_outlier_bounds_by_temporal_class"] = {
        "k": K,
        "method": "median +/- k * 1.4826 * MAD computed within each temporal-baseline class",
        "classes": {
            str(tb): {
                "n": b["coherence_median"]["n"],
                "coherence_median": {kk: round(b["coherence_median"][kk], 4)
                                     for kk in ("median", "scale", "lower", "upper")},
                "largest_component_frac_aoi": {kk: round(b["largest_component_frac_aoi"][kk], 4)
                                               for kk in ("median", "scale", "lower", "upper")},
                "residual_rms_rad": {kk: round(b["residual_rms_rad"][kk], 4)
                                     for kk in ("median", "scale", "lower", "upper")},
            }
            for tb, b in sorted(bounds.items())
        },
    }

    candidates = []
    for row in merged.itertuples():
        b = bounds.get(int(row.temporal_baseline_days)) if pd.notna(row.temporal_baseline_days) else None
        reasons = []
        if b:
            if pd.notna(row.coherence_median) and row.coherence_median < b["coherence_median"]["lower"]:
                reasons.append(
                    f"coherence_median {row.coherence_median:.3f} below the "
                    f"{int(row.temporal_baseline_days)} d class bound "
                    f"{b['coherence_median']['lower']:.3f}"
                )
            if (pd.notna(row.largest_component_frac_aoi)
                    and row.largest_component_frac_aoi < b["largest_component_frac_aoi"]["lower"]):
                reasons.append(
                    f"largest connected component {row.largest_component_frac_aoi:.3f} below the "
                    f"{int(row.temporal_baseline_days)} d class bound "
                    f"{b['largest_component_frac_aoi']['lower']:.3f}"
                )
            if pd.notna(row.residual_rms_rad) and row.residual_rms_rad > b["residual_rms_rad"]["upper"]:
                reasons.append(
                    f"residual RMS {row.residual_rms_rad:.3f} rad above the "
                    f"{int(row.temporal_baseline_days)} d class bound "
                    f"{b['residual_rms_rad']['upper']:.3f}"
                )
        if reasons:
            candidates.append({
                "date12": row.date12,
                "reference_date": row.reference_date,
                "secondary_date": row.secondary_date,
                "temporal_baseline_days": row.temporal_baseline_days,
                "perpendicular_baseline_m": row.perpendicular_baseline_m,
                "coherence_median": row.coherence_median,
                "largest_component_frac_aoi": row.largest_component_frac_aoi,
                "residual_rms_rad": row.residual_rms_rad,
                "residual_frac_abs_gt_1rad": row.residual_frac_abs_gt_1rad,
                "reasons": "; ".join(reasons),
                "n_reasons": len(reasons),
            })

    cand_df = pd.DataFrame(candidates).sort_values(
        ["n_reasons", "coherence_median"], ascending=[False, True]
    ) if candidates else pd.DataFrame()
    cand_df.to_csv(OUT_DIR / "bad_pair_candidates.csv", index=False)

    report["bad_pair_candidates"] = {
        "criteria": (
            "robust outliers of the network distribution: value beyond "
            f"median +/- {K} * 1.4826 * MAD (see robust_outlier_bounds). "
            "Absolute thresholds are NOT used: an uncorrected baseline carries "
            "unmodelled atmosphere and orbit ramps, so a fixed cut is meaningless "
            "(a 1 rad threshold flagged 333 of 336 pairs)."
        ),
        "stratified_by": "temporal_baseline_days",
        "candidates_by_reason": {
            reason: int(sum(1 for c in candidates if reason in c["reasons"]))
            for reason in ("coherence_median", "largest connected component", "residual RMS")
        },
        "n_candidates": int(len(cand_df)),
        "pct_of_network": round(100.0 * len(cand_df) / len(merged), 2),
        "by_temporal_baseline": (
            cand_df["temporal_baseline_days"].value_counts().sort_index().to_dict()
            if not cand_df.empty else {}
        ),
        "note": "PROPOSAL ONLY - nothing has been excluded; all 336 pairs remain in the baseline.",
    }
    print("\n  candidate bad pairs (proposal only): "
          f"{len(cand_df)} of {len(merged)} ({report['bad_pair_candidates']['pct_of_network']}%)")
    if not cand_df.empty:
        print(cand_df[["date12", "temporal_baseline_days", "coherence_median",
                       "largest_component_frac_aoi", "residual_rms_rad", "n_reasons"]]
              .head(12).to_string(index=False))

    (OUT_DIR / "baseline_raw_diagnostics.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"\n  {OUT_DIR / 'baseline_raw_diagnostics.json'}")
    print(f"  {OUT_DIR / 'per_ifg_residuals.csv'}")
    print(f"  {OUT_DIR / 'bad_pair_candidates.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
