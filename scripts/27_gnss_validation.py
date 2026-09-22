#!/usr/bin/env python
"""
GNSS/CORS validation attempt using Nevada Geodetic Laboratory solutions.

Purpose: independently test the InSAR LOS velocity against GNSS vertical rates,
which is a better-posed test than residual RMS. This script establishes what is
actually possible, and says so plainly if the answer is "not much".

NGL publishes daily solutions as `.tenv3` files. Downloads run in parallel.

Outputs
-------
qc/sci/gnss_stations.csv          candidate stations near the AOI
qc/sci/gnss_rates.csv             vertical rates where the span permits one
qc/sci/gnss_validation.json       verdict, including data-availability limits

Usage
-----
    python scripts/27_gnss_validation.py [--radius-km 500]
"""

from __future__ import annotations

import argparse
import json
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "qc" / "sci"
CACHE = PROJECT_ROOT / "data" / "gnss"
HOLDINGS = CACHE / "ngl_holdings.txt"

AOI_LON, AOI_LAT = 77.095, 28.6426
STUDY_START, STUDY_END = "2021-10-06", "2025-09-27"
NGL_HOLDINGS_URL = "https://geodesy.unr.edu/NGLStationPages/DataHoldings.txt"
# NGL moved its time-series products to IGS20; the old /tenv3/IGS14/ path 404s.
# The regional (IN = India) variant is used as a fallback.
NGL_TS_URLS = [
    "https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/IGS20/{sta}.tenv3",
    "https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/IN/{sta}.IN.tenv3",
]

#: A rate needs enough independent daily solutions to be meaningful.
MIN_SOLUTIONS = 100
MIN_SPAN_YEARS = 2.0


def haversine(lat: float, lon: float) -> float:
    R = 6371.0
    dlat = math.radians(lat - AOI_LAT)
    dlon = math.radians(lon - AOI_LON)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(AOI_LAT)) * math.cos(math.radians(lat))
         * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def load_catalogue(radius_km: float) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    if not HOLDINGS.exists():
        print(f"  downloading {NGL_HOLDINGS_URL}")
        urllib.request.urlretrieve(NGL_HOLDINGS_URL, HOLDINGS)
    rows = []
    with HOLDINGS.open() as handle:
        next(handle)
        for line in handle:
            parts = line.split()
            if len(parts) < 10:
                continue
            try:
                sta, lat, lon = parts[0], float(parts[1]), float(parts[2])
                beg, end = parts[7], parts[8]
                nsol = int(parts[10]) if len(parts) > 10 else 0
            except (ValueError, IndexError):
                continue
            dist = haversine(lat, lon)
            if dist > radius_km:
                continue
            rows.append({"station": sta, "lat": lat, "lon": lon,
                         "distance_km": round(dist, 1),
                         "data_begin": beg, "data_end": end, "n_solutions": nsol})
    return pd.DataFrame(rows).sort_values("distance_km").reset_index(drop=True)


def download_tenv3(station: str) -> tuple[str, Path | None, str | None]:
    target = CACHE / f"{station}.tenv3"
    if target.exists() and target.stat().st_size > 1000:
        return station, target, None
    last_error = "no URL attempted"
    for template in NGL_TS_URLS:
        url = template.format(sta=station)
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "delhi-ncr-sbas/1.0"}
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
            if len(payload) < 500:
                last_error = f"{url}: payload too small ({len(payload)} B)"
                continue
            target.write_bytes(payload)
            return station, target, None
        except Exception as exc:  # noqa: BLE001
            last_error = f"{url}: {type(exc).__name__}: {exc}"
    return station, None, last_error


