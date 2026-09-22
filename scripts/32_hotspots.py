#!/usr/bin/env python
"""
Phase I, stage 2: detect and characterize coherent deformation hotspots.

Method
------
Threshold the frozen LOS velocity field, label spatially connected regions, and
discard components below a minimum area so that pixel-scale speckle is not
reported as a feature. A hotspot is therefore a region that is BOTH unusually
fast AND spatially coherent — the two properties that distinguish deformation
from noise.

Detection settings are stated explicitly and their effect is measured
(`mask_persistence` stage re-runs this across quality masks):

  magnitude     |LOS velocity| >= 10 mm/yr. This is ~3x the 3-sigma single-pixel
                noise floor and above the 4.78 mm/yr reference-selection
                systematic, so a detection is not attributable to either.
  quality       temporal coherence >= 0.80 (tier <= 2)
  8-connectivity, minimum component area 0.4 km^2 (250 pixels)

Sign convention
---------------
Negative LOS = ground moving AWAY from the satellite. With ascending
geometry this is the expected sense for subsidence, but LOS is a projection of
the full 3-D motion, so the sign alone does not establish vertical motion. A
vertical-equivalent is reported under an explicit purely-vertical assumption.

Outputs
-------
qc/sci/phase1/hotspots.csv
qc/sci/phase1/hotspots.json
qc/sci/phase1/hotspots.geojson
qc/sci/phase1/hotspot_threshold_sensitivity.csv

Usage
-----
    python scripts/32_hotspots.py [--threshold 10] [--min-area-km2 0.4]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
from pyproj import Transformer
from rasterio.transform import Affine, from_origin
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely.geometry import shape, mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
GEOMETRY = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
OUT_QC = PROJECT_ROOT / "qc" / "sci" / "phase1"

PIXEL_AREA_KM2 = 0.04 * 0.04
REFERENCE_SYSTEMATIC_MM_PER_YR = 4.78
STRUCTURE = np.ones((3, 3), dtype=bool)      # 8-connectivity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=10.0,
                        help="absolute LOS velocity threshold in mm/yr")
    parser.add_argument("--min-area-km2", type=float, default=0.4)
    parser.add_argument("--coherence", type=float, default=0.80)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    OUT_QC.mkdir(parents=True, exist_ok=True)

    with h5py.File(RAW_WORK / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        velocity_std = handle["velocityStd"][:].astype("float64")
        ref_y, ref_x = int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"])
        meta = {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    with h5py.File(RAW_WORK / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(RAW_WORK / "timeseries.h5", "r") as handle:
        dates = np.array(handle["date"]).astype(str)
        first = handle["timeseries"][0].astype("float64")
        last = handle["timeseries"][-1].astype("float64")
    with h5py.File(GEOMETRY, "r") as handle:
        height = handle["height"][:].astype("float64")
        incidence = handle["incidenceAngle"][:].astype("float64")   # degrees
        land = handle["waterMask"][:].astype(bool)                  # True = land

    length, width = int(meta["LENGTH"]), int(meta["WIDTH"])
    aoi = shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shape(transform_geom("EPSG:4326", f"EPSG:{int(meta['EPSG'])}",
                                   aoi.__geo_interface__))
    mask_aoi = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=(length, width),
        transform=from_origin(meta["X_FIRST"], meta["Y_FIRST"],
                              meta["X_STEP"], -meta["Y_STEP"]), invert=True)

    eligible = (mask_aoi & land & np.isfinite(velocity) & (coherence >= args.coherence))
    vel_mm = velocity * 1000.0
    magnitude = np.abs(vel_mm)
    thresholded = eligible & (magnitude >= args.threshold)

    min_pixels = int(round(args.min_area_km2 / PIXEL_AREA_KM2))

    print("=" * 88)
    print("PHASE I - DEFORMATION HOTSPOTS  (product_v1 / RAW-336)")
    print("=" * 88)
    print(f"\n  |LOS velocity| >= {args.threshold:.1f} mm/yr")
    print(f"  temporal coherence >= {args.coherence:.2f}")
    print(f"  minimum area {args.min_area_km2:.2f} km2 = {min_pixels} pixels")
    print(f"  eligible pixels {eligible.sum():,}")

    labels, n_raw = ndimage.label(thresholded, structure=STRUCTURE)
    sizes = ndimage.sum(thresholded, labels, index=np.arange(1, n_raw + 1))
    keep = np.where(sizes >= min_pixels)[0] + 1
    print(f"  connected components: {n_raw:,} raw, {len(keep):,} >= minimum area")

    kept_mask = np.isin(labels, keep)
    print(f"  area in hotspots: {kept_mask.sum():,} px "
          f"({kept_mask.sum() * PIXEL_AREA_KM2:.1f} km2, "
          f"{kept_mask.sum() / max(1, eligible.sum()) * 100:.2f}% of eligible)")

    transform = Affine(meta["X_STEP"], 0.0, meta["X_FIRST"],
                       0.0, -abs(meta["Y_STEP"]), meta["Y_FIRST"])
    to_wgs = Transformer.from_crs(f"EPSG:{int(meta['EPSG'])}", "EPSG:4326", always_xy=True)
    displacement = last - first

    black = np.zeros((length, width), dtype="float64")
    records, geometries = [], []
    for label in keep:
        component = labels == label
        rows, cols = np.where(component)
        v = vel_mm[component]
        n = int(component.sum())
        cy, cx = float(rows.mean()), float(cols.mean())
        x_utm = meta["X_FIRST"] + cx * meta["X_STEP"]
        y_utm = meta["Y_FIRST"] + cy * meta["Y_STEP"]
        lon, lat = to_wgs.transform(x_utm, y_utm)
        inc = float(np.nanmedian(incidence[component]))
        median_v = float(np.median(v))
        cos_inc = float(np.cos(np.radians(inc)))
        xs = meta["X_FIRST"] + cols * meta["X_STEP"]
        ys = meta["Y_FIRST"] + rows * meta["Y_STEP"]
        # Transform every pixel before taking bounds: a region can straddle a UTM
        # zone boundary or span enough longitude that corner-only bounds are wrong.
        lon_px, lat_px = to_wgs.transform(xs, ys)
        record = {
            "hotspot_id": f"H{len(records) + 1:03d}",
            "label": int(label),
            "n_pixels": n,
            "area_km2": round(n * PIXEL_AREA_KM2, 4),
            "centroid_lon": round(lon, 5),
            "centroid_lat": round(lat, 5),
            "centroid_x_utm": round(x_utm, 1),
            "centroid_y_utm": round(y_utm, 1),
            "bbox_lon_min": round(float(np.min(lon_px)), 5),
            "bbox_lat_min": round(float(np.min(lat_px)), 5),
            "bbox_lon_max": round(float(np.max(lon_px)), 5),
            "bbox_lat_max": round(float(np.max(lat_px)), 5),
            "extent_east_km": round(float(xs.max() - xs.min()) / 1000.0, 3),
            "extent_north_km": round(float(ys.max() - ys.min()) / 1000.0, 3),
            "los_velocity_median_mm_per_yr": round(median_v, 3),
            "los_velocity_mean_mm_per_yr": round(float(v.mean()), 3),
            "los_velocity_std_mm_per_yr": round(float(v.std()), 3),
            "los_velocity_p05_mm_per_yr": round(float(np.percentile(v, 5)), 3),
            "los_velocity_p95_mm_per_yr": round(float(np.percentile(v, 95)), 3),
            "los_velocity_peak_abs_mm_per_yr": round(float(v[np.argmax(np.abs(v))]), 3),
            "vertical_equivalent_median_mm_per_yr": round(median_v / cos_inc, 3),
            "incidence_angle_deg": round(inc, 3),
            "temporal_coherence_median": round(float(np.median(coherence[component])), 4),
            "temporal_coherence_min": round(float(np.min(coherence[component])), 4),
            "formal_velocity_std_median_mm_per_yr": round(
                float(np.median(velocity_std[component]) * 1000), 4),
            "cumulative_los_displacement_median_mm": round(
                float(np.median(displacement[component]) * 1000), 2),
            "elevation_median_m": round(float(np.median(height[component])), 1),
            "distance_from_reference_km": round(
                float(np.hypot((cy - ref_y) * 40.0, (cx - ref_x) * 40.0) / 1000.0), 3),
            "sign": "away_from_satellite" if median_v < 0 else "toward_satellite",
        }
        records.append(record)

        black[:] = 0.0
        black[component] = 1.0
        for geom, value in rasterio.features.shapes(black.astype("uint8"),
                                                    mask=component, transform=transform):
            if value == 1:
                geometries.append({
                    "type": "Feature",
                    "properties": {
                        "hotspot_id": record["hotspot_id"],
                        "los_velocity_median_mm_per_yr": record["los_velocity_median_mm_per_yr"],
                        "area_km2": record["area_km2"],
                        "temporal_coherence_median": record["temporal_coherence_median"],
                    },
                    "geometry": transform_geom(f"EPSG:{int(meta['EPSG'])}",
                                               "EPSG:4326", geom),
                })
                break

    frame = pd.DataFrame(records)
    frame["significance"] = (frame["los_velocity_median_mm_per_yr"].abs()
                             * np.sqrt(frame["area_km2"]))
    frame = frame.sort_values("significance", ascending=False).reset_index(drop=True)
    # Renumber so the ranking is readable: H001 is the strongest, not the first found.
    frame["hotspot_id"] = [f"H{i + 1:03d}" for i in range(len(frame))]
    frame.to_csv(OUT_QC / "hotspots.csv", index=False)

    # ---- threshold sensitivity -------------------------------------------
    rows = []
    for threshold in (5, 7.5, 10, 15, 20, 25):
        for coh in (0.70, 0.80, 0.90):
            mask = (mask_aoi & land & np.isfinite(velocity) & (coherence >= coh)
                    & (np.abs(vel_mm) >= threshold))
            lab, raw = ndimage.label(mask, structure=STRUCTURE)
            if raw:
                sz = ndimage.sum(mask, lab, index=np.arange(1, raw + 1))
                big = int((sz >= min_pixels).sum())
                area = float(sz[sz >= min_pixels].sum() * PIXEL_AREA_KM2)
            else:
                big, area = 0, 0.0
            rows.append({"threshold_mm_per_yr": threshold, "coherence_min": coh,
                         "area_km2": round(area, 2), "n_components_ge_min_area": big,
                         "pixels": int(mask.sum())})
    sensitivity = pd.DataFrame(rows)
    sensitivity.to_csv(OUT_QC / "hotspot_threshold_sensitivity.csv", index=False)

    (OUT_QC / "hotspots.geojson").write_text(json.dumps(
        {"type": "FeatureCollection",
         "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
         "features": geometries}, indent=1))

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"freeze": "product_v1",
                   "freeze_id": "2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37",
                   "principal_branch": "RAW-336"},
        "detection": {
            "absolute_velocity_threshold_mm_per_yr": args.threshold,
            "coherence_min": args.coherence,
            "min_area_km2": args.min_area_km2,
            "min_pixels": min_pixels,
            "connectivity": "8",
            "rationale": "threshold is ~3x the 3-sigma single-pixel noise floor and above "
                         "the 4.78 mm/yr reference-selection systematic; the area floor "
                         "rejects pixel-scale speckle",
        },
        "counts": {
            "eligible_pixels": int(eligible.sum()),
            "raw_components": int(n_raw),
            "components_reported": int(len(frame)),
            "hotspot_area_km2": round(float(kept_mask.sum() * PIXEL_AREA_KM2), 3),
            "hotspot_fraction_of_eligible": round(
                float(kept_mask.sum() / max(1, eligible.sum())), 5),
        },
        "sign_convention": "negative LOS = away from satellite",
        "direction_counts": {
            "away_from_satellite": int((frame["los_velocity_median_mm_per_yr"] < 0).sum()),
            "toward_satellite": int((frame["los_velocity_median_mm_per_yr"] > 0).sum()),
        },
        "hotspot_area_weighted_median_velocity_mm_per_yr": round(float(
            np.average(frame["los_velocity_median_mm_per_yr"],
                       weights=frame["area_km2"])), 3) if len(frame) else None,
        "date_span": [dates[0], dates[-1]],
        "hotspots": records,
        "caveat": "LOS is a projection of 3-D motion. The vertical-equivalent assumes "
                  "purely vertical displacement and is for context only.",
    }
    (OUT_QC / "hotspots.json").write_text(json.dumps(payload, indent=2, default=str))

    # ---- console ---------------------------------------------------------
    print(f"\n  {len(frame)} hotspots reported, "
          f"{payload['counts']['hotspot_area_km2']:.1f} km2 total")
    print(f"  sense: {payload['direction_counts']['away_from_satellite']} away from "
          f"satellite, {payload['direction_counts']['toward_satellite']} toward")
    print(f"\n  top {min(args.top, len(frame))} by |median velocity| x sqrt(area):")
    print(f"    {'id':5s} {'area_km2':>9s} {'v_med':>8s} {'v_peak':>8s} {'vert~':>8s} "
          f"{'coh':>6s} {'lon':>9s} {'lat':>9s}")
    for _, r in frame.head(args.top).iterrows():
        print(f"    {r['hotspot_id']:5s} {r['area_km2']:9.2f} "
              f"{r['los_velocity_median_mm_per_yr']:8.2f} "
              f"{r['los_velocity_peak_abs_mm_per_yr']:8.2f} "
              f"{r['vertical_equivalent_median_mm_per_yr']:8.2f} "
              f"{r['temporal_coherence_median']:6.3f} "
              f"{r['centroid_lon']:9.4f} {r['centroid_lat']:9.4f}")

    print(f"\n  {OUT_QC / 'hotspots.csv'}")
    print(f"  {OUT_QC / 'hotspots.geojson'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
