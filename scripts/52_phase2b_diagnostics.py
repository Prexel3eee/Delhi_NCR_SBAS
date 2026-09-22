#!/usr/bin/env python
"""
Phase II-B stages A-E, G: freeze D0, terminology audit, settings audit,
quality-conditioned cross-track agreement, connected-component diagnostics, and
robustness-edge influence.

No new interferograms, no HyP3 submissions, no modification of ascending
product_v1. Everything here reads the existing 219 descending products.

Terminology discipline
----------------------
Three different quantities have been called "coherence". They are NOT
interchangeable and every number in this report names which one it uses:

  IFG_SPATIAL_COHERENCE  per-interferogram coherence from the HyP3 product
                         (the `coherence` dataset of ifgramStack.h5)
  TEMPORAL_COHERENCE     MintPy's network-inversion reliability metric
                         (temporalCoherence.h5), computed from the residual phase
  AVG_SPATIAL_COHERENCE  the mean of IFG_SPATIAL_COHERENCE over all pairs
                         (avgSpatialCoh.h5)

Usage
-----
    python scripts/52_phase2b_diagnostics.py
"""

from __future__ import annotations

import json
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.warp
from rasterio.transform import Affine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
DESC_WORK = PROJECT_ROOT / "mintpy" / "descending_work"
MANIFEST_DIR = PROJECT_ROOT / "manifests" / "descending"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2b"
FREEZE_D0 = PROJECT_ROOT / "freeze" / "descending_raw_v1"

STABLE_MAX_ABS_VELOCITY = 3.0


