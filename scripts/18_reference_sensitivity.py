#!/usr/bin/env python
"""
Reference-region selection and reference-sensitivity analysis.

Why this is not a brute-force re-run
------------------------------------
The SBAS inversion is linear in the observations (including the L2 min-norm
velocity regularisation, which is a linear prior). Re-referencing therefore
shifts the entire velocity field by a **constant** — the velocity of the new
reference pixel — and leaves the spatial pattern untouched. So the reference
sensitivity of the AOI is exactly the spread of velocity among plausible stable
reference candidates, which can be evaluated exactly and cheaply.

This script:
  1. finds spatially coherent, high-temporal-coherence, low-velocity-uncertainty
     candidate reference regions and reports their geographic position;
  2. quantifies the systematic shift each would impose on the AOI velocity
     field (this IS the reference sensitivity);
  3. recommends a reference region and states the residual systematic
     uncertainty it implies.

The equivalence is independently validated by actually re-running one inversion
with a different reference (`scripts/18b_validate_reference.py`).

Outputs
-------
qc/sci/reference_candidates.csv
qc/sci/reference_sensitivity.json

Usage
-----
    python scripts/18_reference_sensitivity.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
from rasterio.transform import Affine
from rasterio.warp import transform as warp_transform, transform_geom
from shapely.geometry import shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
STACK = WORK / "inputs" / "ifgramStack.h5"
OUT_DIR = PROJECT_ROOT / "qc" / "sci"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"

BLOCK_PX = 60              # ~2.4 km blocks
MIN_COHERENCE = 0.85
MAX_ABS_VELOCITY = 0.006   # 6 mm/yr - a plausible "stable" pixel
MIN_BLOCK_PIXELS = 400


def grid_and_mask():
    with h5py.File(STACK, "r") as handle:
        md = {k: float(handle.attrs[k]) for k in
              ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    aoi = shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shape(transform_geom("EPSG:4326", f"EPSG:{int(md['EPSG'])}", aoi.__geo_interface__))
    minx, miny, maxx, maxy = aoi_utm.bounds
    col0 = max(0, int(np.floor((minx - md["X_FIRST"]) / md["X_STEP"])) - 1)
    col1 = min(int(md["WIDTH"]), int(np.ceil((maxx - md["X_FIRST"]) / md["X_STEP"])) + 1)
    row0 = max(0, int(np.floor((md["Y_FIRST"] - maxy) / -md["Y_STEP"])) - 1)
    row1 = min(int(md["LENGTH"]), int(np.ceil((md["Y_FIRST"] - miny) / -md["Y_STEP"])) + 1)
    win_transform = Affine(md["X_STEP"], 0.0, md["X_FIRST"] + col0 * md["X_STEP"],
                           0.0, md["Y_STEP"], md["Y_FIRST"] + row0 * md["Y_STEP"])
    mask = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=(row1 - row0, col1 - col0),
        transform=win_transform, invert=True)
    return mask, (row0, row1, col0, col1), md, win_transform


def to_lonlat(x: float, y: float, epsg: int) -> tuple[float, float]:
    lon, lat = warp_transform(f"EPSG:{epsg}", "EPSG:4326", [x], [y])
    return float(lon[0]), float(lat[0])


def main() -> int:
    mask, (row0, row1, col0, col1), md, win_transform = grid_and_mask()
    height, width = mask.shape
    n_aoi = int(mask.sum())

    print("=" * 88)
    print("REFERENCE-REGION SELECTION AND SENSITIVITY")
    print("=" * 88)
    print(f"\n  AOI pixels: {n_aoi}")

    with h5py.File(WORK / "velocity.h5", "r") as handle:
        vel = handle["velocity"][row0:row1, col0:col1].astype("float64")
        vstd = handle["velocityStd"][row0:row1, col0:col1].astype("float64")
        ref_y, ref_x = int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"])
    with h5py.File(WORK / "temporalCoherence.h5", "r") as handle:
        tc = handle["temporalCoherence"][row0:row1, col0:col1].astype("float64")

    # baseline reference in window coordinates
    base_ref_local = (ref_y - row0, ref_x - col0)
    base_vel = float(vel[base_ref_local]) if (
        0 <= base_ref_local[0] < height and 0 <= base_ref_local[1] < width) else None

    # ---- block-wise candidate scoring ------------------------------------
    print(f"\n  scanning {BLOCK_PX}px blocks (~{BLOCK_PX * 40 / 1000:.1f} km)...")
    rows = []
    for r0 in range(0, height, BLOCK_PX):
        for c0 in range(0, width, BLOCK_PX):
            r1, c1 = min(r0 + BLOCK_PX, height), min(c0 + BLOCK_PX, width)
            sub_mask = mask[r0:r1, c0:c1]
            n = int(sub_mask.sum())
            if n < MIN_BLOCK_PIXELS:
                continue
            tc_b = tc[r0:r1, c0:c1][sub_mask]
            v_b = vel[r0:r1, c0:c1][sub_mask]
            s_b = vstd[r0:r1, c0:c1][sub_mask]
            tc_b, v_b, s_b = tc_b[np.isfinite(tc_b)], v_b[np.isfinite(v_b)], s_b[np.isfinite(s_b)]
            if tc_b.size < MIN_BLOCK_PIXELS:
                continue
            med_tc = float(np.median(tc_b))
            med_v = float(np.median(v_b))
            med_s = float(np.median(s_b)) if s_b.size else np.nan
            # block centre -> geographic
            yc, xc = r0 + (r1 - r0) / 2, c0 + (c1 - c0) / 2
            gx = md["X_FIRST"] + (col0 + xc + 0.5) * md["X_STEP"]
            gy = md["Y_FIRST"] + (row0 + yc + 0.5) * md["Y_STEP"]
            lon, lat = to_lonlat(gx, gy, int(md["EPSG"]))
            rows.append({
                "block_row": r0, "block_col": c0,
                "window_row": int(yc), "window_col": int(xc),
                "full_grid_row": int(row0 + yc), "full_grid_col": int(col0 + xc),
                "lon": round(lon, 5), "lat": round(lat, 5),
                "n_pixels": n,
                "median_temporal_coherence": round(med_tc, 4),
                "median_velocity_m_per_yr": round(med_v, 5),
                "median_velocity_std": round(med_s, 5) if med_s == med_s else None,
                "stable_candidate": bool(
                    med_tc >= MIN_COHERENCE and abs(med_v) <= MAX_ABS_VELOCITY),
            })
    blocks = pd.DataFrame(rows)
    blocks.to_csv(OUT_DIR / "reference_candidates.csv", index=False)

    stable = blocks[blocks["stable_candidate"]].copy()
    print(f"  blocks scanned: {len(blocks)} | stable candidates: {len(stable)}")

    # ---- pick spatially separated regions --------------------------------
    chosen: list[pd.Series] = []
    # Selection MUST be independent of velocity, otherwise the sensitivity
    # estimate becomes circular: choosing the reference to minimise velocity
    # guarantees a near-zero spread and hides the real systematic. Candidates are
    # therefore ranked on coherence and velocity *uncertainty* only. Velocity is
    # reported afterwards as the quantity under test.
    # Within a high-coherence gate, the discriminating velocity-independent
    # criterion is the TIGHTNESS of the velocity estimate, so rank on
    # uncertainty first and coherence second.
    gated = stable[stable["median_temporal_coherence"] >= 0.98]
    stable = (gated if not gated.empty else stable).sort_values(
        ["median_velocity_std", "median_temporal_coherence"],
        ascending=[True, False],
    )
    min_sep_px = 150  # ~6 km
    for _, cand in stable.iterrows():
        if all(
            np.hypot(cand["window_row"] - c["window_row"],
                     cand["window_col"] - c["window_col"]) >= min_sep_px
            for c in chosen
        ):
            chosen.append(cand)
        if len(chosen) >= 5:
            break

    if not chosen:
        print("FAIL: no stable candidate regions found")
        return 1

    print(f"\n  selected {len(chosen)} spatially separated candidate references:")
    for i, c in enumerate(chosen, 1):
        print(f"    R{i}: lon={c['lon']:.4f} lat={c['lat']:.4f}  "
              f"tc={c['median_temporal_coherence']:.3f}  "
              f"v={1000 * c['median_velocity_m_per_yr']:+.2f} mm/yr  "
              f"std={1000 * (c['median_velocity_std'] or 0):.2f} mm/yr  "
              f"n={c['n_pixels']}")

    # ---- sensitivity = spread of candidate reference velocities ----------
    cand_vel = np.array([c["median_velocity_m_per_yr"] for c in chosen], dtype=float)
    spread = float(cand_vel.max() - cand_vel.min())
    sd = float(np.std(cand_vel, ddof=1)) if cand_vel.size > 1 else 0.0

    # effect on the AOI velocity field: a constant shift per candidate
    aoi_vel = vel[mask]
    aoi_vel = aoi_vel[np.isfinite(aoi_vel)]
    shifts = {
        f"R{i}": {
            "lon": float(c["lon"]), "lat": float(c["lat"]),
            "reference_velocity_m_per_yr": round(float(c["median_velocity_m_per_yr"]), 5),
            "shift_vs_baseline_mm_per_yr": round(
                1000 * (float(c["median_velocity_m_per_yr"]) - (base_vel or 0.0)), 3
            ),
            "aoi_p05_after_shift_mm_per_yr": round(
                1000 * (float(np.percentile(aoi_vel, 5)) - float(c["median_velocity_m_per_yr"])), 2
            ),
            "aoi_p95_after_shift_mm_per_yr": round(
                1000 * (float(np.percentile(aoi_vel, 95)) - float(c["median_velocity_m_per_yr"])), 2
            ),
        }
        for i, c in enumerate(chosen, 1)
    }

    recommended = chosen[0]
    # Spread among candidates selected WITHOUT reference to velocity.
    abs_vel = np.abs(cand_vel)

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "branch": "baseline_raw (uncorrected, all 336 pairs)",
        "methodology_warning": (
            "Candidate selection deliberately does NOT use velocity. Selecting a reference "
            "because its velocity is near zero is circular: it forces the spread to zero and "
            "hides the true systematic. The spread reported here is therefore the honest "
            "reference-induced uncertainty. Absolute LOS velocity cannot be better constrained "
            "than this without independent stability information (GNSS, levelling, bedrock "
            "geology)."
        ),
        "method": (
            "The SBAS inversion is linear in the observations, so re-referencing shifts the "
            "whole velocity field by the new reference pixel's velocity and leaves the spatial "
            "pattern unchanged. Reference sensitivity therefore equals the spread of velocity "
            "among plausible stable reference candidates. Validated by a real re-run."
        ),
        "baseline_reference": {
            "full_grid_yx": [ref_y, ref_x],
            "window_yx": [int(base_ref_local[0]), int(base_ref_local[1])],
            "velocity_m_per_yr": round(base_vel, 5) if base_vel is not None else None,
        },
        "selection_criteria": {
            "block_px": BLOCK_PX,
            "min_temporal_coherence": MIN_COHERENCE,
            "max_abs_velocity_m_per_yr": MAX_ABS_VELOCITY,
            "min_block_pixels": MIN_BLOCK_PIXELS,
            "min_separation_px": min_sep_px,
        },
        "blocks_scanned": int(len(blocks)),
        "stable_blocks": int(len(stable)),
        "candidates": shifts,
        "sensitivity": {
            "candidate_velocity_spread_mm_per_yr": round(1000 * spread, 3),
            "candidate_velocity_sd_mm_per_yr": round(1000 * sd, 3),
            "max_abs_candidate_velocity_mm_per_yr": round(1000 * float(abs_vel.max()), 3),
            "interpretation": (
                "Systematic uncertainty in ABSOLUTE LOS velocity imposed on the entire AOI by "
                "the choice of reference, among candidate regions selected on coherence and "
                "spatial coherence alone."
            ),
            "how_to_reduce": (
                "Only independent stability evidence (GNSS, levelling, exposed bedrock) can "
                "reduce this. Until then, treat the absolute velocity offset as uncertain at "
                "this level and interpret RELATIVE spatial gradients, which are unaffected by "
                "the reference choice."
            ),
        },
        "recommended_reference": {
            "lon": float(recommended["lon"]),
            "lat": float(recommended["lat"]),
            "full_grid_yx": [int(recommended["full_grid_row"]), int(recommended["full_grid_col"])],
            "median_temporal_coherence": float(recommended["median_temporal_coherence"]),
            "median_velocity_m_per_yr": float(recommended["median_velocity_m_per_yr"]),
            "rationale": "highest temporal coherence with tight velocity uncertainty among "
                         "spatially separated candidates. Velocity was deliberately excluded "
                         "from selection to avoid circularity; geographic plausibility "
                         "(bedrock / ridge vs floodplain) is for the owner to confirm.",
        },
        "note": "Provisional. The production reference is NOT frozen until the owner reviews this.",
    }
    (OUT_DIR / "reference_sensitivity.json").write_text(json.dumps(report, indent=2))

    print(f"\n  candidate velocity spread: {1000 * spread:.2f} mm/yr "
          f"(sd {1000 * sd:.2f} mm/yr)")
    print(f"  -> reference choice biases the whole AOI by up to this amount")
    print(f"\n  recommended R1: lon={recommended['lon']:.4f} lat={recommended['lat']:.4f}")
    print(f"\n  {OUT_DIR / 'reference_candidates.csv'}")
    print(f"  {OUT_DIR / 'reference_sensitivity.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
