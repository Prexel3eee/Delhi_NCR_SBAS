#!/usr/bin/env python
"""
Phase II-A: correct the Phase-I hotspot polygons (INC-008).

Defect
------
`scripts/32_hotspots.py` wrote `qc/sci/phase1/hotspots.geojson` with two bugs:

  1. `rasterio.features.shapes` can return SEVERAL polygons for one connected
     component. The loop `break`s after the first, so only a single-pixel
     fragment of each hotspot was written. H001, actually 5.59 km2, was stored
     as a 0.002 km2 square.
  2. The feature id was assigned in DETECTION order, but `hotspots.csv` is
     renumbered in SIGNIFICANCE order afterwards. The geojson ids therefore do
     not correspond to the csv ids.

What this did and did not affect
--------------------------------
  NOT affected: every Phase-I statistic. Those were computed from the pixel
  masks, and hotspots.csv / hotspots.json are correct and frozen.
  AFFECTED: any spatial operation that used the polygons. In particular the
  descending burst-selection containment test (scripts/39) and the Gate-2
  hotspot containment check were VACUOUS, because a degenerate polygon is
  trivially "inside" any footprint.

This script regenerates the polygons correctly, proves them against the frozen
csv (id by id, by area), and re-runs the containment test that was vacuous.

The frozen Phase-I artefact set does NOT include the geojson, and nothing frozen
is modified here: the corrected file is written alongside.

Outputs
-------
qc/sci/phase1/hotspots_corrected.geojson
provenance/errata/INC-008.{json,md}
qc/sci/phase2/hotspot_containment_verified.json

Usage
-----
    python scripts/51_fix_hotspot_polygons.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
from rasterio.transform import Affine, from_origin
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely.geometry import shape as shp_shape
from shapely.ops import unary_union

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
ASC_GEOM = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
DESC_WORK = PROJECT_ROOT / "mintpy" / "descending_work"
DESC_GEOM = DESC_WORK / "inputs" / "geometryGeo.h5"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
PHASE1 = PROJECT_ROOT / "qc" / "sci" / "phase1"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2"
ERRATA = PROJECT_ROOT / "provenance" / "errata"

STRUCTURE = np.ones((3, 3), dtype=bool)
THRESHOLD_MM = 10.0
MIN_COHERENCE = 0.80
MIN_AREA_KM2 = 0.4
PIXEL_AREA_KM2 = 0.0016


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ERRATA.mkdir(parents=True, exist_ok=True)

    with h5py.File(ASC_WORK / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        meta = {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    with h5py.File(ASC_WORK / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(ASC_GEOM, "r") as handle:
        land = handle["waterMask"][:].astype(bool)

    aoi = shp_shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", f"EPSG:{int(meta['EPSG'])}",
                                       aoi.__geo_interface__))
    transform = from_origin(meta["X_FIRST"], meta["Y_FIRST"],
                            meta["X_STEP"], -meta["Y_STEP"])
    aoi_mask = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=(int(meta["LENGTH"]), int(meta["WIDTH"])),
        transform=transform, invert=True)

    vel_mm = velocity * 1000.0
    eligible = aoi_mask & land & np.isfinite(velocity) & (coherence >= MIN_COHERENCE)
    thresholded = eligible & (np.abs(vel_mm) >= THRESHOLD_MM)
    labels, n_raw = ndimage.label(thresholded, structure=STRUCTURE)
    sizes = ndimage.sum(thresholded, labels, index=np.arange(1, n_raw + 1))
    keep = list(np.where(sizes >= int(round(MIN_AREA_KM2 / PIXEL_AREA_KM2)))[0] + 1)

    # ---- rebuild the ranking EXACTLY as script 32 does --------------------
    provisional = []
    for label in keep:
        component = labels == label
        values = vel_mm[component]
        area = float(component.sum() * PIXEL_AREA_KM2)
        provisional.append({
            "label": int(label),
            "area_km2": round(area, 4),
            "median_mm": round(float(np.median(values)), 3),
            "significance": abs(float(np.median(values))) * np.sqrt(area),
        })
    provisional.sort(key=lambda r: r["significance"], reverse=True)
    for index, record in enumerate(provisional):
        record["hotspot_id"] = f"H{index + 1:03d}"

    # ---- prove the rebuild reproduces the frozen csv ----------------------
    frozen = pd.read_csv(PHASE1 / "hotspots.csv")
    mismatches = []
    for record in provisional:
        row = frozen[frozen["hotspot_id"] == record["hotspot_id"]]
        if row.empty:
            mismatches.append(f"{record['hotspot_id']} absent from the frozen csv")
            continue
        row = row.iloc[0]
        if abs(row["area_km2"] - record["area_km2"]) > 1e-4:
            mismatches.append(f"{record['hotspot_id']} area {row['area_km2']} != "
                              f"{record['area_km2']}")
        if abs(row["los_velocity_median_mm_per_yr"] - record["median_mm"]) > 1e-3:
            mismatches.append(f"{record['hotspot_id']} velocity mismatch")

    print("=" * 88)
    print("INC-008 - CORRECTING THE PHASE-I HOTSPOT POLYGONS")
    print("=" * 88)
    if mismatches:
        print("\n  FAIL: the rebuild does not reproduce the frozen csv:")
        for problem in mismatches:
            print(f"    {problem}")
        return 1
    print(f"\n  rebuild reproduces the frozen hotspots.csv for all "
          f"{len(provisional)} hotspots (area and velocity agree)")

    # ---- emit full polygons ----------------------------------------------
    features = []
    for record in provisional:
        component = (labels == record["label"]).astype("uint8")
        pieces = [shp_shape(geom) for geom, value
                  in rasterio.features.shapes(component, mask=component.astype(bool),
                                              transform=transform)
                  if value == 1]
        merged = unary_union(pieces)
        features.append({
            "type": "Feature",
            "properties": {
                "hotspot_id": record["hotspot_id"],
                "area_km2_from_pixels": record["area_km2"],
                "area_km2_from_polygon": round(merged.area / 1e6, 4),
                "los_velocity_median_mm_per_yr": record["median_mm"],
                "n_polygon_parts": len(pieces),
            },
            "geometry": transform_geom(f"EPSG:{int(meta['EPSG'])}", "EPSG:4326",
                                       merged.__geo_interface__),
        })

    corrected_path = PHASE1 / "hotspots_corrected.geojson"
    corrected_path.write_text(json.dumps(
        {"type": "FeatureCollection",
         "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
         "note": "Corrected by scripts/51_fix_hotspot_polygons.py (INC-008). Supersedes "
                 "hotspots.geojson, which contained single-pixel fragments with ids in "
                 "detection order rather than the ranked order used by hotspots.csv.",
         "features": features}, indent=1))

    print(f"\n  corrected polygons:")
    print(f"    {'id':5s} {'csv km2':>9s} {'polygon km2':>12s} {'parts':>6s} {'vertices':>9s}")
    worst = 0.0
    for feature in features:
        props = feature["properties"]
        ring = feature["geometry"]["coordinates"]
        n_vertices = sum(len(r) for poly in (
            ring if feature["geometry"]["type"] == "MultiPolygon" else [ring]) for r in poly)
        delta = abs(props["area_km2_from_polygon"] - props["area_km2_from_pixels"])
        worst = max(worst, delta)
        print(f"    {props['hotspot_id']:5s} {props['area_km2_from_pixels']:9.3f} "
              f"{props['area_km2_from_polygon']:12.3f} {props['n_polygon_parts']:6d} "
              f"{n_vertices:9d}")
    print(f"    worst polygon-vs-pixel area disagreement: {worst:.4f} km2")

    # ---- re-run the containment test that was vacuous ---------------------
    containment = {}
    if (DESC_WORK / "velocity.h5").exists():
        with h5py.File(DESC_WORK / "velocity.h5", "r") as handle:
            desc_velocity = handle["velocity"][:]
            desc_meta = {k: float(handle.attrs[k]) for k in
                         ("X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
        desc_transform = from_origin(desc_meta["X_FIRST"], desc_meta["Y_FIRST"],
                                     desc_meta["X_STEP"], -desc_meta["Y_STEP"])
        desc_valid = np.isfinite(desc_velocity)
        print(f"\n  re-running hotspot containment in the DESCENDING footprint "
              f"with CORRECT polygons:")
        print(f"    {'id':5s} {'desc px':>9s} {'of total':>9s} {'fraction':>9s}  status")
        for feature in features:
            hid = feature["properties"]["hotspot_id"]
            geom_utm = shp_shape(transform_geom(
                "EPSG:4326", f"EPSG:{int(desc_meta['EPSG'])}",
                shp_shape(feature["geometry"]).__geo_interface__))
            hmask = rasterio.features.geometry_mask(
                [geom_utm.__geo_interface__], out_shape=desc_valid.shape,
                transform=desc_transform, invert=True)
            total = int(hmask.sum())
            inside = int((hmask & desc_valid).sum())
            fraction = inside / max(1, total)
            containment[hid] = {"descending_pixels": total,
                                "inside_valid_coverage": inside,
                                "fraction": round(fraction, 6),
                                "fully_covered": bool(fraction > 0.99)}
            print(f"    {hid:5s} {inside:9d} {total:9d} {fraction * 100:8.2f}%  "
                  f"{'OK' if fraction > 0.99 else 'INCOMPLETE'}")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "erratum_id": "INC-008",
        "defect": "hotspots.geojson contained single-pixel fragments of each hotspot, "
                  "and its feature ids were in detection order rather than the ranked "
                  "order used by hotspots.csv",
        "root_cause": "scripts/32_hotspots.py broke out of rasterio.features.shapes after "
                      "the first returned polygon",
        "not_affected": ["hotspots.csv", "hotspots.json", "all Phase-I statistics",
                         "the Python-freeze of Phase-I observations (the geojson was not "
                         "in the frozen artefact set)"],
        "affected": ["the descending burst-selection containment test in scripts/39 was "
                     "vacuous", "the Gate-2 hotspot containment check was vacuous",
                     "any spatial overlap or IoU computed from the geojson"],
        "correction": "qc/sci/phase1/hotspots_corrected.geojson",
        "verification": {
            "rebuild_reproduces_frozen_csv": True,
            "worst_polygon_vs_pixel_area_delta_km2": round(worst, 4),
        },
        "hotspot_containment_in_descending": containment,
        "hashes": {
            "qc/sci/phase1/hotspots.geojson": sha256_of(PHASE1 / "hotspots.geojson"),
            "qc/sci/phase1/hotspots_corrected.geojson": sha256_of(corrected_path),
            "qc/sci/phase1/hotspots.csv": sha256_of(PHASE1 / "hotspots.csv"),
        },
    }
    (OUT / "hotspot_containment_verified.json").write_text(
        json.dumps(payload, indent=2, default=str))

    errata_path = ERRATA / "INC-008.json"
    if not errata_path.exists():
        errata_path.write_text(json.dumps(payload, indent=2, default=str))
    index_path = ERRATA / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"errata": []}
    index["errata"] = [e for e in index["errata"] if e.get("erratum_id") != "INC-008"]
    index["errata"].append({
        "erratum_id": "INC-008",
        "created_utc": payload["generated_utc"],
        "json": "provenance/errata/INC-008.json",
        "summary": "Phase-I hotspot geojson held single-pixel fragments with mis-ordered "
                   "ids; corrected file issued and the vacuous containment tests re-run",
    })
    index["updated_utc"] = payload["generated_utc"]
    index_path.write_text(json.dumps(index, indent=2))

    all_ok = all(c["fully_covered"] for c in containment.values()) if containment else None
    print(f"\n  all hotspots inside valid descending coverage: {all_ok}")
    print(f"  {corrected_path}")
    print(f"  {errata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
