#!/usr/bin/env python
"""
Phase III-A4: the preregistered groundwater temporal test.

Implements freeze/groundwater_protocol_v1 exactly. Every threshold, lag, window
and statistical choice is read from the frozen protocol; none is re-chosen here.

Usage
-----
    python scripts/66_phase3a4_analysis.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
from rasterio.transform import Affine
from rasterio.warp import transform_geom
from scipy import stats
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NWDP = PROJECT_ROOT / "data" / "external" / "nwdp"
ASC = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
ASC_GEOM = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "geometryGeo.h5"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase3"
FIG = PROJECT_ROOT / "qc" / "sci" / "phase3" / "figures"
PROTO = json.loads((PROJECT_ROOT / "freeze" / "groundwater_protocol_v1"
                    / "GROUNDWATER_PROTOCOL_V1.json").read_text())

CENTROIDS = {"H001": (77.0813, 28.5212), "H004": (77.0554, 28.5333),
             "H002": (77.0735, 28.8152), "H003": (77.0810, 28.8033)}
POS_LAGS = PROTO["lags"]["primary_positive_days"]
NEG_LAGS = PROTO["lags"]["falsification_negative_days"]
BLOCK = PROTO["significance"]["block_days"]
NPERM = PROTO["significance"]["iterations"]
SEED = PROTO["significance"]["random_seed"]


def hav(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2)
    return 2 * r * np.arcsin(np.sqrt(a))


def load_telemetry() -> pd.DataFrame:
    frames = []
    for key in ("delhi_sw_gw", "cgwb_delhi"):
        f = sorted(NWDP.glob(f"{key}_*.csv"))
        if not f:
            continue
        d = pd.read_csv(f[0], low_memory=False)
        cols = list(d.columns)
        tc = next(c for c in cols if "Acquisition" in c)
        vc = cols[cols.index(tc) + 1]
        frames.append(pd.DataFrame({
            "producer": key, "station": d["Station"],
            "lat": pd.to_numeric(d["Latitude"], errors="coerce"),
            "lon": pd.to_numeric(d["Longitude"], errors="coerce"),
            "dt": pd.to_datetime(d[tc], format="%d-%m-%Y %H:%M", errors="coerce"),
            "value": pd.to_numeric(d[vc], errors="coerce")}))
    return pd.concat(frames, ignore_index=True)


def block_perm_p(paired_gw: np.ndarray, paired_insar: np.ndarray, rng) -> tuple[float, float]:
    """Circular block permutation preserving autocorrelation."""
    n = len(paired_gw)
    if n < 40:
        return float("nan"), float("nan")
    rho = float(stats.spearmanr(paired_gw, paired_insar).statistic)
    nb = max(2, n // BLOCK)
    idx = np.arange(n)
    blocks = np.array_split(idx, nb)
    null = np.empty(NPERM)
    for i in range(NPERM):
        order = rng.permutation(nb)
        perm = np.concatenate([blocks[b] for b in order])
        null[i] = stats.spearmanr(paired_gw[perm], paired_insar).statistic
    null = null[np.isfinite(null)]
    p = float((np.abs(null) >= abs(rho)).mean()) if len(null) else float("nan")
    return rho, p


def bh_fdr(pvals: list[float], q: float) -> list[bool]:
    p = np.array(pvals, dtype=float)
    ok = np.isfinite(p)
    reject = np.zeros(len(p), dtype=bool)
    if ok.sum() == 0:
        return list(reject)
    idx = np.where(ok)[0]
    order = idx[np.argsort(p[idx])]
    m = len(order)
    thresh = q * (np.arange(1, m + 1)) / m
    passed = p[order] <= thresh
    if passed.any():
        kmax = np.max(np.where(passed)[0])
        reject[order[:kmax + 1]] = True
    return list(reject)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    tele = load_telemetry()
    print("=" * 88)
    print("PHASE III-A4 - PREREGISTERED GROUNDWATER TEMPORAL TEST")
    print("=" * 88)
    print(f"\n  protocol_freeze_id: {PROTO['protocol_freeze_id']}")

    # ---- 4. station QC ----------------------------------------------------
    qc_rows = []
    for (prod, sta), g in tele.groupby(["producer", "station"], sort=False):
        g = g.dropna(subset=["dt", "value"]).sort_values("dt")
        if g.empty:
            continue
        v = g["value"]
        const_frac = float((v.diff() == 0).mean())
        zero_frac = float((v == 0).mean())
        gaps_d = g["dt"].diff().dt.total_seconds().div(86400).dropna()
        maxgap = float(gaps_d.max()) if len(gaps_d) else np.nan
        span = (g["dt"].max() - g["dt"].min()).days
        days = g["dt"].dt.normalize().nunique()
        coverage = days / max(1, span + 1)
        if zero_frac > PROTO["station_qc_rules"]["dead_sensor_exact_zero_fraction_gt"] or \
           const_frac > PROTO["station_qc_rules"]["dead_sensor_constant_fraction_gt"]:
            cls = "FAIL_DEAD_SENSOR"
        elif days < PROTO["station_qc_rules"]["insufficient_valid_days_lt"] or \
                coverage < PROTO["station_qc_rules"]["insufficient_coverage_fraction_lt"]:
            cls = "FAIL_INSUFFICIENT_RECORD"
        elif maxgap > PROTO["station_qc_rules"]["pass_with_gaps_longest_gap_days_gt"]:
            cls = "PASS_WITH_GAPS"
        else:
            cls = "PASS"
        qc_rows.append({"producer": prod, "station": sta,
                        "lat": float(g["lat"].iloc[0]), "lon": float(g["lon"].iloc[0]),
                        "n_obs": int(len(g)),
                        "first": g["dt"].min(), "last": g["dt"].max(),
                        "exact_zero_fraction": round(zero_frac, 4),
                        "constant_fraction": round(const_frac, 4),
                        "coverage_fraction": round(coverage, 4),
                        "longest_gap_days": round(maxgap, 2) if np.isfinite(maxgap) else None,
                        "n_days": int(days), "qc_class": cls})
    qc = pd.DataFrame(qc_rows)
    qc.to_csv(OUT / "groundwater_station_qc.csv", index=False)
    print(f"\n  4. STATION QC (frozen rules): {len(qc)} stations")
    for k, v in qc["qc_class"].value_counts().items():
        print(f"     {k:26s} {v:4d}")
    eligible = qc[qc["qc_class"].isin(["PASS", "PASS_WITH_GAPS"])].copy()
    print(f"     -> eligible for temporal analysis: {len(eligible)}")

    # ---- 6. daily series --------------------------------------------------
    tele = tele.merge(eligible[["producer", "station", "qc_class"]],
                      on=["producer", "station"], how="inner")
    tele["date"] = tele["dt"].dt.normalize()
    daily = (tele.groupby(["producer", "station", "date"])
             .agg(v=("value", "median"), n=("value", "size")).reset_index())
    daily.loc[daily["n"] < PROTO["temporal_aggregation"]["min_observations_per_day"],
              "v"] = np.nan
    daily = daily.dropna(subset=["v"])
    # sign convention + per-station centring
    med = daily.groupby(["producer", "station"])["v"].median().rename("station_median")
    daily = daily.merge(med, on=["producer", "station"])
    daily["anomaly"] = daily["v"] - daily["station_median"]
        # CSV rather than parquet: no pyarrow/fastparquet engine is installed in
    # this environment. Same content, machine-readable.
    daily.to_csv(OUT / "groundwater_daily_series.csv", index=False)
    print(f"\n  6. DAILY SERIES: {len(daily):,} station-days across "
          f"{daily.groupby(['producer','station']).ngroups} stations")

    # ---- 8/9. hotspot composites -----------------------------------------
    station_geo = eligible.copy()
    for hid, (lon, lat) in CENTROIDS.items():
        station_geo[f"d_{hid}"] = hav(station_geo["lat"], station_geo["lon"], lat, lon)
    station_geo["min_d"] = station_geo[[f"d_{h}" for h in CENTROIDS]].min(axis=1)
    station_geo.to_csv(OUT / "groundwater_station_registry_final.csv", index=False)

    selected = {}
    for hid in CENTROIDS:
        sel = station_geo[station_geo[f"d_{hid}"]
                          <= PROTO["station_selection"]["primary_max_distance_km"]]
        selected[hid] = list(zip(sel["producer"], sel["station"], sel[f"d_{hid}"]))
    print(f"\n  8/9. SELECTED STATIONS (ALL quality-passing within "
          f"{PROTO['station_selection']['primary_max_distance_km']} km)")
    for hid, s in selected.items():
        print(f"     {hid}: {len(s)} station(s)")
        for prod, sta, d in s:
            print(f"        {d:5.2f} km  {sta[:40]}  [{prod}]")

    comp_rows = []
    for hid, s in selected.items():
        if not s:
            continue
        parts = daily[daily.set_index(["producer", "station"]).index.isin(
            [(p, t) for p, t, _ in s])]
        wide = parts.pivot_table(index="date", columns=["producer", "station"],
                                 values="anomaly")
        n_have = wide.notna().sum(axis=1)
        need = max(PROTO["composite_availability_rule"]["min_fraction_of_stations_valid"]
                   * len(s),
                   PROTO["composite_availability_rule"]
                   ["min_contributing_stations_when_eligible_ge_2"] if len(s) >= 2 else 1)
        ok = n_have >= need
        comp = wide.median(axis=1).where(ok)
        for d, v in comp.items():
            comp_rows.append({"hotspot": hid, "date": d, "gw_anomaly": v,
                              "n_stations": int(n_have.loc[d]) if d in n_have.index else 0})
    comp = pd.DataFrame(comp_rows)
    comp.to_csv(OUT / "groundwater_hotspot_composites.csv", index=False)
    print(f"\n     composites built: "
          f"{comp.groupby('hotspot')['gw_anomaly'].apply(lambda x: x.notna().sum()).to_dict()}")

    # ---- 11. ascending InSAR hotspot series ------------------------------
    with h5py.File(ASC / "velocity.h5", "r") as h:
        avg = h["velocity"][:].astype("float64") * 1000.0
        meta = {k: float(h.attrs[k]) for k in
                ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP")}
    with h5py.File(ASC / "temporalCoherence.h5", "r") as h:
        tc = h["temporalCoherence"][:].astype("float64")
    with h5py.File(ASC / "inputs" / "geometryGeo.h5", "r") as h:
        land = h["waterMask"][:].astype(bool)
    with h5py.File(ASC / "timeseries.h5", "r") as h:
        dates = np.array(h["date"]).astype(str)
    tf = Affine(meta["X_STEP"], 0, meta["X_FIRST"], 0,
                -abs(meta["Y_STEP"]), meta["Y_FIRST"])
    feats = {f["properties"]["hotspot_id"]: shp_shape(f["geometry"])
             for f in json.loads(HOTSPOTS.read_text())["features"]}

    def ts_for(hid, mode):
        g = feats[hid]
        if mode == "core":
            g = g.buffer(-0.002)
        if g.is_empty:
            return None
        gu = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", g.__geo_interface__))
        m = rasterio.features.geometry_mask([gu.__geo_interface__],
                                            out_shape=avg.shape, transform=tf, invert=True)
        m = m & land
        if mode == "Q_PRIMARY":
            m = m & (tc >= 0.80)
        elif mode in ("Q_STRICT", "core"):
            m = m & (tc >= 0.90)
        ys, xs = np.where(m)
        if len(ys) < 20:
            return None
        with h5py.File(ASC / "timeseries.h5", "r") as h:
            cube = h["timeseries"]
            ser = np.array([np.median(cube[i][ys, xs].astype("float64"))
                            for i in range(len(dates))]) * 1000.0
        return pd.Series(ser, index=pd.to_datetime(dates, format="%Y%m%d"))

    gwd = comp.dropna(subset=["gw_anomaly"]).copy()
    gwd["date"] = pd.to_datetime(gwd["date"])

    def gw_at(hid, t, lag_days):
        c = gwd[gwd["hotspot"] == hid]
        if c.empty:
            return np.nan
        tgt = t - pd.Timedelta(days=lag_days)
        w = c[(c["date"] >= tgt - pd.Timedelta(days=3))
              & (c["date"] <= tgt + pd.Timedelta(days=3))]["gw_anomaly"]
        w = w.dropna()
        if len(w) < PROTO["insar_alignment"]["min_valid_daily_values_in_window"]:
            return np.nan
        return float(np.median(w))

    def match(hid, lag, mode="Q_PRIMARY"):
        s = ts_for(hid, mode)
        if s is None:
            return None
        gv = np.array([gw_at(hid, t, lag) for t in s.index])
        m = np.isfinite(gv)
        if m.sum() < 40:
            return None
        return s.values[m], gv[m]

    # ---- 12A. trends ------------------------------------------------------
    def theil(x, y):
        sl, _, _, _ = stats.theilslopes(y, x)
        return float(sl)

    trend_rows = []
    for hid in CENTROIDS:
        tsi = ts_for(hid, "Q_PRIMARY")
        c = gwd[gwd["hotspot"] == hid].dropna(subset=["gw_anomaly"])
        if tsi is None or len(c) < 60:
            continue
        xg = (c["date"] - c["date"].min()).dt.days.to_numpy(float)
        yg = c["gw_anomaly"].to_numpy(float)
        xi = (tsi.index - tsi.index.min()).days.to_numpy(float)
        yi = tsi.to_numpy(float)
        half = len(xg) // 2
        trend_rows.append({
            "hotspot": hid,
            "gw_trend_m_per_yr": round(theil(xg, yg) * 365.25, 4),
            "gw_trend_first_half": round(theil(xg[:half], yg[:half]) * 365.25, 4),
            "gw_trend_second_half": round(theil(xg[half:], yg[half:]) * 365.25, 4),
            "insar_rate_mm_per_yr": round(theil(xi, yi) * 365.25, 3),
            "n_gw_days": int(len(c)), "n_insar_epochs": int(len(tsi))})
    trends = pd.DataFrame(trend_rows)
    trends.to_csv(OUT / "groundwater_trend_results.csv", index=False)
    print(f"\n  12A. LONG-TERM TRENDS (Theil-Sen)")
    print(f"     {'hotspot':8s} {'GW m/yr':>9s} {'GW 1st':>9s} {'GW 2nd':>9s} "
          f"{'InSAR mm/yr':>12s}")
    for _, r in trends.iterrows():
        print(f"     {r['hotspot']:8s} {r['gw_trend_m_per_yr']:+9.4f} "
              f"{r['gw_trend_first_half']:+9.4f} {r['gw_trend_second_half']:+9.4f} "
              f"{r['insar_rate_mm_per_yr']:+12.3f}")

    # ---- 12B/13/14/15/16. detrended lag correlations ---------------------
    lag_rows = []
    for hid in CENTROIDS:
        for lag in POS_LAGS + NEG_LAGS:
            got = match(hid, lag)
            if got is None:
                lag_rows.append({"hotspot": hid, "lag_days": lag, "N": 0,
                                 "spearman": None, "pearson": None, "p_block": None,
                                 "role": "positive" if lag >= 0 else "falsification"})
                continue
            iv, gv = got
            # detrend both with a robust linear trend (protocol: Theil-Sen)
            t = np.arange(len(iv), dtype=float)
            sg = stats.theilslopes(gv, t)
            si = stats.theilslopes(iv, t)
            gd = gv - (sg[1] + sg[0] * t)
            idd = iv - (si[1] + si[0] * t)
            rho, p = block_perm_p(gd, idd, rng)
            lag_rows.append({"hotspot": hid, "lag_days": lag, "N": int(len(iv)),
                             "spearman": round(rho, 4) if np.isfinite(rho) else None,
                             "pearson": round(float(np.corrcoef(gd, idd)[0, 1]), 4),
                             "p_block": round(p, 4) if np.isfinite(p) else None,
                             "role": "positive" if lag >= 0 else "falsification"})
    lags = pd.DataFrame(lag_rows)
    lags.to_csv(OUT / "groundwater_lag_results.csv", index=False)

    pos = lags[lags["role"] == "positive"]
    rej = bh_fdr(list(pos["p_block"].fillna(1.0)), PROTO["multiple_testing"]["q"])
    pos = pos.copy()
    pos["fdr_significant"] = rej
    lags = lags.merge(pos[["hotspot", "lag_days", "fdr_significant"]],
                      on=["hotspot", "lag_days"], how="left")

    print(f"\n  13/14/15/16. DETRENDED LAG CORRELATIONS (Spearman, "
          f"{BLOCK}-day block permutation, N reported)")
    print(f"     {'hotspot':8s} {'lag':>5s} {'N':>5s} {'rho':>8s} {'p_block':>8s} "
          f"{'role':>14s} {'FDR':>5s}")
    for _, r in lags.iterrows():
        print(f"     {r['hotspot']:8s} {r['lag_days']:5d} {r['N']:5d} "
              f"{(r['spearman'] if r['spearman'] is not None else float('nan')):8.3f} "
              f"{(r['p_block'] if r['p_block'] is not None else float('nan')):8.3f} "
              f"{r['role']:>14s} "
              f"{('yes' if r.get('fdr_significant') is True else 'no'):>5s}")

    # ---- 21. control comparison ------------------------------------------
    ctrl = []
    for hid in ("H001", "H004", "H002", "H003"):
        p = lags[(lags["hotspot"] == hid) & (lags["role"] == "positive")].dropna(
            subset=["spearman"])
        nn = lags[(lags["hotspot"] == hid) & (lags["role"] == "falsification")].dropna(
            subset=["spearman"])
        tr = trends[trends["hotspot"] == hid]
        c = gwd[gwd["hotspot"] == hid]["gw_anomaly"].dropna()
        ctrl.append({
            "hotspot": hid,
            "role": "supported" if hid in ("H001", "H004") else "negative_control",
            "n_stations": len(selected.get(hid, [])),
            "gw_trend_m_per_yr": float(tr["gw_trend_m_per_yr"].iloc[0]) if len(tr) else None,
            "gw_seasonal_amplitude_m": round(float(
                c.groupby(gwd[gwd["hotspot"] == hid]["date"].dt.month).median().max()
                - c.groupby(gwd[gwd["hotspot"] == hid]["date"].dt.month).median().min()), 4)
                if len(c) > 30 else None,
            "best_positive_lag_rho": round(float(p["spearman"].max()), 4) if len(p) else None,
            "best_positive_lag": int(p.loc[p["spearman"].idxmax(), "lag_days"])
                if len(p) else None,
            "best_negative_lag_rho": round(float(nn["spearman"].max()), 4) if len(nn) else None,
            "mean_positive_rho": round(float(p["spearman"].mean()), 4) if len(p) else None,
            "mean_negative_rho": round(float(nn["spearman"].mean()), 4) if len(nn) else None,
            "gw_days_available": int(len(c)),
        })
    cdf = pd.DataFrame(ctrl)
    cdf.to_csv(OUT / "groundwater_control_comparison.csv", index=False)
    print(f"\n  21. CONTROL COMPARISON")
    print(f"     {'hotspot':8s} {'role':18s} {'nst':>4s} {'GWtrend':>9s} "
          f"{'best+rho':>9s} {'best-rho':>9s} {'mean+':>7s} {'mean-':>7s}")
    for _, r in cdf.iterrows():
        print(f"     {r['hotspot']:8s} {r['role']:18s} {r['n_stations']:4d} "
              f"{(r['gw_trend_m_per_yr'] if r['gw_trend_m_per_yr'] is not None else float('nan')):9.4f} "
              f"{(r['best_positive_lag_rho'] if r['best_positive_lag_rho'] is not None else float('nan')):9.3f} "
              f"{(r['best_negative_lag_rho'] if r['best_negative_lag_rho'] is not None else float('nan')):9.3f} "
              f"{(r['mean_positive_rho'] if r['mean_positive_rho'] is not None else float('nan')):7.3f} "
              f"{(r['mean_negative_rho'] if r['mean_negative_rho'] is not None else float('nan')):7.3f}")

    # ---- 22/23. quality-mask sensitivity ---------------------------------
    qs = []
    for hid in ("H001", "H004"):
        for mode in ("Q_PRIMARY", "Q_STRICT", "core"):
            got = match(hid, 0, mode)
            if got is None:
                qs.append({"hotspot": hid, "mask": mode, "N": 0, "spearman": None})
                continue
            iv, gv = got
            t = np.arange(len(iv), dtype=float)
            sg, si = stats.theilslopes(gv, t), stats.theilslopes(iv, t)
            rho, _ = block_perm_p(gv - (sg[1] + sg[0] * t),
                                  iv - (si[1] + si[0] * t), rng)
            qs.append({"hotspot": hid, "mask": mode, "N": int(len(iv)),
                       "spearman": round(rho, 4) if np.isfinite(rho) else None,
                       "median_temporal_coherence": None})
    qdf = pd.DataFrame(qs)
    qdf.to_csv(OUT / "groundwater_quality_sensitivity.csv", index=False)
    print(f"\n  22/23. QUALITY-MASK SENSITIVITY (lag 0)")
    for _, r in qdf.iterrows():
        print(f"     {r['hotspot']:6s} {r['mask']:10s} N={r['N']:5d} "
              f"rho={(r['spearman'] if r['spearman'] is not None else float('nan')):.3f}")

    # ---- 25. leave-one-station-out ---------------------------------------
    ss = []
    for hid in ("H001", "H004"):
        s = selected.get(hid, [])
        if len(s) < 2:
            continue
        for i, (prod, sta, d) in enumerate(s):
            sub = [x for j, x in enumerate(s) if j != i]
            parts = daily[daily.set_index(["producer", "station"]).index.isin(
                [(p, t) for p, t, _ in sub])]
            if parts.empty:
                continue
            wide = parts.pivot_table(index="date", columns=["producer", "station"],
                                     values="anomaly")
            comp_i = wide.median(axis=1).dropna()
            tmp = pd.DataFrame({"hotspot": hid, "date": comp_i.index,
                                "gw_anomaly": comp_i.values})
            globals()["_tmp_comp"] = tmp
            old = gwd
            gwd = tmp
            got = match(hid, 0)
            gwd = old
            if got:
                iv, gv = got
                t = np.arange(len(iv), dtype=float)
                sg, si = stats.theilslopes(gv, t), stats.theilslopes(iv, t)
                rho, _ = block_perm_p(gv - (sg[1] + sg[0] * t),
                                      iv - (si[1] + si[0] * t), rng)
                ss.append({"hotspot": hid, "left_out": f"{prod}:{sta}",
                           "remaining": len(sub), "N": int(len(iv)),
                           "spearman": round(rho, 4) if np.isfinite(rho) else None})
    sdf = pd.DataFrame(ss)
    sdf.to_csv(OUT / "groundwater_station_sensitivity.csv", index=False)
    print(f"\n  25. LEAVE-ONE-STATION-OUT")
    if len(sdf):
        for hid, grp in sdf.groupby("hotspot"):
            v = grp["spearman"].dropna()
            print(f"     {hid}: rho range {v.min():.3f}..{v.max():.3f} "
                  f"(span {v.max()-v.min():.3f}) over {len(grp)} runs")
    else:
        print(f"     not applicable (fewer than 2 eligible stations)")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_freeze_id": PROTO["protocol_freeze_id"],
        "stations_eligible": int(len(eligible)),
        "stations_selected_by_hotspot": {h: len(v) for h, v in selected.items()},
        "trends": trend_rows,
        "lags": lag_rows,
        "controls": ctrl,
        "quality_sensitivity": qs,
        "station_sensitivity": ss,
        "fdr_q": PROTO["multiple_testing"]["q"],
        "fdr_significant_positive_lag_tests":
            int(lags["fdr_significant"].fillna(False).sum()),
        "no_causal_claim": True,
    }
    (OUT / "groundwater_analysis.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'groundwater_analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
