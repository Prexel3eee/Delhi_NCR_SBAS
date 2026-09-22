#!/usr/bin/env python
"""
Phase II-B closeout: ERA5 coverage gate by DATE IDENTITY, D3/D2 evaluation, and
the final descending-usability freeze.

Coverage is proved by SET IDENTITY, never by a file count. A cached file, a
differently-mapped epoch, or a single missing date would all be invisible to a
count.

Usage
-----
    python scripts/55_phase2b_closeout.py --coverage-gate
    python scripts/55_phase2b_closeout.py --evaluate
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
import rasterio.warp
from rasterio.transform import Affine
from rasterio.warp import transform_geom
from scipy.ndimage import uniform_filter
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
ASC_GEOM = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
MANIFEST_DIR = PROJECT_ROOT / "manifests" / "descending"
WEATHER = PROJECT_ROOT / "mintpy" / "era5_work" / "mintpy" / "weather" / "ERA5"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2b"
REPORT = PROJECT_ROOT / "qc" / "sci" / "PHASE_IIB_DESCENDING_RELIABILITY_REPORT.md"
FREEZE_CLOSEOUT = PROJECT_ROOT / "freeze" / "phase2b_closeout_v1"
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


def coverage_gate() -> int:
    accepted = pd.read_csv(MANIFEST_DIR / "accepted_acquisitions.csv")
    pairs = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv", dtype={
        "reference_date": str, "secondary_date": str})
    stack_dates = sorted({d for a, b in zip(pairs["reference_date"], pairs["secondary_date"])
                          for d in (a.replace("-", ""), b.replace("-", ""))})
    accepted_dates = sorted(d.replace("-", "") for d in accepted["date"])

    pattern = re.compile(r"ERA5_N\d+_N\d+_E\d+_E\d+_(\d{8})_(\d{2})\.grb$")
    gribs = sorted(WEATHER.rglob("*.grb")) + sorted(WEATHER.rglob("*.grib"))
    found = {}
    for path in gribs:
        match = pattern.search(path.name)
        if match:
            found.setdefault(match.group(1), []).append(match.group(2))

    expected = set(stack_dates)
    hours = sorted({h for v in found.values() for h in v})

    print("=" * 88)
    print("D3 ERA5 COMPLETION GATE - PROVED BY DATE IDENTITY, NOT BY FILE COUNT")
    print("=" * 88)
    print(f"\n  accepted descending acquisitions : {len(accepted_dates)}")
    print(f"  dates actually in the frozen stack: {len(stack_dates)} "
          f"(1 acquisition dropped as unconnectable: 2024-04-13)")
    print(f"  ERA5 GRIB files on disk           : {len(gribs)}")
    print(f"  ERA5 hours present                : {hours}")
    print(f"  expected descending dates         : {len(expected)}")

    # The ERA5 cache is SHARED with the ascending product, which samples a
    # different UTC hour. A naive all-files set comparison therefore reports the
    # 119 ascending dates as "unexpected" and hides the real answer. The gate is
    # evaluated PER HOUR, and the descending hour is the one whose date set
    # matches the frozen stack exactly.
    per_hour = {}
    for hour in hours:
        represented = {d for d, hh in found.items() if hour in hh}
        per_hour[hour] = {
            "represented": len(represented),
            "missing": sorted(expected - represented),
            "unexpected": sorted(represented - expected),
        }
    print(f"\n  per-hour date-identity check:")
    for hour in hours:
        info = per_hour[hour]
        state = "EXACT" if not info["missing"] and not info["unexpected"] else "mismatch"
        print(f"    hour {hour}: represented {info['represented']:4d}  "
              f"missing {len(info['missing']):4d}  unexpected {len(info['unexpected']):4d}  "
              f"{state}")
    exact = [h for h in hours if not per_hour[h]["missing"]
             and not per_hour[h]["unexpected"]]
    descending_hour = exact[0] if exact else None
    if descending_hour:
        missing = per_hour[descending_hour]["missing"]
        unexpected = per_hour[descending_hour]["unexpected"]
        represented_set = {d for d, hh in found.items() if descending_hour in hh}
        print(f"\n  -> descending ERA5 hour identified: {descending_hour} "
              f"(set-identical to the frozen stack)")
        print(f"  MISSING    : {len(missing)}  {missing[:10]}")
        print(f"  UNEXPECTED : {len(unexpected)}  {unexpected[:10]}")
        ok = True
    else:
        best = min(hours, key=lambda h: len(per_hour[h]["missing"])) if hours else None
        missing = per_hour[best]["missing"] if best else sorted(expected)
        unexpected = per_hour[best]["unexpected"] if best else []
        represented_set = set()
        print(f"\n  -> no hour is set-identical. Closest is hour {best} with "
              f"{len(missing)} missing.")
        print(f"  MISSING    : {len(missing)}  {missing[:10]}")
        ok = False
    print(f"\n  DATE-IDENTITY COVERAGE: {'PASSED' if ok else 'FAILED'}")

    # finite correction over the AOI domain, not the whole rectangle
    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "accepted_descending_acquisitions": len(accepted_dates),
        "dates_in_frozen_stack": len(stack_dates),
        "dropped_acquisition": "2024-04-13",
        "era5_grib_files": len(gribs),
        "era5_hours_present": hours,
        "per_hour_check": per_hour,
        "descending_era5_hour": descending_hour,
        "expected_dates": len(expected),
        "missing_dates": missing,
        "unexpected_dates": unexpected,
        "date_identity_passed": ok,
        "method": "GRIB filenames parsed for YYYYMMDD and compared as a SET against the "
                  "dates appearing in the frozen pair manifest; a file count is not "
                  "accepted as evidence",
    }
    (OUT / "era5_coverage_gate.json").write_text(json.dumps(result, indent=2, default=str))
    print(f"\n  {OUT / 'era5_coverage_gate.json'}")
    return 0 if ok else 1


def metrics(work: Path, asc_v, asc_meta, domain_asc, hotspots, stable_mask):
    with h5py.File(work / "velocity.h5", "r") as handle:
        v = handle["velocity"][:].astype("float64") * 1000.0
        vs = handle["velocityStd"][:].astype("float64") * 1000.0
        residue = handle["residue"][:].astype("float64")
        ref = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
    with h5py.File(work / "temporalCoherence.h5", "r") as handle:
        tc = handle["temporalCoherence"][:].astype("float64")
    inverted = vs > 0
    out = {"branch": work.name, "inverted_pixels": int(inverted.sum()),
           "reference_yx": list(ref)}
    if inverted.sum() == 0:
        return out
    tcv = tc[inverted]
    out.update({
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
    })
    filled = np.where(inverted, v, np.nan)
    filled = np.where(inverted, v, np.nanmedian(filled))
    hp = (v - uniform_filter(filled, size=3, mode="nearest"))[inverted]
    hp = hp[np.isfinite(hp)]
    out["highpass_energy"] = round(float(1.4826 * np.median(np.abs(hp - np.median(hp)))), 4)

    dm = meta_of(work / "velocity.h5")
    at = Affine(asc_meta["X_STEP"], 0, asc_meta["X_FIRST"], 0,
                -abs(asc_meta["Y_STEP"]), asc_meta["Y_FIRST"])
    dt = Affine(dm["X_STEP"], 0, dm["X_FIRST"], 0, -abs(dm["Y_STEP"]), dm["Y_FIRST"])

    def resample(array):
        o = np.full(asc_v.shape, np.nan, dtype="float64")
        rasterio.warp.reproject(source=array.astype("float32"), destination=o,
                                src_transform=dt, src_crs="EPSG:32643",
                                dst_transform=at, dst_crs="EPSG:32643",
                                resampling=rasterio.warp.Resampling.bilinear,
                                src_nodata=np.nan, dst_nodata=np.nan)
        return o

    v_a, vs_a, tc_a, res_a = resample(v), resample(vs), resample(tc), resample(residue)
    sel = domain_asc & np.isfinite(asc_v) & np.isfinite(v_a) & (vs_a > 0)
    if sel.sum() > 500:
        a, d = asc_v[sel], v_a[sel]
        ys, xs = np.where(sel)
        A = np.column_stack([np.ones_like(ys, dtype=float), ys, xs])
        pa = a - A @ np.linalg.lstsq(A, a, rcond=None)[0]
        pd_ = d - A @ np.linalg.lstsq(A, d, rcond=None)[0]
        out.update({
            "common_pixels": int(sel.sum()),
            "cross_pearson": round(float(np.corrcoef(a, d)[0, 1]), 4),
            "cross_spearman": round(float(pd.Series(a).corr(pd.Series(d),
                                                            method="spearman")), 4),
            "cross_plane_detrended": round(float(np.corrcoef(pa, pd_)[0, 1]), 4),
            "descending_scatter_common": round(float(d.std()), 3),
        })
    s_stable = sel & stable_mask
    if s_stable.sum() > 500:
        out["stable_area_scatter"] = round(float(v_a[s_stable].std()), 3)
    # residual vs elevation
    if (work / "inputs" / "geometryGeo.h5").exists():
        with h5py.File(work / "inputs" / "geometryGeo.h5", "r") as handle:
            hgt = resample(handle["height"][:].astype("float64"))
        r = sel & np.isfinite(hgt) & np.isfinite(res_a)
        if r.sum() > 500:
            out["resid_elevation_corr"] = round(float(pd.Series(res_a[r]).corr(
                pd.Series(hgt[r]), method="spearman")), 4)
    hs = {}
    for hid, geom in (hotspots or {}).items():
        gu = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", geom.__geo_interface__))
        hm = rasterio.features.geometry_mask([gu.__geo_interface__], out_shape=asc_v.shape,
                                             transform=at, invert=True)
        s = hm & np.isfinite(v_a) & (vs_a > 0)
        if s.sum() > 10:
            hs[hid] = {"n": int(s.sum()),
                       "velocity": round(float(np.median(v_a[s])), 2),
                       "tc": round(float(np.median(tc_a[s])), 4),
                       "velocity_std": round(float(np.median(vs_a[s])), 3)}
    out["hotspots"] = hs
    return out


def evaluate() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    asc_meta = meta_of(ASC_WORK / "velocity.h5")
    with h5py.File(ASC_WORK / "velocity.h5", "r") as handle:
        asc_v = handle["velocity"][:].astype("float64") * 1000.0
    # temporal coherence lives in its own file, not inside velocity.h5
    with h5py.File(ASC_WORK / "temporalCoherence.h5", "r") as handle:
        asc_tc = handle["temporalCoherence"][:].astype("float64")
    domain_asc = np.load(PROJECT_ROOT / "qc" / "sci" / "phase2"
                         / "common_domain_mask.npz")["domain"]
    hotspots = {f["properties"]["hotspot_id"]: shp_shape(f["geometry"])
                for f in json.loads(HOTSPOTS.read_text())["features"]}
    stable_mask = domain_asc & (asc_tc >= np.nanpercentile(asc_tc[domain_asc], 75))

    print("=" * 88)
    print("PHASE II-B CLOSEOUT - BRANCH EVALUATION")
    print("=" * 88)
    d0_vel = BRANCHES["D0_RAW"] / "velocity.h5"
    rows, available, skipped = [], [], {}
    for label, work in BRANCHES.items():
        vel = work / "velocity.h5"
        if not vel.exists():
            skipped[label] = "NOT EVALUATED - never run"
            print(f"\n  {label}: NOT EVALUATED (never run) - not 'rejected'")
            continue
        if work != BRANCHES["D0_RAW"] and vel.stat().st_mtime <= d0_vel.stat().st_mtime:
            skipped[label] = "INCOMPLETE - output is still the cloned D0"
            print(f"\n  {label}: INCOMPLETE (output still the cloned D0); excluded")
            continue
        print(f"\n  {label}: evaluating ...")
        rows.append(metrics(work, asc_v, asc_meta, domain_asc, hotspots, stable_mask))
        available.append(label)

    table = pd.DataFrame(rows)
    table.to_csv(OUT / "branch_comparison.csv", index=False)
    cols = ["branch", "inverted_pixels", "tc_p25", "tc_p50", "tc_p75", "tc_ge_0.5",
            "tc_ge_0.6", "tc_ge_0.7", "median_velocity_std", "velocity_robust_scatter",
            "highpass_energy", "residual_rms", "resid_elevation_corr",
            "stable_area_scatter", "cross_pearson", "cross_spearman",
            "cross_plane_detrended"]
    cols = [c for c in cols if c in table.columns]
    print(f"\n  TABLE")
    print("    " + " ".join(f"{c[:10]:>10s}" for c in cols))
    for _, row in table.iterrows():
        print("    " + " ".join(
            f"{row[c]:>10.4f}" if isinstance(row.get(c), float) else
            f"{str(row.get(c, '-')):>10s}" for c in cols))

    internal = ["tc_p50", "tc_ge_0.5", "tc_ge_0.7", "median_velocity_std",
                "velocity_robust_scatter", "highpass_energy", "residual_rms"]
    decisions = {}
    d0 = table[table["branch"] == "descending_work"]
    if len(d0):
        d0r = d0.iloc[0]
        for _, row in table.iterrows():
            if row["branch"] == "descending_work":
                continue
            detail = {}
            for m in internal:
                old, new = d0r.get(m), row.get(m)
                if old is None or new is None or pd.isna(old) or pd.isna(new):
                    continue
                higher_better = m.startswith("tc")
                detail[m] = bool((new > old) if higher_better else (new < old))
            n = sum(detail.values())
            decisions[row["branch"]] = {
                "metrics_improved_vs_D0": n, "metrics_compared": len(detail),
                "detail": detail, "materially_improved": bool(n >= 4)}
    promoted = [b for b, i in decisions.items() if i["materially_improved"]]
    status = "CANDIDATE FOR REVALIDATION" if promoted else \
        "NOT SUITABLE FOR QUANTITATIVE INDEPENDENT VALIDATION"

    print(f"\n  STOP RULE (>=4 of 7 descending-INTERNAL metrics; cross-track is NOT a criterion)")
    for b, i in decisions.items():
        print(f"    {b}: {i['metrics_improved_vs_D0']}/{i['metrics_compared']} -> "
              f"{'MATERIAL' if i['materially_improved'] else 'not material'}")
        print(f"      {i['detail']}")
    for b, why in skipped.items():
        print(f"    {b}: {why}")
    print(f"\n  D3-D0 change:")
    if "D3_ERA5" in available:
        d3 = table[table["branch"].str.contains("d3")].iloc[0]
        d0r = d0.iloc[0]
        for m in internal + ["cross_pearson", "cross_spearman"]:
            if m in table.columns and pd.notna(d0r.get(m)) and pd.notna(d3.get(m)):
                print(f"    {m:26s} {d0r[m]:>10.4f} -> {d3[m]:>10.4f}  "
                      f"({d3[m] - d0r[m]:+.4f})")
    else:
        print("    D3 not available")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "branches_evaluated": available, "branches_skipped": skipped,
        "branch_table": rows, "stop_rule": decisions, "promoted": promoted,
        "descending_scientific_status": status,
        "procedure_amendment": "D2 was NOT EVALUATED. Connected-component fragmentation "
                               "(81.33% of inverted pixels outside the retained set) was "
                               "the dominant MEASURED issue and no closure-error evidence "
                               "had justified an unwrap-correction branch. An unrun branch "
                               "is recorded as NOT EVALUATED, never as rejected.",
        "protected_conclusions": {
            "H001": "PARTIALLY_SUPPORTED", "H002": "NOT_RESOLVED", "H003": "NOT_RESOLVED",
            "H004": "NOT_RESOLVED", "H005": "NOT_RESOLVED",
            "coherence_velocity": "REPRODUCED ASSOCIATION",
            "physical_origin": "UNRESOLVED",
            "north_south_grouping": "NOT REPRODUCED",
            "spatial_gradients": "NOT REPRODUCED",
            "decomposition": "INVALID / UNPUBLISHED"},
        "disconnected_support_finding": {
            "fraction_outside_connected_set": 0.8133,
            "classification": "STRUCTURAL QUALITY PROBLEM IDENTIFIED; SIMPLE "
                              "CONNECTED-COMPONENT MASKING NOT SUFFICIENT",
            "not_inferred": "the disconnected pixels alone did NOT cause the descending "
                            "failure - D1 masked them and the velocity field got worse"},
        "quality_conditioned_conclusion": "NO EVIDENCE THAT A SIMPLE QUALITY THRESHOLD "
                                          "RECOVERS THE ASCENDING SPATIAL FIELD "
                                          "(r rises only 0.107 -> 0.205). This is NOT a "
                                          "claim that TEMPORAL_COHERENCE is not a quality "
                                          "metric - that would be too broad.",
    }
    (OUT / "closeout_evaluation.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  DESCENDING SCIENTIFIC STATUS: {status}")
    print(f"  {OUT / 'closeout_evaluation.json'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--coverage-gate", action="store_true")
    group.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    return coverage_gate() if args.coverage_gate else evaluate()


if __name__ == "__main__":
    raise SystemExit(main())
