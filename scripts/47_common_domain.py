#!/usr/bin/env python
"""
Phase II-A, stage 6-7, 11: common comparison domain, temporal comparability,
and reference alignment.

Defines ASC_DESC_COMMON_VALID_DOMAIN and writes it to disk. Every subsequent
ascending-vs-descending spatial comparison must use this domain; comparing over
the full ascending AOI would silently treat the ~28% of the AOI that descending
cannot see as agreement.

Reference alignment
-------------------
Three distinct zero levels exist and must never be combined silently:

  ascending AUTHORITATIVE product reference  (1384, 1451)
  ascending INTENDED scientific reference    (1378, 1426)   [not used]
  descending processing reference            (its own pixel)

For cross-track velocity comparisons this script re-references BOTH stacks to a
common stable-control region selected from the COMMON domain, so the comparison
is between two zero levels that mean the same thing. The magnitude of each
re-referencing is reported.

Outputs
-------
qc/sci/phase2/common_domain.json
qc/sci/phase2/common_domain_mask.npz
qc/sci/phase2/temporal_comparability.json
qc/sci/phase2/reference_alignment.json

Usage
-----
    python scripts/47_common_domain.py
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
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2"

COHERENCE_MIN = 0.80
STABLE_COHERENCE = 0.95
STABLE_MAX_ABS_VELOCITY = 3.0        # mm/yr


def meta_of(path: Path) -> dict:
    with h5py.File(path, "r") as handle:
        return {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}


def read_stack(work: Path, ts_name: str):
    with h5py.File(work / "velocity.h5", "r") as handle:
        velocity = handle["velocity"][:].astype("float64")
        velocity_std = handle["velocityStd"][:].astype("float64")
        ref = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
    with h5py.File(work / "temporalCoherence.h5", "r") as handle:
        coherence = handle["temporalCoherence"][:].astype("float64")
    with h5py.File(work / ts_name, "r") as handle:
        dates = np.array(handle["date"]).astype(str)
    return velocity, velocity_std, coherence, dates, ref


def temporal_profile(dates: np.ndarray) -> dict:
    stamps = pd.to_datetime(list(dates), format="%Y%m%d")
    gaps = np.diff(stamps.values).astype("timedelta64[D]").astype(int)
    months = pd.Series([d.month for d in stamps]).value_counts().sort_index()
    return {
        "first": stamps.min().date().isoformat(),
        "last": stamps.max().date().isoformat(),
        "span_years": round(float((stamps.max() - stamps.min()).days) / 365.25, 4),
        "n_acquisitions": int(len(stamps)),
        "median_revisit_days": float(np.median(gaps)),
        "largest_gap_days": int(gaps.max()),
        "gaps_over_36d": int((gaps > 36).sum()),
        "monthly_sampling": {int(k): int(v) for k, v in months.items()},
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for required in (DESC_WORK / "velocity.h5", DESC_GEOM, ASC_GEOM):
        if not required.exists():
            print(f"FAIL: {required} not found.")
            return 1

    asc_meta, desc_meta = meta_of(ASC_WORK / "velocity.h5"), meta_of(DESC_WORK / "velocity.h5")
    asc_ts = "timeseries.h5"
    desc_ts = ("timeseries_ERA5.h5" if (DESC_WORK / "timeseries_ERA5.h5").exists()
               else "timeseries.h5")
    asc_v, asc_vs, asc_coh, asc_dates, asc_ref = read_stack(ASC_WORK, asc_ts)
    desc_v, desc_vs, desc_coh, desc_dates, desc_ref = read_stack(DESC_WORK, desc_ts)

    print("=" * 88)
    print("PHASE II-A - COMMON DOMAIN, TEMPORAL COMPARABILITY, REFERENCE ALIGNMENT")
    print("=" * 88)

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

    desc_v_a = resample(desc_v)
    desc_coh_a = resample(desc_coh)
    desc_vs_a = resample(desc_vs)

    aoi = shp_shape(json.loads(AOI_PATH.read_text())["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", f"EPSG:{int(asc_meta['EPSG'])}",
                                       aoi.__geo_interface__))
    aoi_mask = rasterio.features.geometry_mask(
        [aoi_utm.__geo_interface__], out_shape=shape_out, transform=asc_transform,
        invert=True)

    with h5py.File(ASC_GEOM, "r") as handle:
        asc_land = handle["waterMask"][:].astype(bool)
    with h5py.File(DESC_GEOM, "r") as handle:
        desc_land = handle["waterMask"][:].astype("float64")
    desc_land_a = resample(desc_land) > 0.5

    # The domain is defined by VALIDITY, not by a coherence threshold. The two
    # stacks have structurally different coherence distributions - ascending was
    # built on a 36-day rule, descending on a robust network that includes 108-
    # and 120-day pairs - so a single coherence cut would either empty the domain
    # (descending never reaches the ascending level) or admit unusable ascending
    # pixels. Coherence is handled by stratification in the analysis instead.
    # VALIDITY is `velocityStd > 0`, not `isfinite(velocity)`: MintPy FILLS the
    # region it did not invert with zeros, so a finite check would report full
    # coverage for a product that is only partly inverted. The time series and
    # velocity are finite everywhere; only the inverted pixels have a non-zero
    # formal uncertainty.
    asc_ok = aoi_mask & asc_land & np.isfinite(asc_v) & (asc_vs > 0)
    desc_ok = aoi_mask & desc_land_a & np.isfinite(desc_v_a) & (desc_vs_a > 0)
    domain = asc_ok & desc_ok

    # ---- 6. common domain -------------------------------------------------
    aoi_px = int(aoi_mask.sum())
    print(f"\n  6. ASC_DESC_COMMON_VALID_DOMAIN")
    print(f"     (validity = formal uncertainty > 0, i.e. actually inverted)")
    print(f"     AOI pixels                       {aoi_px:,}")
    print(f"     ascending  valid+quality         {int(asc_ok.sum()):,}")
    print(f"     descending valid+quality         {int(desc_ok.sum()):,}")
    print(f"     COMMON domain                    {int(domain.sum()):,} "
          f"({domain.sum() / max(1, aoi_px) * 100:.2f}% of AOI)")
    print(f"     lost to descending coverage      {int((aoi_mask & ~desc_ok).sum()):,} "
          f"({(aoi_mask & ~desc_ok).sum() / max(1, aoi_px) * 100:.2f}% of AOI)")

    overlap_km2 = float(domain.sum() * 0.0016)
    hotspot_rows = []
    if HOTSPOTS.exists():
        print(f"\n     hotspot containment inside the common domain:")
        for feature in json.loads(HOTSPOTS.read_text())["features"]:
            hid = feature["properties"]["hotspot_id"]
            geom_utm = shp_shape(transform_geom(
                "EPSG:4326", f"EPSG:{int(asc_meta['EPSG'])}",
                shp_shape(feature["geometry"]).__geo_interface__))
            hmask = rasterio.features.geometry_mask(
                [geom_utm.__geo_interface__], out_shape=shape_out,
                transform=asc_transform, invert=True)
            total = int(hmask.sum())
            in_domain = int((hmask & domain).sum())
            frac = in_domain / max(1, total)
            hotspot_rows.append({"hotspot_id": hid, "pixels": total,
                                 "pixels_in_common_domain": in_domain,
                                 "fraction": round(frac, 6),
                                 "fully_covered": bool(frac > 0.99)})
            print(f"       {hid}: {in_domain}/{total} ({frac * 100:.2f}%) "
                  f"{'FULLY COVERED' if frac > 0.99 else 'INCOMPLETE'}")
    if hotspot_rows and not all(r["fully_covered"] for r in hotspot_rows):
        print("\n     WARNING: a Phase-I hotspot is not fully inside the common domain.")

    np.savez_compressed(OUT / "common_domain_mask.npz",
                        domain=domain, ascending_valid=asc_ok, descending_valid=desc_ok,
                        aoi=aoi_mask)

    # ---- 7. temporal comparability ---------------------------------------
    asc_prof, desc_prof = temporal_profile(asc_dates), temporal_profile(desc_dates)
    shared = sorted(set(asc_dates) & set(desc_dates))
    overlap_start = max(asc_prof["first"], desc_prof["first"])
    overlap_end = min(asc_prof["last"], desc_prof["last"])
    print(f"\n  7. temporal comparability")
    print(f"     {'':14s} {'ascending':>12s} {'descending':>12s}")
    for key in ("first", "last", "span_years", "n_acquisitions", "median_revisit_days",
                "largest_gap_days", "gaps_over_36d"):
        print(f"     {key:14s} {str(asc_prof[key]):>12s} {str(desc_prof[key]):>12s}")
    print(f"     shared date interval: {overlap_start} .. {overlap_end}")
    print(f"     exactly shared acquisition dates: {len(shared)}")

    # ---- 11. reference alignment -----------------------------------------
    # Re-reference BOTH stacks to a stable control selected from the COMMON
    # domain, so the two zero levels mean the same thing.
    # Per-stack coherence percentiles: requiring an absolute level would again
    # exclude every pixel from the lower-coherence stack.
    asc_coh_p75 = float(np.nanpercentile(asc_coh[domain], 75))
    desc_coh_p75 = float(np.nanpercentile(desc_coh_a[domain], 75))
    stable = (domain
              & (asc_coh >= asc_coh_p75) & (desc_coh_a >= desc_coh_p75)
              & (np.abs(asc_v * 1000) <= STABLE_MAX_ABS_VELOCITY)
              & (np.abs(desc_v_a * 1000) <= STABLE_MAX_ABS_VELOCITY))
    asc_offset = float(np.median(asc_v[stable]) * 1000) if stable.sum() else 0.0
    desc_offset = float(np.median(desc_v_a[stable]) * 1000) if stable.sum() else 0.0
    asc_v_ref = asc_v * 1000 - asc_offset
    desc_v_ref = desc_v_a * 1000 - desc_offset

    print(f"\n  11. reference alignment")
    print(f"     per-stack stable-control coherence thresholds: "
          f"ascending p75 {asc_coh_p75:.4f}, descending p75 {desc_coh_p75:.4f}")
    print(f"     stable control pixels (common domain): {int(stable.sum()):,}")
    print(f"     ascending  reference pixel {asc_ref}, velocity there "
          f"{float(asc_v[asc_ref]) * 1000:+.4f} mm/yr")
    print(f"     descending reference pixel {desc_ref}, velocity there "
          f"{float(desc_v[desc_ref]) * 1000:+.4f} mm/yr")
    print(f"     re-referencing ascending  by {asc_offset:+.4f} mm/yr")
    print(f"     re-referencing descending by {desc_offset:+.4f} mm/yr")
    print(f"     -> after alignment both are relative to the SAME common stable control")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "domain_definition": "ascending valid coverage AND descending valid coverage "
                             "AND scientific AOI; no coherence threshold is applied to "
                             "the domain because the two stacks have structurally "
                             "different coherence distributions",
        "coherence_distributions": {
            "ascending_p50": round(float(np.nanpercentile(asc_coh[domain], 50)), 4),
            "ascending_p90": round(float(np.nanpercentile(asc_coh[domain], 90)), 4),
            "descending_p50": round(float(np.nanpercentile(desc_coh_a[domain], 50)), 4),
            "descending_p90": round(float(np.nanpercentile(desc_coh_a[domain], 90)), 4),
        },
        "common_domain": {
            "aoi_pixels": aoi_px,
            "ascending_valid_quality_pixels": int(asc_ok.sum()),
            "descending_valid_quality_pixels": int(desc_ok.sum()),
            "common_pixels": int(domain.sum()),
            "overlap_area_km2": round(overlap_km2, 3),
            "overlap_fraction_of_aoi": round(float(domain.sum() / max(1, aoi_px)), 6),
            "aoi_lost_to_descending": int((aoi_mask & ~desc_ok).sum()),
            "aoi_lost_fraction": round(
                float((aoi_mask & ~desc_ok).sum() / max(1, aoi_px)), 6),
            "hotspots": hotspot_rows,
            "requirement": "every ascending-vs-descending spatial comparison must use "
                           "this domain; the full ascending AOI must not be used",
            "mask_file": "qc/sci/phase2/common_domain_mask.npz",
        },
        "temporal": {
            "ascending": asc_prof, "descending": desc_prof,
            "overlap_interval": [overlap_start, overlap_end],
            "exactly_shared_dates": len(shared),
            "shared_date_list": shared,
            "note": "Two comparisons are reported downstream: (A) native record, each "
                    "product over its own full span; (B) common period, both restricted "
                    "to the shared interval. Dates are never resampled to force "
                    "identity.",
        },
        "reference_alignment": {
            "ascending_reference_yx": list(asc_ref),
            "descending_reference_yx": list(desc_ref),
            "ascending_authoritative_reference_note":
                "see provenance/errata/INC-007.json",
            "stable_control_pixels": int(stable.sum()),
            "ascending_stable_coherence_p75": round(asc_coh_p75, 5),
            "descending_stable_coherence_p75": round(desc_coh_p75, 5),
            "stable_max_abs_velocity_mm_per_yr": STABLE_MAX_ABS_VELOCITY,
            "ascending_rereference_offset_mm_per_yr": round(asc_offset, 4),
            "descending_rereference_offset_mm_per_yr": round(desc_offset, 4),
            "convention": "both stacks re-referenced to the median velocity of the common "
                          "stable control, so cross-track differences are between "
                          "identically defined zero levels",
        },
    }
    (OUT / "common_domain.json").write_text(json.dumps(payload, indent=2, default=str))
    (OUT / "temporal_comparability.json").write_text(
        json.dumps(payload["temporal"], indent=2, default=str))
    (OUT / "reference_alignment.json").write_text(
        json.dumps(payload["reference_alignment"], indent=2, default=str))
    print(f"\n  {OUT / 'common_domain.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