def parse_tenv3(path: Path) -> pd.DataFrame:
    """Parse an NGL .tenv3 series, resolving columns FROM THE HEADER.

    The column layout is not what the name suggests: this file has
    `_e0(m) __east(m) ____n0(m) _north(m) u0(m) ____up(m)`, so the up component
    is NOT the 10th field. Reading a fixed index picks up `____n0(m)` - a
    ~3.16e6 m constant - which would produce a nonsense "rate". Column positions
    are therefore looked up by name, the same lesson as resolving MintPy
    products by provenance rather than by filename.

    Dates are `YYMMMDD` (e.g. 23SEP10).
    """
    with path.open() as handle:
        header = handle.readline().split()
        index = {name: i for i, name in enumerate(header)}
        date_col = next((i for i, n in enumerate(header) if n == "YYMMMDD"), 1)
        up_col = index.get("____up(m)")
        north_col = index.get("_north(m)")
        east_col = index.get("__east(m)")
        if up_col is None:
            raise ValueError(f"{path.name}: cannot locate the up component in the header")

        records = []
        for line in handle:
            parts = line.split()
            if len(parts) <= max(up_col, date_col):
                continue
            try:
                records.append({
                    "date": parts[date_col],
                    "dU_m": float(parts[up_col]),
                    "dN_m": float(parts[north_col]) if north_col is not None else None,
                    "dE_m": float(parts[east_col]) if east_col is not None else None,
                })
            except ValueError:
                continue
    frame = pd.DataFrame(records)
    if not frame.empty:
        frame["t"] = pd.to_datetime(frame["date"], format="%y%b%d")
    return frame


