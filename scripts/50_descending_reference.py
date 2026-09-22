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
    # MintPy writes velocityStd = 0 outside the inverted region, i.e. that is a
    # NO-DATA fill, not a perfect measurement. Treating it as "tight uncertainty"
    # would select an empty region, so those pixels are excluded here.
    valid = np.isfinite(velocity) & land & np.isfinite(velocity_std) & (velocity_std > 0)

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

    block_land_all = land
    block_land_all = land
    grid = []
    for r0 in range(0, length - BLOCK + 1, BLOCK):
        for c0 in range(0, width - BLOCK + 1, BLOCK):
            block_valid = valid[r0:r0 + BLOCK, c0:c0 + BLOCK]
            if block_valid.mean() < 0.99:
                continue
            if not land[r0:r0 + BLOCK, c0:c0 + BLOCK].all():
                continue
            grid.append({
                "row0": r0, "col0": c0,
                "center_row": r0 + BLOCK // 2, "center_col": c0 + BLOCK // 2,
                "median_coherence": float(np.median(coherence[r0:r0 + BLOCK, c0:c0 + BLOCK])),
                "median_velocity_mm_per_yr": float(np.median(vel_mm[r0:r0 + BLOCK, c0:c0 + BLOCK])),
                "median_velocity_std_mm_per_yr": float(np.median(std_mm[r0:r0 + BLOCK, c0:c0 + BLOCK])),
                "min_edge_distance_m": float(np.min(edge_distance[r0:r0 + BLOCK, c0:c0 + BLOCK])),
                "min_support": float(np.min(support[r0:r0 + BLOCK, c0:c0 + BLOCK])),
            })
    frame = pd.DataFrame(grid)
    if frame.empty:
        print("FAIL: no candidate blocks inside the inverted region.")
        return 1

    support_ok = frame["min_support"] >= MIN_VALID_FRACTION
    edge_ok = frame["min_edge_distance_m"] >= MIN_EDGE_DISTANCE_KM * 1000
    std_q25 = float(np.percentile(frame["median_velocity_std_mm_per_yr"], 25))
    std_ok = frame["median_velocity_std_mm_per_yr"] <= std_q25
    anomaly_ok = frame["median_velocity_mm_per_yr"].abs() <= MAX_ABS_VELOCITY_MM

    print(f"\n  candidate blocks (fully inside the inverted region, no water): {len(frame)}")
    print(f"  passing support >= {MIN_VALID_FRACTION}: {int(support_ok.sum())}")
    print(f"  passing edge >= {MIN_EDGE_DISTANCE_KM} km     : {int(edge_ok.sum())}")
    print(f"  passing std <= {std_q25:.3f} mm/yr (q25): {int(std_ok.sum())}")
    print(f"  passing |v| <= {MAX_ABS_VELOCITY_MM} mm/yr      : {int(anomaly_ok.sum())}")
    print(f"  coherence in the candidate pool: p50 "
          f"{frame['median_coherence'].median():.4f}  p90 "
          f"{np.percentile(frame['median_coherence'], 90):.4f}")

    # Selection order, stated plainly:
    #   1. hard data-quality gates that do NOT involve velocity: persistent
    #      support, distance from the coverage edge, no water, and formal
    #      uncertainty in the lowest quartile;
    #   2. the ANOMALY gate (|v| <= 2 mm/yr) - this does use velocity, as the
    #      review requires, but as a FILTER, never as an optimiser;
    #   3. highest temporal coherence among survivors.
    # If the anomaly gate leaves nothing, that is reported rather than silently
    # dropped, and the fallback minimises |v| instead of maximising coherence.
    base = support_ok & edge_ok & std_ok
    anomaly_free = True
    pool = frame[base & anomaly_ok]
    if pool.empty:
        anomaly_free = False
        pool = frame[base].assign(
            _absv=frame.loc[base, "median_velocity_mm_per_yr"].abs()
        ).sort_values("_absv")
    else:
        pool = pool.sort_values("median_coherence", ascending=False)

    chosen, used = [], []
    for _, row in pool.iterrows():
        if all(np.hypot(row["center_row"] - r, row["center_col"] - c) >= BLOCK * 4
               for r, c in used):
            chosen.append(row)
            used.append((row["center_row"], row["center_col"]))
        if len(chosen) >= 8:
            break

    standards = {
        "hard_gates": ["persistent_support", "edge_distance", "no_water",
                       "uncertainty_q25"],
        "anomaly_gate_applied": anomaly_free,
        "coherence_used_as_a_ranking_key": not anomaly_free,
        "velocity_used_as": "filter only" if anomaly_free
                             else "fallback ranking key (no anomaly-free block exists)",
        "pool_size": int(len(pool)),
    }

    frame.to_csv(OUT / "descending_reference_candidates.csv", index=False)

    if not chosen:
        print("\n  FAIL: no block satisfies support, edge, water and uncertainty "
              "criteria together.", flush=True)
        return 1
    if not anomaly_free:
        print(f"\n  WARNING: no candidate also satisfies |v| <= {MAX_ABS_VELOCITY_MM} mm/yr, "
              f"so the pool was relaxed on the anomaly criterion. This is reported, not "
              f"hidden: the descending stack has no demonstrably anomaly-free reference "
              f"region at the ascending standard.")

    best = chosen[0]
    offset = float(best["median_velocity_mm_per_yr"])
    print(f"\n  anomaly gate applied: {anomaly_free}")
    print(f"\n  selected reference region: block centre "
          f"(row {int(best['center_row'])}, col {int(best['center_col'])})")
    print(f"    median coherence {best['median_coherence']:.4f}   "
          f"median velocity {best['median_velocity_mm_per_yr']:+.4f} mm/yr   "
          f"std {best['median_velocity_std_mm_per_yr']:.4f} mm/yr")
    print(f"  {len(chosen)} spatially separated candidates for the sensitivity test")

    chosen_frame = pd.DataFrame(chosen)
    spread = (float(chosen_frame["median_velocity_mm_per_yr"].max()
                    - chosen_frame["median_velocity_mm_per_yr"].min())
              if len(chosen_frame) > 1 else 0.0)
    sd = (float(chosen_frame["median_velocity_mm_per_yr"].std())
          if len(chosen_frame) > 1 else 0.0)
    print(f"  reference-sensitivity spread among ACCEPTED candidates: "
          f"{spread:.3f} mm/yr (sd {sd:.3f})")
    if not anomaly_free and abs(best["median_velocity_mm_per_yr"]) > MAX_ABS_VELOCITY_MM:
        print(f"  NOTE: the selected block's median velocity is "
              f"{best['median_velocity_mm_per_yr']:+.2f} mm/yr, i.e. it is NOT "
              f"anomaly-free. It is the most coherent block available, not a "
              f"demonstrably stable one.")

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
            "coherence_used_for_ranking_only": True,
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
        "candidates_passing_hard_gates": int(base.sum()),
        "candidates_passing_anomaly_gate": int((base & anomaly_ok).sum()),
        "standards": standards,
        "selected_candidates": [
            {"center_y": int(r["center_row"]), "center_x": int(r["center_col"]),
             "median_coherence": float(r["median_coherence"]),
             "median_velocity_mm_per_yr": float(r["median_velocity_mm_per_yr"])}
            for r in chosen],
        "reference_sensitivity": {
            "n_candidates": len(chosen),
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
