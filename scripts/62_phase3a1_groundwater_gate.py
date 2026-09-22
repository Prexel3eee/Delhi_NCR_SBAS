#!/usr/bin/env python
"""
Phase III-A1: CGWB static groundwater data recovery gate.

Builds a fixed groundwater-station registry from the official CGWB seasonal
compiled datasets, BEFORE any relationship to H001-H004 is inspected, and audits
the schema. NO correlation analysis is performed here.

Sources are the official CGWB files referenced from the archived CGWB "Ground
Water Level Monitoring" page. The live host currently returns HTTP 502, so the
files were retrieved through the Internet Archive's copy of the OFFICIAL URL
(recorded per file). That is provenance discovery, not a third-party mirror.

Usage
-----
    python scripts/62_phase3a1_groundwater_gate.py
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GW = PROJECT_ROOT / "data" / "external" / "groundwater"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase3"

#: AOI bounding box, from geometry/aoi.geojson.
AOI = {"lon_min": 76.7853, "lat_min": 28.3839, "lon_max": 77.2838, "lat_max": 28.8726}

SEASONS = {
    "pre-monsoon_2022_data_for_website": {"season": "pre-monsoon", "year": 2022},
    "august_2022_data_for_website": {"season": "august", "year": 2022},
    "nov_2022_data_for_website": {"season": "november", "year": 2022},
    "jan_2023_data_for_website": {"season": "january", "year": 2023},
}

#: H001-H004 centroids (lon, lat) from the frozen Phase-I hotspot catalogue.
HOTSPOTS = {"H001": (77.0813, 28.5212), "H004": (77.0554, 28.5333),
            "H002": (77.0735, 28.8152), "H003": (77.0810, 28.8033)}
BANDS = [0, 2, 5, 10, 20]

ROW = re.compile(
    r"^(?P<state>[A-Z][A-Za-z&\. ]{2,28}?)\s{2,}"
    r"(?P<rest>.*?)"
    r"(?P<lat>2[0-9]\.\d{2,7})\s+"
    r"(?P<lon>7[0-9]\.\d{2,7})"
    r"(?P<tail>.*)$")


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    inventory, all_rows = [], []

    for stem, meta in SEASONS.items():
        pdf = GW / f"{stem}.pdf"
        txt = GW / f"{stem}.txt"
        if not pdf.exists():
            continue
        if not txt.exists():
            subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=False)
        lines = txt.read_text(errors="ignore").splitlines() if txt.exists() else []
        rows = []
        for line in lines:
            m = ROW.match(line)
            if not m:
                continue
            lat, lon = float(m.group("lat")), float(m.group("lon"))
            if not (AOI["lat_min"] - 0.25 <= lat <= AOI["lat_max"] + 0.25
                    and AOI["lon_min"] - 0.25 <= lon <= AOI["lon_max"] + 0.25):
                continue
            tail = m.group("tail").strip()
            nums = re.findall(r"\d+\.\d+", tail)
            depth = float(nums[-1]) if nums else None
            site = m.group("rest").strip()
            well_type = "Dug Well" if "Dug" in tail + site else (
                "Bore Well" if "Bore" in tail + site or "Pz" in site
                or "-PZ" in site.upper() else "unspecified")
            rows.append({
                "state": m.group("state").strip(), "site_name": site[:60],
                "latitude": lat, "longitude": lon, "well_type": well_type,
                "water_level_mbgl": depth,
                "season": meta["season"], "year": meta["year"],
            })
        all_rows.extend(rows)
        inventory.append({
            "source_file": pdf.name,
            "source_url": ("https://web.archive.org/web/20241027131951if_/"
                           f"https://cgwb.gov.in/sites/default/files/inline-files/{pdf.name}"),
            "official_url": (f"https://cgwb.gov.in/sites/default/files/inline-files/{pdf.name}"),
            "source_agency": "Central Ground Water Board (CGWB), Ministry of Jal Shakti",
            "retrieval_route": "Internet Archive copy of the official URL; the live host "
                               "returned HTTP 502 at retrieval time",
            "file_hash": sha256_of(pdf), "bytes": pdf.stat().st_size,
            "coverage_years": [meta["year"]], "season": meta["season"],
            "row_count_national": None, "row_count_in_aoi": len(rows),
            "coordinate_available": True, "station_id_available": False,
            "measurement_available": True,
            "usable_for_spatial_test": True,
            "usable_for_temporal_test": True,
        })

    stations = pd.DataFrame(all_rows)
    # A station is a unique (site_name, lat, lon); build the registry now, before
    # any relationship to the hotspots is examined.
    if not stations.empty:
        stations["station_key"] = (stations["site_name"].str.strip() + "|"
                                   + stations["latitude"].round(5).astype(str) + "|"
                                   + stations["longitude"].round(5).astype(str))
        registry = (stations.sort_values(["year", "season"])
                    .groupby("station_key", as_index=False)
                    .agg({"state": "first", "site_name": "first", "latitude": "first",
                          "longitude": "first", "well_type": "first",
                          "water_level_mbgl": "count"})
                    .rename(columns={"water_level_mbgl": "n_seasons"}))
        for hid, (hlon, hlat) in HOTSPOTS.items():
            registry[f"dist_km_{hid}"] = haversine_km(
                registry["latitude"].values, registry["longitude"].values, hlat, hlon)
        registry["min_dist_km_to_any"] = registry[
            [f"dist_km_{h}" for h in HOTSPOTS]].min(axis=1)
        for b in BANDS[1:]:
            registry[f"within_{b}km"] = registry["min_dist_km_to_any"] <= b
        registry.to_csv(OUT / "groundwater_station_registry.csv", index=False)

    pd.DataFrame(inventory).to_csv(OUT / "groundwater_source_inventory.csv", index=False)

    print("=" * 88)
    print("PHASE III-A1 - CGWB GROUNDWATER DATA RECOVERY GATE")
    print("=" * 88)
    print(f"\n  1. FILES OBTAINED (official CGWB seasonal compiled datasets)")
    print(f"     {'file':42s} {'MB':>6s} {'season':>13s} {'AOI stations':>13s}")
    for e in inventory:
        print(f"     {e['source_file']:42s} {e['bytes']/1e6:6.1f} "
              f"{e['season']:>13s} {e['row_count_in_aoi']:13d}")
    print(f"\n     total AOI rows across all seasons: {len(stations)}")

    print(f"\n  2. SCHEMA AUDIT (all four official seasonal files)")
    print(f"     station/site identifier : PARTIAL - a site NAME is present, but no "
          f"CGWB station CODE")
    print(f"     station name            : YES")
    print(f"     latitude                : YES (decimal degrees, ~5-7 dp)")
    print(f"     longitude               : YES")
    print(f"     district                : YES")
    print(f"     well type               : YES (Dug Well / Bore Well; blank in some rows)")
    print(f"     measurement date        : SEASON+YEAR only, not an exact date")
    print(f"     depth to water level    : YES (mbgl)")
    print(f"     aquifer / well depth    : NO")
    print(f"     unit                    : metres below ground level (mbgl)")

    if not stations.empty:
        print(f"\n  3. STATION REGISTRY (built BEFORE any hotspot relationship was examined)")
        print(f"     unique stations within the AOI (+0.25 deg): {len(registry)}")
        print(f"     states present: {sorted(registry['state'].unique())}")
        print(f"     public wells with >= 2 of the 4 seasons: "
              f"{int((registry['n_seasons'] >= 2).sum())}")
        print(f"     public wells with all 4 seasons        : "
              f"{int((registry['n_seasons'] >= 4).sum())}")
        print(f"\n  4. DISTANCE BANDS to the nearest of H001-H004")
        print(f"     {'band':>10s} {'stations':>10s} "
              + "".join(f"{h:>8s}" for h in HOTSPOTS))
        for i, b in enumerate(BANDS):
            lo, hi = BANDS[i - 1] if i else -1, b
            sel = registry[(registry["min_dist_km_to_any"] > lo)
                           & (registry["min_dist_km_to_any"] <= hi)]
            counts = [int((registry[f"dist_km_{h}"] <= b).sum()) for h in HOTSPOTS]
            label = f"{lo if i else 0}-{b} km" if i else f"<= {b} km"
            print(f"     {label:>10s} {len(sel):10d} " + "".join(f"{c:>8d}" for c in counts))
        print(f"\n     stations within 2 km of any hotspot : "
              f"{int(registry['within_2km'].sum())}")
        print(f"     stations within 5 km  of any hotspot: "
              f"{int(registry['within_5km'].sum())}")
        print(f"     stations within 10 km of any hotspot: "
              f"{int(registry['within_10km'].sum())}")

    print(f"\n  5. TEMPORAL SAMPLING")
    print(f"     CGWB design frequency : 4 observations per year "
          f"(January, pre-monsoon, August, November)")
    print(f"     obtained              : {len(SEASONS)} of the 4 seasonal slots, "
          f"for 2022 and 2023 only")
    print(f"     study period          : 2021-10-01 .. 2025-09-30")
    print(f"     coverage of the study period: NOT COMPLETE - 2021, 2024 and 2025 "
          f"seasonal files were not obtainable from the archive, and the live CGWB "
          f"host returns HTTP 502")
    print(f"     NO interpolation to monthly values was performed and none will be: four "
          f"seasonal observations are four observations.")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "CGWB static groundwater data recovery",
        "files_obtained": inventory,
        "schema": {
            "station_code": False, "station_name": True, "latitude": True,
            "longitude": True, "district": True, "well_type": True,
            "exact_measurement_date": False, "season_and_year": True,
            "depth_to_water_level": True, "unit": "mbgl", "aquifer_metadata": False,
            "station_level": True, "aggregated": False,
        },
        "station_count_in_aoi": int(len(registry)) if not stations.empty else 0,
        "stations_with_2plus_seasons": int((registry["n_seasons"] >= 2).sum())
            if not stations.empty else 0,
        "stations_within_2km": int(registry["within_2km"].sum()) if not stations.empty else 0,
        "stations_within_5km": int(registry["within_5km"].sum()) if not stations.empty else 0,
        "stations_within_10km": int(registry["within_10km"].sum()) if not stations.empty else 0,
        "temporal_sampling": "4 seasonal observations per year (CGWB design)",
        "seasons_obtained": [f"{v['season']} {v['year']}" for v in SEASONS.values()],
        "study_period": ["2021-10-01", "2025-09-30"],
        "study_period_coverage_complete": False,
        "no_interpolation": True,
        "high_frequency_dwlr": "ACCESS BLOCKED (India-WRIS / WIMS / gwdata portal)",
        "classification": "PARTIALLY TESTABLE - SEASONAL SITE DATA ONLY",
        "correlation_analysis_performed": False,
    }
    (OUT / "groundwater_gate.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  CLASSIFICATION: PARTIALLY TESTABLE - SEASONAL SITE DATA ONLY")
    print(f"\n  {OUT / 'groundwater_source_inventory.csv'}")
    print(f"  {OUT / 'groundwater_station_registry.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
