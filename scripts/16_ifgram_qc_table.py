#!/usr/bin/env python
"""
AOI-centric interferogram QC table for all 336 pairs.

Reads the frozen `mintpy_input_v1` stack **read-only** and computes, for every
interferogram, statistics restricted to the scientific AOI:

  * validity        - valid unwrapped-phase fraction of the AOI
  * coherence       - median, p25, mean and fraction above 0.2 / 0.3 / 0.5
  * connected comps - components within the AOI and the largest one's share
  * geometry        - temporal baseline, |B_perp|
  * water           - water fraction of the AOI (from the frozen geometry)

Only the AOI's bounding window is read from each interferogram (~1/4.4 of the
grid), so the whole table costs a fraction of a full-stack read.

This is descriptive QC for the RAW-336 baseline: nothing is excluded here.

Outputs
-------
qc/sci/ifgram_qc_table.csv
qc/sci/ifgram_qc_summary.json
qc/sci/aoi_mask_provenance.json

Usage
-----
    python scripts/16_ifgram_qc_table.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio.features
from rasterio.transform import Affine
from shapely.geometry import shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STACK = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "ifgramStack.h5"
GEOMETRY = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
PAIRS_CSV = PROJECT_ROOT / "manifests" / "sbas_pairs.csv"
OUT_DIR = PROJECT_ROOT / "qc" / "sci"

COHERENCE_THRESHOLDS = (0.2, 0.3, 0.5)


def aoi_mask_and_window(stack_meta: dict) -> tuple[np.ndarray, tuple[int, int, int, int], dict]:
    """Rasterise the AOI onto the stack grid, returning the mask and its window."""
    from rasterio.warp import transform_geom

    transform = Affine(
        stack_meta["X_STEP"], 0.0, stack_meta["X_FIRST"],
        0.0, stack_meta["Y_STEP"], stack_meta["Y_FIRST"],
    )
    length, width = int(stack_meta["LENGTH"]), int(stack_meta["WIDTH"])

    aoi = shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shape(transform_geom("EPSG:4326", f"EPSG:{int(stack_meta['EPSG'])}",
                                   aoi.__geo_interface__))

    minx, miny, maxx, maxy = aoi_utm.bounds
    col0 = max(0, int(np.floor((minx - stack_meta["X_FIRST"]) / stack_meta["X_STEP"])) - 1)
    col1 = min(width, int(np.ceil((maxx - stack_meta["X_FIRST"]) / stack_meta["X_STEP"])) + 1)
    row0 = max(0, int(np.floor((stack_meta["Y_FIRST"] - maxy) / -stack_meta["Y_STEP"])) - 1)
    row1 = min(length, int(np.ceil((stack_meta["Y_FIRST"] - miny) / -stack_meta["Y_STEP"])) + 1)

    window = (row0, row1, col0, col1)
    height, wid = row1 - row0, col1 - col0
    win_transform = Affine(
        stack_meta["X_STEP"], 0.0, stack_meta["X_FIRST"] + col0 * stack_meta["X_STEP"],
        0.0, stack_meta["Y_STEP"], stack_meta["Y_FIRST"] + row0 * stack_meta["Y_STEP"],
    )
    mask = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__],
        out_shape=(height, wid),
        transform=win_transform,
        invert=True,
    )
    provenance = {
        "grid": {"length": length, "width": width, "epsg": int(stack_meta["EPSG"]),
                 "x_first": stack_meta["X_FIRST"], "y_first": stack_meta["Y_FIRST"],
                 "x_step": stack_meta["X_STEP"], "y_step": stack_meta["Y_STEP"]},
        "aoi_bounds_utm": [round(v, 3) for v in aoi_utm.bounds],
        "aoi_bounds_source_crs": "EPSG:4326",
        "window_rows_cols": [row0, row1, col0, col1],
        "window_px": int(mask.size),
        "aoi_px": int(mask.sum()),
        "aoi_fraction_of_window": round(float(mask.mean()), 4),
        "aoi_area_km2": round(float(mask.sum()) * 40 * 40 / 1e6, 2),
    }
    return mask, window, provenance


def main() -> int:
    import h5py

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for required in (STACK, GEOMETRY, AOI_PATH, PAIRS_CSV):
        if not required.exists():
            print(f"FAIL: missing {required}")
            return 1

    with h5py.File(STACK, "r") as handle:
        # MintPy stores metadata attributes as strings, so cast explicitly.
        raw = {k: handle.attrs[k] for k in ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST",
                                           "X_STEP", "Y_STEP", "EPSG")}
        meta = {
            "LENGTH": int(float(raw["LENGTH"])),
            "WIDTH": int(float(raw["WIDTH"])),
            "X_FIRST": float(raw["X_FIRST"]),
            "Y_FIRST": float(raw["Y_FIRST"]),
            "X_STEP": float(raw["X_STEP"]),
            "Y_STEP": float(raw["Y_STEP"]),
            "EPSG": int(float(raw["EPSG"])),
        }
        dates = np.array(handle["date"]).astype(str)
        bperp = np.array(handle["bperp"])
        if "dropIfgram" in handle:
            # inverted name: True means IN USE
            in_use = np.array(handle["dropIfgram"]).astype(bool)
            if not in_use.all():
                print(f"FAIL: {int((~in_use).sum())} interferograms are excluded; "
                      "the baseline must use all 336")
                return 1
        n_ifg, length, width = handle["unwrapPhase"].shape
        chunks = handle["unwrapPhase"].chunks

    mask, window, provenance = aoi_mask_and_window(meta)
    row0, row1, col0, col1 = window
    height, wid = row1 - row0, col1 - col0
    n_aoi = int(mask.sum())

    pairs = pd.read_csv(PAIRS_CSV)
    tb_by_pair = {
        f"{a.replace('-', '')}_{b.replace('-', '')}": int(t)
        for a, b, t in zip(pairs["reference_date"], pairs["secondary_date"],
                           pairs["temporal_baseline_days"])
    }

    print("=" * 88)
    print("AOI-CENTRIC INTERFERGRAM QC TABLE (all 336 pairs)")
    print("=" * 88)
    print(f"\n  stack          : {n_ifg} ifgs, grid {length} x {width}, chunks {chunks}")
    print(f"  AOI window     : rows {row0}:{row1}, cols {col0}:{col1} "
          f"({height} x {wid} px)")
    print(f"  AOI pixels     : {n_aoi} ({provenance['aoi_area_km2']} km^2)")
    print(f"  water fraction : computing...")

    # water fraction of the AOI, from frozen geometry
    with h5py.File(GEOMETRY, "r") as handle:
        water = handle["waterMask"][row0:row1, col0:col1]
    # product convention: 0 = water, 1 = land (verified against ASF docs)
    water_in_aoi = float(np.mean(water[mask] == 0)) if n_aoi else 0.0
    provenance["water_fraction_of_aoi"] = round(water_in_aoi, 6)
    provenance["water_mask_convention"] = "0 = water, 1 = land (HyP3 product convention)"
    print(f"  water fraction : {water_in_aoi:.4f} of the AOI")

    rows: list[dict] = []
    print(f"\n  processing {n_ifg} interferograms...")

    with h5py.File(STACK, "r") as handle:
        unw_ds = handle["unwrapPhase"]
        cor_ds = handle["coherence"]
        cc_ds = handle["connectComponent"]

        for i in range(n_ifg):
            ref, sec = dates[i]
            date12 = f"{ref}_{sec}"

            unw = unw_ds[i, row0:row1, col0:col1]
            cor = cor_ds[i, row0:row1, col0:col1]
            cc = cc_ds[i, row0:row1, col0:col1]

            unw_aoi = unw[mask]
            cor_aoi = cor[mask]
            cc_aoi = cc[mask]

            # unwrapped phase: 0 is nodata (HyP3 convention)
            unw_valid = np.isfinite(unw_aoi) & (unw_aoi != 0)
            cor_valid = np.isfinite(cor_aoi) & (cor_aoi > 0)

            cor_ok = cor_aoi[cor_valid]
            n_cc_labels = 0
            largest_cc = 0.0
            cc_nonzero = cc_aoi[cc_aoi > 0]
            if cc_nonzero.size:
                labels, counts = np.unique(cc_nonzero, return_counts=True)
                n_cc_labels = int(labels.size)
                largest_cc = float(counts.max()) / n_aoi

            row = {
                "index": i,
                "date12": date12,
                "reference_date": ref,
                "secondary_date": sec,
                "temporal_baseline_days": tb_by_pair.get(date12),
                "perpendicular_baseline_m": round(float(bperp[i]), 1),
                "aoi_px": n_aoi,
                "unwrap_valid_px": int(unw_valid.sum()),
                "unwrap_valid_frac_aoi": round(float(unw_valid.mean()), 6),
                "coherence_valid_px": int(cor_valid.sum()),
                "coherence_valid_frac_aoi": round(float(cor_valid.mean()), 6),
                "coherence_median": round(float(np.median(cor_ok)), 4) if cor_ok.size else None,
                "coherence_p25": round(float(np.percentile(cor_ok, 25)), 4) if cor_ok.size else None,
                "coherence_mean": round(float(np.mean(cor_ok)), 4) if cor_ok.size else None,
                "components_in_aoi": n_cc_labels,
                "largest_component_frac_aoi": round(largest_cc, 6),
            }
            for t in COHERENCE_THRESHOLDS:
                row[f"coherence_frac_gt_{t}"] = (
                    round(float(np.mean(cor_ok > t)), 6) if cor_ok.size else 0.0
                )
            rows.append(row)

            if (i + 1) % 40 == 0 or i == n_ifg - 1:
                print(f"    {i + 1}/{n_ifg}")

    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "ifgram_qc_table.csv", index=False)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "RAW-336 baseline QC; nothing excluded",
        "frozen_input": "freeze/mintpy_input_v1",
        "interferograms": int(len(table)),
        "aoi": provenance,
        "coherence_thresholds": list(COHERENCE_THRESHOLDS),
        "distributions": {
            "unwrap_valid_frac_aoi": {
                "min": round(float(table["unwrap_valid_frac_aoi"].min()), 6),
                "median": round(float(table["unwrap_valid_frac_aoi"].median()), 6),
                "max": round(float(table["unwrap_valid_frac_aoi"].max()), 6),
            },
            "coherence_median": {
                "min": round(float(table["coherence_median"].min()), 4),
                "p25": round(float(table["coherence_median"].quantile(0.25)), 4),
                "median": round(float(table["coherence_median"].median()), 4),
                "p75": round(float(table["coherence_median"].quantile(0.75)), 4),
                "max": round(float(table["coherence_median"].max()), 4),
            },
            "components_in_aoi": {
                "min": int(table["components_in_aoi"].min()),
                "median": int(table["components_in_aoi"].median()),
                "max": int(table["components_in_aoi"].max()),
            },
            "largest_component_frac_aoi": {
                "min": round(float(table["largest_component_frac_aoi"].min()), 6),
                "median": round(float(table["largest_component_frac_aoi"].median()), 6),
                "max": round(float(table["largest_component_frac_aoi"].max()), 6),
            },
        },
        "by_temporal_baseline": {
            str(int(k)): {
                "count": int(v),
                "median_coherence": round(
                    float(table[table["temporal_baseline_days"] == k]["coherence_median"].median()), 4
                ),
                "median_largest_component_frac": round(
                    float(table[table["temporal_baseline_days"] == k]["largest_component_frac_aoi"].median()), 6
                ),
            }
            for k, v in table["temporal_baseline_days"].value_counts().sort_index().items()
        },
    }
    (OUT_DIR / "ifgram_qc_summary.json").write_text(json.dumps(summary, indent=2))
    (OUT_DIR / "aoi_mask_provenance.json").write_text(json.dumps(provenance, indent=2))

    print("\n" + "=" * 88)
    print("QC TABLE COMPLETE")
    print("=" * 88)
    print(f"  interferograms : {len(table)}")
    print(f"  coherence median across ifgs: "
          f"min {summary['distributions']['coherence_median']['min']} / "
          f"median {summary['distributions']['coherence_median']['median']} / "
          f"max {summary['distributions']['coherence_median']['max']}")
    print(f"  unwrap valid frac (AOI)     : "
          f"min {summary['distributions']['unwrap_valid_frac_aoi']['min']} / "
          f"median {summary['distributions']['unwrap_valid_frac_aoi']['median']}")
    print(f"\n  by temporal baseline:")
    for key, value in summary["by_temporal_baseline"].items():
        print(f"    {key:>3s} d : n={value['count']:3d}  "
              f"median coh={value['median_coherence']:.4f}  "
              f"largest comp={value['median_largest_component_frac']:.4f}")
    print(f"\n  {OUT_DIR / 'ifgram_qc_table.csv'}")
    print(f"  {OUT_DIR / 'ifgram_qc_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
