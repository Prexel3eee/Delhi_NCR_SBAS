#!/usr/bin/env python
"""
Phase I, stage 5: do the hotspots survive reasonable changes of quality mask,
and are their oscillations localised or common-mode?

Part 1 - mask persistence
-------------------------
Every Phase I result so far depends on a threshold choice. A hotspot that only
exists under one particular coherence cut is an artefact of that choice; one
that survives a range of defensible cuts is a feature of the data. Each primary
hotspot is re-tested under a grid of alternative masks, and a hotspot is counted
as persisting only if at least half of its pixels remain inside a single
connected component that also meets the scenario's minimum area.

Part 2 - oscillation diagnostics
--------------------------------
Several hotspots show a large oscillation. Two very different things produce
that shape: real localised seasonal deformation, or common-mode error
(atmosphere, orbit, reference) that moves the whole scene together. The
discriminator is whether the oscillation also appears in an independently
chosen stable area and whether it is shared across hotspots tens of km apart.
A localised process cannot move a distant stable area; a common-mode error must.

This is a diagnostic of the DATA, not an attribution of cause.

Outputs
-------
qc/sci/phase1/hotspot_persistence.csv
qc/sci/phase1/hotspot_persistence.json
qc/sci/phase1/oscillation_diagnostics.json

Usage
-----
    python scripts/35_mask_persistence.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
from rasterio.transform import from_origin
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
GEOMETRY = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
OUT_QC = PROJECT_ROOT / "qc" / "sci" / "phase1"

PIXEL_AREA_KM2 = 0.0016
STRUCTURE = np.ones((3, 3), dtype=bool)

#: (name, coherence_min, |v| threshold mm/yr, min area km2)
SCENARIOS = [
    ("primary",            0.80, 10.0, 0.4),
    ("strict_coh_0.90",    0.90, 10.0, 0.4),
    ("relaxed_coh_0.70",   0.70, 10.0, 0.4),
    ("relaxed_coh_0.60",   0.60, 10.0, 0.4),
    ("relaxed_coh_0.50",   0.50, 10.0, 0.4),
    ("no_coh_cut",         0.00, 10.0, 0.4),
    ("threshold_7.5",      0.80,  7.5, 0.4),
    ("threshold_5",        0.80,  5.0, 0.4),
    ("threshold_15",       0.80, 15.0, 0.4),
    ("min_area_1.0",       0.80, 10.0, 1.0),
    ("min_area_2.0",       0.80, 10.0, 2.0),
    ("min_area_5.0",       0.80, 10.0, 5.0),
    ("coh_0.70_thr_5",     0.70,  5.0, 0.4),
    ("coh_0.90_thr_15",    0.90, 15.0, 0.4),
]


def components(velocity_mm: np.ndarray, base: np.ndarray, threshold_mm: float,
               coherence: np.ndarray, coherence_min: float, min_area_km2: float):
    """Threshold, label, and return only components meeting the minimum area."""
    mask = base & (coherence >= coherence_min)
    thresholded = mask & (np.abs(velocity_mm) >= threshold_mm)
    labels, n = ndimage.label(thresholded, structure=STRUCTURE)
    min_pixels = int(round(min_area_km2 / PIXEL_AREA_KM2))
    if n == 0:
        return labels, []
    sizes = ndimage.sum(thresholded, labels, index=np.arange(1, n + 1))
    keep = list(np.where(sizes >= min_pixels)[0] + 1)
    return labels, keep


def main() -> int:
    OUT_QC.mkdir(parents=True, exist_ok=True)

    with h5py.File(RAW_WORK / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        meta = {k: float(handle.attrs[k]) for k in
                ("X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP")}
    with h5py.File(RAW_WORK / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(RAW_WORK / "maskConnComp.h5", "r") as handle:
        conncomp = handle["mask"][:].astype(bool)
    with h5py.File(GEOMETRY, "r") as handle:
        land = handle["waterMask"][:].astype(bool)
    length, width = velocity.shape

    aoi = shp_shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", aoi.__geo_interface__))
    mask_aoi = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=(length, width),
        transform=from_origin(meta["X_FIRST"], meta["Y_FIRST"],
                              meta["X_STEP"], -meta["Y_STEP"]), invert=True)

    vel_mm = velocity * 1000.0
    base = mask_aoi & land & np.isfinite(velocity)

    print("=" * 88)
    print("PHASE I - MASK PERSISTENCE AND OSCILLATION DIAGNOSTICS")
    print("=" * 88)

    # ---- primary hotspot pixel masks -------------------------------------
    hotspots = pd.read_csv(OUT_QC / "hotspots.csv")
    plabels, pkeep = components(vel_mm, base, 10.0, coherence, 0.80, 0.4)
    masks = {}
    for _, hotspot in hotspots.iterrows():
        row_i = int(round((hotspot["centroid_y_utm"] - meta["Y_FIRST"]) / meta["Y_STEP"]))
        col_i = int(round((hotspot["centroid_x_utm"] - meta["X_FIRST"]) / meta["X_STEP"]))
        lab = plabels[row_i, col_i]
        if lab not in pkeep:
            best, best_d = None, np.inf
            for candidate in pkeep:
                ys, xs = np.where(plabels == candidate)
                d = np.hypot(ys.mean() - row_i, xs.mean() - col_i)
                if d < best_d:
                    best, best_d = int(candidate), d
            lab = best
        masks[hotspot["hotspot_id"]] = (plabels == lab)
    print(f"\n  primary hotspots: {len(masks)}")

    # ---- Part 1: persistence ---------------------------------------------
    records = []
    for name, coh_min, threshold, min_area in SCENARIOS:
        labels, keep = components(vel_mm, base, threshold, coherence, coh_min, min_area)
        for hid, pmask in masks.items():
            n_primary = int(pmask.sum())
            overlapping = labels[pmask]
            overlapping = overlapping[overlapping > 0]
            if overlapping.size == 0:
                records.append({"hotspot_id": hid, "scenario": name, "coherence_min": coh_min,
                                "threshold_mm_per_yr": threshold, "min_area_km2": min_area,
                                "overlap_fraction": 0.0, "component_area_km2": 0.0,
                                "component_median_mm_per_yr": None, "persists": False})
                continue
            values, counts = np.unique(overlapping, return_counts=True)
            best_lab = int(values[np.argmax(counts)])
            overlap = float(counts.max() / n_primary)
            if best_lab in keep:
                area = float((labels == best_lab).sum() * PIXEL_AREA_KM2)
                median_v = float(np.median(vel_mm[labels == best_lab]))
            else:
                area, median_v = 0.0, None
            records.append({
                "hotspot_id": hid, "scenario": name, "coherence_min": coh_min,
                "threshold_mm_per_yr": threshold, "min_area_km2": min_area,
                "overlap_fraction": round(overlap, 4),
                "component_area_km2": round(area, 4),
                "component_median_mm_per_yr": round(median_v, 3) if median_v is not None else None,
                "persists": bool(overlap >= 0.5 and best_lab in keep),
            })
    persistence = pd.DataFrame(records)
    persistence.to_csv(OUT_QC / "hotspot_persistence.csv", index=False)

    print(f"\n  Part 1 - persistence across {len(SCENARIOS)} mask scenarios:")
    table = persistence.pivot(index="hotspot_id", columns="scenario", values="persists")
    order = [s[0] for s in SCENARIOS]
    print(f"    {'id':5s} " + "".join(f"{s[:11]:>12s}" for s in order))
    for hid in table.index:
        print(f"    {hid:5s} " + "".join(
            f"{('yes' if table.loc[hid, s] else 'NO'):>12s}" for s in order))
    persist_counts = persistence.groupby("hotspot_id")["persists"].sum().to_dict()
    print(f"\n    scenarios survived (of {len(SCENARIOS)}):")
    for hid, count in sorted(persist_counts.items()):
        print(f"      {hid}  {int(count):2d}/{len(SCENARIOS)}")

    # ---- Part 2: oscillation diagnostics ---------------------------------
    long_ts = pd.read_csv(OUT_QC / "hotspot_timeseries.csv", dtype={"date": str})
    control_path = OUT_QC / "stable_control_timeseries.csv"
    diagnostics = {"available": False}
    if control_path.exists():
        control = pd.read_csv(control_path, dtype={"date": str}).sort_values("date")
        dates = sorted(long_ts["date"].unique())
        t = np.array([int(d[:4]) + (int(d[4:6]) - 1) / 12 + (int(d[6:]) - 1) / 365.25
                      for d in dates])
        t = t - t[0]

        def detrend(y, order=1):
            design = np.column_stack([t ** k for k in range(order + 1)])
            coef, *_ = np.linalg.lstsq(design, y, rcond=None)
            return y - design @ coef

        # A linear detrend leaves long-term CURVATURE in the residual, and a
        # "steep then flat" series has the opposite curvature to a steadily
        # accelerating one. Correlating those residuals measures shape difference
        # rather than a shared oscillation. The quadratic detrend removes the
        # low-frequency shape so the residual is dominated by the seasonal band.
        # Both are reported so the difference is visible.
        control_y = control.set_index("date").loc[dates, "los_displacement_mm"].to_numpy(float)
        control_res = detrend(control_y, 1)
        control_res2 = detrend(control_y, 2)
        ctrl_amp = float(np.percentile(control_res, 97.5) - np.percentile(control_res, 2.5))
        ctrl_amp2 = float(np.percentile(control_res2, 97.5) - np.percentile(control_res2, 2.5))

        def corr(a, b):
            if np.std(a) > 0 and np.std(b) > 0:
                return round(float(np.corrcoef(a, b)[0, 1]), 4)
            return None

        per_hotspot, residuals, residuals2 = {}, {}, {}
        for hid in sorted(long_ts["hotspot_id"].unique()):
            sub = long_ts[long_ts["hotspot_id"] == hid].sort_values("date")
            y = sub.set_index("date").loc[dates, "los_displacement_mm"].to_numpy(float)
            res = detrend(y, 1)
            res2 = detrend(y, 2)
            residuals[hid] = res
            residuals2[hid] = res2
            amplitude = float(np.percentile(res, 97.5) - np.percentile(res, 2.5))
            amplitude2 = float(np.percentile(res2, 97.5) - np.percentile(res2, 2.5))
            per_hotspot[hid] = {
                "detrended_amplitude_mm": round(amplitude, 3),
                "detrended_amplitude_quadratic_mm": round(amplitude2, 3),
                "correlation_with_stable_control": corr(res, control_res),
                "correlation_with_stable_control_quadratic": corr(res2, control_res2),
                "control_amplitude_mm": round(ctrl_amp, 3),
                "control_amplitude_quadratic_mm": round(ctrl_amp2, 3),
                "amplitude_ratio_to_control": round(amplitude / ctrl_amp, 3) if ctrl_amp else None,
                "amplitude_ratio_to_control_quadratic":
                    round(amplitude2 / ctrl_amp2, 3) if ctrl_amp2 else None,
            }

        hids = sorted(residuals)
        cross, cross2 = {}, {}
        for i, a in enumerate(hids):
            for b in hids[i + 1:]:
                key = f"{a}_vs_{b}"
                cross[key] = corr(residuals[a], residuals[b])
                cross2[key] = corr(residuals2[a], residuals2[b])
        pair_values = [v for v in cross.values() if v is not None]
        pair_values2 = [v for v in cross2.values() if v is not None]
        diagnostics = {
            "available": True,
            "method": "remove a linear (and separately a quadratic) trend from each series, "
                      "then correlate the residuals against an independent stable-area "
                      "control and against each other",
            "stable_control_amplitude_mm": round(ctrl_amp, 3),
            "stable_control_amplitude_quadratic_mm": round(ctrl_amp2, 3),
            "per_hotspot": per_hotspot,
            "cross_hotspot_correlation": cross,
            "cross_hotspot_correlation_quadratic": cross2,
            "cross_hotspot_correlation_median": round(float(np.median(pair_values)), 4),
            "cross_hotspot_correlation_median_quadratic":
                round(float(np.median(pair_values2)), 4),
            "interpretation": (
                "A residual strongly correlated with the independently chosen stable area is "
                "common-mode: it moves the whole scene and is therefore not localised "
                "deformation. A residual confined to one hotspot is localised and requires a "
                "local explanation. The quadratic variant is the more specific seasonality "
                "test; if the grouping changes between the two, the linear correlation was "
                "partly measuring long-term shape rather than a shared oscillation."),
        }
        print(f"\n  Part 2 - oscillation diagnostics:")
        print(f"    stable-control detrended amplitude: {ctrl_amp:.2f} mm "
              f"(quadratic {ctrl_amp2:.2f} mm)")
        print(f"    {'id':5s} {'amp':>8s} {'amp(q)':>8s} {'amp/ctl':>8s} {'amp/ctl(q)':>11s} "
              f"{'corr ctl':>9s} {'corr ctl(q)':>12s}")
        for hid, info in per_hotspot.items():
            print(f"    {hid:5s} {info['detrended_amplitude_mm']:8.2f} "
                  f"{info['detrended_amplitude_quadratic_mm']:8.2f} "
                  f"{(info['amplitude_ratio_to_control'] or float('nan')):8.3f} "
                  f"{(info['amplitude_ratio_to_control_quadratic'] or float('nan')):11.3f} "
                  f"{(info['correlation_with_stable_control'] or float('nan')):9.3f} "
                  f"{(info['correlation_with_stable_control_quadratic'] or float('nan')):12.3f}")
        print(f"\n    cross-hotspot residual correlation:")
        print(f"      {'pair':16s} {'linear':>9s} {'quadratic':>11s}")
        for key in cross:
            q = cross2.get(key)
            print(f"      {key:16s} {cross[key]:+9.3f} "
                  f"{(q if q is not None else float('nan')):+11.3f}")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"freeze": "product_v1",
                   "freeze_id": "2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37"},
        "scenarios": [{"name": n, "coherence_min": c, "threshold_mm_per_yr": t,
                       "min_area_km2": a} for n, c, t, a in SCENARIOS],
        "persistence": {hid: {"scenarios_survived": int(persist_counts[hid]),
                              "scenarios_total": len(SCENARIOS),
                              "outcome": ("robust" if persist_counts[hid] >= 0.8 * len(SCENARIOS)
                                          else "moderate" if persist_counts[hid] >= 0.5 * len(SCENARIOS)
                                          else "mask_dependent")}
                        for hid in persist_counts},
        "oscillation": diagnostics,
    }
    (OUT_QC / "hotspot_persistence.json").write_text(json.dumps(payload, indent=2, default=str))
    (OUT_QC / "oscillation_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, default=str))

    print(f"\n  {OUT_QC / 'hotspot_persistence.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
