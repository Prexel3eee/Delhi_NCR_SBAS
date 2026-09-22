#!/usr/bin/env python
"""
Phase II-B Outcome B: repeat the Phase-IIA validation comparisons ONCE against
the promoted branch D2 (DESCENDING_PRODUCT_V2_CANDIDATE).

Only the comparisons are repeated. No further tuning is authorised, and the
frozen Phase-IIA result set is left untouched - this writes a separate,
clearly-labelled V2 comparison.

Usage
-----
    python scripts/57_desc2_revalidation.py
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
DESC2 = PROJECT_ROOT / "mintpy" / "descending_d2_unwrap_work"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2b"

STRUCTURE = np.ones((3, 3), dtype=bool)
THRESHOLD_MM = 10.0
MIN_AREA_KM2 = 0.4
PIXEL_AREA_KM2 = 0.0016


def los_unit_vector(heading_deg, incidence_deg):
    h, p = np.radians(heading_deg), np.radians(incidence_deg)
    return (float(np.sin(p) * np.cos(h)), float(-np.sin(p) * np.sin(h)),
            float(np.cos(p)))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for required in (DESC2 / "velocity.h5", DESC2 / "inputs" / "geometryGeo.h5"):
        if not required.exists():
            print(f"FAIL: {required} not found.")
            return 1

    def meta_of(path):
        with h5py.File(path, "r") as handle:
            return {k: float(handle.attrs[k]) for k in
                    ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}

    asc_meta, d2_meta = meta_of(ASC_WORK / "velocity.h5"), meta_of(DESC2 / "velocity.h5")
    with h5py.File(ASC_WORK / "velocity.h5", "r") as handle:
        asc_v = handle["velocity"][:].astype("float64") * 1000.0
        asc_vs = handle["velocityStd"][:].astype("float64") * 1000.0
    with h5py.File(ASC_WORK / "temporalCoherence.h5", "r") as handle:
        asc_tc = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(DESC2 / "velocity.h5", "r") as handle:
        d2_v = handle["velocity"][:].astype("float64") * 1000.0
        d2_vs = handle["velocityStd"][:].astype("float64") * 1000.0
        d2_ref = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
    with h5py.File(DESC2 / "temporalCoherence.h5", "r") as handle:
        d2_tc = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(ASC_GEOM, "r") as handle:
        asc_inc = handle["incidenceAngle"][:].astype("float64")
        asc_heading = float(handle.attrs.get("HEADING", -12.585825751670313))
    with h5py.File(DESC2 / "inputs" / "geometryGeo.h5", "r") as handle:
        d2_inc = handle["incidenceAngle"][:].astype("float64")
        d2_heading = float(handle.attrs.get("HEADING", -167.396))

    print("=" * 88)
    print("PHASE II-B OUTCOME B - REPEAT PHASE-IIA COMPARISONS AGAINST D2")
    print("=" * 88)

    asc_u = los_unit_vector(asc_heading, float(np.nanmedian(asc_inc)))
    d2_u = los_unit_vector(d2_heading, float(np.nanmedian(d2_inc)))
    print(f"\n  geometry  ascending  u = ({asc_u[0]:+.4f}, {asc_u[1]:+.4f}, {asc_u[2]:+.4f})")
    print(f"            D2         u = ({d2_u[0]:+.4f}, {d2_u[1]:+.4f}, {d2_u[2]:+.4f})")

    at = Affine(asc_meta["X_STEP"], 0, asc_meta["X_FIRST"], 0,
                -abs(asc_meta["Y_STEP"]), asc_meta["Y_FIRST"])
    dt = Affine(d2_meta["X_STEP"], 0, d2_meta["X_FIRST"], 0,
                -abs(d2_meta["Y_STEP"]), d2_meta["Y_FIRST"])
    shape_out = asc_v.shape

    def resample(array):
        out = np.full(shape_out, np.nan, dtype="float64")
        rasterio.warp.reproject(source=array.astype("float32"), destination=out,
                                src_transform=dt, src_crs="EPSG:32643",
                                dst_transform=at, dst_crs="EPSG:32643",
                                resampling=rasterio.warp.Resampling.bilinear,
                                src_nodata=np.nan, dst_nodata=np.nan)
        return out

    d2_v_a, d2_vs_a, d2_tc_a = resample(d2_v), resample(d2_vs), resample(d2_tc)

    aoi = shp_shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", aoi.__geo_interface__))
    aoi_mask = rasterio.features.geometry_mask([aoi_utm.__geo_interface__],
                                               out_shape=shape_out, transform=at,
                                               invert=True)
    # validity = velocityStd > 0 (MintPy fills the non-inverted region)
    domain = (aoi_mask & np.isfinite(asc_v) & (asc_vs > 0)
              & np.isfinite(d2_v_a) & (d2_vs_a > 0))
    print(f"\n  ASC_DESC_COMMON_VALID_DOMAIN (V2): {int(domain.sum()):,} px "
          f"({domain.sum() / max(1, aoi_mask.sum()) * 100:.2f}% of AOI)")

    a, d = asc_v[domain], d2_v_a[domain]
    ys, xs = np.where(domain)
    A = np.column_stack([np.ones_like(ys, dtype=float), ys, xs])
    pa = a - A @ np.linalg.lstsq(A, a, rcond=None)[0]
    pd_ = d - A @ np.linalg.lstsq(A, d, rcond=None)[0]
    agreement = {
        "n": int(domain.sum()),
        "pearson": round(float(np.corrcoef(a, d)[0, 1]), 4),
        "spearman": round(float(pd.Series(a).corr(pd.Series(d), method="spearman")), 4),
        "plane_detrended": round(float(np.corrcoef(pa, pd_)[0, 1]), 4),
        "median_offset_mm_per_yr": round(float(np.median(d) - np.median(a)), 3),
        "ascending_scatter": round(float(a.std()), 3),
        "descending_scatter": round(float(d.std()), 3),
    }
    print(f"  Pearson {agreement['pearson']:+.4f}  Spearman {agreement['spearman']:+.4f}  "
          f"plane-detrended {agreement['plane_detrended']:+.4f}")
    print(f"  scatter: ascending {agreement['ascending_scatter']:.2f}  "
          f"D2 {agreement['descending_scatter']:.2f} mm/yr")

    # ---- hotspot cross-validation ----------------------------------------
    features = json.loads(HOTSPOTS.read_text())["features"]

    def detect(velocity_mm, coherence):
        eligible = aoi_mask & np.isfinite(velocity_mm) & (coherence >= 0.5)
        thresholded = eligible & (np.abs(velocity_mm) >= THRESHOLD_MM)
        labels, n = ndimage.label(thresholded, structure=STRUCTURE)
        if n == 0:
            return labels, []
        sizes = ndimage.sum(thresholded, labels, index=np.arange(1, n + 1))
        return labels, list(np.where(sizes >= int(round(MIN_AREA_KM2 / PIXEL_AREA_KM2)))[0] + 1)

    d2_labels, d2_keep = detect(d2_v_a, d2_tc_a)
    print(f"\n  independent D2 detection (|v| >= {THRESHOLD_MM}, TC >= 0.5, "
          f">= {MIN_AREA_KM2} km2): {len(d2_keep)} components")

    rows = []
    for feature in features:
        hid = feature["properties"]["hotspot_id"]
        gu = shp_shape(transform_geom("EPSG:4326", "EPSG:32643",
                                      shp_shape(feature["geometry"]).__geo_interface__))
        hm = rasterio.features.geometry_mask([gu.__geo_interface__], out_shape=shape_out,
                                             transform=at, invert=True)
        sel = hm & domain
        if sel.sum() == 0:
            rows.append({"hotspot_id": hid, "n": 0})
            continue
        ov = d2_labels[hm]
        ov = ov[ov > 0]
        detected, overlap = False, 0.0
        if ov.size:
            values, counts = np.unique(ov, return_counts=True)
            best = int(values[np.argmax(counts)])
            overlap = float(counts.max() / max(1, int(hm.sum())))
            detected = best in d2_keep
        av, dv = float(np.median(asc_v[sel])), float(np.median(d2_v_a[sel]))
        rows.append({
            "hotspot_id": hid, "n": int(sel.sum()),
            "ascending_los": round(av, 2), "descending_v2_los": round(dv, 2),
            "same_sign": bool(av * dv > 0),
            "magnitude_ratio": round(abs(dv) / max(1e-9, abs(av)), 3),
            "descending_component_detected": bool(detected),
            "overlap_fraction": round(overlap, 4),
            "ascending_tc": round(float(np.median(asc_tc[sel])), 4),
            "descending_v2_tc": round(float(np.median(d2_tc_a[sel])), 4),
        })
    hv = pd.DataFrame(rows)
    hv.to_csv(OUT / "hotspot_validation_v2.csv", index=False)
    print(f"\n  {'id':5s} {'asc':>8s} {'D2':>8s} {'same':>5s} {'ratio':>6s} "
          f"{'det':>5s} {'overlap':>8s} {'asc tc':>7s} {'D2 tc':>7s}")
    for row in rows:
        if row.get("n", 0) == 0:
            continue
        print(f"  {row['hotspot_id']:5s} {row['ascending_los']:8.2f} "
              f"{row['descending_v2_los']:8.2f} {str(row['same_sign']):>5s} "
              f"{row['magnitude_ratio']:6.2f} "
              f"{str(row['descending_component_detected']):>5s} "
              f"{row['overlap_fraction']:8.3f} {row['ascending_tc']:7.3f} "
              f"{row['descending_v2_tc']:7.3f}")

    # ---- coherence-velocity ----------------------------------------------
    bins = np.arange(0.3, 1.0001, 0.05)
    curve = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        s = domain & (d2_tc_a >= lo) & (d2_tc_a < hi)
        if s.sum() < 200:
            continue
        curve.append({"low": round(float(lo), 2), "high": round(float(hi), 2),
                      "n": int(s.sum()),
                      "median_v": round(float(np.median(d2_v_a[s])), 3)})
    print(f"\n  D2 coherence-velocity curve:")
    for c in curve:
        print(f"    TC {c['low']:.2f}-{c['high']:.2f}  n={c['n']:8,d}  "
              f"median {c['median_v']:+8.2f} mm/yr")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": "DESCENDING_PRODUCT_V2_CANDIDATE = mintpy/descending_d2_unwrap_work "
                  "(bridging+phase_closure; no ERA5, no DEM residual, no deramp, no "
                  "network change)",
        "descending_reference_yx": list(d2_ref),
        "geometry": {"ascending_los_unit_ENU": [round(v, 5) for v in asc_u],
                     "descending_v2_los_unit_ENU": [round(v, 5) for v in d2_u]},
        "agreement_v2": agreement,
        "agreement_v1_phase2a": {"pearson": 0.1752, "spearman": 0.2068,
                                 "plane_detrended": 0.1269,
                                 "descending_scatter": 29.248},
        "improvement": {
            "pearson": round(agreement["pearson"] - 0.1752, 4),
            "spearman": round(agreement["spearman"] - 0.2068, 4),
            "plane_detrended": round(agreement["plane_detrended"] - 0.1269, 4),
        },
        "hotspots": rows,
        "coherence_velocity_curve": curve,
        "note": "This repeats ONLY the Phase-IIA comparisons, as authorised under "
                "Outcome B. The frozen Phase-IIA result set is unchanged.",
    }
    (OUT / "revalidation_v2.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'revalidation_v2.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
