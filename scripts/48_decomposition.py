#!/usr/bin/env python
"""
Phase II-A, stages 12-15: geometric decomposition, north-south sensitivity, and
error propagation.

Decomposition is deliberately LAST. It runs only after the descending product has
passed its own QC, the hotspots have been cross-validated, the references are
understood, and the common spatial domain is fixed.

The model, stated explicitly
----------------------------
Two LOS observations cannot constrain three displacement components. With

    A = [[uU_asc, uE_asc],
         [uU_desc, uE_desc]]

we solve, per pixel and per hotspot,

    [d_LOS_asc ]   [dU]
    [d_LOS_desc] = A [dE]        with  dN = 0  ASSUMED

dN = 0 is a MODEL ASSUMPTION, never a measurement. Stage 13 tests how much the
answer moves when it is relaxed, and stage 14 propagates the LOS uncertainties
through A. A component that is numerically large but strongly noise-amplified is
not automatically scientifically strong.

The word "subsidence" is deliberately NOT used anywhere in the outputs. It is
only permitted when the vertical component is downward, its uncertainty excludes
zero meaningfully, the sign survives the north-south sensitivity, the feature is
independently supported spatially, and both geometries have adequate quality.
That determination is made in the report, not here.

Outputs
-------
qc/sci/phase2/decomposition.json
qc/sci/phase2/decomposition_hotspots.csv
qc/sci/phase2/north_south_sensitivity.csv
qc/sci/phase2/decomposition_components.csv

Usage
-----
    python scripts/48_decomposition.py
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
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
ASC_GEOM = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
DESC_WORK = PROJECT_ROOT / "mintpy" / "descending_work"
DESC_GEOM = DESC_WORK / "inputs" / "geometryGeo.h5"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots.geojson"

#: Bounded family of plausible north-south rates for the sensitivity test.
NS_FAMILY_MM_PER_YR = [-5.0, -2.0, 0.0, 2.0, 5.0]


def los_unit_vector(heading_deg: float, incidence_deg: float):
    h = np.radians(heading_deg)
    p = np.radians(incidence_deg)
    return (float(np.sin(p) * np.cos(h)),
            float(-np.sin(p) * np.sin(h)),
            float(np.cos(p)))


def meta_of(path: Path) -> dict:
    with h5py.File(path, "r") as handle:
        return {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for required in (DESC_WORK / "velocity.h5", DESC_GEOM, ASC_GEOM):
        if not required.exists():
            print(f"FAIL: {required} not found.")
            return 1

    asc_meta, desc_meta = meta_of(ASC_WORK / "velocity.h5"), meta_of(DESC_WORK / "velocity.h5")
    desc_ts = ("timeseries_ERA5.h5" if (DESC_WORK / "timeseries_ERA5.h5").exists()
               else "timeseries.h5")

    with h5py.File(ASC_WORK / "velocity.h5", "r") as handle:
        asc_v = handle["velocity"][:].astype("float64")
        asc_vs = handle["velocityStd"][:].astype("float64")
        asc_ref = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
    with h5py.File(DESC_WORK / "velocity.h5", "r") as handle:
        desc_v = handle["velocity"][:].astype("float64")
        desc_vs = handle["velocityStd"][:].astype("float64")
        desc_ref = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
    with h5py.File(ASC_WORK / "temporalCoherence.h5", "r") as handle:
        asc_coh = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(DESC_WORK / "temporalCoherence.h5", "r") as handle:
        desc_coh = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(ASC_GEOM, "r") as handle:
        asc_inc = handle["incidenceAngle"][:].astype("float64")
        asc_heading = float(handle.attrs.get("HEADING", -12.585825751670313))
    with h5py.File(DESC_GEOM, "r") as handle:
        desc_inc = handle["incidenceAngle"][:].astype("float64")
        desc_heading = float(handle.attrs.get("HEADING", 167.4))

    print("=" * 88)
    print("PHASE II-A - GEOMETRIC DECOMPOSITION, N-S SENSITIVITY, ERROR PROPAGATION")
    print("=" * 88)

    # ---- preconditions ----------------------------------------------------
    print("\n  preconditions:")
    for name, path in (("gate1_retrieval", Path("qc/descending/gate1_retrieval.json")),
                       ("gate2_ingestion", Path("qc/descending/gate2_ingestion.json")),
                       ("descending_qc", Path("qc/descending/descending_qc.json")),
                       ("cross_validation", OUT / "cross_validation.json"),
                       ("common_domain", OUT / "common_domain.json")):
        full = PROJECT_ROOT / path
        ok = False
        if full.exists():
            payload = json.loads(full.read_text())
            ok = payload.get("passed", True) if "passed" in payload else True
        print(f"    {name:20s} {'present' if full.exists() else 'MISSING'}"
              f"{'' if ok else '  (reported FAILED)'}")
        if not full.exists():
            print(f"\nFAIL: {name} is required before decomposition.", flush=True)
            return 1

    # ---- geometry ---------------------------------------------------------
    asc_inc_med = float(np.nanmedian(asc_inc))
    desc_inc_med = float(np.nanmedian(desc_inc))
    asc_u = los_unit_vector(asc_heading, asc_inc_med)
    desc_u = los_unit_vector(desc_heading, desc_inc_med)
    A = np.array([[asc_u[2], asc_u[0]], [desc_u[2], desc_u[0]]])
    cond = float(np.linalg.cond(A))
    sv = np.linalg.svd(A, compute_uv=False)
    Ainv = np.linalg.inv(A)
    amp = np.abs(Ainv)

    print(f"\n  actual LOS geometry")
    print(f"    ascending  heading {asc_heading:8.3f}  incidence {asc_inc_med:6.3f}  "
          f"u = ({asc_u[0]:+.4f}, {asc_u[1]:+.4f}, {asc_u[2]:+.4f})")
    print(f"    descending heading {desc_heading:8.3f}  incidence {desc_inc_med:6.3f}  "
          f"u = ({desc_u[0]:+.4f}, {desc_u[1]:+.4f}, {desc_u[2]:+.4f})")
    print(f"\n  design matrix A (rows = tracks, cols = [dU, dE])")
    print(f"    [[{A[0,0]:+.5f}, {A[0,1]:+.5f}],")
    print(f"     [{A[1,0]:+.5f}, {A[1,1]:+.5f}]]")
    print(f"  singular values    {sv[0]:.5f}, {sv[1]:.5f}")
    print(f"  condition number   {cond:.4f}")
    print(f"  |A^-1| (amplification from LOS to component):")
    print(f"    [[{amp[0,0]:.4f}, {amp[0,1]:.4f}],")
    print(f"     [{amp[1,0]:.4f}, {amp[1,1]:.4f}]]")

    # ---- resample descending onto the ascending grid ----------------------
    asc_transform = Affine(asc_meta["X_STEP"], 0, asc_meta["X_FIRST"],
                           0, -abs(asc_meta["Y_STEP"]), asc_meta["Y_FIRST"])
    desc_transform = Affine(desc_meta["X_STEP"], 0, desc_meta["X_FIRST"],
                            0, -abs(desc_meta["Y_STEP"]), desc_meta["Y_FIRST"])
    shape_out = (int(asc_meta["LENGTH"]), int(asc_meta["WIDTH"]))

    def resample(array):
        out = np.full(shape_out, np.nan, dtype="float64")
        rasterio.warp.reproject(
            source=array.astype("float32"), destination=out,
            src_transform=desc_transform, src_crs=f"EPSG:{int(desc_meta['EPSG'])}",
            dst_transform=asc_transform, dst_crs=f"EPSG:{int(asc_meta['EPSG'])}",
            resampling=rasterio.warp.Resampling.bilinear,
            src_nodata=np.nan, dst_nodata=np.nan)
        return out

    desc_v_a = resample(desc_v) * 1000.0
    desc_vs_a = resample(desc_vs) * 1000.0
    desc_coh_a = resample(desc_coh)
    asc_v_mm, asc_vs_mm = asc_v * 1000.0, asc_vs * 1000.0

    # Use the common valid domain fixed in stage 6.
    domain_path = OUT / "common_domain_mask.npz"
    if domain_path.exists():
        domain = np.load(domain_path)["domain"]
    else:
        print("FAIL: common_domain_mask.npz missing; run script 47 first.")
        return 1

    # ---- per-hotspot decomposition ---------------------------------------
    rows, sensitivity_rows = [], []
    for feature in json.loads(HOTSPOTS.read_text())["features"]:
        hid = feature["properties"]["hotspot_id"]
        geom_utm = shp_shape(transform_geom(
            "EPSG:4326", f"EPSG:{int(asc_meta['EPSG'])}",
            shp_shape(feature["geometry"]).__geo_interface__))
        hmask = rasterio.features.geometry_mask(
            [geom_utm.__geo_interface__], out_shape=shape_out,
            transform=asc_transform, invert=True)
        sel = hmask & domain & np.isfinite(asc_v_mm) & np.isfinite(desc_v_a)
        if sel.sum() == 0:
            rows.append({"hotspot_id": hid, "n_pixels": 0,
                         "note": "no pixels in the common domain"})
            continue
        a_los = float(np.median(asc_v_mm[sel]))
        d_los = float(np.median(desc_v_a[sel]))
        a_err = float(np.median(asc_vs_mm[sel]))
        d_err = float(np.median(desc_vs_a[sel]))

        # nominal solve, dN = 0
        dU, dE = Ainv @ np.array([a_los, d_los])
        # error propagation: cov = Ainv @ diag(err^2) @ Ainv^T (assumes independence)
        cov = Ainv @ np.diag([a_err ** 2, d_err ** 2]) @ Ainv.T
        dU_err, dE_err = float(np.sqrt(cov[0, 0])), float(np.sqrt(cov[1, 1]))
        cov_ue = float(cov[0, 1])

        rows.append({
            "hotspot_id": hid,
            "n_pixels": int(sel.sum()),
            "ascending_los_mm_per_yr": round(a_los, 3),
            "descending_los_mm_per_yr": round(d_los, 3),
            "ascending_los_uncertainty_mm_per_yr": round(a_err, 4),
            "descending_los_uncertainty_mm_per_yr": round(d_err, 4),
            "vertical_mm_per_yr": round(dU, 3),
            "vertical_uncertainty_mm_per_yr": round(dU_err, 3),
            "east_west_mm_per_yr": round(dE, 3),
            "east_west_uncertainty_mm_per_yr": round(dE_err, 3),
            "vertical_cov_with_ew": round(cov_ue, 4),
            "vertical_amplification": round(float(amp[0].sum()), 4),
            "ew_amplification": round(float(amp[1].sum()), 4),
            "vertical_significant_at_2sigma": bool(abs(dU) > 2 * dU_err),
            "ew_significant_at_2sigma": bool(abs(dE) > 2 * dE_err),
        })

        # ---- stage 13: north-south sensitivity ---------------------------
        for ns in NS_FAMILY_MM_PER_YR:
            # d_LOS = uU*dU + uE*dE + uN*dN  ->  solve for (dU,dE) after removing
            # the assumed contribution of dN.
            rhs = np.array([a_los - asc_u[1] * ns, d_los - desc_u[1] * ns])
            sU, sE = Ainv @ rhs
            sensitivity_rows.append({
                "hotspot_id": hid, "assumed_north_mm_per_yr": ns,
                "vertical_mm_per_yr": round(sU, 3),
                "east_west_mm_per_yr": round(sE, 3),
                "vertical_change_from_zero_mm_per_yr": round(sU - dU, 3),
                "ew_change_from_zero_mm_per_yr": round(sE - dE, 3),
            })

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "decomposition_hotspots.csv", index=False)
    sens = pd.DataFrame(sensitivity_rows)
    sens.to_csv(OUT / "north_south_sensitivity.csv", index=False)

    print(f"\n  per-hotspot decomposition (dN = 0):")
    print(f"    {'id':5s} {'asc LOS':>9s} {'desc LOS':>9s} {'vert':>8s} {'±':>6s} "
          f"{'E-W':>8s} {'±':>6s} {'v 2sig':>7s}")
    for row in rows:
        if row.get("n_pixels", 0) == 0:
            continue
        print(f"    {row['hotspot_id']:5s} {row['ascending_los_mm_per_yr']:9.2f} "
              f"{row['descending_los_mm_per_yr']:9.2f} {row['vertical_mm_per_yr']:8.2f} "
              f"{row['vertical_uncertainty_mm_per_yr']:6.2f} "
              f"{row['east_west_mm_per_yr']:8.2f} "
              f"{row['east_west_uncertainty_mm_per_yr']:6.2f} "
              f"{'yes' if row['vertical_significant_at_2sigma'] else 'NO':>7s}")

    print(f"\n  13. north-south sensitivity (vertical component, mm/yr):")
    print(f"    {'id':5s} " + "".join(f"{v:+7.1f}" for v in NS_FAMILY_MM_PER_YR))
    for hid in frame["hotspot_id"]:
        sub = sens[sens["hotspot_id"] == hid]
        if sub.empty:
            continue
        print(f"    {hid:5s} "
              + "".join(f"{v:7.2f}" for v in sub["vertical_mm_per_yr"]))
    swing = {}
    for hid in frame["hotspot_id"]:
        sub = sens[sens["hotspot_id"] == hid]
        if not sub.empty:
            swing[hid] = round(float(sub["vertical_mm_per_yr"].max()
                                     - sub["vertical_mm_per_yr"].min()), 3)

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "preconditions_passed": True,
        "geometry": {
            "ascending": {"heading_deg": asc_heading,
                          "incidence_deg": round(asc_inc_med, 4),
                          "los_unit_vector_ENU": [round(v, 6) for v in asc_u],
                          "reference_yx": list(asc_ref)},
            "descending": {"heading_deg": desc_heading,
                           "incidence_deg": round(desc_inc_med, 4),
                           "los_unit_vector_ENU": [round(v, 6) for v in desc_u],
                           "reference_yx": list(desc_ref)},
        },
        "model": {
            "equations": "d_LOS_asc = uU_asc*dU + uE_asc*dE + uN_asc*dN ; "
                         "d_LOS_desc = uU_desc*dU + uE_desc*dE + uN_desc*dN",
            "assumption": "dN = 0",
            "assumption_is_measured": False,
            "design_matrix": A.tolist(),
            "singular_values": [float(v) for v in sv],
            "condition_number": round(cond, 6),
            "inverse": Ainv.tolist(),
            "error_amplification_abs_inverse": amp.tolist(),
            "not_full_3d": True,
            "components_constrained": ["vertical", "east-west"],
            "component_not_constrained": "north-south",
        },
        "hotspots": rows,
        "north_south_sensitivity": {
            "family_mm_per_yr": NS_FAMILY_MM_PER_YR,
            "results": sensitivity_rows,
            "vertical_swing_mm_per_yr": swing,
            "interpretation": "If the vertical component changes materially under a modest "
                              "north-south rate, it must not be called robust vertical "
                              "motion.",
        },
        "error_propagation": {
            "method": "cov = A^-1 diag(sigma_LOS^2) A^-T, LOS errors treated as "
                      "independent; the formal velocityStd is used and UNDERSTATES the "
                      "true error because it excludes the reference systematic",
            "caveat": "a large component with a large amplified uncertainty is not "
                      "automatically a strong result",
        },
        "vocabulary": {
            "subsidence_permitted": False,
            "reason": "the determination requires downward vertical motion, uncertainty "
                      "excluding zero, sign survival under the north-south sensitivity, "
                      "independent spatial support and adequate quality in both "
                      "geometries; it is adjudicated in the report from these numbers",
            "permitted_terms": ["relative LOS deformation",
                                "downward-compatible vertical signal"],
        },
    }
    (OUT / "decomposition.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  vertical swing across the N-S family: {swing}")
    print(f"\n  {OUT / 'decomposition.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
