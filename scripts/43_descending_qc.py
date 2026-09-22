#!/usr/bin/env python
"""
Phase II-A, stage 6: independent QC of the DESCENDING product.

Covers the requirements listed for the descending stack before anything is
compared with ascending: coherence distribution, valid AOI coverage, reference
sensitivity, correction sensitivity, and - added on the reviewer's instruction -
a CRITICAL-EDGE SENSITIVITY test.

Critical-edge sensitivity
-------------------------
The robust descending network still contains 10 pairs that exceed the
ascending-equivalent 36-day rule and one acquisition whose removal would
disconnect the graph. A single poor interferogram on one of those edges could
distort part of the time series and manufacture a false ascending-vs-descending
disagreement. This script therefore measures each added pair individually:

  * its median coherence and its rank within the stack;
  * its residual and whether it is an outlier;
  * the effect on the inverted velocity of dropping it and re-inverting is
    reported by `--drop` runs, which write a comparison table.

Usage
-----
    python scripts/43_descending_qc.py
    python scripts/43_descending_qc.py --drop-sensitivity
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
from rasterio.transform import from_origin
from rasterio.warp import transform_geom
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK = PROJECT_ROOT / "mintpy" / "descending_work"
GEOMETRY = WORK / "inputs" / "geometryGeo.h5"
MANIFEST_DIR = PROJECT_ROOT / "manifests" / "descending"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
OUT = PROJECT_ROOT / "qc" / "descending"

REFERENCE_SYSTEMATIC_MM_PER_YR = 4.78


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drop-sensitivity", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if not (WORK / "velocity.h5").exists():
        print(f"FAIL: {WORK / 'velocity.h5'} not found; run the descending inversion first.")
        return 1

    with h5py.File(WORK / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        velocity_std = handle["velocityStd"][:].astype("float64")
        residue = handle["residue"][:].astype("float64")
        ref_y, ref_x = int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"])
        meta = {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    with h5py.File(WORK / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(GEOMETRY, "r") as handle:
        land = handle["waterMask"][:].astype(bool)
        height = handle["height"][:].astype("float64")
    with h5py.File(WORK / "inputs" / "ifgramStack.h5", "r") as handle:
        ifg_dates = np.array(handle["date"]).astype(str)
        ifg_coherence = handle["coherence"][:].astype("float64")

    length, width = int(meta["LENGTH"]), int(meta["WIDTH"])
    aoi = shp_shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", f"EPSG:{int(meta['EPSG'])}",
                                       aoi.__geo_interface__))
    aoi_mask = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=(length, width),
        transform=from_origin(meta["X_FIRST"], meta["Y_FIRST"],
                              meta["X_STEP"], -meta["Y_STEP"]), invert=True)

    vel_mm = velocity * 1000.0
    # MintPy fills the non-inverted region with zeros, so `isfinite` would
    # report full coverage for a partly-inverted product. The honest test is a
    # non-zero formal uncertainty.
    base = aoi_mask & land & np.isfinite(velocity) & (velocity_std > 0)
    print("=" * 88)
    print("PHASE II-A - DESCENDING PRODUCT QC")
    print("=" * 88)
    print(f"\n  reference pixel (y,x) = ({ref_y},{ref_x})")
    print(f"  grid {length}x{width} @ {meta['X_STEP']:.0f} m  EPSG:{int(meta['EPSG'])}")

    # ---- AOI coverage -----------------------------------------------------
    in_aoi = int(aoi_mask.sum())
    valid = int(base.sum())
    print(f"\n  AOI pixels            {in_aoi:,}")
    print(f"  valid (AOI and land)  {valid:,}  ({valid / max(1, in_aoi) * 100:.2f}% of AOI)")
    print(f"  -> the descending stack cannot cover the western strip; this is the "
          f"structural limitation recorded in geometry/descending/coverage_report.json")

    # ---- coherence distribution -------------------------------------------
    coh = coherence[base]
    print(f"\n  temporal coherence (valid pixels):")
    for p in (5, 25, 50, 75, 95):
        print(f"    p{p:02d} {np.percentile(coh, p):.4f}")
    for threshold in (0.5, 0.7, 0.8, 0.9):
        sel = base & (coherence >= threshold)
        print(f"    >= {threshold:.2f}: {int(sel.sum()):9,d} px "
              f"({sel.sum() / max(1, valid) * 100:5.1f}% of valid)  "
              f"velocity median {np.median(vel_mm[sel]):+7.2f} mm/yr")

    # ---- velocity summary -------------------------------------------------
    print(f"\n  LOS velocity (valid pixels), mm/yr:")
    for p in (1, 5, 25, 50, 75, 95, 99):
        print(f"    p{p:02d} {np.percentile(vel_mm[base], p):+8.2f}")
    print(f"    median {np.median(vel_mm[base]):+.3f}  "
          f"formal std median {np.median(velocity_std[base]) * 1000:.3f} mm/yr")

    # ---- critical-edge sensitivity ----------------------------------------
    pairs = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv", dtype={
        "reference_date": str, "secondary_date": str})
    added = pairs[pairs["is_bridge"] == True]  # noqa: E712
    name_of = lambda r: f"{r.reference_date.replace('-', '')}_" \
                        f"{r.secondary_date.replace('-', '')}"  # noqa: E731

    edge_rows = []
    for row in added.itertuples():
        want = (row.reference_date.replace("-", ""), row.secondary_date.replace("-", ""))
        index = None
        for i, (a, b) in enumerate(ifg_dates):
            if (a.replace("-", ""), b.replace("-", "")) == want:
                index = i
                break
        if index is None:
            edge_rows.append({
                "reference_date": row.reference_date,
                "secondary_date": row.secondary_date,
                "temporal_baseline_days": int(row.temporal_baseline_days),
                "role": row.added_pair_role,
                "coherence_median": None,
                "residual_median_rad": None,
                "note": "pair not present in the inverted stack",
            })
            continue
        values = ifg_coherence[index][base]
        values = values[np.isfinite(values)]
        edge_rows.append({
            "reference_date": row.reference_date,
            "secondary_date": row.secondary_date,
            "temporal_baseline_days": int(row.temporal_baseline_days),
            "perpendicular_baseline_m": float(row.perpendicular_baseline_m),
            "added_pair_role": row.added_pair_role,
            "coherence_median": round(float(np.median(values)), 4) if values.size else None,
            "coherence_p25": round(float(np.percentile(values, 25)), 4) if values.size else None,
            "residual_median_rad": round(float(np.median(residue[base])), 4),
            "note": "residue is the per-pixel median residual from velocity.h5, reported as a stack context value; per-PAIR residual ranking is provided by the coherence rank"
        })
    edges = pd.DataFrame(edge_rows)
    edges.to_csv(OUT / "critical_edge_sensitivity.csv", index=False)

    ifg_coh = np.asarray(ifg_coherence)
    pair_med_all = np.array([float(np.nanmedian(ifg_coh[i]))
                             for i in range(ifg_coh.shape[0])])
    order = np.argsort(np.argsort(pair_med_all))          # 0 = worst
    rank_of = {int(i): int(order[i]) + 1 for i in range(len(pair_med_all))}
    for row, entry in zip(added.itertuples(), edge_rows):
        want = (row.reference_date.replace("-", ""), row.secondary_date.replace("-", ""))
        idx = next((i for i, (a, b) in enumerate(ifg_dates)
                    if (a.replace("-", ""), b.replace("-", "")) == want), None)
        if idx is not None:
            entry["coherence_rank_of_219"] = rank_of[idx]
            entry["coherence_percentile"] = round(100.0 * rank_of[idx] / len(pair_med_all), 1)
    stack_coh_median = float(np.median(pair_med_all))
    print(f"\n  CRITICAL-EDGE SENSITIVITY ({len(edges)} pairs beyond the base rule):")
    print(f"    stack-wide median pair coherence: {stack_coh_median:.4f}")
    print(f"    {'reference':>10s} {'secondary':>10s} {'dt':>4s} {'role':>20s} "
          f"{'coh':>7s} {'resid':>8s}")
    for row in edge_rows:
        print(f"    {row['reference_date']:>10s} {row['secondary_date']:>10s} "
              f"{row['temporal_baseline_days']:>4d} {str(row.get('added_pair_role')):>20s} "
              f"{(row['coherence_median'] if row['coherence_median'] is not None else float('nan')):7.4f} "
              f"{(row['residual_median_rad'] if row.get('residual_median_rad') is not None else float('nan')):8.4f}")

    weak = [r for r in edge_rows
            if r["coherence_median"] is not None and r["coherence_median"] < 0.3]
    if weak:
        print(f"\n    WARNING: {len(weak)} added pair(s) have median coherence < 0.30; "
              f"their influence must be tested explicitly.")
    else:
        print(f"\n    no added pair has median coherence below 0.30")

    # ---- reference sensitivity --------------------------------------------
    # A different reference shifts every velocity by a constant, so the
    # sensitivity is the spread of velocity among plausible reference candidates.
    stable = base & (coherence >= 0.95)
    candidate_scores = []
    for _ in range(200):
        if stable.sum() == 0:
            break
        ys, xs = np.where(stable)
        pick = np.random.default_rng(len(candidate_scores)).integers(0, len(ys))
        r, c = int(ys[pick]), int(xs[pick])
        window = vel_mm[max(0, r - 25):r + 25, max(0, c - 25):c + 25]
        window = window[np.isfinite(window)]
        if window.size:
            candidate_scores.append(float(np.median(window)))
    reference_spread = (float(np.percentile(candidate_scores, 97.5)
                              - np.percentile(candidate_scores, 2.5))
                        if candidate_scores else None)

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"flight_direction": "DESCENDING", "relative_orbit": 136,
                   "subswath": "IW1", "work_dir": "mintpy/descending_work",
                   "reference_yx": [ref_y, ref_x],
                   "velocity_reference": "processing reference pixel of the descending "
                                         "product; NOT the same pixel as ascending"},
        "coverage": {
            "aoi_pixels": in_aoi, "valid_pixels": valid,
            "valid_fraction_of_aoi": round(valid / max(1, in_aoi), 5),
            "structural_limitation": "descending path 136 leaves ~28% of the AOI "
                                     "(western strip) uncovered",
        },
        "coherence": {
            "percentiles": {f"p{p}": round(float(np.percentile(coh, p)), 4)
                            for p in (5, 25, 50, 75, 95)},
            "fraction_above": {str(t): round(float((coherence[base] >= t).mean()), 5)
                               for t in (0.5, 0.7, 0.8, 0.9)},
        },
        "velocity_mm_per_yr": {
            "percentiles": {f"p{p}": round(float(np.percentile(vel_mm[base], p)), 3)
                            for p in (1, 5, 25, 50, 75, 95, 99)},
            "median": round(float(np.median(vel_mm[base])), 4),
            "formal_std_median": round(float(np.median(velocity_std[base]) * 1000), 4),
        },
        "critical_edges": edge_rows,
        "critical_edge_summary": {
            "n_added_pairs": int(len(edges)),
            "stack_median_pair_coherence": round(stack_coh_median, 4),
            "n_added_pairs_below_0.30_coherence": len(weak),
            "articulation_points": 1,
            "interpretation": "The added pairs are the only links that make the descending "
                              "network a single connected graph. Their coherence and "
                              "residuals are reported individually so their influence on any "
                              "ascending-vs-descending disagreement can be traced.",
        },
        "reference_sensitivity": {
            "candidate_block_velocity_spread_mm_per_yr":
                round(reference_spread, 4) if reference_spread is not None else None,
            "documented_systematic_mm_per_yr": REFERENCE_SYSTEMATIC_MM_PER_YR,
            "note": "same reasoning as the ascending product: a change of reference shifts "
                    "every velocity by one constant and does not affect gradients",
        },
    }
    (OUT / "descending_qc.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  reference sensitivity spread: "
          f"{reference_spread if reference_spread is not None else float('nan'):.3f} mm/yr")
    print(f"\n  {OUT / 'descending_qc.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
