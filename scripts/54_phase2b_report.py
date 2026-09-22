#!/usr/bin/env python
"""
Phase II-B stages H, I, J: branch evaluation and the reliability report.

Evaluates D0 (RAW), D1 (connected-component masking), D2 (unwrap-corrected, if
run) and D3 (ERA5) on the SAME table of internal-quality metrics, then applies
the predeclared stop rule.

The winner is NOT chosen from ascending/descending correlation. A branch is only
promotable if it improves its own internal quality. Cross-track agreement is
reported as a secondary diagnostic.

Usage
-----
    python scripts/54_phase2b_report.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
import rasterio.warp
from rasterio.transform import Affine, from_origin
from rasterio.warp import transform_geom
from scipy.ndimage import uniform_filter
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
ASC_GEOM = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2b"
REPORT = PROJECT_ROOT / "qc" / "sci" / "PHASE_IIB_DESCENDING_RELIABILITY_REPORT.md"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"

BRANCHES = {
    "D0_RAW": PROJECT_ROOT / "mintpy" / "descending_work",
    "D1_CONNCOMP": PROJECT_ROOT / "mintpy" / "descending_d1_conncomp_work",
    "D2_UNWRAP": PROJECT_ROOT / "mintpy" / "descending_d2_unwrap_work",
    "D3_ERA5": PROJECT_ROOT / "mintpy" / "descending_d3_era5_work",
}


def meta_of(path: Path) -> dict:
    with h5py.File(path, "r") as handle:
        return {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP")}


def metrics(work: Path, asc_v, asc_vs, asc_meta, domain_asc, height_asc, hotspots):
    """Internal-quality metrics for one branch, plus cross-track diagnostics."""
    key = work.name
    with h5py.File(work / "velocity.h5", "r") as handle:
        v = handle["velocity"][:].astype("float64") * 1000.0
        vs = handle["velocityStd"][:].astype("float64") * 1000.0
        residue = handle["residue"][:].astype("float64")
        ref = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
    with h5py.File(work / "temporalCoherence.h5", "r") as handle:
        tc = handle["temporalCoherence"][:].astype("float64")

    inverted = vs > 0
    result = {
        "branch": key,
        "inverted_pixels": int(inverted.sum()),
        "reference_yx": list(ref),
    }
    if inverted.sum() == 0:
        return result

    tcv = tc[inverted]
    result.update({
        "tc_p25": round(float(np.percentile(tcv, 25)), 4),
        "tc_p50": round(float(np.median(tcv)), 4),
        "tc_p75": round(float(np.percentile(tcv, 75)), 4),
        "tc_ge_0.5": int((tcv >= 0.5).sum()),
        "tc_ge_0.6": int((tcv >= 0.6).sum()),
        "tc_ge_0.7": int((tcv >= 0.7).sum()),
        "median_velocity_std": round(float(np.median(vs[inverted])), 4),
        "velocity_robust_scatter": round(float(1.4826 * np.median(np.abs(
            v[inverted] - np.median(v[inverted])))), 3),
        "residual_rms": round(float(np.sqrt(np.mean(residue[inverted] ** 2))), 4),
        "closure_burden_p90_abs_residue": round(
            float(np.percentile(np.abs(residue[inverted]), 90)), 4),
    })

    # short-wavelength high-pass energy (same estimator as Phase I)
    filled = np.where(inverted, v, np.nan)
    med = np.nanmedian(filled)
    filled = np.where(inverted, v, med)
    hp = (v - uniform_filter(filled, size=3, mode="nearest"))[inverted]
    hp = hp[np.isfinite(hp)]
    result["highpass_energy"] = round(
        float(1.4826 * np.median(np.abs(hp - np.median(hp)))), 4)

    # resample onto the ascending grid for the cross-track diagnostics
    dm = meta_of(work / "velocity.h5")
    at = Affine(asc_meta["X_STEP"], 0, asc_meta["X_FIRST"], 0,
                -abs(asc_meta["Y_STEP"]), asc_meta["Y_FIRST"])
    dt = Affine(dm["X_STEP"], 0, dm["X_FIRST"], 0, -abs(dm["Y_STEP"]), dm["Y_FIRST"])
    shape_out = asc_v.shape

    def resample(array):
        out = np.full(shape_out, np.nan, dtype="float64")
        rasterio.warp.reproject(source=array.astype("float32"), destination=out,
                                src_transform=dt, src_crs="EPSG:32643",
                                dst_transform=at, dst_crs="EPSG:32643",
                                resampling=rasterio.warp.Resampling.bilinear,
                                src_nodata=np.nan, dst_nodata=np.nan)
        return out

    v_a, vs_a, tc_a = resample(v), resample(vs), resample(tc)
    sel = domain_asc & np.isfinite(asc_v) & np.isfinite(v_a) & (vs_a > 0)
    if sel.sum() > 500:
        a, d = asc_v[sel], v_a[sel]
        ys, xs = np.where(sel)
        A = np.column_stack([np.ones_like(ys, dtype=float), ys, xs])
        pa = a - A @ np.linalg.lstsq(A, a, rcond=None)[0]
        pd_ = d - A @ np.linalg.lstsq(A, d, rcond=None)[0]
        result.update({
            "common_pixels": int(sel.sum()),
            "cross_pearson": round(float(np.corrcoef(a, d)[0, 1]), 4),
            "cross_spearman": round(float(pd.Series(a).corr(
                pd.Series(d), method="spearman")), 4),
            "cross_plane_detrended": round(float(np.corrcoef(pa, pd_)[0, 1]), 4),
            "descending_scatter_common": round(float(d.std()), 3),
        })
    # residual vs elevation
    if (work / "inputs" / "geometryGeo.h5").exists():
        with h5py.File(work / "inputs" / "geometryGeo.h5", "r") as handle:
            hgt = handle["height"][:].astype("float64")
        hgt_a = resample(hgt)
        hsel = domain_asc & np.isfinite(hgt_a) & np.isfinite(residue if residue.shape == shape_out else hgt_a)
        rsel = sel & np.isfinite(hgt_a)
        if rsel.sum() > 500:
            res_a = resample(residue)
            rsel2 = rsel & np.isfinite(res_a)
            if rsel2.sum() > 500:
                result["resid_elevation_corr"] = round(float(pd.Series(
                    res_a[rsel2]).corr(pd.Series(hgt_a[rsel2]), method="spearman")), 4)

    # hotspot medians
    hotspot_out = {}
    if hotspots:
        with h5py.File(work / "velocity.h5", "r") as handle:
            pass
        for hid, geom in hotspots.items():
            gu = shp_shape(transform_geom("EPSG:4326", "EPSG:32643",
                                          geom.__geo_interface__))
            hm = rasterio.features.geometry_mask([gu.__geo_interface__],
                                                 out_shape=shape_out, transform=at,
                                                 invert=True)
            s = hm & np.isfinite(v_a) & (vs_a > 0)
            if s.sum() > 10:
                hotspot_out[hid] = {
                    "n": int(s.sum()),
                    "velocity": round(float(np.median(v_a[s])), 2),
                    "tc": round(float(np.median(tc_a[s])), 4),
                    "velocity_std": round(float(np.median(vs_a[s])), 3),
                }
    result["hotspots"] = hotspot_out
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    asc_meta = meta_of(ASC_WORK / "velocity.h5")
    with h5py.File(ASC_WORK / "velocity.h5", "r") as handle:
        asc_v = handle["velocity"][:].astype("float64") * 1000.0
        asc_vs = handle["velocityStd"][:].astype("float64") * 1000.0
    with h5py.File(ASC_GEOM, "r") as handle:
        height_asc = handle["height"][:]
    domain_asc = np.load(PROJECT_ROOT / "qc" / "sci" / "phase2"
                         / "common_domain_mask.npz")["domain"]
    hotspots = {f["properties"]["hotspot_id"]: shp_shape(f["geometry"])
                for f in json.loads(HOTSPOTS.read_text())["features"]}

    print("=" * 88)
    print("PHASE II-B - BRANCH EVALUATION")
    print("=" * 88)

    rows, available, skipped = [], [], {}
    for label, work in BRANCHES.items():
        vel = work / "velocity.h5"
        if not vel.exists():
            print(f"\n  {label}: NOT RUN (no velocity.h5)")
            skipped[label] = "not run"
            continue
        # A branch work dir is an APFS CLONE of D0, which preserves mtimes. If the
        # branch's velocity is not newer than the D0 velocity it is still the
        # cloned file and the branch has not actually produced a result. Without
        # this guard a half-finished branch would be evaluated as if it were done.
        d0_vel = (PROJECT_ROOT / "mintpy" / "descending_work" / "velocity.h5")
        if work != d0_vel.parent and vel.stat().st_mtime <= d0_vel.stat().st_mtime:
            print(f"\n  {label}: INCOMPLETE - velocity.h5 is still the cloned D0 "
                  f"(not produced by this branch); excluded from evaluation")
            skipped[label] = "incomplete at evaluation time"
            continue
        print(f"\n  {label}: evaluating ...")
        row = metrics(work, asc_v, asc_vs, asc_meta, domain_asc, height_asc, hotspots)
        rows.append(row)
        available.append(label)

    if not rows:
        print("FAIL: no branches available.")
        return 1
    if skipped:
        print(f"\n  branches skipped: {skipped}")
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "branch_comparison.csv", index=False)

    cols = ["branch", "inverted_pixels", "tc_p25", "tc_p50", "tc_p75", "tc_ge_0.5",
            "tc_ge_0.6", "tc_ge_0.7", "median_velocity_std", "velocity_robust_scatter",
            "highpass_energy", "residual_rms", "closure_burden_p90_abs_residue",
            "cross_pearson", "cross_spearman", "cross_plane_detrended",
            "descending_scatter_common"]
    print(f"\n  BRANCH COMPARISON TABLE")
    present = [c for c in cols if c in table.columns]
    print("    " + " ".join(f"{c[:11]:>11s}" for c in present))
    for _, row in table.iterrows():
        print("    " + " ".join(
            f"{row[c]:>11.4f}" if isinstance(row.get(c), float) else
            f"{str(row.get(c, '-')):>11s}" for c in present))

    print(f"\n  H001-H005 by branch:")
    for _, row in table.iterrows():
        hs = row.get("hotspots", {})
        if not isinstance(hs, dict):
            continue
        print(f"    {row['branch']}: " + "  ".join(
            f"{hid}={v['velocity']:+.1f}(tc {v['tc']:.3f})" for hid, v in hs.items()))

    # ---- stop rule --------------------------------------------------------
    # branch labels are the work-dir names, so D0 is "descending_work"
    d0 = table[table["branch"] == "descending_work"]
    d0_row = d0.iloc[0] if len(d0) else None
    decisions = {}
    for _, row in table.iterrows():
        if row["branch"] == "descending_work":
            continue
        better = {}
        if d0_row is not None:
            for metric, higher_better in (("tc_p50", True), ("tc_ge_0.5", True),
                                          ("tc_ge_0.7", True),
                                          ("median_velocity_std", False),
                                          ("velocity_robust_scatter", False),
                                          ("highpass_energy", False),
                                          ("residual_rms", False)):
                old, new = d0_row.get(metric), row.get(metric)
                if old is None or new is None:
                    continue
                better[metric] = bool((new > old) if higher_better else (new < old))
        improved = sum(better.values())
        decisions[row["branch"]] = {
            "metrics_improved_vs_D0": improved,
            "metrics_compared": len(better),
            "detail": better,
            "materially_improved": bool(improved >= 4),
        }

    print(f"\n  STOP-RULE EVALUATION (a branch must improve >=4 of 7 internal metrics)")
    for branch, info in decisions.items():
        print(f"    {branch}: {info['metrics_improved_vs_D0']}/{info['metrics_compared']} "
              f"-> {'MATERIAL IMPROVEMENT' if info['materially_improved'] else 'not material'}")
        print(f"      {info['detail']}")

    promoted = [b for b, i in decisions.items() if i["materially_improved"]]
    status = ("USABLE FOR REVALIDATION" if promoted
              else "NOT SUITABLE FOR QUANTITATIVE INDEPENDENT VALIDATION")

    # ---- H. coherence-velocity interpretation ----------------------------
    cv_path = PROJECT_ROOT / "qc" / "sci" / "phase2" / "cross_validation.json"
    cv = json.loads(cv_path.read_text()) if cv_path.exists() else {}
    curve_r = cv.get("coherence_velocity", {}).get("curve_correlation")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "branches_evaluated": available,
        "branches_skipped": skipped,
        "branch_table": rows,
        "stop_rule": decisions,
        "promoted": promoted,
        "descending_scientific_status": status,
        "coherence_velocity_curve_correlation": curve_r,
        "coherence_velocity_classification": "REPRODUCED ASSOCIATION",
        "not_validated_deformation": True,
        "decomposition_status": "INVALID - the descending input is not scientifically "
                                "reliable; good matrix conditioning does not make a good "
                                "component estimate",
        "hotspot_status_unchanged": {
            "H001": "PARTIALLY_SUPPORTED", "H002": "NOT_RESOLVED",
            "H003": "NOT_RESOLVED", "H004": "NOT_RESOLVED", "H005": "NOT_RESOLVED"},
        "no_causal_attribution": True,
    }
    (OUT / "branch_evaluation.json").write_text(json.dumps(payload, indent=2, default=str))

    # ---- J. report --------------------------------------------------------
    diag = json.loads((OUT / "diagnostics.json").read_text()) if (OUT / "diagnostics.json").exists() else {}
    L = []
    add = L.append
    add("# Phase II-B — Descending Reliability Diagnostics")
    add("")
    add(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.")
    add("")
    add("**Scope.** Identify whether a specific, testable processing or data-quality "
        "issue explains the poor descending solution, and whether ONE defensible "
        "alternative can become suitable for independent validation. No new HyP3 jobs, "
        "no modification of ascending `product_v1`, no causal attribution.")
    add("")
    add("## A. Frozen D0 baseline")
    add("")
    d0f = PROJECT_ROOT / "freeze" / "descending_raw_v1" / "FREEZE.json"
    if d0f.exists():
        m = json.loads(d0f.read_text())
        add(f"`DESCENDING_RAW_V1` frozen, `freeze_id {m['freeze_id']}`. "
            f"{m['acquisitions']} acquisitions, {m['interferograms']} interferograms, "
            f"{m['robustness_edges']} robustness edges, {m['bridges']} bridges, "
            f"{m['articulation_points']} articulation point, "
            f"reference {m['reference_yx']}. Retained regardless of branch outcome.")
    add("")

    add("## B. Coherence terminology audit")
    add("")
    add("Three distinct quantities existed under the single word \"coherence\". Every "
        "number below now names its metric.")
    add("")
    add("| Metric | Definition | Descending value |")
    add("|---|---|---:|")
    cr = diag.get("coherence_metric_ranges", {})
    add(f"| `IFG_SPATIAL_COHERENCE` | per-interferogram coherence from the HyP3 product | "
        f"stack median {cr.get('IFG_SPATIAL_COHERENCE_stack_median')} |")
    add(f"| `TEMPORAL_COHERENCE` | MintPy network-inversion reliability | "
        f"p50 {cr.get('TEMPORAL_COHERENCE_valid_p50')}, "
        f"p90 {cr.get('TEMPORAL_COHERENCE_valid_p90')} |")
    add(f"| `AVG_SPATIAL_COHERENCE` | mean of IFG_SPATIAL_COHERENCE over pairs | "
        f"p50 {cr.get('AVG_SPATIAL_COHERENCE_valid_p50')} |")
    add("")
    add("Previously reported numbers, now resolved:")
    add("")
    add("| Reported | Actually was | Recomputed |")
    add("|---|---|---:|")
    for label, info in (diag.get("terminology_audit") or {}).items():
        add(f"| `{label}` | {info['metric']} — {info['quantity']} | `{info['value']}` |")
    add("")
    add("**This audit caught an error of my own.** In Phase II-A I reported that the 10 "
        "robustness edges had coherence 0.46–0.75 against a stack median of 0.277, and "
        "concluded they were not the weakest links. Those two numbers were computed over "
        "**different pixel domains** — the edges over the inverted/AOI region, the stack "
        "median over the whole grid — so the comparison was invalid. Computed "
        "consistently over the whole grid, the edges have `IFG_SPATIAL_COHERENCE` "
        "0.258–0.271 against a stack median of 0.277, giving them **ranks 1–79 of 219**. "
        "Section G below supersedes the Phase II-A claim.")
    add("")

    add("## C. Quality-conditioned cross-track agreement")
    add("")
    add("Agreement improves only marginally with descending quality, and never becomes "
        "good. Stratified by `TEMPORAL_COHERENCE` (equal-count quintiles):")
    add("")
    add("| Stratum | n | Pearson | Spearman | Plane-detrended | Desc scatter |")
    add("|---|---:|---:|---:|---:|---:|")
    for key, value in (diag.get("quality_conditioned_agreement", {})
                       .get("temporal_coherence", {}) or {}).items():
        if value is None:
            continue
        add(f"| {key} | {value['n']:,} | {value['pearson']:+.3f} | "
            f"{value['spearman']:+.3f} | {value['plane_detrended_pearson']:+.3f} | "
            f"{value['descending_scatter']:.2f} |")
    add("")
    add("Progressively better quality subsets (thresholds were **not** lowered to gain "
        "pixels):")
    add("")
    add("| Subset | n | Pearson | Spearman | Plane-detrended |")
    add("|---|---:|---:|---:|---:|")
    for key, value in (diag.get("progressive_quality_subsets") or {}).items():
        if value is None:
            add(f"| {key} | too few | | | |")
            continue
        add(f"| {key} | {value['n']:,} | {value['pearson']:+.3f} | "
            f"{value['spearman']:+.3f} | {value['plane_detrended_pearson']:+.3f} |")
    add("")
    add("**Answer to the posed question: no.** Agreement rises from r = 0.107 in the "
        "worst `TEMPORAL_COHERENCE` quintile to r = 0.205 in the best, and peaks at "
        "r = 0.202 for `TEMPORAL_COHERENCE` >= 0.55. Even the best-supported descending "
        "pixels reproduce the ascending structure at only r ≈ 0.20. Notably, descending "
        "scatter **increases** with quality stratum (25.1 -> 33.7 mm/yr), so the "
        "descending quality metrics do not behave as quality indicators.")
    add("")

    add("## D. Inversion-setting audit")
    add("")
    add("Read from the executed template, not assumed:")
    add("")
    add("| Setting | Executed value |")
    add("|---|---|")
    for key, value in (diag.get("executed_inversion_settings") or {}).items():
        add(f"| `{key}` | `{value}` |")
    add("")
    add(f"`weightFunc` is already `var` (inverse-variance), so **no weighting branch was "
        f"needed** — that diagnostic is closed by inspection. `maskDataset` was `no`, so a "
        f"connected-component-masked branch (D1) was justified as a sensitivity experiment.")
    add("")

    add("## E. Unwrapping / connected-component diagnostics")
    add("")
    cc = diag.get("connected_components", {})
    add(f"* inverted descending pixels: **{cc.get('inverted_pixels', 0):,}**")
    add(f"* inside the retained connected set: **{cc.get('inside_connected', 0):,}** "
        f"(**{cc.get('fraction_inside', 0) * 100:.2f}%**)")
    add(f"* outside the connected set: median |velocity| "
        f"{cc.get('outside_median_abs_velocity')} mm/yr vs inside "
        f"{cc.get('inside_median_abs_velocity')} mm/yr")
    add(f"* outside: `TEMPORAL_COHERENCE` {cc.get('outside_median_temporal_coherence')} vs "
        f"inside {cc.get('inside_median_temporal_coherence')}")
    add("")
    add(f"**{100 - cc.get('fraction_inside', 0) * 100:.1f}% of the inverted area lies "
        f"outside the retained connected set**, and those pixels carry both larger "
        f"|velocity| and lower `TEMPORAL_COHERENCE`. With `maskDataset = no` the D0 "
        f"inversion used them anyway. This is the strongest single candidate cause, and "
        f"it is directly testable as branch D1.")
    add("")
    rb = diag.get("residual_burden", {})
    add(f"Residual burden on inverted pixels: median |residue| "
        f"{rb.get('median_abs_residue_rad')} rad, p90 {rb.get('p90_abs_residue_rad')} rad. "
        f"({rb.get('note', '')})")
    add("")

    add("## F. ERA5 test")
    add("")
    d3 = table[table["branch"] == "D3_ERA5"]
    if len(d3):
        r = d3.iloc[0]
        add(f"ERA5 branch executed over the 91 descending epochs (missing GRIBs "
            f"downloaded; the ascending cache did not cover descending dates).")
        add("")
        add(f"* `residual` vs elevation correlation: {r.get('resid_elevation_corr', 'n/a')}")
        add(f"* median `velocityStd`: {r.get('median_velocity_std')} mm/yr")
        add(f"* short-wavelength high-pass energy: {r.get('highpass_energy')} mm/yr")
        add(f"* robust velocity scatter: {r.get('velocity_robust_scatter')} mm/yr")
        add(f"* `TEMPORAL_COHERENCE` p50: {r.get('tc_p50')}")
        add(f"* cross-track Pearson: {r.get('cross_pearson')}")
    else:
        add("D3 was not available for evaluation.")
    add("")

    add("## G. Long-gap / robustness-edge influence")
    add("")
    add("| Reference | Secondary | dt | `IFG_SPATIAL_COHERENCE` | Rank of 219 | Percentile | Role |")
    add("|---|---|---:|---:|---:|---:|---|")
    for e in diag.get("robustness_edges", []):
        add(f"| {e['reference_date']} | {e['secondary_date']} | "
            f"{e['temporal_baseline_days']} | {e['ifg_spatial_coherence_median']} | "
            f"{e['coherence_rank_of_219']} | {e['coherence_percentile']} | {e['role']} |")
    add("")
    add("Computed consistently over the whole grid, the robustness edges rank **1–79 of "
        "219** (median 30) — they ARE among the weakest pairs, contradicting the invalid "
        "Phase II-A comparison. However the absolute spread is small (0.258–0.271 against "
        "a stack median of 0.277): the whole stack is low-coherence, so the edges are "
        "weak largely because everything is weak. Their actual leverage on the velocity "
        "field is quantified by the D-branch comparison, not by rank alone.")
    add("")

    add("## H. Coherence–velocity interpretation")
    add("")
    add(f"Curve correlation across geometries: **r = {curve_r}**.")
    add("")
    add("Classification: **REPRODUCED ASSOCIATION**, not VALIDATED DEFORMATION.")
    add("")
    add("The relationship recurs in an independent heading, incidence and network, so it "
        "is a property of the data rather than of one processing configuration. It does "
        "**not** distinguish physical deformation from a quality-dependent structured "
        "bias. Conditioning it on `TEMPORAL_COHERENCE`, `AVG_SPATIAL_COHERENCE`, velocity "
        "uncertainty and observation count is the discriminating test; land-cover "
        "stratification is not authorised in this phase. The association must not be "
        "overinterpreted.")
    add("")

    add("## I. Branch comparison")
    add("")
    add("| Branch | Inverted px | TC p25 | TC p50 | TC p75 | TC>=0.5 | TC>=0.6 | TC>=0.7 | med vStd | robust scatter | high-pass | resid RMS | asc/desc r | Spearman | plane-detrended |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in table.iterrows():
        def g(col, fmt="{:.3f}"):
            value = row.get(col)
            return "n/a" if value is None or pd.isna(value) else fmt.format(value)
        def gi(col):
            value = row.get(col)
            return "n/a" if value is None or pd.isna(value) else f"{int(value):,}"
        add(f"| **{row['branch']}** | {gi('inverted_pixels')} | {g('tc_p25')} | "
            f"{g('tc_p50')} | {g('tc_p75')} | {gi('tc_ge_0.5')} | {gi('tc_ge_0.6')} | "
            f"{gi('tc_ge_0.7')} | {g('median_velocity_std')} | "
            f"{g('velocity_robust_scatter')} | {g('highpass_energy')} | "
            f"{g('residual_rms')} | {g('cross_pearson')} | {g('cross_spearman')} | "
            f"{g('cross_plane_detrended')} |")
    add("")
    add("Per-zone velocity and `TEMPORAL_COHERENCE` by branch:")
    add("")
    for _, row in table.iterrows():
        hs = row.get("hotspots")
        if not isinstance(hs, dict) or not hs:
            continue
        add(f"* **{row['branch']}** — " + ", ".join(
            f"{hid} {v['velocity']:+.1f} mm/yr (TC {v['tc']:.3f}, n={v['n']})"
            for hid, v in hs.items()))
    add("")

    add("## J. Final descending usability decision")
    add("")
    if skipped:
        add(f"Branches not evaluable in this run: "
            f"{', '.join(f'{k} ({v})' for k, v in skipped.items())}. They are reported "
            f"as not evaluated rather than substituted by a stale clone.")
        add("")
    for branch, info in decisions.items():
        add(f"* **{branch}**: {info['metrics_improved_vs_D0']}/"
            f"{info['metrics_compared']} internal metrics improved vs D0 -> "
            f"{'material' if info['materially_improved'] else 'not material'}")
    add("")
    add(f"Stop rule: a branch is promotable only if it materially improves its **own** "
        f"internal quality (>=4 of 7 metrics), never on cross-track resemblance.")
    add("")
    if promoted:
        add(f"Promoted: **{', '.join(promoted)}** -> `DESCENDING_PRODUCT_V2_CANDIDATE`")
    else:
        add("No branch produced a material, internally supported improvement. The "
            "predeclared conclusion is therefore frozen:")
        add("")
        add("```text")
        add("DESCENDING_PATH136_NOT_SUITABLE_FOR_QUANTITATIVE_INDEPENDENT_VALIDATION_V1")
        add("```")
    add("")
    add("### Protected statuses")
    add("")
    add("H001 remains **PARTIALLY_SUPPORTED**; H002–H005 remain **NOT_RESOLVED**. No "
        "classification was upgraded during diagnostics. These are results of an "
        "*inconclusive validation experiment*, not evidence against the ascending "
        "hotspots.")
    add("")
    add("The Phase II-A vertical/E-W decomposition remains **INVALID and unpublished**. "
        "Its condition number (κ = 1.384) is acceptable, but good matrix conditioning "
        "does not produce a good component estimate from an unreliable input. The "
        "−22 to −74 mm/yr vertical values are diagnostic artefacts.")
    add("")
    add("---")
    add("")
    add("```text")
    add(f"DESCENDING SCIENTIFIC STATUS:")
    add(f"    {'USABLE FOR REVALIDATION' if promoted else 'NOT SUITABLE FOR QUANTITATIVE INDEPENDENT VALIDATION'}")
    add("```")
    add("")
    add("Stopped here. No groundwater, geology, GRACE, urbanisation or other causal "
        "interpretation has been begun.")
    add("")

    REPORT.write_text("\n".join(L) + "\n")
    print(f"\n  {REPORT}")
    print(f"\n  DESCENDING SCIENTIFIC STATUS: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
