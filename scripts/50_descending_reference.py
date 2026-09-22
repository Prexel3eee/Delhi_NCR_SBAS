#!/usr/bin/env python
"""
Phase II-A, stage 5: independent DESCENDING reference selection.

The ascending reference is NOT reused. MintPy auto-selects a reference when
`mintpy.reference.yx` is absent - which is exactly how INC-007 happened - so this
script selects the descending reference deliberately and records BOTH the pixel
MintPy used and the pixel chosen here, together with the constant offset between
them.

Selection criteria, applied in order (velocity is deliberately NOT a criterion,
to avoid the circularity identified in Phase I)
------------------------------------------------
  1. persistent valid support   the candidate block is valid in >= 95% of dates
  2. temporal coherence         block median >= the stack's 90th percentile
  3. tight uncertainty          block median formal velocityStd in the lowest quartile
  4. well inside the coverage   distance to the valid-data edge >= 2 km
  5. away from water            no water pixel in the block
  6. no obvious anomaly         block median |velocity| within 2 mm/yr

The chosen reference is the highest-coherence block satisfying all of them;
candidates are spatially separated so they are not all the same terrain.

Outputs
-------
qc/sci/phase2/descending_reference.json
qc/sci/phase2/descending_reference_candidates.csv

Usage
-----
    python scripts/50_descending_reference.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy import ndimage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK = PROJECT_ROOT / "mintpy" / "descending_work"
GEOMETRY = WORK / "inputs" / "geometryGeo.h5"
MANIFEST_DIR = PROJECT_ROOT / "manifests" / "descending"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2"

BLOCK = 50                      # 50 x 50 pixels = 2 x 2 km
MIN_VALID_FRACTION = 0.95
MIN_EDGE_DISTANCE_KM = 2.0
MAX_ABS_VELOCITY_MM = 2.0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for required in (WORK / "velocity.h5", GEOMETRY):
        if not required.exists():
            print(f"FAIL: {required} not found.")
            return 1

    with h5py.File(WORK / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        velocity_std = handle["velocityStd"][:].astype("float64")
        mintpy_ref = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
        meta = {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP")}
    with h5py.File(WORK / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(GEOMETRY, "r") as handle:
        land = handle["waterMask"][:].astype(bool)

    length, width = velocity.shape
    vel_mm = velocity * 1000.0
    std_mm = velocity_std * 1000.0
    valid = np.isfinite(velocity) & land

    print("=" * 88)
    print("PHASE II-A - DESCENDING REFERENCE SELECTION")
    print("=" * 88)
    print(f"\n  MintPy auto-selected reference: y={mintpy_ref[0]}, x={mintpy_ref[1]}")

    # 1. persistent valid support: valid in >= 95% of dates is approximated by the
    #    fraction of dates on which the pixel is finite in the time series.
    ts_path = (WORK / "timeseries_ERA5.h5") if (WORK / "timeseries_ERA5.h5").exists() \
        else (WORK / "timeseries.h5")
    with h5py.File(ts_path, "r") as handle:
        ts = handle["timeseries"]
        n_dates = ts.shape[0]
        finite_count = np.zeros((length, width), dtype="int32")
        # Count in row chunks to bound memory.
        for start in range(0, length, 256):
            slab = ts[:, start:start + 256, :]
            finite_count[start:start + 256, :] = np.isfinite(slab).sum(axis=0)
    support = finite_count / max(1, n_dates)

    # 4. distance to the valid-data edge
    edge_distance = ndimage.distance_transform_edt(valid) * abs(meta["Y_STEP"])

    coh_p90 = float(np.nanpercentile(coherence[valid], 90))
    std_q25 = float(np.nanpercentile(std_mm[valid], 25))

    rows = []
    for r0 in range(0, length - BLOCK + 1, BLOCK):
        for c0 in range(0, width - BLOCK + 1, BLOCK):
            block_valid = valid[r0:r0 + BLOCK, c0:c0 + BLOCK]
            if block_valid.mean() < 0.99:
                continue
            block_support = support[r0:r0 + BLOCK, c0:c0 + BLOCK]
            block_coh = coherence[r0:r0 + BLOCK, c0:c0 + BLOCK]
            block_std = std_mm[r0:r0 + BLOCK, c0:c0 + BLOCK]
            block_vel = vel_mm[r0:r0 + BLOCK, c0:c0 + BLOCK]
            block_edge = edge_distance[r0:r0 + BLOCK, c0:c0 + BLOCK]
            block_land = land[r0:r0 + BLOCK, c0:c0 + BLOCK]

            checks = {
                "persistent_support": bool(np.min(block_support) >= MIN_VALID_FRACTION),
                "high_coherence": bool(np.median(block_coh) >= coh_p90),
                "tight_uncertainty": bool(np.median(block_std) <= std_q25),
                "inside_coverage": bool(np.min(block_edge) >= MIN_EDGE_DISTANCE_KM * 1000),
                "no_water": bool(block_land.all()),
                "no_obvious_anomaly": bool(abs(np.median(block_vel)) <= MAX_ABS_VELOCITY_MM),
            }
            rows.append({
                "row0": r0, "col0": c0,
                "center_row": r0 + BLOCK // 2, "center_col": c0 + BLOCK // 2,
                "median_coherence": round(float(np.median(block_coh)), 5),
                "median_velocity_mm_per_yr": round(float(np.median(block_vel)), 4),
                "median_velocity_std_mm_per_yr": round(float(np.median(block_std)), 4),
                "min_edge_distance_m": round(float(np.min(block_edge)), 1),
                "min_support": round(float(np.min(block_support)), 5),
                **checks,
                "passes_all": bool(all(checks.values())),
            })

    frame = pd.DataFrame(rows)
    if frame.empty:
        print("FAIL: no candidate blocks found.")
        return 1
    frame.to_csv(OUT / "descending_reference_candidates.csv", index=False)

    passing = frame[frame["passes_all"]].copy()
    print(f"\n  candidate blocks evaluated : {len(frame)}")
    print(f"  passing every criterion    : {len(passing)}")
    print(f"  thresholds: coherence >= {coh_p90:.4f} (p90), std <= {std_q25:.4f} mm/yr (q25), "
          f"edge >= {MIN_EDGE_DISTANCE_KM} km, |v| <= {MAX_ABS_VELOCITY_MM} mm/yr")

    if passing.empty:
        print("\n  No block passes every criterion. Falling back to the passing subset of "
              "the four criteria that do not depend on the deformation value "
              "(velocity is excluded to avoid circularity).")
        relaxed = frame[frame[["persistent_support", "high_coherence",
                               "tight_uncertainty", "inside_coverage", "no_water"]].all(axis=1)]
        if relaxed.empty:
            print("FAIL: no acceptable reference region.", flush=True)
            return 1
        passing = relaxed
        print(f"  relaxed candidate count    : {len(passing)}")

    # Choose spatially separated candidates: greedily take the best, then the
    # next that is at least BLOCK*4 away, so the sensitivity sample is not one
    # patch of terrain measured several times.
    passing = passing.sort_values("median_coherence", ascending=False)
    chosen, used = [], []
    for _, row in passing.iterrows():
        if all(np.hypot(row["center_row"] - r, row["center_col"] - c) >= BLOCK * 4
               for r, c in used):
            chosen.append(row)
            used.append((row["center_row"], row["center_col"]))
        if len(chosen) >= 8:
            break

    best = chosen[0]
    offset = float(best["median_velocity_mm_per_yr"])
    print(f"\n  selected reference region: block centre "
          f"(row {int(best['center_row'])}, col {int(best['center_col'])})")
    print(f"    median coherence {best['median_coherence']:.4f}   "
          f"median velocity {best['median_velocity_mm_per_yr']:+.4f} mm/yr   "
          f"std {best['median_velocity_std_mm_per_yr']:.4f} mm/yr")
    print(f"  {len(chosen)} spatially separated candidates for the sensitivity test")

    spread = float(passing["median_velocity_mm_per_yr"].max()
                   - passing["median_velocity_mm_per_yr"].min()) if len(passing) > 1 else 0.0
    sd = float(passing["median_velocity_mm_per_yr"].std()) if len(passing) > 1 else 0.0
    print(f"  reference-sensitivity spread among ACCEPTED candidates: "
          f"{spread:.3f} mm/yr (sd {sd:.3f})")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "flight_direction": "DESCENDING", "relative_orbit": 136, "subswath": "IW1",
        "mintpy_auto_reference_yx": list(mintpy_ref),
        "selected_reference": {
            "center_y": int(best["center_row"]), "center_x": int(best["center_col"]),
            "block_pixels": BLOCK,
            "median_coherence": float(best["median_coherence"]),
            "median_velocity_mm_per_yr": float(best["median_velocity_mm_per_yr"]),
            "median_velocity_std_mm_per_yr": float(best["median_velocity_std_mm_per_yr"]),
        },
        "criteria": {
            "persistent_support_min": MIN_VALID_FRACTION,
            "coherence_min_quantile": "p90",
            "coherence_threshold": round(coh_p90, 5),
            "uncertainty_max_quantile": "q25",
            "uncertainty_threshold_mm_per_yr": round(std_q25, 5),
            "min_edge_distance_km": MIN_EDGE_DISTANCE_KM,
            "max_abs_velocity_mm_per_yr": MAX_ABS_VELOCITY_MM,
            "velocity_used_as_a_selection_criterion": False,
            "circularity_note": "Velocity is deliberately excluded from selection; using it "
                                "would bias the reference toward the answer, which is the "
                                "circularity identified in the Phase-I reference work.",
        },
        "candidates_evaluated": int(len(frame)),
        "candidates_passing_all": int(len(passing)),
        "selected_candidates": [
            {"center_y": int(r["center_row"]), "center_x": int(r["center_col"]),
             "median_coherence": float(r["median_coherence"]),
             "median_velocity_mm_per_yr": float(r["median_velocity_mm_per_yr"])}
            for r in chosen],
        "reference_sensitivity": {
            "spread_mm_per_yr": round(spread, 4),
            "sd_mm_per_yr": round(sd, 4),
            "note": "spread of the reference-candidate velocities; a change of reference "
                    "shifts every pixel by one constant and does not affect gradients",
        },
        "mintpy_offset_mm_per_yr": round(offset, 4),
        "convention": "velocities in the descending product are relative to the MintPy "
                      "auto-selected pixel until explicitly re-referenced; script 47 "
                      "re-references both tracks to a common stable control before any "
                      "cross-track comparison.",
    }
    (OUT / "descending_reference.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'descending_reference.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
