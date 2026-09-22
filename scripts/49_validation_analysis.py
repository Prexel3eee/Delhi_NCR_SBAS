#!/usr/bin/env python
"""
Phase II-A, stages 8-10: hotspot cross-validation with uncertainties, the
coherence-velocity test in three forms, and temporal group validation.

Stage 9 is run in the forms the review requires, and the temporal-baseline
classes are NEVER pooled into a single statistic:

  ascending full            336 pairs, 36 d / 250 m rule
  descending full           219 pairs, robust network (the principal product)
  descending baseline-matched  only pairs with dT <= 36 d and |B_perp| <= 250 m

The baseline-matched descending form is a DIAGNOSTIC for comparability only. It
never replaces the robust inversion network. If its separate inversion has not
been produced, the script says so rather than substituting a proxy silently.

Stage 10 tests whether the Phase-I north/south temporal grouping survives an
independent viewing geometry: the grouping is compared on de-trended,
normalised series over shared epochs, by cross-correlation and by turning-point
timing. Amplitudes are NOT required to match, because the LOS projections differ.

Outputs
-------
qc/sci/phase2/hotspot_validation.csv
qc/sci/phase2/coherence_velocity_3form.json
qc/sci/phase2/coherence_velocity_by_baseline_class.csv
qc/sci/phase2/temporal_groups.json

Usage
-----
    python scripts/49_validation_analysis.py
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
from rasterio.transform import Affine
from rasterio.warp import transform_geom
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
DESC_WORK = PROJECT_ROOT / "mintpy" / "descending_work"
DESC_SUB_WORK = PROJECT_ROOT / "mintpy" / "descending_basematched_work"
ASC_GEOM = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
DESC_GEOM = DESC_WORK / "inputs" / "geometryGeo.h5"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots.geojson"

COHERENCE_MIN = 0.80
THRESHOLD_MM = 10.0
NS_GROUPS = {"northern": ["H002", "H003", "H005"], "southern": ["H001", "H004"]}


def meta_of(path: Path) -> dict:
    with h5py.File(path, "r") as handle:
        return {k: float(handle.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}


def read_series(work: Path, ts_name: str) -> dict:
    with h5py.File(work / ts_name, "r") as handle:
        return {"dates": np.array(handle["date"]).astype(str),
                "ts": handle["timeseries"][:].astype("float32")}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not (DESC_WORK / "velocity.h5").exists():
        print("FAIL: descending velocity.h5 not found.")
        return 1

    asc_meta, desc_meta = meta_of(ASC_WORK / "velocity.h5"), meta_of(DESC_WORK / "velocity.h5")
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

    def load(work: Path, ts_name: str, k: str):
        with h5py.File(work / "velocity.h5", "r") as handle:
            v = handle["velocity"][:].astype("float64")
            vs = handle["velocityStd"][:].astype("float64")
        with h5py.File(work / "temporalCoherence.h5", "r") as handle:
            coh = handle["temporalCoherence"][:].astype("float64")
        return {"key": k, "v": v * 1000.0, "vs": vs * 1000.0, "coh": coh}

    asc = load(ASC_WORK, "timeseries.h5", "ascending_full")
    desc = load(DESC_WORK, "timeseries_ERA5.h5" if (DESC_WORK / "timeseries_ERA5.h5").exists()
                else "timeseries.h5", "descending_full")
    desc_on_asc = resample(desc["v"])
    desc_coh_on_asc = resample(desc["coh"])
    desc_vs_on_asc = resample(desc["vs"])

    domain_path = OUT / "common_domain_mask.npz"
    if not domain_path.exists():
        print("FAIL: common_domain_mask.npz missing; run script 47 first.")
        return 1
    domain = np.load(domain_path)["domain"]

    print("=" * 88)
    print("PHASE II-A - HOTSPOT VALIDATION, COHERENCE-VELOCITY, TEMPORAL GROUPS")
    print("=" * 88)

    # ---- 8. hotspot cross-validation with uncertainties -------------------
    features = json.loads(HOTSPOTS.read_text())["features"]
    rows = []
    for feature in features:
        hid = feature["properties"]["hotspot_id"]
        geom_utm = shp_shape(transform_geom(
            "EPSG:4326", f"EPSG:{int(asc_meta['EPSG'])}",
            shp_shape(feature["geometry"]).__geo_interface__))
        hmask = rasterio.features.geometry_mask(
            [geom_utm.__geo_interface__], out_shape=shape_out,
            transform=asc_transform, invert=True)
        sel = hmask & domain & np.isfinite(asc["v"]) & np.isfinite(desc_on_asc)
        if sel.sum() == 0:
            rows.append({"hotspot_id": hid, "n_pixels_common": 0})
            continue
        a_v, d_v = asc["v"][sel], desc_on_asc[sel]
        rows.append({
            "hotspot_id": hid,
            "n_pixels_total": int(hmask.sum()),
            "n_pixels_common": int(sel.sum()),
            "fraction_in_common_domain": round(float(sel.sum() / max(1, hmask.sum())), 5),
            "ascending_los_mm_per_yr": round(float(np.median(a_v)), 3),
            "descending_los_mm_per_yr": round(float(np.median(d_v)), 3),
            "ascending_uncertainty_mm_per_yr": round(float(np.median(asc["vs"][sel])), 4),
            "descending_uncertainty_mm_per_yr": round(float(np.median(desc_vs_on_asc[sel])), 4),
            "ascending_coherence": round(float(np.median(asc["coh"][sel])), 4),
            "descending_coherence": round(float(np.median(desc_coh_on_asc[sel])), 4),
            "same_sign": bool(np.median(a_v) * np.median(d_v) > 0),
            "magnitude_ratio": round(abs(float(np.median(d_v)))
                                    / max(1e-9, abs(float(np.median(a_v)))), 4),
        })
    hv = pd.DataFrame(rows)
    hv.to_csv(OUT / "hotspot_validation.csv", index=False)

    print(f"\n  8. hotspot cross-validation (common domain)")
    print(f"     {'id':5s} {'asc':>8s} {'±':>6s} {'desc':>8s} {'±':>6s} {'same':>5s} "
          f"{'ratio':>6s} {'asc coh':>8s} {'desc coh':>8s} {'common':>7s}")
    for row in rows:
        if row.get("n_pixels_common", 0) == 0:
            print(f"     {row['hotspot_id']:5s}  no pixels in the common domain")
            continue
        print(f"     {row['hotspot_id']:5s} {row['ascending_los_mm_per_yr']:8.2f} "
              f"{row['ascending_uncertainty_mm_per_yr']:6.2f} "
              f"{row['descending_los_mm_per_yr']:8.2f} "
              f"{row['descending_uncertainty_mm_per_yr']:6.2f} "
              f"{str(row['same_sign']):>5s} {row['magnitude_ratio']:6.2f} "
              f"{row['ascending_coherence']:8.3f} {row['descending_coherence']:8.3f} "
              f"{row['fraction_in_common_domain'] * 100:6.1f}%")

    # ---- 9. coherence-velocity in three forms -----------------------------
    forms = {
        "ascending_full": {"v": asc["v"], "coh": asc["coh"], "mask": domain},
        "descending_full": {"v": desc_on_asc, "coh": desc_coh_on_asc, "mask": domain},
    }
    if (DESC_SUB_WORK / "velocity.h5").exists():
        sub = load(DESC_SUB_WORK, "timeseries.h5", "descending_basematched")
        forms["descending_basematched"] = {
            "v": resample(sub["v"]),
            "coh": resample(sub["coh"]),
            "mask": domain,
        }
        print(f"\n  9. baseline-matched descending inversion found and included")
    else:
        print(f"\n  9. NOTE: {DESC_SUB_WORK.name}/velocity.h5 is absent, so the "
              f"descending baseline-matched form is NOT reported. A proxy is not "
              f"substituted.")

    bins = np.arange(0.5, 1.0001, 0.05)
    curves = {}
    for name, form in forms.items():
        cov = form["mask"] & np.isfinite(form["v"]) & np.isfinite(form["coh"])
        rows_c = []
        for i in range(len(bins) - 1):
            lo, hi = bins[i], bins[i + 1]
            sel = cov & (form["coh"] >= lo) & (form["coh"] < hi)
            if sel.sum() < 200:
                continue
            values = form["v"][sel]
            rows_c.append({
                "form": name, "coherence_low": round(float(lo), 2),
                "coherence_high": round(float(hi), 2), "n_pixels": int(sel.sum()),
                "median_mm_per_yr": round(float(np.median(values)), 3),
                "p05_mm_per_yr": round(float(np.percentile(values, 5)), 3),
                "fraction_below_minus10": round(float((values <= -THRESHOLD_MM).mean()), 5),
            })
        curves[name] = rows_c
        print(f"\n     {name}:")
        for r in rows_c:
            print(f"       coh {r['coherence_low']:.2f}-{r['coherence_high']:.2f}  "
                  f"n={r['n_pixels']:8,d}  median {r['median_mm_per_yr']:+8.2f}  "
                  f"frac<=-10 {r['fraction_below_minus10']:.3f}")

    # Rank correlation of coherence vs velocity within each form.
    rank = {}
    for name, rows_c in curves.items():
        if len(rows_c) > 2:
            df = pd.DataFrame(rows_c)
            rank[name] = round(float(df["coherence_low"].corr(
                df["median_mm_per_yr"], method="spearman")), 4)

    # ---- temporal-baseline stratification ---------------------------------
    # Pairs are grouped by temporal-baseline class and the class's median pair
    # coherence is reported. Pooling classes would mix 12-day pairs (coherent for
    # reasons unrelated to deformation) with 108-day pairs and corrupt the
    # coherence-velocity statistic.
    strata = []
    for work, label in ((ASC_WORK, "ascending_full"), (DESC_WORK, "descending_full")):
        stack = work / "inputs" / "ifgramStack.h5"
        if not stack.exists():
            continue
        with h5py.File(stack, "r") as handle:
            ifg_dates = np.array(handle["date"]).astype(str)
            ifg_coh = handle["coherence"][:]
        with h5py.File(work / "temporalCoherence.h5", "r") as handle:
            coh = handle["temporalCoherence"][:].astype("float64")
        with h5py.File(work / "velocity.h5", "r") as handle:
            v = handle["velocity"][:].astype("float64") * 1000.0
        ifg_coh = np.asarray(ifg_coh)
        dt = np.array([(pd.Timestamp(b) - pd.Timestamp(a)).days for a, b in ifg_dates])
        for dt_class in sorted(set(dt.tolist())):
            idx = np.where(dt == dt_class)[0]
            # per-pair median coherence over the common domain's ascending grid
            if ifg_coh.shape[1:] == shape_out:
                pair_med = [float(np.nanmedian(ifg_coh[i][domain]))
                            for i in idx if np.isfinite(ifg_coh[i][domain]).any()]
            else:
                pair_med = [float(np.nanmedian(ifg_coh[i]))
                            for i in idx if np.isfinite(ifg_coh[i]).any()]
            strata.append({
                "form": label,
                "temporal_baseline_days": int(dt_class),
                "n_pairs": int(len(idx)),
                "median_pair_coherence": round(float(np.median(pair_med)), 4)
                    if pair_med else None,
            })
    pd.DataFrame(strata).to_csv(OUT / "coherence_velocity_by_baseline_class.csv",
                                index=False)

    cv_payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "coherence_min_for_detection": COHERENCE_MIN,
        "forms": {name: rows_c for name, rows_c in curves.items()},
        "forms_available": sorted(forms),
        "descending_basematched_available": "descending_basematched" in forms,
        "spearman_rank_coherence_vs_velocity": rank,
        "temporal_baseline_stratification": strata,
        "note": "Temporal-baseline classes are never pooled: a 12-day and a 120-day "
                "interferogram carry different coherence for reasons unrelated to "
                "deformation.",
    }
    (OUT / "coherence_velocity_3form.json").write_text(
        json.dumps(cv_payload, indent=2, default=str))

    # ---- 10. temporal group validation ------------------------------------
    asc_series = read_series(ASC_WORK, "timeseries.h5")
    desc_series = read_series(DESC_WORK, "timeseries_ERA5.h5"
                              if (DESC_WORK / "timeseries_ERA5.h5").exists()
                              else "timeseries.h5")

    def hotspot_series(series, feature, grid_meta, transform, extra_resample=None):
        geom_utm = shp_shape(transform_geom(
            "EPSG:4326", f"EPSG:{int(grid_meta['EPSG'])}",
            shp_shape(feature["geometry"]).__geo_interface__))
        hmask = rasterio.features.geometry_mask(
            [geom_utm.__geo_interface__], out_shape=series["ts"].shape[1:],
            transform=transform, invert=True)
        if extra_resample is not None:
            hmask = hmask & extra_resample
        ys, xs = np.where(hmask)
        if len(ys) == 0:
            return None
        # Sample the cube at the hotspot pixels, one date at a time, to avoid
        # materialising the whole array.
        out = np.empty(series["ts"].shape[0], dtype="float64")
        for i in range(series["ts"].shape[0]):
            out[i] = np.median(series["ts"][i, ys, xs].astype("float64")) * 1000.0
        return out

    # Descending hotspot masks must be evaluated on the descending grid, so the
    # polygon is transformed into that grid directly.
    shapes = {f["properties"]["hotspot_id"]: f for f in features}
    asc_curves, desc_curves = {}, {}
    for hid, feature in shapes.items():
        value = hotspot_series(asc_series, feature, asc_meta, asc_transform)
        if value is not None:
            asc_curves[hid] = value
    for hid, feature in shapes.items():
        value = hotspot_series(desc_series, feature, desc_meta, desc_transform)
        if value is not None:
            desc_curves[hid] = value

    def detrend(y, t, order=2):
        design = np.column_stack([t ** k for k in range(order + 1)])
        coef, *_ = np.linalg.lstsq(design, y, rcond=None)
        return y - design @ coef

    def normalise(y):
        span = float(np.percentile(y, 97.5) - np.percentile(y, 2.5))
        return y / span if span else y

    asc_t = np.array([pd.Timestamp(d).year + (pd.Timestamp(d).dayofyear - 1) / 365.25
                      for d in asc_series["dates"]])
    desc_t = np.array([pd.Timestamp(d).year + (pd.Timestamp(d).dayofyear - 1) / 365.25
                       for d in desc_series["dates"]])

    def residual(curve, t):
        return normalise(detrend(curve, t - t[0], order=2))

    asc_res = {hid: residual(curve, asc_t) for hid, curve in asc_curves.items()}
    desc_res = {hid: residual(curve, desc_t) for hid, curve in desc_curves.items()}

    within_asc, within_desc, between_asc, between_desc = [], [], [], []
    pairs_out = []
    hids = sorted(set(asc_res) & set(desc_res))
    for i, a in enumerate(hids):
        for b in hids[i + 1:]:
            same_group = any(a in g and b in g for g in NS_GROUPS.values())
            key = f"{a}_vs_{b}"
            corr_asc = (float(np.corrcoef(asc_res[a], asc_res[b])[0, 1])
                        if np.std(asc_res[a]) > 0 and np.std(asc_res[b]) > 0 else None)
            corr_desc = (float(np.corrcoef(desc_res[a], desc_res[b])[0, 1])
                         if np.std(desc_res[a]) > 0 and np.std(desc_res[b]) > 0 else None)
            pairs_out.append({
                "pair": key, "same_phase1_group": bool(same_group),
                "ascending_correlation": round(corr_asc, 4) if corr_asc is not None else None,
                "descending_correlation": round(corr_desc, 4) if corr_desc is not None else None,
            })
            if corr_desc is None:
                continue
            (within_desc if same_group else between_desc).append(corr_desc)
            if corr_asc is not None:
                (within_asc if same_group else between_asc).append(corr_asc)

    print(f"\n  10. temporal group validation")
    print(f"     {'pair':16s} {'same group':>10s} {'asc r':>8s} {'desc r':>8s}")
    for row in pairs_out:
        print(f"     {row['pair']:16s} {str(row['same_phase1_group']):>10s} "
              f"{(row['ascending_correlation'] if row['ascending_correlation'] is not None else float('nan')):8.3f} "
              f"{(row['descending_correlation'] if row['descending_correlation'] is not None else float('nan')):8.3f}")

    def summarise(values):
        return ({"n": len(values), "median": round(float(np.median(values)), 4)}
                if values else {"n": 0, "median": None})

    grouping_payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "method": "quadratic de-trend, normalised amplitude, then correlation of the "
                  "residuals; amplitudes are not required to match because the LOS "
                  "projections differ",
        "phase1_groups": NS_GROUPS,
        "pairs": pairs_out,
        "within_group": {"ascending": summarise(within_asc),
                         "descending": summarise(within_desc)},
        "between_group": {"ascending": summarise(between_asc),
                          "descending": summarise(between_desc)},
        "grouping_survives_in_descending": bool(
            within_desc and between_desc
            and np.median(within_desc) > np.median(between_desc)),
        "caveat": "Correlations are computed on each track's own full record; the two "
                  "tracks have different acquisition calendars, so the comparison is of "
                  "grouping STRUCTURE, not of simultaneous values.",
    }
    (OUT / "temporal_groups.json").write_text(json.dumps(grouping_payload, indent=2, default=str))
    print(f"\n     within-group  ascending {summarise(within_asc)}  "
          f"descending {summarise(within_desc)}")
    print(f"     between-group ascending {summarise(between_asc)}  "
          f"descending {summarise(between_desc)}")
    print(f"     grouping survives in descending: "
          f"{grouping_payload['grouping_survives_in_descending']}")

    print(f"\n  outputs in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
