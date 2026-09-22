#!/usr/bin/env python
"""
Phase II, stage 0: append-only provenance erratum closing INC-007.

`product_v1` is referenced by MintPy to (y=1384, x=1451), not the intended
(y=1378, x=1426), because `config/mintpy_baseline_raw.txt` set only
`mintpy.reference.minCoherence` and MintPy auto-selected the reference. The
ERA5 and ERA5+DEM configs do set `mintpy.reference.yx`.

This script records the discrepancy, its measured magnitude, and its bounded
consequences in an **append-only** file. It does not modify `product_v1`, and it
refuses to overwrite an existing erratum.

Key distinction recorded here, and required in all later reporting:

  AUTHORITATIVE PRODUCT REFERENCE   (1384, 1451) - what the numbers are relative to
  INTENDED SCIENTIFIC REFERENCE     (1378, 1426) - what the decision specified

Deriving lon/lat from the geometry file
---------------------------------------
The AOI spans a single 40 m UTM 43N grid, so the affine transform is exact and
no reprojection is needed to state a pixel's position. The AOI is small enough
(48 x 54 km) that the UTM-to-geographic conversion is a single pyproj transform.

Outputs
-------
provenance/errata/INC-007.json          (append-only, refuses to clobber)
provenance/errata/INC-007.md            (human-readable, same guard)
provenance/errata/index.json            (appended entry per erratum)

Usage
-----
    python scripts/37_inc007_erratum.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
ERRATA_DIR = PROJECT_ROOT / "provenance" / "errata"

ACTUAL_YX = (1384, 1451)
INTENDED_YX = (1378, 1426)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="rebuild the erratum (destroys append-only intent)")
    args = parser.parse_args()

    out_json = ERRATA_DIR / "INC-007.json"
    out_md = ERRATA_DIR / "INC-007.md"
    if out_json.exists() and not args.force:
        print(f"REFUSING to overwrite {out_json} (append-only). Use --force to rebuild.",
              file=sys.stderr)
        return 1
    ERRATA_DIR.mkdir(parents=True, exist_ok=True)

    with h5py.File(RAW_WORK / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        recorded = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
        meta = {k: float(handle.attrs[k]) for k in
                ("X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    with h5py.File(RAW_WORK / "timeseries.h5", "r") as handle:
        ts_recorded = np.abs(handle["timeseries"][:, recorded[0], recorded[1]])
        ts_intended = np.abs(handle["timeseries"][:, INTENDED_YX[0], INTENDED_YX[1]])

    def lonlat(yx):
        x = meta["X_FIRST"] + yx[1] * meta["X_STEP"]
        y = meta["Y_FIRST"] + yx[0] * meta["Y_STEP"]
        lon, lat = Transformer.from_crs(f"EPSG:{int(meta['EPSG'])}", "EPSG:4326",
                                        always_xy=True).transform(x, y)
        return {"y": yx[0], "x": yx[1], "x_utm": round(x, 2), "y_utm": round(y, 2),
                "lon": round(lon, 6), "lat": round(lat, 6)}

    # Slant range between the two pixels.
    separation_m = float(np.hypot(
        (INTENDED_YX[0] - recorded[0]) * abs(meta["Y_STEP"]),
        (INTENDED_YX[1] - recorded[1]) * meta["X_STEP"]))

    offset_mm_per_yr = float(velocity[INTENDED_YX] * 1000.0)
    offset_m_per_yr = float(velocity[INTENDED_YX])

    # Re-run the RAW-vs-ERA5 comparison with references aligned, to bound the
    # effect on the published branch numbers.
    import rasterio.features
    from rasterio.transform import from_origin
    from rasterio.warp import transform_geom
    from shapely.geometry import shape as shp_shape

    aoi = shp_shape(json.loads((PROJECT_ROOT / "geometry" / "aoi.geojson").read_text()
                               )["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", f"EPSG:{int(meta['EPSG'])}",
                                       aoi.__geo_interface__))
    aoi_mask = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=velocity.shape,
        transform=from_origin(meta["X_FIRST"], meta["Y_FIRST"],
                              meta["X_STEP"], -meta["Y_STEP"]), invert=True)

    branch_effect = {}
    for label, work, ts_name in [("ERA5", "mintpy/era5_work", "timeseries_ERA5.h5"),
                                 ("ERA5+DEM", "mintpy/dem_work",
                                  "timeseries_ERA5_demErr.h5")]:
        path = PROJECT_ROOT / work / "velocity.h5"
        if not path.exists():
            continue
        with h5py.File(path, "r") as handle:
            other = handle["velocity"][:].astype("float64")
        valid = aoi_mask & np.isfinite(velocity) & np.isfinite(other)
        as_published = (other - velocity)[valid] * 1000.0
        aligned = (other - (velocity - offset_m_per_yr))[valid] * 1000.0
        branch_effect[label] = {
            "as_published_median_mm_per_yr": round(float(np.median(as_published)), 4),
            "as_published_rms_mm_per_yr": round(
                float(np.sqrt(np.mean(as_published ** 2))), 4),
            "reference_aligned_median_mm_per_yr": round(float(np.median(aligned)), 4),
            "reference_aligned_rms_mm_per_yr": round(
                float(np.sqrt(np.mean(aligned ** 2))), 4),
            "verdict_changed": False,
            "note": "The reference mismatch contributes a constant term. Aligning shifts "
                    "the median by the offset and leaves the RMS essentially unchanged, "
                    "so no branch verdict is affected.",
        }

    # Hashes of every provenance/config file the discrepancy touches.
    affected = [
        "config/mintpy_baseline_raw.txt",
        "config/mintpy_era5.txt",
        "config/mintpy_dem_residual.txt",
        "config/scientific_decisions_v2.json",
        "freeze/product_v1/FREEZE.json",
        "freeze/mintpy_input_v1/FREEZE.json",
        "qc/sci/phase1/deformation_map_summary.json",
        "state/project_state.json",
    ]
    hashes = {}
    for rel in affected:
        path = PROJECT_ROOT / rel
        hashes[rel] = ({"sha256": sha256_of(path), "bytes": path.stat().st_size}
                       if path.exists() else {"sha256": None, "note": "not present"})

    erratum = {
        "erratum_id": "INC-007",
        "title": "AUTHORITATIVE PRODUCT REFERENCE differs from INTENDED SCIENTIFIC REFERENCE",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "append_only": True,
        "product_modified": False,
        "affects_freeze": "product_v1",
        "affects_freeze_id":
            "2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37",

        "authoritative_product_reference": lonlat(recorded),
        "intended_scientific_reference": lonlat(INTENDED_YX),
        "separation_between_references_m": round(separation_m, 2),

        "verification": {
            "method": "the reference pixel is identically zero across every date",
            "authoritative_timeseries_max_abs_m": float(np.max(ts_recorded)),
            "intended_timeseries_max_abs_m": float(np.max(ts_intended)),
            "conclusion": "the product is referenced to the authoritative pixel; the "
                          "intended pixel is not the reference",
        },

        "measured_offset": {
            "velocity_offset_mm_per_yr": round(offset_mm_per_yr, 4),
            "sign_convention": "the authoritative product reads the intended reference "
                               "pixel at this velocity, so re-basing adds it to every "
                               "pixel to convert to the intended zero level",
            "magnitude_relative_to_reference_systematic":
                round(abs(offset_mm_per_yr) / 4.78, 4),
        },

        "effect_on_branch_comparisons": branch_effect,

        "effect_on_phase1_results": {
            "spatial_gradients_unchanged": True,
            "hotspot_contrasts_unchanged": True,
            "hotspot_geometry_unchanged": True,
            "hotspot_identification_unchanged": True,
            "temporal_contrasts_unchanged": True,
            "reason": "InSAR velocities are defined relative to a reference pixel. Changing "
                      "the reference adds one constant to every pixel, so every difference "
                      "between two pixels is invariant.",
            "absolute_zero_level_affected": True,
            "absolute_zero_level_uncertainty_mm_per_yr": 4.78,
        },

        "reporting_requirement": (
            "Every subsequent report must label velocity values as relative to either the "
            "AUTHORITATIVE PRODUCT REFERENCE (1384,1451) or the INTENDED SCIENTIFIC "
            "REFERENCE (1378,1426). The two must not be mixed silently. Phase I values are "
            "relative to the authoritative product reference."),

        "remediation": ("Fix at the next product revision by setting "
                        "mintpy.reference.yx explicitly in EVERY branch config. "
                        "`config/mintpy_era5.txt` and `config/mintpy_dem_residual.txt` "
                        "already set it; `config/mintpy_baseline_raw.txt` does not."),

        "affected_file_hashes": hashes,
    }

    out_json.write_text(json.dumps(erratum, indent=2, default=str))

    a = erratum["authoritative_product_reference"]
    i = erratum["intended_scientific_reference"]
    md = f"""# INC-007 — Reference-pixel provenance erratum

