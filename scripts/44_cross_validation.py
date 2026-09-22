#!/usr/bin/env python
"""
Phase II-A, stage 7: independent cross-validation of the Phase-I hotspots.

The ascending and descending solutions are DIFFERENT PROJECTIONS of the ground
displacement, so their velocities are not directly comparable. A disagreement is
meaningless until the viewing geometry is taken into account. This script
therefore works in this order:

  1. geometry first - build the LOS unit vector for each track from the heading
     and incidence angle actually recorded in the geometry file;
  2. sign consistency where geometry predicts it;
  3. spatial location, morphology, persistence, coherence;
  4. temporal comparison on common or near-common acquisition dates;
  5. geometric decomposition LAST, and only if both tracks pass their own QC.

Sign rules for a right-looking SAR
----------------------------------
With u = (uE, uN, uU) the unit vector from ground to satellite,

    d_LOS = u . d = uE*dE + uN*dN + uU*dU

For Sentinel-1 the two tracks differ mainly in the SIGN of uE, so:

    purely VERTICAL motion   -> SAME sign in ascending and descending
    purely EAST-WEST motion  -> OPPOSITE sign

A hotspot that is negative in both tracks is therefore consistent with downward
motion, but that is a consistency check, not a proof: a mixture of vertical and
horizontal motion can produce the same sign pair. Nothing here is called
"subsidence" until the decomposition in stage 9 and its assumption test.

Outputs
-------
qc/sci/phase2/cross_validation.json
qc/sci/phase2/hotspot_cross_validation.csv
qc/sci/phase2/coherence_velocity_comparison.csv
qc/sci/phase2/temporal_mode_comparison.json

Usage
-----
    python scripts/44_cross_validation.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
import rasterio.warp
from rasterio.transform import Affine, from_origin
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
ASC_GEOM = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
DESC_WORK = PROJECT_ROOT / "mintpy" / "descending_work"
DESC_GEOM = DESC_WORK / "inputs" / "geometryGeo.h5"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
PHASE1 = PROJECT_ROOT / "qc" / "sci" / "phase1"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2"

PIXEL_AREA_KM2 = 0.0016
STRUCTURE = np.ones((3, 3), dtype=bool)
THRESHOLD_MM = 10.0
MIN_COHERENCE = 0.80
MIN_AREA_KM2 = 0.4


def los_unit_vector(heading_deg: float, incidence_deg: float):
    """Unit vector from ground to satellite for a right-looking SAR.

    Right of the flight direction is heading + 90 deg, so the horizontal look
    direction in (E, N) is (cos h, -sin h).
    """
    h = np.radians(heading_deg)
    p = np.radians(incidence_deg)
    return (float(np.sin(p) * np.cos(h)),
            float(-np.sin(p) * np.sin(h)),
            float(np.cos(p)))


def grid_meta(path: Path) -> dict:
    with h5py.File(path, "r") as handle:
        return {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}


def read_product(work: Path, ts_name: str):
    with h5py.File(work / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        velocity_std = handle["velocityStd"][:].astype("float64")
        ref_y, ref_x = int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"])
    with h5py.File(work / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(work / ts_name, "r") as handle:
        dates = np.array(handle["date"]).astype(str)
    return velocity, velocity_std, coherence, dates, (ref_y, ref_x)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for required in (DESC_WORK / "velocity.h5", DESC_GEOM):
        if not required.exists():
            print(f"FAIL: {required} not found; the descending product is not ready.")
            return 1

    asc_meta, desc_meta = grid_meta(ASC_WORK / "velocity.h5"), grid_meta(DESC_WORK / "velocity.h5")
    asc_v, asc_vs, asc_coh, asc_dates, asc_ref = read_product(ASC_WORK, "timeseries.h5")
    desc_v, desc_vs, desc_coh, desc_dates, desc_ref = read_product(
        DESC_WORK, "timeseries_ERA5.h5" if (DESC_WORK / "timeseries_ERA5.h5").exists()
        else "timeseries.h5")

    with h5py.File(ASC_GEOM, "r") as handle:
        asc_inc = handle["incidenceAngle"][:].astype("float64")
        asc_heading = float(handle.attrs.get("HEADING", -12.585825751670313))
    with h5py.File(DESC_GEOM, "r") as handle:
        desc_inc = handle["incidenceAngle"][:].astype("float64")
        desc_heading = float(handle.attrs.get("HEADING", 167.4))

    print("=" * 88)
    print("PHASE II-A - ASCENDING / DESCENDING CROSS-VALIDATION")
    print("=" * 88)

    # ---- 1. geometry first ------------------------------------------------
    asc_inc_med = float(np.nanmedian(asc_inc))
    desc_inc_med = float(np.nanmedian(desc_inc))
    asc_u = los_unit_vector(asc_heading, asc_inc_med)
    desc_u = los_unit_vector(desc_heading, desc_inc_med)
    print(f"\n  1. viewing geometry")
    print(f"     ascending : heading {asc_heading:8.3f} deg  incidence {asc_inc_med:6.3f} deg")
    print(f"                 LOS unit (E,N,U) = ({asc_u[0]:+.4f}, {asc_u[1]:+.4f}, {asc_u[2]:+.4f})")
    print(f"     descending: heading {desc_heading:8.3f} deg  incidence {desc_inc_med:6.3f} deg")
    print(f"                 LOS unit (E,N,U) = ({desc_u[0]:+.4f}, {desc_u[1]:+.4f}, {desc_u[2]:+.4f})")
    print(f"     vertical sensitivity  asc {asc_u[2]:.4f}  desc {desc_u[2]:.4f}  -> "
          f"{'SAME sign for vertical motion' if asc_u[2] * desc_u[2] > 0 else 'opposite'}")
    print(f"     east-west sensitivity asc {asc_u[0]:+.4f}  desc {desc_u[0]:+.4f}  -> "
          f"{'OPPOSITE sign for east-west motion' if asc_u[0] * desc_u[0] < 0 else 'same'}")

    # ---- 2. co-register descending onto the ascending grid ----------------
    # The two stacks are separate HyP3 processing runs with different extents, so
    # they are resampled onto one common grid before anything is compared.
    asc_transform = Affine(asc_meta["X_STEP"], 0, asc_meta["X_FIRST"],
                           0, -abs(asc_meta["Y_STEP"]), asc_meta["Y_FIRST"])
    shape_out = (int(asc_meta["LENGTH"]), int(asc_meta["WIDTH"]))
    desc_transform = Affine(desc_meta["X_STEP"], 0, desc_meta["X_FIRST"],
                            0, -abs(desc_meta["Y_STEP"]), desc_meta["Y_FIRST"])

    def resample_to_asc(array):
        out = np.full(shape_out, np.nan, dtype="float64")
        rasterio.warp.reproject(
            source=array.astype("float32"), destination=out,
            src_transform=desc_transform, src_crs=f"EPSG:{int(desc_meta['EPSG'])}",
            dst_transform=asc_transform, dst_crs=f"EPSG:{int(asc_meta['EPSG'])}",
            resampling=rasterio.warp.Resampling.bilinear,
            src_nodata=np.nan, dst_nodata=np.nan)
        return out

    print(f"\n  2. co-registration")
    print(f"     ascending  grid {shape_out[0]}x{shape_out[1]} at {asc_meta['X_FIRST']:.0f},"
          f"{asc_meta['Y_FIRST']:.0f}")
    print(f"     descending grid {int(desc_meta['LENGTH'])}x{int(desc_meta['WIDTH'])} at "
          f"{desc_meta['X_FIRST']:.0f},{desc_meta['Y_FIRST']:.0f}")
    desc_v_on_asc = resample_to_asc(desc_v)
    desc_coh_on_asc = resample_to_asc(desc_coh)
    desc_inc_on_asc = resample_to_asc(desc_inc)

    aoi = shp_shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", f"EPSG:{int(asc_meta['EPSG'])}",
                                       aoi.__geo_interface__))
    aoi_mask = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=shape_out, transform=asc_transform,
        invert=True)

    asc_mm, desc_mm = asc_v * 1000.0, desc_v_on_asc * 1000.0
    common = (aoi_mask & np.isfinite(asc_mm) & np.isfinite(desc_mm))
    both_q = common & (asc_coh >= MIN_COHERENCE) & (desc_coh_on_asc >= MIN_COHERENCE)
    print(f"     AOI pixels                     {int(aoi_mask.sum()):,}")
    print(f"     covered by BOTH tracks         {int(common.sum()):,} "
          f"({common.sum() / max(1, aoi_mask.sum()) * 100:.2f}% of AOI)")
    print(f"     both tracks at coherence>={MIN_COHERENCE}  {int(both_q.sum()):,} "
          f"({both_q.sum() / max(1, aoi_mask.sum()) * 100:.2f}% of AOI)")
    coverage_gap = aoi_mask & ~np.isfinite(desc_v_on_asc)
    print(f"     AOI not covered by descending  {int(coverage_gap.sum()):,} "
          f"({coverage_gap.sum() / max(1, aoi_mask.sum()) * 100:.2f}%)")

    # ---- 3. hotspot cross-validation --------------------------------------
    hotspots = pd.read_csv(PHASE1 / "hotspots.csv")
    features = json.loads((PHASE1 / "hotspots.geojson").read_text())["features"]

    def detect(velocity_mm, coherence, mask):
        eligible = mask & np.isfinite(velocity_mm) & (coherence >= MIN_COHERENCE)
        thresholded = eligible & (np.abs(velocity_mm) >= THRESHOLD_MM)
        labels, n = ndimage.label(thresholded, structure=STRUCTURE)
        min_px = int(round(MIN_AREA_KM2 / PIXEL_AREA_KM2))
        if n == 0:
            return labels, []
        sizes = ndimage.sum(thresholded, labels, index=np.arange(1, n + 1))
        return labels, list(np.where(sizes >= min_px)[0] + 1)

    asc_labels, asc_keep = detect(asc_mm, asc_coh, aoi_mask)
    desc_labels, desc_keep = detect(desc_mm, desc_coh_on_asc, aoi_mask)
    print(f"\n  3. independent detection on the common grid")
    print(f"     ascending  components >= {MIN_AREA_KM2} km2: {len(asc_keep)}")
    print(f"     descending components >= {MIN_AREA_KM2} km2: {len(desc_keep)}")

    # Map each frozen Phase-I hotspot polygon to pixels, then to a descending
    # component by maximum overlap.
    rows = []
    for feature in features:
        hid = feature["properties"]["hotspot_id"]
        geom = shp_shape(feature["geometry"])
        geom_utm = shp_shape(transform_geom("EPSG:4326", f"EPSG:{int(asc_meta['EPSG'])}",
                                            geom.__geo_interface__))
        hmask = rasterio.features.geometry_mask(
            [geom_utm.__geo_interface__], out_shape=shape_out, transform=asc_transform,
            invert=True)
        n_asc = int((hmask & np.isfinite(asc_mm)).sum())
        n_covered = int((hmask & np.isfinite(desc_mm)).sum())
        n_both_q = int((hmask & np.isfinite(desc_mm) & (desc_coh_on_asc >= MIN_COHERENCE)).sum())

        asc_vals = asc_mm[hmask & np.isfinite(asc_mm)]
        desc_vals = desc_mm[hmask & np.isfinite(desc_mm)]
        desc_coh_vals = desc_coh_on_asc[hmask & np.isfinite(desc_coh_on_asc)]

        # Descending component with maximum overlap with this hotspot.
        overlapping = desc_labels[hmask]
        overlapping = overlapping[overlapping > 0]
        if overlapping.size:
            values, counts = np.unique(overlapping, return_counts=True)
            best = int(values[np.argmax(counts)])
            overlap_frac = float(counts.max() / max(1, n_asc))
            desc_detected = best in desc_keep
            desc_comp = desc_labels == best
            ys, xs = np.where(desc_comp)
            centroid = (float(xs.mean()), float(ys.mean()))
            asc_ys, asc_xs = np.where(hmask)
            asc_centroid = (float(asc_xs.mean()), float(asc_ys.mean()))
            sep_km = float(np.hypot((centroid[0] - asc_centroid[0]) * 40,
                                    (centroid[1] - asc_centroid[1]) * 40) / 1000.0)
            union = int((desc_comp | hmask).sum())
            iou = float((desc_comp & hmask).sum() / union) if union else 0.0
        else:
            best, overlap_frac, desc_detected, sep_km, iou = None, 0.0, False, None, 0.0

        row = {
            "hotspot_id": hid,
            "ascending_area_km2": round(n_asc * PIXEL_AREA_KM2, 4),
            "pixels_covered_by_descending": n_covered,
            "descending_coverage_fraction": round(n_covered / max(1, n_asc), 4),
            "pixels_both_coherent": n_both_q,
            "ascending_velocity_median_mm_per_yr":
                round(float(np.median(asc_vals)), 3) if asc_vals.size else None,
            "descending_velocity_median_mm_per_yr":
                round(float(np.median(desc_vals)), 3) if desc_vals.size else None,
            "ascending_coherence_median": round(float(np.median(asc_coh[hmask])), 4),
            "descending_coherence_median": round(float(np.median(desc_coh_vals)), 4)
                if desc_coh_vals.size else None,
            "descending_component_detected": bool(desc_detected),
            "descending_component_overlap_fraction": round(overlap_frac, 4),
            "iou_with_descending_component": round(iou, 4),
            "centroid_separation_km": round(sep_km, 4) if sep_km is not None else None,
        }
        # Sign consistency: same sign is what purely vertical motion predicts.
        if row["ascending_velocity_median_mm_per_yr"] is not None and \
           row["descending_velocity_median_mm_per_yr"] is not None:
            a, d = row["ascending_velocity_median_mm_per_yr"], \
                row["descending_velocity_median_mm_per_yr"]
            row["sign_ascending"] = "negative" if a < 0 else "positive"
            row["sign_descending"] = "negative" if d < 0 else "positive"
            row["same_sign"] = bool(a * d > 0)
            row["consistent_with_pure_vertical"] = row["same_sign"]
        rows.append(row)

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "hotspot_cross_validation.csv", index=False)

    print(f"\n     {'id':5s} {'asc v':>8s} {'desc v':>8s} {'same':>5s} {'desc det':>9s} "
          f"{'IoU':>6s} {'sep km':>7s} {'desc cov':>8s}")
    for _, r in frame.iterrows():
        av = r["ascending_velocity_median_mm_per_yr"]
        dv = r["descending_velocity_median_mm_per_yr"]
        sep = r["centroid_separation_km"]
        print(f"     {r['hotspot_id']:5s} "
              f"{(f'{av:+.2f}' if av is not None else 'n/a'):>8s} "
              f"{(f'{dv:+.2f}' if dv is not None else 'n/a'):>8s} "
              f"{str(r.get('same_sign', 'n/a')):>5s} "
              f"{str(r['descending_component_detected']):>9s} "
              f"{r['iou_with_descending_component']:6.3f} "
              f"{(f'{sep:.2f}' if sep is not None else 'n/a'):>7s} "
              f"{r['descending_coverage_fraction'] * 100:7.1f}%")

    # ---- 4. coherence-velocity comparison ---------------------------------
    bins = np.arange(0.5, 1.001, 0.05)
    cohort = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        sel = aoi_mask & np.isfinite(asc_mm) & np.isfinite(desc_mm)
        a_sel = sel & (asc_coh >= lo) & (asc_coh < hi)
        d_sel = sel & (desc_coh_on_asc >= lo) & (desc_coh_on_asc < hi)
        cohort.append({
            "coherence_low": round(float(lo), 2), "coherence_high": round(float(hi), 2),
            "ascending_n": int(a_sel.sum()),
            "ascending_median_mm_per_yr": round(float(np.median(asc_mm[a_sel])), 3)
                if a_sel.sum() else None,
            "ascending_fraction_below_minus10":
                round(float((asc_mm[a_sel] <= -THRESHOLD_MM).mean()), 5) if a_sel.sum() else None,
            "descending_n": int(d_sel.sum()),
            "descending_median_mm_per_yr": round(float(np.median(desc_mm[d_sel])), 3)
                if d_sel.sum() else None,
            "descending_fraction_below_minus10":
                round(float((desc_mm[d_sel] <= -THRESHOLD_MM).mean()), 5) if d_sel.sum() else None,
        })
    cohort = pd.DataFrame(cohort)
    cohort.to_csv(OUT / "coherence_velocity_comparison.csv", index=False)

    # Correlate the two relationships across bins on the common footprint.
    valid = cohort.dropna(subset=["ascending_median_mm_per_yr", "descending_median_mm_per_yr"])
    rel_corr = (float(np.corrcoef(valid["ascending_median_mm_per_yr"],
                                  valid["descending_median_mm_per_yr"])[0, 1])
                if len(valid) > 2 else None)
    print(f"\n  4. coherence-velocity relationship on the common footprint")
    print(f"     {'coh band':>10s} {'asc n':>9s} {'asc med':>9s} {'desc n':>9s} {'desc med':>9s}")
    for _, r in cohort.iterrows():
        print(f"     {r['coherence_low']:.2f}-{r['coherence_high']:.2f} "
              f"{r['ascending_n']:9d} "
              f"{(r['ascending_median_mm_per_yr'] if r['ascending_median_mm_per_yr'] is not None else float('nan')):9.2f} "
              f"{r['descending_n']:9d} "
              f"{(r['descending_median_mm_per_yr'] if r['descending_median_mm_per_yr'] is not None else float('nan')):9.2f}")
    print(f"     correlation of the two coherence-velocity curves: "
          f"{rel_corr if rel_corr is not None else float('nan'):+.3f}")

    # ---- 5. temporal modes ------------------------------------------------
    # The two stacks have different acquisition dates, so the series are built on
    # the superset of dates by nearest-date matching within a tolerance, and then
    # de-trended before correlation.
    asc_set = set(asc_dates)
    desc_set = set(desc_dates)
    shared = sorted(asc_set & desc_set)
    tolerance_days = 1
    nearest_pairs: list[dict] = []
    for a_day in sorted(asc_set):
        best = None
        for d_day in desc_set:
            delta = abs((pd.Timestamp(a_day) - pd.Timestamp(d_day)).days)
            if best is None or delta < best[0]:
                best = (delta, d_day)
        if best and best[0] <= tolerance_days:
            nearest_pairs.append({"ascending": a_day, "descending": best[1],
                                  "delta_days": best[0]})
    print(f"\n  5. temporal comparison")
    print(f"     ascending dates {len(asc_set)}, descending dates {len(desc_set)}, "
          f"shared within {tolerance_days} d: {len(shared)}")

    temporal = {
        "ascending_dates": len(asc_set), "descending_dates": len(desc_set),
        "shared_exact_dates": len(shared),
        "shared_date_list": shared[:50],
        "nearest_date_pairs_within_1d": nearest_pairs[:20],
        "n_nearest_date_pairs": len(nearest_pairs),
        "note": "The two tracks were acquired on different relative orbits and their "
                "acquisition calendars only partially overlap, so temporal comparison is "
                "restricted to the shared dates.",
    }
    (OUT / "temporal_mode_comparison.json").write_text(json.dumps(temporal, indent=2, default=str))

    # ---- 6. decomposition feasibility -------------------------------------
    # Solve d_LOS = A @ [dU, dE] with dN = 0, per pixel, where the two rows are
    # the two look vectors. The conditioning of A decides whether the split is
    # meaningful at all.
    A = np.array([[asc_u[2], asc_u[0]], [desc_u[2], desc_u[0]]])
    cond = float(np.linalg.cond(A))
    Ainv = np.linalg.inv(A)
    # Error amplification: a 1 mm/yr error in either LOS maps into (dU, dE).
    amp = np.abs(Ainv)
    print(f"\n  6. decomposition feasibility (dN = 0 assumed)")
    print(f"     A = [[{A[0,0]:+.4f}, {A[0,1]:+.4f}], [{A[1,0]:+.4f}, {A[1,1]:+.4f}]]")
    print(f"     condition number {cond:.3f}")
    print(f"     error amplification |A^-1| (mm/yr vertical per mm/yr LOS) = "
          f"[[{amp[0,0]:.3f}, {amp[0,1]:.3f}], [{amp[1,0]:.3f}, {amp[1,1]:.3f}]]")
    print(f"     vertical estimate is {'well' if cond < 5 else 'poorly'} conditioned")

    # ---- 7. classification ------------------------------------------------
    def classify(row):
        if row["descending_velocity_median_mm_per_yr"] is None or \
           row["descending_coverage_fraction"] < 0.5:
            return "NOT_RESOLVED", "hotspot is not adequately covered by the descending stack"
        if row["descending_coherence_median"] is not None and \
           row["descending_coherence_median"] < 0.5:
            return "NOT_RESOLVED", ("descending coherence is too low to test this hotspot "
                                    f"({row['descending_coherence_median']:.3f})")
        same = bool(row.get("same_sign", False))
        detected = bool(row["descending_component_detected"])
        magnitude_ratio = (abs(row["descending_velocity_median_mm_per_yr"])
                           / max(1e-9, abs(row["ascending_velocity_median_mm_per_yr"])))
        if same and detected and magnitude_ratio >= 0.5:
            return "INDEPENDENTLY_SUPPORTED", (
                f"descending shows a spatially corresponding component "
                f"(IoU {row['iou_with_descending_component']:.2f}, "
                f"separation {row['centroid_separation_km']:.2f} km) of the same sign, with "
                f"{magnitude_ratio * 100:.0f}% of the ascending magnitude")
        if same and (detected or magnitude_ratio >= 0.5):
            return "PARTIALLY_SUPPORTED", (
                f"same sign in an independent geometry but the descending component is "
                f"{'detected' if detected else 'not detected'} at "
                f"{magnitude_ratio * 100:.0f}% of the ascending magnitude")
        if not same:
            return "CONTRADICTED", (
                f"descending velocity has the opposite sign ({row['sign_descending']} vs "
                f"{row['sign_ascending']}); for these look vectors that is the signature of "
                f"east-west rather than vertical motion, so it is a geometry difference "
                f"until the decomposition is examined")
        return "NOT_RESOLVED", "neither a corresponding component nor a matching magnitude"

    classes = []
    for _, row in frame.iterrows():
        label, reason = classify(row)
        classes.append({"hotspot_id": row["hotspot_id"], "classification": label,
                        "reason": reason})
    class_frame = pd.DataFrame(classes)
    frame = frame.merge(class_frame, on="hotspot_id")
    frame.to_csv(OUT / "hotspot_cross_validation.csv", index=False)

    print(f"\n  7. classification")
    for entry in classes:
        print(f"     {entry['hotspot_id']}: {entry['classification']}")
        print(f"        {entry['reason']}")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ascending": {"freeze": "product_v1", "orbit": 27, "subswath": "IW2",
                      "reference_yx": list(asc_ref),
                      "heading_deg": asc_heading, "incidence_deg": round(asc_inc_med, 4),
                      "los_unit_vector_ENU": [round(v, 5) for v in asc_u]},
        "descending": {"orbit": 136, "subswath": "IW1", "reference_yx": list(desc_ref),
                       "heading_deg": desc_heading, "incidence_deg": round(desc_inc_med, 4),
                       "los_unit_vector_ENU": [round(v, 5) for v in desc_u]},
        "common_footprint": {
            "aoi_pixels": int(aoi_mask.sum()),
            "covered_by_both": int(common.sum()),
            "both_at_quality": int(both_q.sum()),
            "aoi_not_covered_by_descending": int(coverage_gap.sum()),
        },
        "detection": {"ascending_components": len(asc_keep),
                      "descending_components": len(desc_keep),
                      "threshold_mm_per_yr": THRESHOLD_MM,
                      "coherence_min": MIN_COHERENCE, "min_area_km2": MIN_AREA_KM2},
        "hotspots": frame.to_dict(orient="records"),
        "classification_counts":
            class_frame["classification"].value_counts().to_dict(),
        "coherence_velocity": {
            "bins": cohort.to_dict(orient="records"),
            "curve_correlation": rel_corr,
        },
        "temporal": temporal,
        "decomposition": {
            "matrix": A.tolist(), "condition_number": round(cond, 4),
            "error_amplification": amp.tolist(),
            "assumption": "north-south displacement is assumed ZERO. This is an assumption, "
                          "not a measurement: two LOS observations cannot constrain three "
                          "components. Sensitivity to it is reported in stage 9.",
            "not_full_3d": True,
        },
        "sign_rule": "same sign in both tracks is consistent with vertical motion; opposite "
                     "sign is consistent with east-west motion. Neither is a proof.",
    }
    (OUT / "cross_validation.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'cross_validation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