def vertical_rate(frame: pd.DataFrame, window: pd.DataFrame) -> dict:
    """Weighted linear vertical rate over a date window, in mm/yr."""
    subset = frame[(frame["t"] >= window["start"]) & (frame["t"] <= window["end"])]
    n = len(subset)
    if n < 3:
        return {"n": n, "rate_mm_per_yr": None, "uncertainty_mm_per_yr": None}
    t = (subset["t"] - subset["t"].min()).dt.days.values.astype(float) / 365.25
    u = subset["dU_m"].values.astype(float)
    design = np.vstack([t, np.ones_like(t)]).T
    solution, *_ = np.linalg.lstsq(design, u, rcond=None)
    residual = u - design @ solution
    dof = max(1, n - 2)
    variance = float(residual @ residual) / dof
    covariance = variance * np.linalg.inv(design.T @ design)
    return {
        "n": n,
        "span_years": round(float(t.max()), 3),
        "rate_mm_per_yr": round(1000 * float(solution[0]), 3),
        "uncertainty_mm_per_yr": round(1000 * float(np.sqrt(covariance[0, 0])), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radius-km", type=float, default=500.0)
    parser.add_argument("--workers", type=int, default=18)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 88)
    print("GNSS / CORS VALIDATION ATTEMPT (Nevada Geodetic Laboratory)")
    print("=" * 88)

    catalogue = load_catalogue(args.radius_km)
    print(f"\n  NGL stations within {args.radius_km:.0f} km of the AOI: {len(catalogue)}")
    catalogue.to_csv(OUT_DIR / "gnss_stations.csv", index=False)

    window = {"start": pd.Timestamp(STUDY_START), "end": pd.Timestamp(STUDY_END)}
    in_period = catalogue[
        (catalogue["data_begin"] <= STUDY_END) & (catalogue["data_end"] >= STUDY_START)
    ]
    print(f"  ...whose data overlaps the study period: {len(in_period)}")

    stations = in_period["station"].tolist()
    if len(catalogue):
        stations += [s for s in catalogue["station"].head(12) if s not in stations]

    print(f"\n  downloading {len(stations)} time series with {args.workers} workers...")
    downloaded: dict[str, Path] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_tenv3, s): s for s in stations}
        for future in as_completed(futures):
            station, path, error = future.result()
            if path:
                downloaded[station] = path
            else:
                errors[station] = error or "unknown"
    print(f"  downloaded: {len(downloaded)}  (failed: {len(errors)})")
    for station, error in list(errors.items())[:3]:
        print(f"    {station}: {error[:150]}")

    rows = []
    for station, path in sorted(downloaded.items()):
        meta = catalogue[catalogue["station"] == station].iloc[0]
        frame = parse_tenv3(path)
        study = vertical_rate(frame, window)
        full = vertical_rate(frame, {"start": frame["t"].min() if len(frame) else None,
                                     "end": frame["t"].max() if len(frame) else None}) \
            if len(frame) else {"n": 0, "rate_mm_per_yr": None, "uncertainty_mm_per_yr": None}
        rows.append({
            "station": station,
            "distance_km": meta["distance_km"],
            "catalogue_solutions": meta["n_solutions"],
            "parsed_solutions": len(frame),
            "data_begin": str(frame["t"].min().date()) if len(frame) else None,
            "data_end": str(frame["t"].max().date()) if len(frame) else None,
            "study_period_n": study["n"],
            "study_period_span_years": study.get("span_years"),
            "study_period_vertical_rate_mm_per_yr": study["rate_mm_per_yr"],
            "study_period_uncertainty_mm_per_yr": study["uncertainty_mm_per_yr"],
            "full_record_vertical_rate_mm_per_yr": full["rate_mm_per_yr"],
            "usable": bool(
                study["n"] >= MIN_SOLUTIONS
                and (study.get("span_years") or 0) >= MIN_SPAN_YEARS
            ),
        })
    rates = pd.DataFrame(rows)
    if rates.empty:
        rates = pd.DataFrame(columns=[
            "station", "distance_km", "catalogue_solutions", "parsed_solutions",
            "data_begin", "data_end", "study_period_n", "study_period_span_years",
            "study_period_vertical_rate_mm_per_yr",
            "study_period_uncertainty_mm_per_yr",
            "full_record_vertical_rate_mm_per_yr", "usable",
        ])
    rates = rates.sort_values("distance_km")
    rates.to_csv(OUT_DIR / "gnss_rates.csv", index=False)

    print(f"\n  {'station':7s} {'dist_km':>8s} {'n_study':>8s} {'span_yr':>8s} "
          f"{'rate_mm/yr':>11s} {'+-':>7s}  usable")
    for row in rates.itertuples():
        if row.study_period_n and row.study_period_n > 0:
            print(f"  {row.station:7s} {row.distance_km:8.1f} {row.study_period_n:8d} "
                  f"{(row.study_period_span_years or 0):8.2f} "
                  f"{str(row.study_period_vertical_rate_mm_per_yr):>11s} "
                  f"{str(row.study_period_uncertainty_mm_per_yr):>7s}  {row.usable}")

    usable = rates[rates["usable"]] if not rates.empty else pd.DataFrame()
    nearest_usable = None
    if not usable.empty:
        nearest_usable = usable.iloc[0].to_dict()

    verdict = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Nevada Geodetic Laboratory daily GNSS solutions (IGS14)",
        "aoi_centre_lonlat": [AOI_LON, AOI_LAT],
        "study_period": [STUDY_START, STUDY_END],
        "radius_km_searched": args.radius_km,
        "stations_within_radius": int(len(catalogue)),
        "stations_downloaded": len(downloaded),
        "download_errors": errors,
        "usable_stations": int(len(usable)),
        "nearest_usable_station": nearest_usable,
        "criteria": {"min_solutions": MIN_SOLUTIONS, "min_span_years": MIN_SPAN_YEARS},
    }

    if usable.empty:
        verdict["outcome"] = "GNSS VALIDATION NOT POSSIBLE"
        verdict["reason"] = (
            "No NGL station within the search radius provides enough daily solutions "
            "spanning the InSAR study period to estimate a vertical rate. The stations "
            "closest to the AOI have only a handful of solutions, and the densest nearby "
            "record (LIAA, ~7.5 km) ends before the study period begins. GNSS therefore "
            "cannot discriminate between the RAW / ERA5 / ERA5+DEM branches over the AOI, "
            "and cannot constrain the absolute velocity offset."
        )
        print("\n  VERDICT: GNSS validation not possible with available data.")
        print("  Nearest stations lack the temporal sampling and span required.")
    else:
        verdict["outcome"] = "GNSS REFERENCE AVAILABLE"
        verdict["reason"] = (
            f"{len(usable)} station(s) support a rate estimate over the study period. "
            "Compare against InSAR LOS converted to vertical via the local incidence angle."
        )
        print(f"\n  VERDICT: {len(usable)} usable station(s).")

    (OUT_DIR / "gnss_validation.json").write_text(json.dumps(verdict, indent=2, default=str))
    print(f"\n  {OUT_DIR / 'gnss_stations.csv'}")
    print(f"  {OUT_DIR / 'gnss_rates.csv'}")
    print(f"  {OUT_DIR / 'gnss_validation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
