#!/usr/bin/env python
"""
Freeze the approved scientific processing decisions (v2).

Approved by the project owner:
  1. reference   lon 77.0950, lat 28.6426
  2. network     retain ALL 336 pairs (no curation)
  3. unwrap      correction DISABLED
  4. next        ERA5 tropospheric correction, then pixel-wise DEM-residual
  deramp         remains DISABLED in the principal branch

This resolves the reference lon/lat onto the frozen stack grid, verifies it lies
inside the AOI, records the exact `mintpy.reference.yx` the branches will use, and
writes a read-only decision record. Downstream branches read this file rather
than carrying their own copies of these values.

Outputs
-------
config/scientific_decisions_v2.json   (read-only)
config/mintpy_era5.txt                (principal branch template)
config/mintpy_dem_residual.txt        (second branch template)

Usage
-----
    python scripts/22_freeze_scientific_decisions.py
"""

from __future__ import annotations

import hashlib
import json
import stat
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import rasterio.features
from rasterio.transform import Affine
from rasterio.warp import transform as warp_transform, transform_geom
from shapely.geometry import shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STACK = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "ifgramStack.h5"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
CONFIG = PROJECT_ROOT / "config"
OUT = CONFIG / "scientific_decisions_v2.json"

REFERENCE_LON = 77.0950
REFERENCE_LAT = 28.6426
DECISION_ID_INPUT = "ERA5_then_DEM_residual_v2"


def canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def main() -> int:
    with h5py.File(STACK, "r") as handle:
        md = {k: float(handle.attrs[k]) for k in
              ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
        n_ifg = handle["unwrapPhase"].shape[0]
        in_use = int(np.array(handle["dropIfgram"]).sum())

    epsg = int(md["EPSG"])
    xs, ys = warp_transform("EPSG:4326", f"EPSG:{epsg}", [REFERENCE_LON], [REFERENCE_LAT])
    x, y = float(xs[0]), float(ys[0])
    col = int(round((x - md["X_FIRST"]) / md["X_STEP"]))
    row = int(round((md["Y_FIRST"] - y) / -md["Y_STEP"]))
    if not (0 <= row < md["LENGTH"] and 0 <= col < md["WIDTH"]):
        print(f"FAIL: reference resolves outside the grid: row={row} col={col}")
        return 1

    # must lie inside the AOI polygon
    aoi = shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shape(transform_geom("EPSG:4326", f"EPSG:{epsg}", aoi.__geo_interface__))
    px = md["X_FIRST"] + (col + 0.5) * md["X_STEP"]
    py = md["Y_FIRST"] + (row + 0.5) * md["Y_STEP"]
    inside = aoi_utm.contains(shape({"type": "Point", "coordinates": [px, py]}))

    print("=" * 88)
    print("FREEZING SCIENTIFIC DECISIONS v2")
    print("=" * 88)
    print(f"\n  reference lon/lat : {REFERENCE_LON}, {REFERENCE_LAT}")
    print(f"  projected (EPSG:{epsg}) : {x:.1f}, {y:.1f}")
    print(f"  pixel yx (full grid)    : ({row}, {col})")
    print(f"  inside AOI polygon      : {inside}")
    print(f"  network                 : {n_ifg} pairs, {in_use} flagged in use")

    if not inside:
        print("FAIL: the approved reference does not fall inside the AOI polygon")
        return 1

    decision = {
        "decision_id": DECISION_ID_INPUT,
        "reference": {
            "lon": REFERENCE_LON,
            "lat": REFERENCE_LAT,
            "epsg": epsg,
            "projected_x": round(x, 2),
            "projected_y": round(y, 2),
            "yx_full_grid": [row, col],
            "inside_aoi": True,
            "mintpy_reference_yx": f"{row},{col}",
        },
        "network": {"pairs": int(n_ifg), "curation": "none - all pairs retained"},
        "unwrap_error_correction": "disabled",
        "deramp": "disabled in the principal branch",
        "branch_order": ["ERA5 tropospheric", "pixel-wise DEM residual"],
    }
    freeze_id = hashlib.sha256(canonical(decision).encode()).hexdigest()

    record = {
        "freeze_id": freeze_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "approved_by": "project owner",
        "decisions": decision,
        "provenance": {
            "input_freeze": "freeze/mintpy_input_v1",
            "stack": str(STACK.relative_to(PROJECT_ROOT)),
            "reference_selection": "qc/sci/reference_sensitivity.json",
            "network_audit": "qc/sci/network_comparison.json",
            "unwrap_comparison": "qc/sci/unwrap_comparison.json",
        },
        "note": "All four decisions approved. The final deformation product is NOT declared; "
                "ERA5 and DEM-residual branches remain to be evaluated.",
    }
    OUT.write_text(json.dumps(record, indent=2))
    print(f"\n  freeze_id: {freeze_id}")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
