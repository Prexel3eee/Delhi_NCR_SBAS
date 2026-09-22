#!/usr/bin/env python
"""
Phase III-A stages A-B, D, E: external dataset registry and acquisition.

METHOD ORDER MATTERS
--------------------
The inclusion/exclusion decisions below were made from endpoint reconnaissance
ALONE, before any explanatory value was computed. Nothing here was selected
because it agreed with the InSAR pattern. That ordering is the point of the
registry.

Usage
-----
    python scripts/60_phase3_registry.py --registry
    python scripts/60_phase3_registry.py --acquire-era5
    python scripts/60_phase3_registry.py --acquire-grace
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "qc" / "sci" / "phase3"
DATA = PROJECT_ROOT / "data" / "external"

#: AOI centre, for the record.
AOI = {"lon_min": 76.7853, "lat_min": 28.3839, "lon_max": 77.2838, "lat_max": 28.8726}
STUDY = {"start": "2021-10-01", "end": "2025-09-30"}

#: Reconnaissance results, established BEFORE any explanatory analysis.
REGISTRY = [
    {
        "dataset": "CGWB groundwater level time series (site level)",
        "source": "India-WRIS / CGWB gwdata portal",
        "endpoints_tried": ["https://indiawris.gov.in", "https://gwdata.cgwb.gov.in",
                            "https://www.cgwb.gov.in"],
        "observed": "indiawris.gov.in unreachable (curl code 000); www.cgwb.gov.in "
                    "unreachable; gwdata.cgwb.gov.in returns an HTML page titled "
                    "'Maintenance Mode' on every path tried (/api, /api/v1, "
                    "/swagger/index.html, /api/groundwater, /api/WaterLevel all 404).",
        "coverage": None,
        "resolution": None,
        "time_span": None,
        "decision": "NOT OBTAINABLE",
        "reason": "All three public routes are down or unreachable at the time of "
                  "reconnaissance. No site-level piezometric time series for Delhi-NCR "
                  "could be retrieved.",
        "consequence": "HYPOTHESIS G (groundwater) cannot be tested with site data in this "
                       "phase. This is the single largest limitation of Phase III-A.",
    },
    {
        "dataset": "data.gov.in CGWB groundwater resources",
        "source": "data.gov.in API",
        "endpoints_tried": ["https://api.data.gov.in/lists",
                            "https://api.data.gov.in/resource/<id>"],
        "observed": "Catalogue search works and returns CGWB resources, but every "
                    "resource query returns HTTP 400 {'error': 'Authorization field "
                    "missing'} - an API key is required.",
        "coverage": "State/UT and district-level AGGREGATES (annual draft, recharge, "
                    "assessment-unit categories, decadal fluctuation)",
        "resolution": "state/district",
        "time_span": "varies, mostly annual",
        "decision": "NOT OBTAINABLE and NOT SUITABLE",
        "reason": "Two independent grounds: (1) no API key is available in this "
                  "environment; (2) even with a key, the accessible CGWB resources are "
                  "state/district ANNUAL aggregates, not the station-level monthly time "
                  "series the temporal analysis in section 8 requires. Annual district "
                  "aggregates cannot resolve monthly seasonal timing at a hotspot.",
    },
    {
        "dataset": "ERA5 total precipitation (single levels)",
        "source": "Copernicus Climate Data Store, via cdsapi",
        "endpoints_tried": ["https://cds.climate.copernicus.eu/api"],
        "observed": "HTTP 202, cdsapi importable, ~/.cdsapirc present and already proven "
                    "by the descending ERA5 retrieval (91 GRIBs downloaded).",
        "coverage": "global, AOI subset [40, 70, 20, 80]",
        "resolution": "0.25 deg (~28 km) native, monthly means requested",
        "time_span": STUDY,
        "decision": "INCLUDED",
        "reason": "Reachable, credentials verified, directly addresses HYPOTHESIS H "
                  "(hydrological/seasonal forcing) and the non-stationarity question.",
    },
    {
        "dataset": "GRACE / GRACE-FO mascon (GSFC RL06 v2.0)",
        "source": "NASA GSFC",
        "endpoints_tried": ["https://earth.gsfc.nasa.gov/geo/data/grace-mascons"],
        "observed": "HTTP 200; direct file href resolvable "
                    "(gsfc.glb_.200204_202603_rl06v2.0_obp-ice6gd_halfdegree.nc).",
        "coverage": "global",
        "resolution": "0.5 deg (~55 km) mascon",
        "time_span": "2002-04 to 2026-03",
        "decision": "INCLUDED AS REGIONAL CONTEXT ONLY",
        "reason": "Reachable. At ~55 km resolution it cannot resolve a 0.8-13 km2 "
                  "hotspot, so it is admitted only as regional water-storage CONTEXT, "
                  "never as a hotspot discriminator.",
    },
    {
        "dataset": "Aquifer type / alluvium thickness / lithology / geomorphology",
        "source": "CGWB aquifer maps, GSI, Bhukosh",
        "endpoints_tried": ["https://bhukosh.gsi.gov.in", "https://www.cgwb.gov.in"],
        "observed": "Not reachable during reconnaissance.",
        "coverage": None, "resolution": None, "time_span": None,
        "decision": "NOT OBTAINABLE",
        "reason": "No reachable source found in the time available. HYPOTHESIS GEO is "
                  "therefore testable only INDIRECTLY, through proxies already in hand "
                  "(elevation, and any land-cover class that carries a sedimentological "
                  "meaning).",
    },
    {
        "dataset": "Built-up / land cover (GHSL, ESA WorldCover)",
        "source": "Copernicus Data Space, JRC GHSL",
        "endpoints_tried": ["https://dataspace.copernicus.eu"],
        "observed": "HTTP 200, but no authenticated download was completed in this "
                    "session.",
        "coverage": None, "resolution": None, "time_span": None,
        "decision": "NOT OBTAINED",
        "reason": "Endpoint reachable but acquisition not completed. HYPOTHESIS U "
                  "(urban loading) is therefore testable only through the coherence "
                  "confounding test and existing geometry, not through an independent "
                  "built-up raster.",
    },
]


def write_registry() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "aoi": AOI, "study_period": STUDY,
        "method_note": "Inclusion decisions were made from endpoint reconnaissance alone, "
                       "before any explanatory value was computed. No dataset was "
                       "selected or rejected on the basis of agreement with the InSAR "
                       "pattern.",
        "datasets": REGISTRY,
        "summary": {
            "obtainable": [d["dataset"] for d in REGISTRY
                           if d["decision"].startswith("INCLUDED")],
            "not_obtainable": [d["dataset"] for d in REGISTRY
                               if d["decision"].startswith("NOT")],
            "priority_A_groundwater": "NOT OBTAINABLE - see consequences",
        },
    }
    (OUT / "dataset_registry.json").write_text(json.dumps(payload, indent=2, default=str))
    print("=" * 88)
    print("PHASE III-A - EXTERNAL DATASET REGISTRY (decided before any analysis)")
    print("=" * 88)
    for d in REGISTRY:
        print(f"\n  {d['dataset']}")
        print(f"    decision : {d['decision']}")
        print(f"    reason   : {d['reason'][:100]}...")
    print(f"\n  OBTAINABLE    : {payload['summary']['obtainable']}")
    print(f"  NOT OBTAINABLE: {payload['summary']['not_obtainable']}")
    print(f"\n  {OUT / 'dataset_registry.json'}")
    return 0


def acquire_era5() -> int:
    import cdsapi
    DATA.mkdir(parents=True, exist_ok=True)
    target = DATA / "era5_total_precipitation_monthly.nc"
    if target.exists():
        print(f"  already present: {target}")
        return 0
    client = cdsapi.Client()
    years = ["2021", "2022", "2023", "2024", "2025"]
    months = [f"{m:02d}" for m in range(1, 13)]
    print(f"  requesting ERA5 monthly-mean total precipitation for {years}...")
    client.retrieve(
        "reanalysis-era5-single-levels-monthly-means",
        {"product_type": "monthly_averaged_reanalysis",
         "variable": "total_precipitation",
         "year": years, "month": months, "time": "00:00",
         "area": [40, 70, 20, 80], "data_format": "netcdf",
         "download_format": "unarchived"},
        str(target))
    print(f"  wrote {target} ({target.stat().st_size / 1e6:.2f} MB)")
    return 0


def acquire_grace() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    target = DATA / "grace_gsfc_rl06v2_mascon.nc"
    if target.exists():
        print(f"  already present: {target}")
        return 0
    url = ("https://earth.gsfc.nasa.gov/sites/default/files/geo/"
           "gsfc.glb_.200204_202603_rl06v2.0_obp-ice6gd_halfdegree.nc")
    print(f"  downloading {url}")
    result = subprocess.run(["curl", "-sL", "--max-time", "900", "-o", str(target), url],
                            capture_output=True, text=True)
    if result.returncode != 0 or not target.exists():
        print(f"  FAILED: {result.stderr[:200]}", file=sys.stderr)
        return 1
    print(f"  wrote {target} ({target.stat().st_size / 1e6:.2f} MB)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--registry", action="store_true")
    g.add_argument("--acquire-era5", action="store_true")
    g.add_argument("--acquire-grace", action="store_true")
    args = parser.parse_args()
    if args.registry:
        return write_registry()
    if args.acquire_era5:
        return acquire_era5()
    return acquire_grace()


if __name__ == "__main__":
    raise SystemExit(main())