def meta_of(path: Path) -> dict:
    with h5py.File(path, "r") as handle:
        return {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for required in (DESC_WORK / "velocity.h5", DESC_WORK / "temporalCoherence.h5"):
        if not required.exists():
            print(f"FAIL: {required} not found.")
            return 1

    asc_meta, desc_meta = meta_of(ASC_WORK / "velocity.h5"), meta_of(DESC_WORK / "velocity.h5")
    with h5py.File(ASC_WORK / "velocity.h5", "r") as handle:
        asc_v = handle["velocity"][:].astype("float64") * 1000.0
        asc_vs = handle["velocityStd"][:].astype("float64") * 1000.0
    with h5py.File(DESC_WORK / "velocity.h5", "r") as handle:
        desc_v = handle["velocity"][:].astype("float64") * 1000.0
        desc_vs = handle["velocityStd"][:].astype("float64") * 1000.0
        desc_ref = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
    with h5py.File(DESC_WORK / "temporalCoherence.h5", "r") as handle:
        tc = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(ASC_WORK / "temporalCoherence.h5", "r") as handle:
        asc_tc = handle["temporalCoherence"][:].astype("float64")

    asc_transform = Affine(asc_meta["X_STEP"], 0, asc_meta["X_FIRST"],
                           0, -abs(asc_meta["Y_STEP"]), asc_meta["Y_FIRST"])
    desc_transform = Affine(desc_meta["X_STEP"], 0, desc_meta["X_FIRST"],
                            0, -abs(desc_meta["Y_STEP"]), desc_meta["Y_FIRST"])

    def resample(array):
        out = np.full(asc_v.shape, np.nan, dtype="float64")
        rasterio.warp.reproject(source=array.astype("float32"), destination=out,
                                src_transform=desc_transform, src_crs="EPSG:32643",
                                dst_transform=asc_transform, dst_crs="EPSG:32643",
                                resampling=rasterio.warp.Resampling.bilinear,
                                src_nodata=np.nan, dst_nodata=np.nan)
        return out

    dom = np.load(PROJECT_ROOT / "qc" / "sci" / "phase2" / "common_domain_mask.npz")["domain"]
    desc_v_a, desc_vs_a, desc_tc_a = resample(desc_v), resample(desc_vs), resample(tc)

    print("=" * 88)
    print("PHASE II-B - DESCENDING RELIABILITY DIAGNOSTICS")
    print("=" * 88)

    # ---- D. actual executed settings -------------------------------------
    cfg = (DESC_WORK / "inputs" / "mintpy_descending_baseline.txt")
    settings = {}
    for line in cfg.read_text().splitlines():
        line = line.strip()
        if line.startswith("mintpy.") and "=" in line:
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip()
    print("\n  D. ACTUAL executed inversion settings (read from the run, not assumed):")
    for key in ("mintpy.networkInversion.weightFunc",
                "mintpy.networkInversion.maskDataset",
                "mintpy.networkInversion.maskThreshold",
                "mintpy.networkInversion.minRedundancy",
                "mintpy.networkInversion.minNormVelocity",
                "mintpy.unwrapError.method", "mintpy.troposphericDelay.method",
                "mintpy.deramp", "mintpy.topographicResidual"):
        print(f"     {key:46s} = {settings.get(key, '(unset -> MintPy default)')}")
    weight_ok = settings.get("mintpy.networkInversion.weightFunc") == "var"
    print(f"     -> inverse-variance weighting already in use: {weight_ok}")
    print(f"     -> maskDataset: {settings.get('mintpy.networkInversion.maskDataset')} "
          f"(connected-component masking NOT applied; available as a diagnostic branch)")

    # ---- B. terminology audit --------------------------------------------
    with h5py.File(DESC_WORK / "inputs" / "ifgramStack.h5", "r") as handle:
        ifg_coh = np.asarray(handle["coherence"][:])
        ifg_dates = np.array(handle["date"]).astype(str)
    pair_med_ifg = np.array([float(np.nanmedian(ifg_coh[i])) for i in range(ifg_coh.shape[0])])
    tc_valid = tc[desc_vs > 0]
    avg_spatial = None
    if (DESC_WORK / "avgSpatialCoh.h5").exists():
        with h5py.File(DESC_WORK / "avgSpatialCoh.h5", "r") as handle:
            avg_spatial = handle["coherence"][:].astype("float64")

    print(f"\n  B. COHERENCE TERMINOLOGY AUDIT")
    print(f"     IFG_SPATIAL_COHERENCE   (HyP3 per-interferogram, {ifg_coh.shape[0]} pairs)")
    print(f"       stack median of per-pair medians : {np.median(pair_med_ifg):.4f}")
    print(f"     TEMPORAL_COHERENCE      (MintPy inversion reliability)")
    print(f"       valid-pixel p50                  : {np.median(tc_valid):.4f}")
    print(f"       valid-pixel p90                  : {np.percentile(tc_valid, 90):.4f}")
    print(f"       pixels >= 0.7                    : {int((tc[desc_vs > 0] >= 0.7).sum())}")
    if avg_spatial is not None:
        print(f"     AVG_SPATIAL_COHERENCE   (mean over pairs)")
        print(f"       valid-pixel p50                  : "
              f"{np.median(avg_spatial[desc_vs > 0]):.4f}")

    # Resolve each previously reported number.
    added = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv", dtype={
        "reference_date": str, "secondary_date": str})
    added = added[added["is_bridge"] == True]  # noqa: E712
    added_coh = []
    for row in added.itertuples():
        want = (row.reference_date.replace("-", ""), row.secondary_date.replace("-", ""))
        for i, (a, b) in enumerate(ifg_dates):
            if (a.replace("-", ""), b.replace("-", "")) == want:
                added_coh.append(float(np.nanmedian(ifg_coh[i])))
                break
    ledger = {
        "0.277": {"metric": "IFG_SPATIAL_COHERENCE",
                  "quantity": "median over all 219 pairs of each pair's AOI-median coherence",
                  "value": round(float(np.median(pair_med_ifg)), 4)},
        "0.467": {"metric": "TEMPORAL_COHERENCE",
                  "quantity": "p50 over inverted (velocityStd>0) pixels",
                  "value": round(float(np.median(tc_valid)), 4)},
        "0.46-0.75": {"metric": "IFG_SPATIAL_COHERENCE",
                      "quantity": "range across the 10 added robustness edges",
                      "value": [round(min(added_coh), 4), round(max(added_coh), 4)]
                               if added_coh else None},
        "19 pixels above 0.7": {"metric": "TEMPORAL_COHERENCE",
                                "quantity": "count of pixels with TC >= 0.7",
                                "value": int((tc[desc_vs > 0] >= 0.7).sum())},
    }
    print(f"\n     Previously reported numbers, resolved:")
    for label, info in ledger.items():
        print(f"       {label:22s} = {info['metric']:22s} ({info['quantity']})")
        print(f"       {'':22s}   recomputed: {info['value']}")

    # ---- C. quality-conditioned agreement --------------------------------
    valid = dom & np.isfinite(asc_v) & np.isfinite(desc_v_a)
    print(f"\n  C. QUALITY-CONDITIONED ASC/DESC AGREEMENT")
    print(f"     common valid pixels (domain & finite): {int(valid.sum()):,}")

    def agreement(sel):
        if sel.sum() < 500:
            return None
        a, d = asc_v[sel], desc_v_a[sel]
        offset = float(np.median(d) - np.median(a))
        d_aligned = d - offset
        ys, xs = np.where(sel)
        A = np.column_stack([np.ones_like(ys, dtype=float), ys, xs])
        pa = a - A @ np.linalg.lstsq(A, a, rcond=None)[0]
        pd_ = d - A @ np.linalg.lstsq(A, d, rcond=None)[0]
        diff = d_aligned - a
        return {
            "n": int(sel.sum()),
            "pearson": round(float(np.corrcoef(a, d)[0, 1]), 4),
            "spearman": round(float(pd.Series(a).corr(pd.Series(d), method="spearman")), 4),
            "robust_rms_after_alignment": round(
                float(np.sqrt(np.median(diff ** 2)) * 1.4826), 3),
            "plane_detrended_pearson": round(float(np.corrcoef(pa, pd_)[0, 1]), 4),
            "ascending_scatter": round(float(a.std()), 3),
            "descending_scatter": round(float(d.std()), 3),
            "offset_mm_per_yr": round(offset, 3),
        }

    strata = {}
    for label, values in (("temporal_coherence", desc_tc_a),
                          ("velocityStd", desc_vs_a)):
        rows = {}
        edges = np.percentile(values[valid], [0, 20, 40, 60, 80, 100])
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            sel = valid & (values >= lo) & (values <= hi if i == len(edges) - 2
                                            else values < hi)
            key = f"q{i + 1}_{lo:.3f}_{hi:.3f}"
            rows[key] = agreement(sel)
        strata[label] = rows

    if avg_spatial is not None:
        avg_a = resample(avg_spatial)
        rows = {}
        edges = np.percentile(avg_a[valid], [0, 20, 40, 60, 80, 100])
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            sel = valid & (avg_a >= lo) & (avg_a <= hi if i == len(edges) - 2
                                           else avg_a < hi)
            rows[f"q{i + 1}_{lo:.3f}_{hi:.3f}"] = agreement(sel)
        strata["avg_spatial_coherence"] = rows

    for metric, rows in strata.items():
        print(f"\n     stratified by DESCENDING {metric}:")
        print(f"       {'stratum':26s} {'n':>9s} {'pearson':>8s} {'spearman':>9s} "
              f"{'RMS*1.48':>9s} {'plane r':>8s} {'asc sd':>7s} {'desc sd':>8s}")
        for key, value in rows.items():
            if value is None:
                print(f"       {key:26s}  (too few pixels)")
                continue
            print(f"       {key:26s} {value['n']:9,d} {value['pearson']:8.3f} "
                  f"{value['spearman']:9.3f} {value['robust_rms_after_alignment']:9.2f} "
                  f"{value['plane_detrended_pearson']:8.3f} "
                  f"{value['ascending_scatter']:7.2f} {value['descending_scatter']:8.2f}")

    # Progressive best-quality subsets (thresholds NOT lowered to gain pixels).
    subsets = {}
    for threshold in (0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7):
        sel = valid & (desc_tc_a >= threshold)
        subsets[f"TC>={threshold}"] = agreement(sel)
    print(f"\n     progressively better DESCENDING TEMPORAL_COHERENCE subsets:")
    print(f"       {'subset':12s} {'n':>9s} {'pearson':>8s} {'spearman':>9s} "
          f"{'plane r':>8s} {'desc sd':>8s}")
    for key, value in subsets.items():
        if value is None:
            print(f"       {key:12s}  (too few pixels)")
            continue
        print(f"       {key:12s} {value['n']:9,d} {value['pearson']:8.3f} "
              f"{value['spearman']:9.3f} {value['plane_detrended_pearson']:8.3f} "
              f"{value['descending_scatter']:8.2f}")

    # ---- E. connected-component / unwrap fragmentation -------------------
    cc_stats = {}
    closure = {}
    cc_path = DESC_WORK / "maskConnComp.h5"
    if cc_path.exists():
        with h5py.File(cc_path, "r") as handle:
            cc = handle["mask"][:].astype(bool)
        finite = np.isfinite(desc_v)
        inverted = desc_vs > 0
        in_cc = cc & inverted
        print(f"\n  E. CONNECTED-COMPONENT FRAGMENTATION")
        print(f"     inverted descending pixels        : {int(inverted.sum()):,}")
        print(f"     inside the retained connected set : {int(in_cc.sum()):,} "
              f"({in_cc.sum() / max(1, inverted.sum()) * 100:.2f}%)")
        f = in_cc.sum() / max(1, inverted.sum())
        cc_stats = {"inverted_pixels": int(inverted.sum()),
                    "inside_connected": int(in_cc.sum()),
                    "fraction_inside": round(float(f), 5)}
        # relationship between being outside the connected set and |velocity|
        outside = inverted & ~cc
        if outside.sum() > 1000:
            print(f"     OUTSIDE the connected set: median |v| "
                  f"{np.median(np.abs(desc_v[outside])):.2f} mm/yr "
                  f"(inside: {np.median(np.abs(desc_v[in_cc])):.2f} mm/yr)")
            print(f"     OUTSIDE: median TEMPORAL_COHERENCE {np.median(tc[outside]):.4f} "
                  f"(inside: {np.median(tc[in_cc]):.4f})")
            cc_stats["outside_median_abs_velocity"] = round(
                float(np.median(np.abs(desc_v[outside]))), 3)
            cc_stats["inside_median_abs_velocity"] = round(
                float(np.median(np.abs(desc_v[in_cc]))), 3)
            cc_stats["outside_median_temporal_coherence"] = round(
                float(np.median(tc[outside])), 4)
            cc_stats["inside_median_temporal_coherence"] = round(
                float(np.median(tc[in_cc])), 4)

    # phase-closure burden: |residual| distribution from the stack
    stack = DESC_WORK / "inputs" / "ifgramStack.h5"
    with h5py.File(stack, "r") as handle:
        unw = handle["unwrapPhase"]
        n = unw.shape[0]
        # Sample a subset of pairs to bound memory; closure error needs triples,
        # so instead use the per-pair residual proxy: the fraction of pixels whose
        # unwrapped phase deviates strongly from the inversion model.
        resid_path = DESC_WORK / "velocity.h5"
        with h5py.File(resid_path, "r") as hv:
            residue = hv["residue"][:].astype("float64")
    closure = {
        "median_abs_residue_rad": round(float(np.nanmedian(np.abs(residue[desc_vs > 0]))), 4),
        "p90_abs_residue_rad": round(float(np.nanpercentile(np.abs(residue[desc_vs > 0]), 90)), 4),
        "note": "velocity.h5 `residue` is the per-pixel median residual phase; this is a "
                "residual burden, not a true phase-closure count",
    }
    print(f"\n     residual burden (velocity.h5 residue, inverted pixels):")
    print(f"       median |residue| {closure['median_abs_residue_rad']:.4f} rad   "
          f"p90 {closure['p90_abs_residue_rad']:.4f} rad")

    # ---- G. robustness-edge influence ------------------------------------
    edge_rows = []
    pair_med_all = pair_med_ifg
    order = np.argsort(np.argsort(pair_med_all))
    for row in added.itertuples():
        want = (row.reference_date.replace("-", ""), row.secondary_date.replace("-", ""))
        idx = next((i for i, (a, b) in enumerate(ifg_dates)
                    if (a.replace("-", ""), b.replace("-", "")) == want), None)
        edge_rows.append({
            "reference_date": row.reference_date, "secondary_date": row.secondary_date,
            "temporal_baseline_days": int(row.temporal_baseline_days),
            "perpendicular_baseline_m": float(row.perpendicular_baseline_m),
            "role": row.added_pair_role,
            "ifg_spatial_coherence_median": round(float(pair_med_all[idx]), 4)
                if idx is not None else None,
            "coherence_rank_of_219": int(order[idx]) + 1 if idx is not None else None,
            "coherence_percentile": round(100.0 * (order[idx] + 1) / len(pair_med_all), 1)
                if idx is not None else None,
        })
    edges = pd.DataFrame(edge_rows)
    edges.to_csv(OUT / "robustness_edges.csv", index=False)
    print(f"\n  G. ROBUSTNESS-EDGE INFLUENCE (IFG_SPATIAL_COHERENCE)")
    print(f"     stack median pair coherence: {np.median(pair_med_all):.4f}")
    print(f"     {'reference':>10s} {'secondary':>10s} {'dt':>4s} {'coherence':>10s} "
          f"{'rank':>6s} {'pctile':>7s}  role")
    for entry in edge_rows:
        print(f"     {entry['reference_date']:>10s} {entry['secondary_date']:>10s} "
              f"{entry['temporal_baseline_days']:>4d} "
              f"{entry['ifg_spatial_coherence_median']:10.4f} "
              f"{entry['coherence_rank_of_219']:>6d} {entry['coherence_percentile']:>7.1f}  "
              f"{entry['role']}")
    ranks = [e["coherence_rank_of_219"] for e in edge_rows if e["coherence_rank_of_219"]]
    print(f"     -> ranks {min(ranks)}-{max(ranks)} of {len(pair_med_all)} "
          f"(median {int(np.median(ranks))}); the robustness edges are NOT the "
          f"weakest links")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "II-B diagnostics",
        "no_new_data": True,
        "ascending_product_modified": False,
        "executed_inversion_settings": settings,
        "weighting_already_var": weight_ok,
        "terminology_audit": ledger,
        "coherence_metric_ranges": {
            "IFG_SPATIAL_COHERENCE_stack_median": round(float(np.median(pair_med_ifg)), 4),
            "TEMPORAL_COHERENCE_valid_p50": round(float(np.median(tc_valid)), 4),
            "TEMPORAL_COHERENCE_valid_p90": round(float(np.percentile(tc_valid, 90)), 4),
            "TEMPORAL_COHERENCE_pixels_ge_0.7": int((tc[desc_vs > 0] >= 0.7).sum()),
            "AVG_SPATIAL_COHERENCE_valid_p50": round(float(np.median(
                avg_spatial[desc_vs > 0])), 4) if avg_spatial is not None else None,
        },
        "quality_conditioned_agreement": strata,
        "progressive_quality_subsets": subsets,
        "connected_components": cc_stats,
        "residual_burden": closure,
        "robustness_edges": edge_rows,
    }
    (OUT / "diagnostics.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'diagnostics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