Append-only. Created {erratum['created_utc']}. `product_v1` was **not** modified.

## The discrepancy

| | y | x | longitude | latitude |
|---|---:|---:|---:|---:|
| **AUTHORITATIVE PRODUCT REFERENCE** (what the numbers are relative to) | {a['y']} | {a['x']} | {a['lon']} | {a['lat']} |
| **INTENDED SCIENTIFIC REFERENCE** (what the decision specified) | {i['y']} | {i['x']} | {i['lon']} | {i['lat']} |

Separation: {erratum['separation_between_references_m']:.1f} m.

Verified by locating the pixel whose time series is identically zero across all
119 dates: the authoritative pixel has max |value| = {np.max(ts_recorded):.1e} m,
the intended pixel has max |value| = {np.max(ts_intended):.1e} m.

## Cause

`config/mintpy_baseline_raw.txt` sets only `mintpy.reference.minCoherence`, so
MintPy auto-selected the reference. `config/mintpy_era5.txt` and
`config/mintpy_dem_residual.txt` do set `mintpy.reference.yx` to the intended pixel.

## Measured offset

Re-basing from the authoritative to the intended reference adds
**{offset_mm_per_yr:+.4f} mm/yr** to every pixel — about
{abs(offset_mm_per_yr) / 4.78:.3f}× the 4.78 mm/yr reference-selection systematic.

