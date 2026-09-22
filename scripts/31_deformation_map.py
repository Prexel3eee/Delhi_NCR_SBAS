#!/usr/bin/env python
"""
Phase I, stage 1: the authoritative deformation map from frozen `product_v1`.

This script does NOT alter the solution. It reads the frozen RAW-336 products,
publishes them as georeferenced rasters with an explicit quality mask, and
reports the first-order statistics that every later Phase I stage builds on.

What is published
-----------------
  los_velocity_mm_per_yr.tif              LOS velocity, mm/yr, relative to the
                                          processing reference pixel
  los_velocity_uncertainty_mm_per_yr.tif  formal 1-sigma from the inversion
  los_displacement_mm.tif                 cumulative LOS change, first -> last date
  temporal_coherence.tif                  MintPy temporal coherence
  quality_mask.tif                        tier code, 0 = excluded
  elevation_m.tif                         Copernicus DEM, for context only

Units and conventions
---------------------
Sentinel-1 measures **line-of-sight (LOS)** displacement, not vertical. Every
value here is LOS unless explicitly labelled otherwise. Velocities are
**relative** to the processing reference pixel, because InSAR has no absolute
reference. The vertical-equivalent is reported for context under an explicit
purely-vertical assumption and must not be read as a measured vertical rate.

The formal 1-sigma (`velocityStd`) is a *fit* uncertainty. It is far smaller
than the true error budget, which is dominated by the reference-choice
systematic (4.78 mm/yr) and unmodelled atmosphere. Both are reported; the
formal value is never used alone as a significance measure.

Quality tiers
-------------
  1  best      temporal coherence >= 0.90
  2  good      temporal coherence >= 0.80
  3  moderate  temporal coherence >= 0.70
  4  permissive all finite land pixels inside the AOI
  0  excluded  water, outside AOI, or non-finite

Outputs
-------
products/product_v1/*.tif
qc/sci/phase1/deformation_map_summary.json

Usage
-----
    python scripts/31_deformation_map.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import rasterio
import rasterio.features
from rasterio.transform import Affine, from_origin
from rasterio.warp import transform_geom
from shapely.geometry import shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
GEOMETRY = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
TIMESERIES = RAW_WORK / "timeseries.h5"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"

OUT_PRODUCTS = PROJECT_ROOT / "products" / "product_v1"
OUT_QC = PROJECT_ROOT / "qc" / "sci" / "phase1"

TIERS = [(1, 0.90), (2, 0.80), (3, 0.70), (4, None)]
PRIMARY_TIER = 2


def load_grid():
    with h5py.File(RAW_WORK / "velocity.h5", "r") as handle:
        meta = {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    return meta


def aoi_mask(meta) -> np.ndarray:
    aoi = shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shape(transform_geom(
        "EPSG:4326", f"EPSG:{int(meta['EPSG'])}", aoi.__geo_interface__))
    return rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__],
        out_shape=(int(meta["LENGTH"]), int(meta["WIDTH"])),
        transform=from_origin(meta["X_FIRST"], meta["Y_FIRST"],
                              meta["X_STEP"], -meta["Y_STEP"]),
        invert=True)


def write_raster(path: Path, array: np.ndarray, meta: dict, dtype: str,
                 nodata: float, description: str) -> None:
    transform = Affine(meta["X_STEP"], 0.0, meta["X_FIRST"],
                       0.0, -abs(meta["Y_STEP"]), meta["Y_FIRST"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path, "w", driver="GTiff", height=int(meta["LENGTH"]),
        width=int(meta["WIDTH"]), count=1, dtype=dtype, crs=f"EPSG:{int(meta['EPSG'])}",
        transform=transform, nodata=nodata, compress="deflate", tiled=True,
        blockxsize=256, blockysize=256, predictor=3 if np.issubdtype(np.dtype(dtype), np.floating) else 1,
    ) as dst:
        dst.write(array.astype(dtype), 1)
        dst.set_band_description(1, description)


def describe(values: np.ndarray, mm: bool = False) -> dict:
    v = values[np.isfinite(values)]
    if v.size == 0:
        return {}
    scale = 1000.0 if mm else 1.0
    return {
        "n": int(v.size),
        "median": round(float(np.median(v) * scale), 4),
        "mean": round(float(v.mean() * scale), 4),
        "std": round(float(v.std() * scale), 4),
        "p01": round(float(np.percentile(v, 1) * scale), 4),
        "p05": round(float(np.percentile(v, 5) * scale), 4),
        "p25": round(float(np.percentile(v, 25) * scale), 4),
        "p75": round(float(np.percentile(v, 75) * scale), 4),
        "p95": round(float(np.percentile(v, 95) * scale), 4),
        "p99": round(float(np.percentile(v, 99) * scale), 4),
        "min": round(float(v.min() * scale), 4),
        "max": round(float(v.max() * scale), 4),
    }


def main() -> int:
    OUT_PRODUCTS.mkdir(parents=True, exist_ok=True)
    OUT_QC.mkdir(parents=True, exist_ok=True)
    meta = load_grid()
    length, width = int(meta["LENGTH"]), int(meta["WIDTH"])

    print("=" * 88)
    print("PHASE I - AUTHORITATIVE DEFORMATION MAP  (product_v1 / RAW-336)")
    print("=" * 88)

    # ---- load the frozen products (read-only) ----------------------------
    with h5py.File(RAW_WORK / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        velocity_std = handle["velocityStd"][:].astype("float64")
        residue = handle["residue"][:].astype("float64")
        ref_y, ref_x = int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"])
    with h5py.File(RAW_WORK / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(GEOMETRY, "r") as handle:
        height = handle["height"][:].astype("float64")
        land = handle["waterMask"][:].astype(bool)   # True = land, False = water
    with h5py.File(TIMESERIES, "r") as handle:
        dates = np.array(handle["date"]).astype(str)
        first = handle["timeseries"][0, :, :].astype("float64")
        last = handle["timeseries"][-1, :, :].astype("float64")

    mask_aoi = aoi_mask(meta)
    finite = np.isfinite(velocity)
    in_aoi = mask_aoi & finite
    on_land = in_aoi & land

    print(f"\n  grid            {length} x {width} @ {meta['X_STEP']:.0f} m  EPSG:{int(meta['EPSG'])}")
    print(f"  AOI pixels      {int(mask_aoi.sum()):,}")
    print(f"  finite in AOI   {int(in_aoi.sum()):,}")
    print(f"  land in AOI     {int(on_land.sum()):,}  "
          f"({on_land.sum() / max(1, mask_aoi.sum()) * 100:.2f}% of AOI)")
    print(f"  water in AOI    {int((in_aoi & ~land).sum()):,}  "
          f"({(in_aoi & ~land).sum() / max(1, mask_aoi.sum()) * 100:.2f}%)")

    # ---- reporting reference ---------------------------------------------
    frozen_ref = (1378, 1426)
    print(f"\n  processing reference pixel (from timeseries.h5) : y={ref_y}, x={ref_x}")
    print(f"  reference pixel in frozen decision              : y={frozen_ref[0]}, x={frozen_ref[1]}")
    reference_mismatch = bool((ref_y, ref_x) != frozen_ref)
    if reference_mismatch:
        offset = float(velocity[frozen_ref] * 1000)
        print(f"  -> MISMATCH. RAW-336 velocity at the frozen pixel = {offset:+.4f} mm/yr,")
        print("     so the v1 product carries a constant reference offset of that size")
        print("     relative to the frozen decision. Spatial gradients are unaffected.")

    # ---- cumulative displacement -----------------------------------------
    displacement = (last - first)
    displacement[~in_aoi] = np.nan
    print(f"\n  cumulative LOS displacement {dates[0]} -> {dates[-1]} "
          f"({len(dates)} dates)")

    # ---- quality tiers ---------------------------------------------------
    tier_counts = {}
    for code, threshold in TIERS:
        selected = on_land if threshold is None else (on_land & (coherence >= threshold))
        tier_counts[str(code)] = int(selected.sum())

    # Assign from most permissive to most restrictive so the STRICTEST tier a
    # pixel qualifies for is the one it keeps. Assigning in the other order lets
    # the permissive tier overwrite everything.
    tier = np.zeros((length, width), dtype="uint8")
    for code, threshold in reversed(TIERS):
        selected = on_land if threshold is None else (on_land & (coherence >= threshold))
        tier[selected] = code
    print("\n  quality tiers (temporal coherence):")
    for code, threshold in TIERS:
        label = "permissive (all finite land)" if threshold is None else f">= {threshold:.2f}"
        count = tier_counts[str(code)]
        print(f"    tier {code}  {label:28s} {count:9,d} px  "
              f"{count / max(1, on_land.sum()) * 100:6.2f}% of land")

    # Tier 0 means excluded (water, outside AOI, non-finite), so it must be
    # excluded explicitly: `tier <= PRIMARY_TIER` alone would select it.
    primary = (tier >= 1) & (tier <= PRIMARY_TIER)

    # ---- short-wavelength noise floor ------------------------------------
    from scipy.ndimage import uniform_filter
    filled = np.where(primary, velocity * 1000.0, np.nan)
    filled = np.where(primary, filled, np.nanmedian(filled))
    smooth = uniform_filter(filled, size=3, mode="nearest")
    highpass = (velocity * 1000.0 - smooth)[primary]
    highpass = highpass[np.isfinite(highpass)]
    noise_sigma = float(1.4826 * np.median(np.abs(highpass - np.median(highpass))))
    print(f"\n  short-wavelength noise floor (3x3 high-pass, robust sigma): "
          f"{noise_sigma:.3f} mm/yr")
    print(f"  -> a 3-sigma single-pixel detection limit is {3 * noise_sigma:.2f} mm/yr")

    # ---- write rasters ---------------------------------------------------
    nodata = -9999.0
    def masked(array, scale=1.0):
        out = np.full(array.shape, nodata, dtype="float64")
        sel = primary & np.isfinite(array)
        out[sel] = array[sel] * scale
        return out

    written = []
    for name, array, dtype, desc, scale in [
        ("los_velocity_mm_per_yr.tif", velocity, "float32",
         "LOS velocity (mm/yr), relative to processing reference; primary mask",
         1000.0),
        ("los_velocity_uncertainty_mm_per_yr.tif", velocity_std, "float32",
         "Formal 1-sigma LOS velocity (mm/yr) from the inversion", 1000.0),
        ("los_displacement_mm.tif", displacement, "float32",
         f"Cumulative LOS displacement (mm), {dates[0]} to {dates[-1]}", 1000.0),
        ("temporal_coherence.tif", coherence, "float32",
         "MintPy temporal coherence", 1.0),
        ("elevation_m.tif", height, "float32", "Copernicus DEM elevation (m)", 1.0),
        ("los_residue_rad.tif", residue, "float32",
         "Median residual phase (rad)", 1.0),
    ]:
        path = OUT_PRODUCTS / name
        write_raster(path, masked(array, scale), meta, dtype, nodata, desc)
        written.append(name)
        print(f"    wrote {name}")

    write_raster(OUT_PRODUCTS / "quality_mask.tif", tier.astype("float32"), meta,
                 "float32", 0.0,
                 "Quality tier: 1 tc>=0.90, 2 tc>=0.80, 3 tc>=0.70, 4 permissive")
    written.append("quality_mask.tif")
    print("    wrote quality_mask.tif")

    # ---- summary ---------------------------------------------------------
    vel_mm = velocity * 1000.0
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "freeze": "product_v1",
            "freeze_id": "2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37",
            "principal_branch": "RAW-336",
            "velocity_file": "mintpy/baseline_raw_work/velocity.h5",
            "timeseries_file": "mintpy/baseline_raw_work/timeseries.h5",
        },
        "grid": {"length": length, "width": width, "x_first": meta["X_FIRST"],
                 "y_first": meta["Y_FIRST"], "x_step": meta["X_STEP"],
                 "y_step": meta["Y_STEP"], "epsg": int(meta["EPSG"])},
        "dates": {"first": dates[0], "last": dates[-1], "count": int(len(dates))},
        "reference": {
            "processing_ref_yx": [ref_y, ref_x],
            "frozen_decision_yx": list(frozen_ref),
            "mismatch": reference_mismatch,
            "raw_velocity_at_frozen_pixel_mm_per_yr": round(float(velocity[frozen_ref] * 1000), 4),
            "note": "InSAR yields relative LOS values. Gradients are unaffected by this "
                    "choice; the absolute offset is uncertain at the 4.78 mm/yr "
                    "reference-selection systematic.",
        },
        "counts": {
            "aoi_pixels": int(mask_aoi.sum()),
            "finite_in_aoi": int(in_aoi.sum()),
            "land_in_aoi": int(on_land.sum()),
            "water_in_aoi": int((in_aoi & ~land).sum()),
            "land_fraction_of_aoi": round(float(on_land.sum() / max(1, mask_aoi.sum())), 4),
            "water_fraction_of_aoi": round(float((in_aoi & ~land).sum() / max(1, mask_aoi.sum())), 6),
        },
        "quality_tiers": {str(code): {"threshold": threshold,
                                      "pixels": tier_counts[str(code)]}
                          for code, threshold in TIERS},
        "primary_tier": PRIMARY_TIER,
        "primary_mask_pixels": int(primary.sum()),
        "noise_floor": {
            "short_wavelength_robust_sigma_mm_per_yr": round(noise_sigma, 4),
            "three_sigma_detection_limit_mm_per_yr": round(3 * noise_sigma, 4),
            "method": "3x3 boxcar high-pass over the primary mask; 1.4826*MAD",
        },
        "los_velocity_mm_per_yr_primary_mask": describe(vel_mm[primary]),
        "los_velocity_mm_per_yr_all_land": describe(vel_mm[on_land]),
        "formal_uncertainty_mm_per_yr_primary_mask": describe(velocity_std[primary] * 1000),
        "cumulative_displacement_mm_primary_mask": describe(displacement[primary] * 1000),
        "temporal_coherence_primary_mask": describe(coherence[primary]),
        "elevation_m_primary_mask": describe(height[primary]),
        "rasters": written,
        "units_note": "All deformation values are LINE-OF-SIGHT and RELATIVE to the "
                      "processing reference pixel.",
    }
    (OUT_QC / "deformation_map_summary.json").write_text(
        json.dumps(summary, indent=2, default=str))

    # ---- console ---------------------------------------------------------
    s = summary["los_velocity_mm_per_yr_primary_mask"]
    print(f"\n  LOS velocity, primary mask (tier <= {PRIMARY_TIER}, {primary.sum():,} px):")
    print(f"    median {s['median']:+.2f}   mean {s['mean']:+.2f}   std {s['std']:.2f} mm/yr")
    print(f"    p01 {s['p01']:+.2f}  p05 {s['p05']:+.2f}  p25 {s['p25']:+.2f}  "
          f"p75 {s['p75']:+.2f}  p95 {s['p95']:+.2f}  p99 {s['p99']:+.2f}")
    print(f"    min {s['min']:+.2f}   max {s['max']:+.2f} mm/yr")
    f = summary["formal_uncertainty_mm_per_yr_primary_mask"]
    print(f"\n  formal 1-sigma   median {f['median']:.3f} mm/yr  (p95 {f['p95']:.3f})")
    print(f"  true error floor is dominated by the 4.78 mm/yr reference systematic,")
    print(f"  roughly {4.78 / max(f['median'], 1e-9):.1f}x the formal value.")

    print(f"\n  {OUT_QC / 'deformation_map_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
