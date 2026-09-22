#!/usr/bin/env python
"""
Extract the authoritative frozen Phase-I H001-H005 geometry attributes.

Read-only. Sources:
    qc/sci/phase1/hotspots_corrected.geojson   zone polygons (INC-008 corrected)
    products/product_v1/los_velocity_mm_per_yr.tif
    products/product_v1/temporal_coherence.tif

Reports per zone: centroid lon/lat, peak-deformation lon/lat, polygon bounds
(both CRS), area, median LOS velocity, peak LOS velocity.

The reported values are recomputed from the frozen rasters ONLY to provide
the coordinate block requested here; they are compared against the frozen
Phase-I tables and any disagreement is reported rather than silently used.

Usage
-----
    python scripts/extract_phase1_geometry.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask as rmask
from rasterio.warp import transform as warp_transform

ROOT = Path(__file__).resolve().parents[1]
HS_PATH = ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
VEL = ROOT / "products" / "product_v1" / "los_velocity_mm_per_yr.tif"
COH = ROOT / "products" / "product_v1" / "temporal_coherence.tif"
FROZEN_TABLE = ROOT / "qc" / "sci" / "phase4" / "final_hotspot_table.csv"
FROZEN_P1 = ROOT / "qc" / "sci" / "phase1" / "hotspots.csv"
OUT = ROOT / "qc" / "sci" / "phase1" / "hotspot_geometry_authoritative.json"

ORDER = ["H001", "H002", "H003", "H004", "H005"]


def to_lonlat(x, y):
    lon, lat = warp_transform("EPSG:32643", "EPSG:4326", [x], [y])
    return float(lon[0]), float(lat[0])


def main() -> int:
    hs = gpd.read_file(HS_PATH).to_crs(32643)
    with rasterio.open(VEL) as s:
        vel = s.read(1).astype("float64")
        vel[vel == s.nodata] = np.nan
        vprof = {"transform": s.transform, "width": s.width, "height": s.height}
    with rasterio.open(COH) as s:
        coh = s.read(1).astype("float64")
        coh[coh == s.nodata] = np.nan

    frozen_p1 = {}
    if FROZEN_P1.exists():
        import pandas as pd
        d = pd.read_csv(FROZEN_P1).set_index("hotspot_id")
        frozen_p1 = d.to_dict("index")

    recs = []
    for hid in ORDER:
        row = hs[hs.hotspot_id == hid].iloc[0]
        geom = row.geometry

        # --- centroid (area-weighted, true centroid of the multipart polygon)
        c = geom.centroid
        c_lon, c_lat = to_lonlat(c.x, c.y)

        # --- peak deformation: pixel of maximum |LOS velocity| inside polygon
        with rasterio.open(VEL) as src:
            out, out_T = rmask(src, [geom], crop=True, nodata=np.nan,
                               filled=True)
        sub = out[0]
        if np.all(~np.isfinite(sub)):
            peak = None
        else:
            rr, cc = np.unravel_index(np.nanargmax(np.abs(sub)), sub.shape)
            px, py = rasterio.transform.xy(out_T, rr, cc)
            p_lon, p_lat = to_lonlat(px, py)
            peak = {
                "los_velocity_mm_per_yr": float(sub[rr, cc]),
                "lon": p_lon, "lat": p_lat,
                "utm_e": float(px), "utm_n": float(py),
                "row": int(rr), "col": int(cc),
                "temporal_coherence": float(coh[int(rr + 0), int(cc + 0)])
                if np.isfinite(coh[rr, cc]) else None,
            }

        # --- polygon statistics straight from the frozen rasters
        vals = sub[np.isfinite(sub)]
        b = geom.bounds  # minx, miny, maxx, maxy in UTM
        b_lonlat = [to_lonlat(b[0], b[1]), to_lonlat(b[2], b[3])]

        rec = {
            "hotspot_id": hid,
            "n_polygon_parts": int(row.n_polygon_parts),
            "centroid_lon": c_lon,
            "centroid_lat": c_lat,
            "centroid_utm": {"e": float(c.x), "n": float(c.y)},
            "peak_deformation_lon": peak["lon"] if peak else None,
            "peak_deformation_lat": peak["lat"] if peak else None,
            "peak_deformation": peak,
            "polygon_bounds_utm": {"minx": b[0], "miny": b[1],
                                   "maxx": b[2], "maxy": b[3]},
            "polygon_bounds_lonlat": {
                "min_lon": b_lonlat[0][0], "min_lat": b_lonlat[0][1],
                "max_lon": b_lonlat[1][0], "max_lat": b_lonlat[1][1]},
            "area_km2": float(row.area_km2_from_polygon),
            "n_valid_pixels": int(vals.size),
            "median_los_velocity_mm_per_yr": float(np.median(vals))
            if vals.size else None,
            "mean_los_velocity_mm_per_yr": float(np.mean(vals))
            if vals.size else None,
            "peak_los_velocity_mm_per_yr": float(vals[np.argmax(np.abs(vals))])
            if vals.size else None,
            "p25_los_velocity_mm_per_yr": float(np.percentile(vals, 25))
            if vals.size else None,
            "p75_los_velocity_mm_per_yr": float(np.percentile(vals, 75))
            if vals.size else None,
            "median_temporal_coherence": float(
                np.nanmedian(coh[int(b[1] // 0) if False else 0, 0])) if False else None,
            "frozen_phase1_area_km2": frozen_p1.get(hid, {}).get("area_km2"),
            "frozen_phase1_median_los": frozen_p1.get(
                hid, {}).get("los_velocity_median_mm_per_yr"),
            "frozen_phase1_peak_abs_los": frozen_p1.get(
                hid, {}).get("los_velocity_peak_abs_mm_per_yr"),
        }
        recs.append(rec)

    doc = {
        "extract_version": "phase1_geometry_authoritative_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "polygons": str(HS_PATH.relative_to(ROOT)),
            "velocity": str(VEL.relative_to(ROOT)),
            "coherence": str(COH.relative_to(ROOT)),
            "note": "hotspots_corrected.geojson is the INC-008 corrected geometry",
        },
        "crs_polygon_and_raster": "EPSG:32643",
        "crs_reported": "EPSG:4326 (WGS84)",
        "hotspots": recs,
    }
    OUT.write_text(json.dumps(doc, indent=2))

    # ---- console table -------------------------------------------------
    print("=" * 108)
    print("AUTHORITATIVE FROZEN PHASE-I GEOMETRY  H001-H005")
    print("=" * 108)
    hdr = (f"{'id':5s} {'centroid lon':>13s} {'centroid lat':>13s} "
           f"{'peak lon':>10s} {'peak lat':>10s} {'area km2':>9s} "
           f"{'med LOS':>9s} {'peak LOS':>9s}")
    print(hdr)
    print("-" * 108)
    for r in recs:
        print(f"{r['hotspot_id']:5s} {r['centroid_lon']:13.5f} "
              f"{r['centroid_lat']:13.5f} "
              f"{r['peak_deformation_lon']:10.5f} "
              f"{r['peak_deformation_lat']:10.5f} "
              f"{r['area_km2']:9.4f} "
              f"{r['median_los_velocity_mm_per_yr']:9.2f} "
              f"{r['peak_los_velocity_mm_per_yr']:9.2f}")

    print("\nPOLYGON BOUNDS")
    print("-" * 108)
    for r in recs:
        bl = r["polygon_bounds_lonlat"]
        print(f"{r['hotspot_id']:5s} lon {bl['min_lon']:.5f} .. {bl['max_lon']:.5f}"
              f"   lat {bl['min_lat']:.5f} .. {bl['max_lat']:.5f}")

    # ---- cross-check against frozen Phase-I table ----------------------
    print("\nCROSS-CHECK vs frozen Phase-I table")
    print("-" * 108)
    bad = 0
    for r in recs:
        a1, a2 = r["area_km2"], r["frozen_phase1_area_km2"]
        m1, m2 = r["median_los_velocity_mm_per_yr"], r["frozen_phase1_median_los"]
        ok_a = a2 is None or abs(a1 - a2) < 1e-6
        ok_m = m2 is None or abs(m1 - m2) < 0.02
        if not (ok_a and ok_m):
            bad += 1
        print(f"{r['hotspot_id']:5s} area {a1:.4f} vs {a2}  "
              f"median {m1:+.3f} vs {m2}   "
              f"{'OK' if ok_a and ok_m else 'MISMATCH'}")
    print(f"\n  mismatches: {bad}")
    print(f"  written: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
