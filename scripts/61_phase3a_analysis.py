#!/usr/bin/env python
"""
Phase III-A stages C-M, O-Q: the analyses that the obtainable datasets permit,
and the report.

SCOPE LIMITATION, STATED FIRST
------------------------------
Priority-A (groundwater) and priority-B (geology) datasets were NOT obtainable,
and priority-C (land cover) was not acquired. The consequence is that the two
hypotheses that motivated Phase III cannot be tested with independent data:
HYPOTHESIS G (groundwater) and HYPOTHESIS GEO (geology) are UNTESTABLE here, not
"unsupported". Only HYPOTHESIS H (hydrological/seasonal forcing), HYPOTHESIS ART
(measurement-quality artefact) and regional GRACE context can be examined.

The coherence-confounding test (section 11) is the most valuable test available,
because it is the only one that can discriminate the surviving
coherence-velocity association using data already in hand.

Usage
-----
    python scripts/61_phase3a_analysis.py
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
from scipy.ndimage import uniform_filter
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
D2_WORK = PROJECT_ROOT / "mintpy" / "descending_d2_unwrap_work"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase3"
REPORT = PROJECT_ROOT / "qc" / "sci" / "PHASE_IIIA_CAUSAL_EVIDENCE_REPORT.md"
PRECIP = PROJECT_ROOT / "data" / "external" / "era5_total_precipitation_monthly.nc"
GRACE = PROJECT_ROOT / "data" / "external" / "grace_gsfc_rl06v2_mascon.nc"

CLASSES = {"H001": "supported", "H004": "supported",
           "H002": "negative_control", "H003": "negative_control",
           "H005": "excluded_contradiction"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    registry = json.loads((OUT / "dataset_registry.json").read_text())
    recon = json.loads((PROJECT_ROOT / "qc" / "sci" / "phase2c"
                        / "hotspot_reconciliation.json").read_text())

    with h5py.File(ASC_WORK / "velocity.h5", "r") as h:
        asc_v = h["velocity"][:].astype("float64") * 1000.0
        asc_vs = h["velocityStd"][:].astype("float64") * 1000.0
        meta = {k: float(h.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
    with h5py.File(ASC_WORK / "temporalCoherence.h5", "r") as h:
        asc_tc = h["temporalCoherence"][:].astype("float64")
    with h5py.File(ASC_WORK / "inputs" / "geometryGeo.h5", "r") as h:
        land = h["waterMask"][:].astype(bool)
        height = h["height"][:].astype("float64")
    with h5py.File(ASC_WORK / "timeseries.h5", "r") as h:
        asc_dates = np.array(h["date"]).astype(str)

    tf = Affine(meta["X_STEP"], 0, meta["X_FIRST"], 0,
                -abs(meta["Y_STEP"]), meta["Y_FIRST"])
    shape_out = asc_v.shape
    aoi = shp_shape(json.loads((PROJECT_ROOT / "geometry" / "aoi.geojson")
                               .read_text())["features"][0]["geometry"])
    aoi_utm = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", aoi.__geo_interface__))
    aoi_mask = rasterio.features.geometry_mask([aoi_utm.__geo_interface__],
                                               out_shape=shape_out, transform=tf,
                                               invert=True)
    asc_mask = aoi_mask & land & np.isfinite(asc_v) & (asc_vs > 0)

    features = json.loads(HOTSPOTS.read_text())["features"]
    hmask = {}
    for f in features:
        hid = f["properties"]["hotspot_id"]
        gu = shp_shape(transform_geom("EPSG:4326", "EPSG:32643",
                                      shp_shape(f["geometry"]).__geo_interface__))
        hmask[hid] = rasterio.features.geometry_mask([gu.__geo_interface__],
                                                     out_shape=shape_out, transform=tf,
                                                     invert=True)
    any_hot = np.zeros(shape_out, dtype=bool)
    for m in hmask.values():
        any_hot |= m
    # control = AOI outside every hotspot, same quality gate
    bg = asc_mask & ~any_hot

    print("=" * 88)
    print("PHASE III-A - CAUSAL EVIDENCE TESTING")
    print("=" * 88)

    # ---- 11. COHERENCE-CONFOUNDING TEST -----------------------------------
    # The central question: is the hotspot contrast explained by measurement
    # quality? If hotspots simply sit in lower-coherence terrain, the contrast
    # could be a quality artefact.
    print(f"\n  11. COHERENCE CONFOUNDING TEST (the decisive available test)")
    qbands = [(0.80, 0.85), (0.85, 0.90), (0.90, 0.95), (0.95, 1.001)]
    conf = {}
    for hid in ("H001", "H004", "H002", "H003"):
        conf[hid] = {"coherence_median": round(float(np.median(asc_tc[hmask[hid] & asc_mask])), 4),
                     "background_coherence_median": round(float(np.median(asc_tc[bg])), 4),
                     "bands": {}}
    print(f"     {'class':6s} {'TC median':>10s} {'n':>8s}")
    for hid in ("H001", "H004", "H002", "H003"):
        sel = hmask[hid] & asc_mask
        print(f"     {hid:6s} {conf[hid]['coherence_median']:10.4f} {int(sel.sum()):8,d}")
    print(f"     {'bg':6s} {conf['H002']['background_coherence_median']:10.4f} "
          f"{int(bg.sum()):8,d}")

    print(f"\n     WITHIN COHERENCE-MATCHED BANDS (background vs each zone):")
    print(f"     {'band':>12s} " + "".join(f"{h:>9s}" for h in ("H001", "H004", "H002", "H003"))
          + f"{'bg':>9s}")
    for lo, hi in qbands:
        band = asc_mask & (asc_tc >= lo) & (asc_tc < hi)
        cells = []
        for hid in ("H001", "H004", "H002", "H003"):
            s = band & hmask[hid]
            v = float(np.median(asc_v[s])) if s.sum() >= 20 else None
            conf[hid]["bands"][f"{lo}-{hi}"] = (
                {"n": int(s.sum()), "median": round(v, 2)} if v is not None
                else {"n": int(s.sum()), "median": None})
            cells.append(f"{v:9.2f}" if v is not None else f"{'n/a':>9s}")
        bv = float(np.median(asc_v[band & bg])) if (band & bg).sum() >= 20 else None
        conf.setdefault("background_bands", {})[f"{lo}-{hi}"] = {
            "n": int((band & bg).sum()), "median": round(bv, 2) if bv is not None else None}
        print(f"     {lo:.2f}-{hi:.2f} " + "".join(cells)
              + (f"{bv:9.2f}" if bv is not None else f"{'n/a':>9s}"))

    # does the hotspot contrast survive within the tightest common band?
    shared_band = asc_mask & (asc_tc >= 0.90) & (asc_tc < 0.95)
    surv = {}
    for hid in ("H001", "H004", "H002", "H003"):
        s = shared_band & hmask[hid]
        b = shared_band & bg
        if s.sum() >= 20 and b.sum() >= 20:
            surv[hid] = {"hotspot": round(float(np.median(asc_v[s])), 2),
                         "background": round(float(np.median(asc_v[b])), 2),
                         "contrast": round(float(np.median(asc_v[s])
                                                 - np.median(asc_v[b])), 2)}
    print(f"\n     contrast preserved inside the 0.90-0.95 coherence band:")
    for hid, v in surv.items():
        print(f"       {hid}: hotspot {v['hotspot']:+.2f}  bg {v['background']:+.2f}  "
              f"contrast {v['contrast']:+.2f} mm/yr")

    # ---- H. HYDROLOGICAL / SEASONAL ---------------------------------------
    print(f"\n  H. HYDROLOGICAL FORCING (ERA5 monthly total precipitation)")
    hydro = {"available": PRECIP.exists()}
    if PRECIP.exists():
        import netCDF4
        with netCDF4.Dataset(PRECIP) as ds:
            var = [v for v in ds.variables if "tp" in v.lower() or "precip" in v.lower()]
            vname = var[0] if var else list(ds.variables)[-1]
            arr = np.asarray(ds.variables[vname][:]).squeeze()
            time_name = [t for t in ds.variables if t.lower() in ("time", "valid_time")]
            tvar = ds.variables[time_name[0]] if time_name else None
            units = getattr(tvar, "units", "") if tvar is not None else ""
            try:
                dates = netCDF4.num2date(tvar[:], units)
                months = pd.to_datetime([d.isoformat() for d in dates])
            except Exception:
                months = pd.date_range("2021-01-01", periods=len(np.ravel(arr)), freq="MS")
        # Normalise BOTH indices to month-start: netCDF times carry a time of day,
        # so a naive intersection with a resampled "MS" index is empty and every
        # lag correlation silently returns NaN.
        months = pd.DatetimeIndex(months).to_period("M").to_timestamp()
        series = pd.Series(np.ravel(np.asarray(arr).mean(axis=(-2, -1))
                                    if arr.ndim > 1 else arr), index=months)
        series = series[(series.index >= "2021-10-01") & (series.index <= "2025-09-30")]
        # ERA5 monthly-mean tp is in m/day of accumulated precipitation rate
        mm_month = series * 1000.0 * series.index.days_in_month
        hydro.update({
            "variable": vname, "units": units, "n_months": int(len(mm_month)),
            "monthly_mm": {d.strftime("%Y-%m"): round(float(v), 1)
                           for d, v in mm_month.items()},
            "climatology_mm": {int(m): round(float(v), 1) for m, v in
                               mm_month.groupby(mm_month.index.month).mean().items()},
            "trend_mm_per_yr": round(float(np.polyfit(
                np.arange(len(mm_month)), mm_month.values, 1)[0] * 12), 1),
        })
        print(f"     variable {vname} ({units}), {len(mm_month)} months")
        cl = hydro["climatology_mm"]
        print(f"     monsoon climatology (Jul-Sep): "
              f"{cl.get(7, 0):.0f}, {cl.get(8, 0):.0f}, {cl.get(9, 0):.0f} mm/month")
        print(f"     driest (Nov): {cl.get(11, 0):.0f} mm/month")
        print(f"     linear trend over the record: {hydro['trend_mm_per_yr']:+.1f} mm/yr")

        # hotspot seasonal cycle vs precipitation, PREDEFINED lags 0-3 months
        print(f"\n     hotspot seasonal cycle vs precipitation (predefined lags 0-3 months):")
        print(f"     {'zone':6s} {'amp mm':>8s} {'peak month':>11s} "
              + "".join(f"{f'lag{l}':>8s}" for l in range(4)))
        seasonal = {}
        for hid in ("H001", "H004", "H002", "H003"):
            ys, xs = np.where(hmask[hid] & asc_mask)
            if len(ys) < 20:
                continue
            with h5py.File(ASC_WORK / "timeseries.h5", "r") as h:
                cube = h["timeseries"]
                ts = np.array([np.median(cube[i][ys, xs].astype("float64"))
                               for i in range(len(asc_dates))]) * 1000.0
            idx = pd.to_datetime([str(d) for d in asc_dates], format="%Y%m%d")
            ms = pd.Series(ts, index=idx).resample("MS").mean().dropna()
            ms.index = ms.index.to_period("M").to_timestamp()
            pidx = mm_month.index.to_period("M").to_timestamp()
            mm = pd.Series(mm_month.values, index=pidx)
            amp = float(ms.groupby(ms.index.month).mean().max()
                        - ms.groupby(ms.index.month).mean().min())
            peak = int(ms.groupby(ms.index.month).mean().idxmax())
            common = ms.index.intersection(mm.index)
            lags = {}
            for lag in range(4):
                p = mm.reindex(common - pd.DateOffset(months=lag)).values
                v = ms.reindex(common).values
                ok = np.isfinite(p) & np.isfinite(v)
                lags[lag] = (round(float(np.corrcoef(p[ok], v[ok])[0, 1]), 3)
                             if ok.sum() > 12 else None)
            seasonal[hid] = {"seasonal_amplitude_mm": round(amp, 1), "peak_month": peak,
                             "lag_correlations": lags}
            print(f"     {hid:6s} {amp:8.1f} {peak:11d} "
                  + "".join(f"{(lags[l] if lags[l] is not None else float('nan')):8.3f}"
                            for l in range(4)))
        hydro["seasonal_by_zone"] = seasonal

    # ---- E. GRACE regional context ---------------------------------------
    print(f"\n  E. GRACE REGIONAL CONTEXT (0.5 deg; cannot resolve a hotspot)")
    grace = {"available": GRACE.exists()}
    if GRACE.exists():
        try:
            import netCDF4
            with netCDF4.Dataset(GRACE) as ds:
                names = list(ds.variables)
                grace["variables"] = names[:20]
                grace["note"] = ("mascon product retrieved; at 0.5 deg (~55 km) its "
                                 "footprint is larger than the entire AOI, so it is "
                                 "admitted as regional context only and is NOT used to "
                                 "discriminate hotspots")
        except Exception as exc:  # noqa: BLE001
            grace["error"] = f"{type(exc).__name__}: {exc}"
        print(f"     file present ({GRACE.stat().st_size / 1e6:.0f} MB)")
        print(f"     {grace.get('note', grace.get('error'))}")

    # ---- 9. CONTROL COMPARISON -------------------------------------------
    print(f"\n  9. CONTROL COMPARISON (H002/H003 as negative controls)")
    ctrl = {}
    for hid in ("H001", "H004", "H002", "H003"):
        s = hmask[hid] & asc_mask
        ctrl[hid] = {
            "class": CLASSES[hid],
            "n": int(s.sum()),
            "ascending_median": round(float(np.median(asc_v[s])), 2),
            "tc_median": round(float(np.median(asc_tc[s])), 4),
            "elevation_median": round(float(np.median(height[s])), 1),
            "bg_elevation_median": round(float(np.median(height[bg])), 1),
            "bg_ascending_median": round(float(np.median(asc_v[bg])), 2),
        }
    print(f"     {'zone':6s} {'class':22s} {'asc med':>8s} {'TC':>7s} {'elev':>7s}")
    for hid, v in ctrl.items():
        print(f"     {hid:6s} {v['class']:22s} {v['ascending_median']:8.2f} "
              f"{v['tc_median']:7.4f} {v['elevation_median']:7.1f}")
    print(f"     {'bg':6s} {'background':22s} {ctrl['H001']['bg_ascending_median']:8.2f} "
          f"{'':7s} {ctrl['H001']['bg_elevation_median']:7.1f}")
    # Does an explanatory factor discriminate supported from control zones?
    sup = [v for k, v in ctrl.items() if CLASSES[k] == "supported"]
    neg = [v for k, v in ctrl.items() if CLASSES[k] == "negative_control"]
    print(f"\n     supported zones  : asc {np.median([v['ascending_median'] for v in sup]):+.2f}  "
          f"TC {np.median([v['tc_median'] for v in sup]):.4f}  "
          f"elev {np.median([v['elevation_median'] for v in sup]):.1f}")
    print(f"     control zones    : asc {np.median([v['ascending_median'] for v in neg]):+.2f}  "
          f"TC {np.median([v['tc_median'] for v in neg]):.4f}  "
          f"elev {np.median([v['elevation_median'] for v in neg]):.1f}")
    print(f"     -> a factor that cannot separate these two groups cannot explain WHY "
          f"H001/H004 reproduce and H002/H003 do not")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope_limitation": {
            "groundwater": "NOT OBTAINABLE - priority-A dataset unavailable",
            "geology": "NOT OBTAINABLE",
            "land_cover": "NOT OBTAINED",
            "consequence": "HYPOTHESIS G and HYPOTHESIS GEO are UNTESTABLE in this phase, "
                           "not unsupported.",
        },
        "coherence_confounding": conf,
        "contrast_within_matched_band": surv,
        "hydrology": hydro,
        "grace": grace,
        "controls": ctrl,
        "frozen_inputs": {
            "H001": "INDEPENDENTLY_SUPPORTED / decomposition eligible / history NOT reproduced",
            "H004": "INDEPENDENTLY_SUPPORTED / decomposition eligible / history NOT reproduced",
            "H002": "NOT_REPRODUCED / ascending-only / negative control",
            "H003": "NOT_REPRODUCED / ascending-only / negative control",
            "H005": "UNRESOLVED_CONTRADICTION / excluded from mechanism fitting",
        },
    }
    (OUT / "phase3a_analysis.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'phase3a_analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
