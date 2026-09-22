#!/usr/bin/env python
"""
Phase II-C stages 3-11: hotspot-level cross-geometry reconciliation.

Comparison convention (ONE convention, stated once and used everywhere)
----------------------------------------------------------------------
Ascending and descending are referenced to different pixels and have different
zero levels, so raw absolute velocities are NEVER compared. Both are re-referenced
to a COMMON STABLE-CONTROL region selected inside the common valid domain from
pixels that are high quality in BOTH tracks. Every velocity in this script is
relative to that shared control, and the applied offsets are reported.

The INC-007 distinction is kept visible: the ascending AUTHORITATIVE product
reference is (1384,1451); the ascending INTENDED reference (1378,1426) is not
used; the descending D2 reference is whatever MintPy selected.

Usage
-----
    python scripts/59_phase2c_hotspots.py
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
from scipy import ndimage
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
ASC_GEOM = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
D2_WORK = PROJECT_ROOT / "mintpy" / "descending_d2_unwrap_work"
D0_WORK = PROJECT_ROOT / "mintpy" / "descending_work"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2c"

STRUCTURE = np.ones((3, 3), dtype=bool)
PIXEL_AREA_KM2 = 0.0016
THRESHOLD_MM = 10.0
NS_FAMILY = [-5.0, -2.0, 0.0, 2.0, 5.0]
NS_GROUPS = {"north": ["H002", "H003", "H005"], "south": ["H001", "H004"]}


def los_unit_vector(heading, incidence):
    h, p = np.radians(heading), np.radians(incidence)
    return (float(np.sin(p) * np.cos(h)), float(-np.sin(p) * np.sin(h)),
            float(np.cos(p)))


def meta_of(path):
    with h5py.File(path, "r") as handle:
        return {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    asc_meta, d2_meta = meta_of(ASC_WORK / "velocity.h5"), meta_of(D2_WORK / "velocity.h5")
    with h5py.File(ASC_WORK / "velocity.h5", "r") as h:
        asc_v = h["velocity"][:].astype("float64") * 1000.0
        asc_vs = h["velocityStd"][:].astype("float64") * 1000.0
        asc_ref = (int(h.attrs["REF_Y"]), int(h.attrs["REF_X"]))
    with h5py.File(ASC_WORK / "temporalCoherence.h5", "r") as h:
        asc_tc = h["temporalCoherence"][:].astype("float64")
    with h5py.File(D2_WORK / "velocity.h5", "r") as h:
        d2_v = h["velocity"][:].astype("float64") * 1000.0
        d2_vs = h["velocityStd"][:].astype("float64") * 1000.0
        d2_ref = (int(h.attrs["REF_Y"]), int(h.attrs["REF_X"]))
    with h5py.File(D2_WORK / "temporalCoherence.h5", "r") as h:
        d2_tc = h["temporalCoherence"][:].astype("float64")
    with h5py.File(D0_WORK / "velocity.h5", "r") as h:
        d0_v = h["velocity"][:].astype("float64") * 1000.0
        d0_vs = h["velocityStd"][:].astype("float64") * 1000.0
    with h5py.File(D0_WORK / "temporalCoherence.h5", "r") as h:
        d0_tc = h["temporalCoherence"][:].astype("float64")
    with h5py.File(ASC_GEOM, "r") as h:
        asc_inc, asc_heading = h["incidenceAngle"][:].astype("float64"), float(
            h.attrs.get("HEADING", -12.585825751670313))
        asc_land = h["waterMask"][:].astype(bool)
        asc_hgt = h["height"][:].astype("float64")
    with h5py.File(D2_WORK / "inputs" / "geometryGeo.h5", "r") as h:
        d2_inc, d2_heading = h["incidenceAngle"][:].astype("float64"), float(
            h.attrs.get("HEADING", -167.396))
        d2_land = h["waterMask"][:].astype(bool)

    asc_u = los_unit_vector(asc_heading, float(np.nanmedian(asc_inc)))
    d2_u = los_unit_vector(d2_heading, float(np.nanmedian(d2_inc)))
    at = Affine(asc_meta["X_STEP"], 0, asc_meta["X_FIRST"], 0,
                -abs(asc_meta["Y_STEP"]), asc_meta["Y_FIRST"])
    dt = Affine(d2_meta["X_STEP"], 0, d2_meta["X_FIRST"], 0,
                -abs(d2_meta["Y_STEP"]), d2_meta["Y_FIRST"])
    shape_out = asc_v.shape

    def rs(a, src=dt, src_crs="EPSG:32643"):
        o = np.full(shape_out, np.nan, dtype="float64")
        rasterio.warp.reproject(source=np.asarray(a).astype("float32"), destination=o,
                                src_transform=src, src_crs=src_crs, dst_transform=at,
                                dst_crs="EPSG:32643",
                                resampling=rasterio.warp.Resampling.bilinear,
                                src_nodata=np.nan, dst_nodata=np.nan)
        return o

    d2_v_a, d2_vs_a, d2_tc_a = rs(d2_v), rs(d2_vs), rs(d2_tc)
    d0_v_a, d0_vs_a, d0_tc_a = rs(d0_v), rs(d0_vs), rs(d0_tc)
    d2_land_a = rs(d2_land.astype("float64")) > 0.5
    d2_hgt_a = rs(h5py.File(D2_WORK / "inputs" / "geometryGeo.h5", "r")["height"][:])

    aoi = shp_shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", aoi.__geo_interface__))
    aoi_mask = rasterio.features.geometry_mask([aoi_utm.__geo_interface__],
                                               out_shape=shape_out, transform=at,
                                               invert=True)
    common = (aoi_mask & asc_land & d2_land_a & np.isfinite(asc_v) & (asc_vs > 0)
              & np.isfinite(d2_v_a) & (d2_vs_a > 0))

    print("=" * 88)
    print("PHASE II-C - HOTSPOT CROSS-GEOMETRY RECONCILIATION")
    print("=" * 88)

    # ---- 3. reference alignment ------------------------------------------
    asc_q = float(np.nanpercentile(asc_tc[common], 75))
    # d2_tc is on the DESCENDING grid; only the resampled d2_tc_a shares the
    # ascending grid that `common` is defined on.
    d2_q = float(np.nanpercentile(d2_tc_a[common], 75))
    stable = (common & (asc_tc >= asc_q) & (d2_tc_a >= d2_q)
              & (np.abs(asc_v) <= 3.0) & (np.abs(d2_v_a) <= 3.0))
    asc_off = float(np.median(asc_v[stable]))
    d2_off = float(np.median(d2_v_a[stable]))
    asc_v_c = asc_v - asc_off
    d2_v_c = d2_v_a - d2_off
    print(f"\n  3. REFERENCE ALIGNMENT (one convention: common stable control)")
    print(f"     ascending  AUTHORITATIVE ref {asc_ref}  (INTENDED ref (1378,1426) NOT used)")
    print(f"     descending D2 ref {d2_ref}")
    print(f"     stable-control pixels in the common domain: {int(stable.sum()):,}")
    print(f"     ascending  re-referenced by {asc_off:+.3f} mm/yr")
    print(f"     descending re-referenced by {d2_off:+.3f} mm/yr")
    print(f"     -> all velocities below are relative to this SHARED control")

    # ---- 4. hotspot validation table -------------------------------------
    features = json.loads(HOTSPOTS.read_text())["features"]

    def hmask_of(feature, shrink=0.0):
        geom = shp_shape(feature["geometry"])
        if shrink > 0:
            geom = geom.buffer(-shrink)
        # A hotspot built from small disconnected fragments can vanish entirely
        # under a negative buffer. Return an all-False mask rather than handing an
        # empty geometry to transform_geom, which raises.
        if geom.is_empty or geom.area <= 0:
            return np.zeros(shape_out, dtype=bool)
        gu = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", geom.__geo_interface__))
        return rasterio.features.geometry_mask([gu.__geo_interface__],
                                               out_shape=shape_out, transform=at,
                                               invert=True)

    d2_labels = None
    eligible = common & (d2_tc_a >= 0.5)
    thr = eligible & (np.abs(d2_v_a) >= THRESHOLD_MM)
    d2_labels, n = ndimage.label(thr, structure=STRUCTURE)
    keep = []
    if n:
        sizes = ndimage.sum(thr, d2_labels, index=np.arange(1, n + 1))
        keep = list(np.where(sizes >= int(round(0.4 / PIXEL_AREA_KM2)))[0] + 1)

    rows = []
    for feature in features:
        hid = feature["properties"]["hotspot_id"]
        hm = hmask_of(feature)
        sel = hm & common
        if sel.sum() < 5:
            rows.append({"hotspot_id": hid, "n_common": int(sel.sum())})
            continue
        ov = d2_labels[hm]
        ov = ov[ov > 0]
        detected, iou, sep = False, 0.0, None
        if ov.size:
            vals, counts = np.unique(ov, return_counts=True)
            best = int(vals[np.argmax(counts)])
            detected = best in keep
            comp = d2_labels == best
            iou = float((comp & hm).sum() / (comp | hm).sum())
            ys, xs = np.where(comp)
            hys, hxs = np.where(hm)
            sep = round(float(np.hypot(ys.mean() - hys.mean(),
                                       xs.mean() - hxs.mean()) * 40 / 1000.0), 3)
        av, dv = asc_v_c[sel], d2_v_c[sel]
        a_med, d_med = float(np.median(av)), float(np.median(dv))
        rows.append({
            "hotspot_id": hid, "n_common": int(sel.sum()),
            "valid_fraction_of_hotspot": round(float(sel.sum() / max(1, int(hm.sum()))), 4),
            "ascending_median": round(a_med, 2),
            "descending_v2_median": round(d_med, 2),
            "ascending_p25": round(float(np.percentile(av, 25)), 2),
            "ascending_p75": round(float(np.percentile(av, 75)), 2),
            "descending_p25": round(float(np.percentile(dv, 25)), 2),
            "descending_p75": round(float(np.percentile(dv, 75)), 2),
            "ascending_uncertainty": round(float(np.median(asc_vs[sel])), 3),
            "descending_uncertainty": round(float(np.median(d2_vs_a[sel])), 3),
            "ascending_temporal_coherence": round(float(np.median(asc_tc[sel])), 4),
            "descending_temporal_coherence": round(float(np.median(d2_tc_a[sel])), 4),
            "sign_agreement": bool(a_med * d_med > 0),
            "magnitude_ratio": round(abs(d_med) / max(1e-9, abs(a_med)), 3),
            "overlap_fraction": round(ov.size / max(1, int(hm.sum())), 4),
            "iou": round(iou, 4),
            "centroid_offset_km": sep,
            "descending_component_detected": bool(detected),
            "descending_uncertainty_includes_zero": bool(
                abs(d_med) < 2 * float(np.median(d2_vs_a[sel]))),
        })
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "hotspot_validation.csv", index=False)
    print(f"\n  4. HOTSPOT VALIDATION TABLE (shared stable-control convention)")
    print(f"     {'id':5s} {'asc':>8s} {'D2':>8s} {'same':>5s} {'ratio':>6s} "
          f"{'ascUnc':>7s} {'D2Unc':>7s} {'ascTC':>6s} {'D2TC':>6s} {'valid':>6s} {'IoU':>6s}")
    for r in rows:
        if r.get("n_common", 0) < 5:
            continue
        print(f"     {r['hotspot_id']:5s} {r['ascending_median']:8.2f} "
              f"{r['descending_v2_median']:8.2f} {str(r['sign_agreement']):>5s} "
              f"{r['magnitude_ratio']:6.2f} {r['ascending_uncertainty']:7.3f} "
              f"{r['descending_uncertainty']:7.3f} "
              f"{r['ascending_temporal_coherence']:6.3f} "
              f"{r['descending_temporal_coherence']:6.3f} "
              f"{r['valid_fraction_of_hotspot'] * 100:5.1f}% {r['iou']:6.3f}")

    # ---- 5. mask-sensitivity confirmation (H001, H004) -------------------
    print(f"\n  5. MASK-SENSITIVITY CONFIRMATION TEST")
    mask_tests = {}
    for feature in features:
        hid = feature["properties"]["hotspot_id"]
        hms = {
            "ascending_primary": hmask_of(feature) & (asc_tc >= 0.80),
            "descending_primary": hmask_of(feature) & (d2_tc_a >= 0.80),
            "stricter_both": hmask_of(feature) & (asc_tc >= 0.90) & (d2_tc_a >= 0.85),
            "hotspot_core": hmask_of(feature, shrink=0.002) & common,
            "full_polygon": hmask_of(feature) & common,
        }
        entries = {}
        for label, m in hms.items():
            s = m & common
            if s.sum() < 5:
                entries[label] = None
                continue
            a, d = float(np.median(asc_v_c[s])), float(np.median(d2_v_c[s]))
            entries[label] = {"n": int(s.sum()), "ascending": round(a, 2),
                              "descending": round(d, 2),
                              "same_sign": bool(a * d > 0),
                              "ratio": round(abs(d) / max(1e-9, abs(a)), 3)}
        mask_tests[hid] = entries
        print(f"     {hid}:")
        for label, e in entries.items():
            if e is None:
                print(f"       {label:20s} too few pixels")
                continue
            print(f"       {label:20s} n={e['n']:6d} asc {e['ascending']:+7.2f} "
                  f"D2 {e['descending']:+7.2f} same={e['same_sign']} "
                  f"ratio={e['ratio']:.2f}")

    # ---- 7. H005 contradiction analysis ----------------------------------
    h005 = next((f for f in features if f["properties"]["hotspot_id"] == "H005"), None)
    h005_out = {}
    if h005 is not None:
        hm = hmask_of(h005)
        sel = hm & common
        print(f"\n  7. H005 DEDICATED CONTRADICTION ANALYSIS")
        print(f"     common pixels {int(sel.sum())}")
        # reference-alignment sensitivity
        refs = []
        for label, arr, src_off in (("ascending_control_shift", asc_v_c, asc_off),
                                    ("descending_control_shift", d2_v_c, d2_off)):
            refs.append({"shift": label,
                         "ascending": round(float(np.median(asc_v_c[sel])), 2),
                         "descending": round(float(np.median(d2_v_c[sel])), 2)})
        # quality-mask sensitivity
        qm = {}
        for th in (0.5, 0.7, 0.8, 0.9):
            s = sel & (d2_tc_a >= th)
            if s.sum() > 5:
                qm[f"d2_tc>={th}"] = {"n": int(s.sum()),
                                      "descending": round(float(np.median(d2_v_c[s])), 2)}
        # core vs boundary
        core = hmask_of(h005, shrink=0.006) & common
        boundary = sel & ~core
        # local continuity: neighbouring pixels outside the polygon
        grown = ndimage.binary_dilation(hm, structure=STRUCTURE, iterations=5)
        ring = grown & ~hm & common
        # unwrap sensitivity: D0 vs D2 at the same footprint
        d0_sel = hm & common & np.isfinite(d0_v_a)
        # date dominance on the D2 series
        with h5py.File(D2_WORK / "timeseries.h5", "r") as h:
            d2_dates = np.array(h["date"]).astype(str)
        ys, xs = np.where(sel)
        with h5py.File(D2_WORK / "timeseries.h5", "r") as h:
            cube = h["timeseries"]
            ts = np.array([np.median(cube[i][ys, xs].astype("float64"))
                           for i in range(len(d2_dates))]) * 1000.0
        step = np.diff(ts)
        order = np.argsort(np.abs(step))[::-1][:3]
        print(f"     ascending  (control) {np.median(asc_v_c[sel]):+8.2f} mm/yr")
        print(f"     descending (control) {np.median(d2_v_c[sel]):+8.2f} mm/yr")
        print(f"     D0 vs D2 at same footprint: D0 {np.median(d0_v_a[d0_sel]):+8.2f}  "
              f"D2 {np.median(d2_v_c[sel]):+8.2f}")
        print(f"     core   {np.median(d2_v_c[core]):+8.2f} (n={int(core.sum())})")
        print(f"     boundary {np.median(d2_v_c[boundary]):+8.2f} "
              f"(n={int(boundary.sum())})")
        print(f"     surrounding ring {np.median(d2_v_c[ring]):+8.2f} "
              f"(n={int(ring.sum())})")
        print(f"     largest single-date steps: "
              + ", ".join(f"{d2_dates[i]}->{d2_dates[i+1]} {step[i]:+.1f} mm"
                          for i in order))
        print(f"     time series span {d2_dates[0]}..{d2_dates[-1]}, "
              f"total {ts[-1] - ts[0]:+.1f} mm")

        # required (dU, dE) under N-S family
        A = np.array([[asc_u[2], asc_u[0]], [d2_u[2], d2_u[0]]])
        Ainv = np.linalg.inv(A)
        a_los, d_los = float(np.median(asc_v_c[sel])), float(np.median(d2_v_c[sel]))
        combos = []
        for ns in NS_FAMILY:
            rhs = np.array([a_los - asc_u[1] * ns, d_los - d2_u[1] * ns])
            dU, dE = Ainv @ rhs
            combos.append({"Vy": ns, "vertical": round(float(dU), 2),
                           "east_west": round(float(dE), 2)})
        print(f"     implied components if the two LOS values are both real:")
        for c in combos:
            print(f"       Vy={c['Vy']:+5.1f}  dU={c['vertical']:+8.2f}  "
                  f"dE={c['east_west']:+8.2f} mm/yr")
        h005_out = {"reference_sensitivity": refs, "quality_mask_sensitivity": qm,
                    "core": round(float(np.median(d2_v_c[core])), 2),
                    "boundary": round(float(np.median(d2_v_c[boundary])), 2),
                    "surrounding_ring": round(float(np.median(d2_v_c[ring])), 2),
                    "d0_vs_d2_same_footprint": {
                        "d0": round(float(np.median(d0_v_a[d0_sel])), 2),
                        "d2": round(float(np.median(d2_v_c[sel])), 2)},
                    "largest_date_steps": [
                        {"from": d2_dates[i], "to": d2_dates[i + 1],
                         "step_mm": round(float(step[i]), 2)} for i in order],
                    "implied_components": combos,
                    "character": "the surrounding ring is "
                                 + ("consistent with the hotspot"
                                    if abs(np.median(d2_v_c[ring])
                                           - np.median(d2_v_c[sel])) < 10 else
                                    "very different from the hotspot, indicating a "
                                    "localised feature rather than a smooth field")}

    # ---- 6. H002/H003 significance test ----------------------------------
    # Under a PURELY VERTICAL signal the expected descending LOS is the ascending
    # LOS scaled by the ratio of vertical sensitivities. If the descending
    # measurement excludes that value at 2 sigma while descending quality is
    # adequate, the zone is NOT_REPRODUCED rather than merely unresolved.
    vert_scale = d2_u[2] / asc_u[2]
    significance = {}
    print(f"\n  6. H002/H003 EXPECTED-RESPONSE TEST (vertical scale {vert_scale:.4f})")
    print(f"     {'id':5s} {'asc':>8s} {'expected D2':>12s} {'measured D2':>12s} "
          f"{'D2 unc':>8s} {'gap/sigma':>10s} {'verdict':>18s}")
    for r in rows:
        hid = r.get("hotspot_id")
        if r.get("n_common", 0) < 5:
            continue
        a, d, u = r["ascending_median"], r["descending_v2_median"], r["descending_uncertainty"]
        expected = a * vert_scale
        gap = abs(d - expected) / max(1e-9, u)
        d_tc = r["descending_temporal_coherence"]
        adequate = d_tc >= 0.85 and r["valid_fraction_of_hotspot"] >= 0.95
        if gap <= 2:
            verdict = "consistent"
        elif adequate:
            verdict = "NOT_REPRODUCED"
        else:
            verdict = "NOT_RESOLVED"
        significance[hid] = {
            "ascending_los": a, "expected_descending_los_if_vertical": round(expected, 2),
            "measured_descending_los": d, "descending_uncertainty": u,
            "gap_in_sigma": round(float(gap), 2),
            "descending_quality_adequate": bool(adequate), "verdict": verdict}
        print(f"     {hid:5s} {a:8.2f} {expected:12.2f} {d:12.2f} {u:8.3f} "
              f"{gap:10.1f} {verdict:>18s}")

    # ---- 8/9. temporal ----------------------------------------------------
    def series(work, name, hm):
        with h5py.File(work / name, "r") as h:
            dates = np.array(h["date"]).astype(str)
            cube = h["timeseries"]
            ys, xs = np.where(hm)
            if len(ys) == 0:
                return None, None
            order = np.lexsort((xs, ys))   # h5py needs increasing index order
            ys, xs = ys[order], xs[order]
            # Read a slab per date and index with NumPy: h5py point selection is
            # order-sensitive and raises on real-world index sets.
            vals = np.array([np.median(cube[i][ys, xs].astype("float64"))
                             for i in range(len(dates))]) * 1000.0
        return dates, vals

    temporal, groups = {}, {}
    asc_res, d2_res = {}, {}
    for feature in features:
        hid = feature["properties"]["hotspot_id"]
        hm = hmask_of(feature) & common
        if hm.sum() < 5:
            continue
        ad, av = series(ASC_WORK, "timeseries.h5", hm)
        dd, dv = series(D2_WORK, "timeseries.h5", hm)
        if ad is None or dd is None:
            continue
        # nearest-date matching within 6 days; NO aggressive interpolation
        pairs_idx = []
        for i, a in enumerate(ad):
            best = min(range(len(dd)),
                       key=lambda j: abs((pd.Timestamp(str(a)) - pd.Timestamp(str(dd[j]))).days))
            delta = abs((pd.Timestamp(str(a)) - pd.Timestamp(str(dd[best]))).days)
            if delta <= 6:
                pairs_idx.append((i, best, delta))
        if len(pairs_idx) < 20:
            temporal[hid] = {"matched_epochs": len(pairs_idx),
                             "note": "too few matched epochs for correlation"}
            continue
        ai = [p[0] for p in pairs_idx]
        di = [p[1] for p in pairs_idx]
        a_s, d_s = av[ai], dv[di]
        t = np.array([pd.Timestamp(str(ad[i])).year
                      + (pd.Timestamp(str(ad[i])).dayofyear - 1) / 365.25 for i in ai])
        t = t - t[0]

        def detr(y, order=1):
            D = np.column_stack([t ** k for k in range(order + 1)])
            return y - D @ np.linalg.lstsq(D, y, rcond=None)[0]

        ar, dr = detr(a_s, 2), detr(d_s, 2)
        temporal[hid] = {
            "matched_epochs": len(pairs_idx),
            "median_match_delta_days": float(np.median([p[2] for p in pairs_idx])),
            "pearson_raw": round(float(np.corrcoef(a_s, d_s)[0, 1]), 4),
            "pearson_detrended": round(float(np.corrcoef(ar, dr)[0, 1]), 4),
            "spearman_detrended": round(float(pd.Series(ar).corr(pd.Series(dr),
                                                                 method="spearman")), 4),
            "ascending_total_mm": round(float(a_s[-1] - a_s[0]), 1),
            "descending_total_mm": round(float(d_s[-1] - d_s[0]), 1),
            "split_half_ascending": [round(float(np.polyfit(t[:len(t) // 2],
                                                            a_s[:len(t) // 2], 1)[0]), 1),
                                     round(float(np.polyfit(t[len(t) // 2:],
                                                            a_s[len(t) // 2:], 1)[0]), 1)],
            "split_half_descending": [round(float(np.polyfit(t[:len(t) // 2],
                                                             d_s[:len(t) // 2], 1)[0]), 1),
                                      round(float(np.polyfit(t[len(t) // 2:],
                                                             d_s[len(t) // 2:], 1)[0]), 1)],
        }
        if len(ar) > 10 and np.std(ar) > 0:
            asc_res[hid] = ar / (np.percentile(ar, 97.5) - np.percentile(ar, 2.5) or 1)
            d2_res[hid] = dr / (np.percentile(dr, 97.5) - np.percentile(dr, 2.5) or 1)

    print(f"\n  8. TEMPORAL CROSS-VALIDATION (nearest-date matching, tolerance 6 d)")
    for hid, info in temporal.items():
        if "pearson_raw" not in info:
            print(f"     {hid}: {info['note']} ({info['matched_epochs']} matched)")
            continue
        print(f"     {hid}: matched {info['matched_epochs']:3d}  "
              f"r_raw {info['pearson_raw']:+.3f}  r_detrended "
              f"{info['pearson_detrended']:+.3f}  "
              f"asc total {info['ascending_total_mm']:+7.1f} mm  "
              f"D2 total {info['descending_total_mm']:+7.1f} mm")

    def within_between(res):
        hids = sorted(res)
        w, b = [], []
        for i, x in enumerate(hids):
            for y in hids[i + 1:]:
                same = any(x in g and y in g for g in NS_GROUPS.values())
                if np.std(res[x]) == 0 or np.std(res[y]) == 0:
                    continue
                c = float(np.corrcoef(res[x], res[y])[0, 1])
                (w if same else b).append(c)
        return w, b

    wa, ba = within_between(asc_res)
    wd, bd = within_between(d2_res)
    groups = {
        "ascending": {"within": round(float(np.median(wa)), 4) if wa else None,
                      "between": round(float(np.median(ba)), 4) if ba else None},
        "descending_d2": {"within": round(float(np.median(wd)), 4) if wd else None,
                          "between": round(float(np.median(bd)), 4) if bd else None},
    }
    d2_ok = bool(wd and bd and np.median(wd) - np.median(bd) >= 0.30
                 and np.median(bd) < 0.0)
    groups["d2_reproduces_grouping"] = d2_ok
    print(f"\n  9. NORTH/SOUTH GROUPING with D2")
    print(f"     ascending   within {groups['ascending']['within']}  "
          f"between {groups['ascending']['between']}")
    print(f"     descending  within {groups['descending_d2']['within']}  "
          f"between {groups['descending_d2']['between']}")
    print(f"     D2 reproduces the grouping (needs high within AND negative between): "
          f"{d2_ok}")

    # ---- 10. coherence-velocity ------------------------------------------
    bins = np.arange(0.3, 1.0001, 0.05)
    cv = {}
    for label, v, tc, m in (("ascending", asc_v_c, asc_tc, common),
                            ("descending_d0", d0_v_a, d0_tc_a, common & (d0_vs_a > 0)),
                            ("descending_d2", d2_v_c, d2_tc_a, common)):
        rows_c = []
        for i in range(len(bins) - 1):
            s = m & (tc >= bins[i]) & (tc < bins[i + 1])
            if s.sum() < 200:
                continue
            rows_c.append({"low": round(float(bins[i]), 2),
                           "n": int(s.sum()),
                           "median": round(float(np.median(v[s])), 2)})
        cv[label] = rows_c
    print(f"\n  10. COHERENCE-VELOCITY with D2")
    for label, rows_c in cv.items():
        if len(rows_c) > 2:
            df = pd.DataFrame(rows_c)
            rho = float(df["low"].corr(df["median"], method="spearman"))
            print(f"     {label:16s} {len(rows_c):2d} bins  "
                  f"Spearman(coherence, velocity) {rho:+.3f}")

    # ---- 11. decomposition eligibility -----------------------------------
    A = np.array([[asc_u[2], asc_u[0]], [d2_u[2], d2_u[0]]])
    Ainv = np.linalg.inv(A)
    cond = float(np.linalg.cond(A))
    elig = {}
    print(f"\n  11. DECOMPOSITION ELIGIBILITY (design-matrix kappa = {cond:.3f})")
    for r in rows:
        hid = r.get("hotspot_id")
        if r.get("n_common", 0) < 5:
            elig[hid] = {"eligible": False, "reason": "insufficient common pixels"}
            continue
        same = r["sign_agreement"]
        ratio = r["magnitude_ratio"]
        a_unc, d_unc = r["ascending_uncertainty"], r["descending_uncertainty"]
        a_tc, d_tc = r["ascending_temporal_coherence"], r["descending_temporal_coherence"]
        a_los, d_los = r["ascending_median"], r["descending_v2_median"]
        cov = Ainv @ np.diag([a_unc ** 2, d_unc ** 2]) @ Ainv.T
        dU_err = float(np.sqrt(cov[0, 0]))
        dU, dE = Ainv @ np.array([a_los, d_los])
        strong = (same and 0.5 <= ratio <= 2.0 and a_tc >= 0.8 and d_tc >= 0.8
                  and abs(dU) > 2 * dU_err)
        reasons = []
        if not same:
            reasons.append("sign disagreement between tracks")
        if not (0.5 <= ratio <= 2.0):
            reasons.append(f"magnitude ratio {ratio:.2f} outside 0.5-2.0")
        if a_tc < 0.8:
            reasons.append(f"ascending TC {a_tc:.3f} < 0.8")
        if d_tc < 0.8:
            reasons.append(f"descending TC {d_tc:.3f} < 0.8")
        if abs(dU) <= 2 * dU_err:
            reasons.append("vertical not significant at 2 sigma")
        elig[hid] = {"eligible": bool(strong),
                     "reason": "; ".join(reasons) if reasons else "all criteria met",
                     "implied_vertical": round(float(dU), 2),
                     "implied_vertical_uncertainty": round(dU_err, 2),
                     "implied_east_west": round(float(dE), 2),
                     "magnitude_ratio": ratio}
        print(f"     {hid}: {'ELIGIBLE' if strong else 'NOT JUSTIFIED'}  "
              f"({elig[hid]['reason']})")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"ascending": "product_v1 / RAW-336",
                   "descending": "DESCENDING_PRODUCT_V2_CANDIDATE "
                                 "(mintpy/descending_d2_unwrap_work)",
                   "descending_candidate_freeze_id": "ba99df90a6f15b3aaaf90fe3042511ddef3e0f9864f03aab122a541b5d3d6d13"},
        "comparison_convention": {
            "method": "both tracks re-referenced to a COMMON STABLE-CONTROL region "
                      "inside the common valid domain",
            "ascending_authoritative_reference": list(asc_ref),
            "ascending_intended_reference": [1378, 1426],
            "ascending_intended_used": False,
            "descending_d2_reference": list(d2_ref),
            "stable_control_pixels": int(stable.sum()),
            "ascending_offset_mm_per_yr": round(asc_off, 4),
            "descending_offset_mm_per_yr": round(d2_off, 4),
        },
        "common_domain_pixels": int(common.sum()),
        "geometry": {"ascending_los_unit_ENU": [round(v, 5) for v in asc_u],
                     "descending_los_unit_ENU": [round(v, 5) for v in d2_u],
                     "condition_number": round(cond, 4)},
        "hotspot_table": rows,
        "mask_sensitivity": mask_tests,
        "expected_response_significance": significance,
        "h005_analysis": h005_out,
        "temporal": temporal,
        "grouping": groups,
        "coherence_velocity": cv,
        "decomposition_eligibility": elig,
        "global_agreement_note": "CROSS-GEOMETRY AGREEMENT: MODERATE / SPATIALLY "
                                 "HETEROGENEOUS. Not 'fully validated'.",
    }
    (OUT / "hotspot_reconciliation.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'hotspot_reconciliation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