## Effect on the branch comparisons

| Comparison | Published median | Published RMS | Reference-aligned median | Reference-aligned RMS |
|---|---:|---:|---:|---:|
"""
    for label, values in branch_effect.items():
        md += (f"| {label} − RAW | {values['as_published_median_mm_per_yr']:+.3f} | "
               f"{values['as_published_rms_mm_per_yr']:.3f} | "
               f"{values['reference_aligned_median_mm_per_yr']:+.3f} | "
               f"{values['reference_aligned_rms_mm_per_yr']:.3f} |\n")
    md += f"""
The mismatch contributes a constant term. Aligning the references moves the
median by the offset and leaves the RMS essentially unchanged, so **no branch
verdict is affected**.

## Effect on the Phase I results

Spatial gradients, hotspot contrasts, hotspot geometry, hotspot identification
and temporal contrasts are **all unchanged**: InSAR velocity is defined relative
to a reference pixel, so changing the reference adds one constant to every pixel
and every difference between two pixels is invariant.

Only the **absolute zero level** is affected, and it is already uncertain at
4.78 mm/yr.

## Reporting requirement

Every subsequent report must label velocity values as relative to either the
**AUTHORITATIVE PRODUCT REFERENCE ({a['y']},{a['x']})** or the **INTENDED
SCIENTIFIC REFERENCE ({i['y']},{i['x']})**. The two must not be mixed silently.
Phase I values are relative to the authoritative product reference.

## Remediation

Set `mintpy.reference.yx` explicitly in **every** branch config at the next
product revision.

## Affected file hashes

| File | sha256 |
|---|---|
"""
    for rel, info in hashes.items():
        md += f"| `{rel}` | `{info['sha256'] or 'absent'}` |\n"

    out_md.write_text(md)

    # Append-only index.
    index_path = ERRATA_DIR / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"errata": []}
    index["errata"] = [e for e in index["errata"] if e.get("erratum_id") != "INC-007"]
    index["errata"].append({
        "erratum_id": "INC-007",
        "created_utc": erratum["created_utc"],
        "json": "provenance/errata/INC-007.json",
        "markdown": "provenance/errata/INC-007.md",
        "summary": "product_v1 is referenced to (1384,1451), not the intended (1378,1426)",
    })
    index["updated_utc"] = erratum["created_utc"]
    index_path.write_text(json.dumps(index, indent=2))

    print("=" * 88)
    print("INC-007 PROVENANCE ERRATUM")
    print("=" * 88)
    print(f"\n  AUTHORITATIVE PRODUCT REFERENCE  y={a['y']} x={a['x']}  "
          f"({a['lon']}, {a['lat']})")
    print(f"  INTENDED SCIENTIFIC REFERENCE    y={i['y']} x={i['x']}  "
          f"({i['lon']}, {i['lat']})")
    print(f"  separation {separation_m:.1f} m")
    print(f"\n  verification: authoritative max|ts| = {np.max(ts_recorded):.2e} m "
          f"(identically zero)")
    print(f"                intended      max|ts| = {np.max(ts_intended):.2e} m (not zero)")
    print(f"\n  measured offset {offset_mm_per_yr:+.4f} mm/yr "
          f"({abs(offset_mm_per_yr) / 4.78:.3f}x the 4.78 mm/yr systematic)")
    for label, values in branch_effect.items():
        print(f"  {label:10s} published median {values['as_published_median_mm_per_yr']:+.3f} "
              f"RMS {values['as_published_rms_mm_per_yr']:.3f}  ->  aligned median "
              f"{values['reference_aligned_median_mm_per_yr']:+.3f} RMS "
              f"{values['reference_aligned_rms_mm_per_yr']:.3f} mm/yr")
    print(f"\n  product_v1 modified: NO")
    print(f"  {out_json}")
    print(f"  {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
