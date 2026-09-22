#!/usr/bin/env python
"""
Phase III-A3: NWDP telemetry acquisition and station/coverage audit.

NO correlation between groundwater and InSAR is performed. This stage stops at
the station and coverage audit, as instructed.

Usage
-----
    python scripts/64_phase3a3_nwdp_audit.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NWDP = PROJECT_ROOT / "data" / "external" / "nwdp"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase3"
REPORT = PROJECT_ROOT / "qc" / "sci" / "PHASE_IIIA3_NWDP_RECOVERY_AUDIT.md"

HOTSPOTS = {"H001": (77.0813, 28.5212), "H004": (77.0554, 28.5333),
            "H002": (77.0735, 28.8152), "H003": (77.0810, 28.8033)}
STUDY_START, STUDY_END = pd.Timestamp("2021-10-01"), pd.Timestamp("2025-10-01")
BANDS = [1, 2, 5, 10, 20]


def hav(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def load(key: str) -> pd.DataFrame:
    files = sorted(NWDP.glob(f"{key}_*.csv"))
    if not files:
        return pd.DataFrame()
    df = pd.read_csv(files[0], low_memory=False)
    df["__producer"] = key
    return df


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((NWDP / "nwdp_download_manifest.json").read_text())

    frames = {k: load(k) for k in ("delhi_sw_gw", "cgwb_delhi")}
    for k, d in frames.items():
        if not d.empty:
            print(f"  {k}: {len(d):,} rows, {len(d.columns)} columns")

    # identify the value column (the one after the acquisition-time column)
    sample = frames["cgwb_delhi"]
    cols = list(sample.columns)
    time_col = next((c for c in cols if "Acquisition" in c), None)
    ti = cols.index(time_col)
    value_col = cols[ti + 1] if ti + 1 < len(cols) else None
    print(f"  time column : {time_col}")
    print(f"  value column: {value_col}")

    all_stations, interval_rows = [], []
    for key, df in frames.items():
        if df.empty:
            continue
        df = df.copy()
        df["__dt"] = pd.to_datetime(df[time_col], format="%d-%m-%Y %H:%M", errors="coerce")
        df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
        for name, grp in df.groupby("Station", sort=False):
            g = grp.dropna(subset=["__dt"]).sort_values("__dt")
            if g.empty:
                continue
            dt = g["__dt"]
            gaps = dt.diff().dt.total_seconds().div(3600).dropna()
            gaps = gaps[gaps > 0]
            span_days = (dt.max() - dt.min()).total_seconds() / 86400.0
            in_study = g[(g["__dt"] >= STUDY_START) & (g["__dt"] < STUDY_END)]
            med = float(np.median(gaps)) if len(gaps) else np.nan
            expected = (span_days * 24 / med) if med and med > 0 else np.nan
            months = g["__dt"].dt.to_period("M")
            counts = months.value_counts()
            all_stations.append({
                "producer": key,
                "station_id": f"{key}:{name}",
                "station_name": name,
                "agency": g["Agency"].iloc[0] if "Agency" in g else None,
                "district": g["District"].iloc[0] if "District" in g else None,
                "latitude": float(g["Latitude"].iloc[0]),
                "longitude": float(g["Longitude"].iloc[0]),
                "record_start": dt.min(), "record_end": dt.max(),
                "observation_count": int(len(g)),
                "observations_in_study_period": int(len(in_study)),
                "median_sampling_hours": round(med, 3) if np.isfinite(med) else None,
                "min_interval_hours": round(float(gaps.min()), 3) if len(gaps) else None,
                "max_routine_interval_hours": round(float(np.percentile(gaps, 99)), 3)
                    if len(gaps) else None,
                "largest_gap_hours": round(float(gaps.max()), 3) if len(gaps) else None,
                "study_period_coverage_pct": round(
                    100.0 * len(in_study) / max(1, expected), 2),
                "observed_expected_ratio": round(len(g) / expected, 4)
                    if np.isfinite(expected) and expected else None,
                "months_represented": int(len(counts)),
                **{f"dist_{h}_km": round(float(hav(g["Latitude"].iloc[0],
                                                   g["Longitude"].iloc[0], la, lo)), 3)
                   for h, (lo, la) in HOTSPOTS.items()},
            })
            interval_rows.append({"producer": key, "station": name, "gaps": gaps})

    reg = pd.DataFrame(all_stations)
    reg["min_dist_km"] = reg[[f"dist_{h}_km" for h in HOTSPOTS]].min(axis=1)
    reg.to_csv(OUT / "nwdp_telemetry_station_registry.csv", index=False)

    # ---- 2. ACTUAL sampling interval --------------------------------------
    allgaps = pd.concat([r["gaps"] for r in interval_rows]) if interval_rows else pd.Series()
    modes = allgaps.round(0).value_counts().head(5) if len(allgaps) else pd.Series()
    print("\n" + "=" * 88)
    print("PHASE III-A3 - NWDP TELEMETRY RECOVERY AUDIT")
    print("=" * 88)
    print(f"\n  1. FILES ACQUIRED")
    for m in manifest:
        print(f"     {m['key']:12s} {m['bytes']/1e6:7.2f} MB  HTTP {m['http_status']}  "
              f"{m['resource_name'][:52]}")
        print(f"       sha256 {m['sha256'][:24]}...  portal update {m['portal_update']}")
    print(f"\n  2. ACTUAL SAMPLING INTERVAL (from timestamps, NOT the page title)")
    if len(allgaps):
        print(f"     median interval      : {np.median(allgaps):.3f} h")
        print(f"     mode interval        : {modes.index[0]:.0f} h "
              f"({100*modes.iloc[0]/len(allgaps):.1f}% of all intervals)")
        print(f"     minimum interval     : {allgaps.min():.3f} h")
        print(f"     99th-percentile      : {np.percentile(allgaps,99):.3f} h")
        print(f"     maximum interval     : {allgaps.max():.1f} h")

    print(f"\n  3. SCHEMA")
    print(f"     station name      : YES (Station)")
    print(f"     latitude/longitude: YES (decimal degrees, 8 dp)")
    print(f"     timestamp         : YES ({time_col}, DD-MM-YYYY HH:MM)")
    print(f"     groundwater level : YES ({value_col})")
    print(f"     agency/producer   : YES (Agency)")
    print(f"     district hierarchy: YES (State/District/Tehsil/Block/Village LGD codes)")
    print(f"     station ID        : NO explicit code - station NAME is the identifier")
    print(f"     well depth/aquifer: NO")

    print(f"\n  4. TELEMETRY STATION REGISTRY: {len(reg)} stations")
    print(f"     {'producer':12s} {'stations':>9s} {'median_obs':>11s} "
          f"{'median_h':>9s} {'study_obs':>10s}")
    for key, grp in reg.groupby("producer"):
        print(f"     {key:12s} {len(grp):9d} {int(grp['observation_count'].median()):11d} "
              f"{grp['median_sampling_hours'].median():9.2f} "
              f"{int(grp['observations_in_study_period'].median()):10d}")

    print(f"\n  5. DISTANCE GATE - THE DECISIVE TEST")
    print(f"     {'hotspot':8s} {'nearest':>9s} {'<=1km':>6s} {'<=2km':>6s} "
          f"{'2-5km':>6s} {'5-10km':>7s} {'10-20km':>8s}")
    tiers = {}
    for hid in HOTSPOTS:
        c = f"dist_{hid}_km"
        tiers[hid] = {
            "nearest_km": round(float(reg[c].min()), 3) if len(reg) else None,
            "le1km": int((reg[c] <= 1).sum()), "le2km": int((reg[c] <= 2).sum()),
            "2to5km": int(((reg[c] > 2) & (reg[c] <= 5)).sum()),
            "5to10km": int(((reg[c] > 5) & (reg[c] <= 10)).sum()),
            "10to20km": int(((reg[c] > 10) & (reg[c] <= 20)).sum()),
        }
        t = tiers[hid]
        print(f"     {hid:8s} {t['nearest_km']:9.2f} {t['le1km']:6d} {t['le2km']:6d} "
              f"{t['2to5km']:6d} {t['5to10km']:7d} {t['10to20km']:8d}")
    h001_le5 = (reg["dist_H001_km"] <= 5).sum() if len(reg) else 0
    print(f"\n     >>> DOES NWDP TELEMETRY PROVIDE A STATION WITHIN 5 km OF H001? "
          f"{'YES' if h001_le5 else 'NO'}  ({h001_le5} station(s))")
    print(f"         previous seasonal figure was 5.92 km; that remains valid for the "
          f"SEASONAL dataset and is not assumed to describe the telemetry network")

    print(f"\n  6. TEMPORAL COMPLETENESS (study period 2021-10-01 .. 2025-10-01)")
    print(f"     {'station':34s} {'producer':12s} {'n_study':>8s} {'cov%':>6s} "
          f"{'months':>7s} {'med_h':>7s} {'maxgap_h':>9s}")
    for _, r in reg.nsmallest(12, "min_dist_km").iterrows():
        print(f"     {str(r['station_name'])[:34]:34s} {r['producer']:12s} "
              f"{r['observations_in_study_period']:8d} "
              f"{r['study_period_coverage_pct']:6.1f} {r['months_represented']:7d} "
              f"{r['median_sampling_hours']:7.2f} {r['largest_gap_hours']:9.1f}")

    # ---- 7. cross-producer duplication ------------------------------------
    dup = {"shared_station_names": 0, "shared_coordinates": 0, "note": ""}
    if len(frames["delhi_sw_gw"]) and len(frames["cgwb_delhi"]):
        a = frames["delhi_sw_gw"].drop_duplicates("Station")
        b = frames["cgwb_delhi"].drop_duplicates("Station")
        names_a, names_b = set(a["Station"]), set(b["Station"])
        coord_a = set(zip(a["Latitude"].round(4), a["Longitude"].round(4)))
        coord_b = set(zip(b["Latitude"].round(4), b["Longitude"].round(4)))
        dup = {"shared_station_names": len(names_a & names_b),
               "shared_coordinates": len(coord_a & coord_b),
               "delhi_sw_gw_stations": len(names_a), "cgwb_stations": len(names_b),
               "note": "station NAME is the only available identifier; no authoritative "
                       "station code is present in either file, so identity could not be "
                       "established beyond name and coordinate matching"}
        print(f"\n  7. CROSS-PRODUCER DUPLICATION")
        print(f"     Delhi SW GW stations {len(names_a)}   CGWB stations {len(names_b)}")
        print(f"     shared station NAMES       : {len(names_a & names_b)}")
        print(f"     shared rounded COORDINATES : {len(coord_a & coord_b)}")
        print(f"     -> {dup['note']}")

    # ---- 8. quality flags -------------------------------------------------
    flags = []
    for key, df in frames.items():
        if df.empty:
            continue
        v = pd.to_numeric(df[value_col], errors="coerce")
        for name, grp in df.assign(__v=v).groupby("Station", sort=False):
            g = grp.dropna(subset=["__v"])
            if g.empty:
                continue
            vals = g["__v"]
            n_dup_ts = int(g["__dt"].duplicated().sum()) if "__dt" in g else 0
            flags.append({
                "producer": key, "station": name, "n": int(len(vals)),
                "min_value": round(float(vals.min()), 3),
                "max_value": round(float(vals.max()), 3),
                "n_negative": int((vals < 0).sum()),
                "n_exact_zero": int((vals == 0).sum()),
                "frac_constant_on_runs": round(float(
                    (vals.diff() == 0).sum() / max(1, len(vals) - 1)), 3),
                "duplicate_timestamps": n_dup_ts,
                "abrupt_jump_gt_10m": int((vals.diff().abs() > 10).sum()),
            })
    qf = pd.DataFrame(flags)
    qf.to_csv(OUT / "nwdp_quality_flags.csv", index=False)
    print(f"\n  8. QUALITY FLAGS (not repaired, only flagged)")
    if len(qf):
        neg = qf[qf["n_negative"] > 0]
        zer = qf[qf["n_exact_zero"] > qf["n"] * 0.5]
        flat = qf[qf["frac_constant_on_runs"] > 0.9]
        jump = qf[qf["abrupt_jump_gt_10m"] > 0]
        dts = qf[qf["duplicate_timestamps"] > 0]
        print(f"     stations with any negative level      : {len(neg)}")
        print(f"     stations >50% exact zeros             : {len(zer)}")
        print(f"     stations >90% consecutive-constant    : {len(flat)}")
        print(f"     stations with a >10 m step            : {len(jump)}")
        print(f"     stations with duplicate timestamps    : {len(dts)}")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "files_acquired": manifest,
        "actual_sampling": {
            "median_hours": round(float(np.median(allgaps)), 3) if len(allgaps) else None,
            "mode_hours": float(modes.index[0]) if len(modes) else None,
            "min_hours": round(float(allgaps.min()), 3) if len(allgaps) else None,
            "max_hours": round(float(allgaps.max()), 3) if len(allgaps) else None,
            "source": "derived from timestamps, NOT from the page title",
        },
        "schema": {"station_name": True, "latitude": True, "longitude": True,
                   "timestamp": True, "groundwater_level": True, "agency": True,
                   "administrative_hierarchy": True, "explicit_station_code": False,
                   "well_depth_or_aquifer": False,
                   "time_column": time_col, "value_column": value_col},
        "station_count": int(len(reg)),
        "station_tiers": tiers,
        "h001_within_5km": bool(h001_le5),
        "cross_producer_duplication": dup,
        "quality_flags_summary": {
            "stations": int(len(qf)),
            "with_negative_levels": int((qf["n_negative"] > 0).sum()) if len(qf) else 0,
            "mostly_exact_zero": int((qf["n_exact_zero"] > qf["n"] * 0.5).sum())
                if len(qf) else 0,
            "mostly_constant": int((qf["frac_constant_on_runs"] > 0.9).sum())
                if len(qf) else 0,
            "with_large_step": int((qf["abrupt_jump_gt_10m"] > 0).sum())
                if len(qf) else 0,
            "with_duplicate_timestamps": int((qf["duplicate_timestamps"] > 0).sum())
                if len(qf) else 0,
        },
        "correlation_analysis_performed": False,
        "classification_placeholder": "see report",
    }
    (OUT / "nwdp_audit.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'nwdp_telemetry_station_registry.csv'}")
    print(f"  {OUT / 'nwdp_audit.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
