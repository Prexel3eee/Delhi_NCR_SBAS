#!/usr/bin/env python
"""
Phase B - select and freeze the geographic reference burst collection.

Goal
----
For the frozen Delhi-NCR AOI, find the **smallest valid contiguous burst
collection** on ascending relative orbit 27, VV, IW that fully contains the
AOI, then validate it against every hard HyP3 multi-burst rule and freeze it.

The earlier hand-entered K=3 collection (056011/056012/056013) is rejected: its
union does not contain the AOI (a ~0.37 % sliver at the AOI's north-west corner
falls outside). The AOI is NOT shrunk to preserve K=3.

Outputs
-------
geometry/selected_bursts.geojson
geometry/coverage_report.json
manifests/geographic_reference_bursts.csv

Usage
-----
    python scripts/02_select_reference_bursts.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from itertools import combinations
from pathlib import Path

import asf_search as asf
import pandas as pd
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asf_client as ac  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GEOMETRY_DIR = PROJECT_ROOT / "geometry"
MANIFEST_DIR = PROJECT_ROOT / "manifests"

#: Hard HyP3 multi-burst limits (brief section 5.1).
MAX_BURSTS = 15
MAX_BURST_TIME_SPREAD_SECONDS = 120

EXPECTED_PATH = 27
EXPECTED_DIRECTION = "ASCENDING"
EXPECTED_POLARIZATION = "VV"
EXPECTED_BEAM_MODE = "IW"

#: Representative acquisition date used to define the geographic collection.
DEFAULT_REFERENCE_DATE = "2025-09-27"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_aoi() -> tuple[dict, object]:
    geojson_path = GEOMETRY_DIR / "aoi.geojson"
    payload = json.loads(geojson_path.read_text())
    polygon = shape(payload["features"][0]["geometry"])
    return payload["features"][0]["geometry"], polygon


def wkt_of(geometry: dict) -> str:
    coords = geometry["coordinates"][0]
    body = ",".join(f"{x} {y}" for x, y in coords)
    return f"POLYGON(({body}))"


def search_bursts_for_date(day: str, aoi_wkt: str, *, tries: int = 5) -> list[dict]:
    """All burst footprints intersecting the AOI on one date, with retries."""

    def once():
        results = asf.geo_search(
            intersectsWith=aoi_wkt,
            dataset=asf.DATASET.SLC_BURST,
            start=f"{day}T00:00:00Z",
            end=f"{day}T23:59:59Z",
            polarization=EXPECTED_POLARIZATION,
            flightDirection=EXPECTED_DIRECTION,
            relativeOrbit=EXPECTED_PATH,
            beamMode=EXPECTED_BEAM_MODE,
            maxResults=500,
        )
        results.raise_if_incomplete()
        return list(results)

    results = ac._retry(once, tries=tries, label=f"geo_search {day}")

    bursts = []
    for product in results:
        props = product.properties
        burst = props.get("burst") or {}
        bursts.append(
            {
                "full_burst_id": burst.get("fullBurstID"),
                "relative_burst_id": int(burst.get("relativeBurstID")),
                "absolute_burst_id": burst.get("absoluteBurstID"),
                "burst_index": burst.get("burstIndex"),
                "samples_per_burst": burst.get("samplesPerBurst"),
                "subswath": burst.get("subswath"),
                "relative_orbit": int(props.get("pathNumber")),
                "flight_direction": props.get("flightDirection"),
                "polarization": props.get("polarization"),
                "platform": props.get("platform"),
                "start_time": props.get("startTime"),
                "azimuth_time": burst.get("azimuthTime"),
                "azimuth_anx_time": burst.get("azimuthAnxTime"),
                "scene_name": props.get("sceneName"),
                "url": props.get("url"),
                "geometry": product.geometry,
            }
        )
    return sorted(bursts, key=lambda b: b["relative_burst_id"])


# ---------------------------------------------------------------------------
# Minimum covering collection
# ---------------------------------------------------------------------------


def contiguous_runs(bursts: list[dict]) -> list[list[dict]]:
    """All contiguous along-track runs of bursts sharing one sub-swath."""
    runs: list[list[dict]] = []
    by_swath: dict[str, list[dict]] = {}
    for burst in bursts:
        by_swath.setdefault(burst["subswath"], []).append(burst)

    for swath_bursts in by_swath.values():
        ordered = sorted(swath_bursts, key=lambda b: b["relative_burst_id"])
        for i in range(len(ordered)):
            for j in range(i, len(ordered)):
                run = ordered[i : j + 1]
                ids = [b["relative_burst_id"] for b in run]
                if ids != list(range(ids[0], ids[0] + len(ids))):
                    continue  # not gap-free contiguous
                if len(run) > MAX_BURSTS:
                    continue
                runs.append(run)
    return runs


def evaluate_run(run: list[dict], aoi) -> dict:
    union = unary_union([shape(b["geometry"]) for b in run])
    covered = union.intersection(aoi)
    uncovered = aoi.difference(union)
    return {
        "k": len(run),
        "bursts": run,
        "contains_aoi": bool(union.contains(aoi)),
        "coverage_fraction": covered.area / aoi.area,
        "uncovered_fraction": uncovered.area / aoi.area,
        "uncovered_bounds": None if uncovered.is_empty else [round(v, 5) for v in uncovered.bounds],
        "union_area_ratio": union.area / aoi.area,
        "union_geometry": union,
    }


def select_minimum_collection(bursts: list[dict], aoi) -> tuple[dict, list[dict]]:
    """Smallest run that fully contains the AOI; ties broken by tightest footprint."""
    evaluated = [evaluate_run(run, aoi) for run in contiguous_runs(bursts)]
    valid = [e for e in evaluated if e["contains_aoi"]]
    if not valid:
        raise SystemExit(
            "FAIL: no contiguous burst run on this date fully contains the AOI. "
            "Widen the candidate search before choosing a collection."
        )
    valid.sort(key=lambda e: (e["k"], e["union_area_ratio"]))
    rejected_smaller = [e for e in evaluated if e["k"] < valid[0]["k"]]
    return valid[0], rejected_smaller


# ---------------------------------------------------------------------------
# Rule validation (HyP3 multi-burst hard limits)
# ---------------------------------------------------------------------------


def validate_collection(bursts: list[dict], aoi) -> dict:
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    ids = [b["relative_burst_id"] for b in bursts]
    check("burst_count_1_to_15", 1 <= len(bursts) <= MAX_BURSTS, f"K={len(bursts)}")
    check(
        "contiguous_gap_free",
        ids == list(range(ids[0], ids[0] + len(ids))),
        f"relative burst IDs {ids}",
    )

    paths = {b["relative_orbit"] for b in bursts}
    check("single_relative_orbit", paths == {EXPECTED_PATH}, f"paths={sorted(paths)}")

    directions = {b["flight_direction"] for b in bursts}
    check("single_flight_direction", directions == {EXPECTED_DIRECTION}, f"directions={sorted(directions)}")

    pols = {b["polarization"] for b in bursts}
    check("single_polarization", pols == {EXPECTED_POLARIZATION}, f"polarizations={sorted(pols)}")

    subswaths = sorted({b["subswath"] for b in bursts})
    check(
        "single_or_adjacent_subswath",
        len(subswaths) == 1,
        f"subswaths={subswaths} (single sub-swath: no cross-sub-swath offset rule invoked)",
    )

    # All bursts must have been acquired within two minutes of one another.
    times = pd.to_datetime([b["azimuth_time"] or b["start_time"] for b in bursts], utc=True)
    spread = (times.max() - times.min()).total_seconds()
    check(
        "acquisition_within_2_minutes",
        spread <= MAX_BURST_TIME_SPREAD_SECONDS,
        f"spread={spread:.1f}s (limit {MAX_BURST_TIME_SPREAD_SECONDS}s)",
    )

    lons = [xy[0] for b in bursts for xy in shape(b["geometry"]).exterior.coords]
    antimeridian = any(abs(lon) > 179.0 for lon in lons)
    check("no_antimeridian_crossing", not antimeridian, f"lon range {min(lons):.3f}..{max(lons):.3f}")

    union = unary_union([shape(b["geometry"]) for b in bursts])
    check("aoi_fully_contained", bool(union.contains(aoi)), f"coverage={union.intersection(aoi).area / aoi.area:.6f}")

    # Compactness: a single contiguous run in one sub-swath is inherently
    # rectangular; confirm the union is not L- or T-shaped by checking that the
    # along-track span equals the sum of burst spans (no lateral offset).
    if len(bursts) >= 2:
        widths = [shape(b["geometry"]).bounds[2] - shape(b["geometry"]).bounds[0] for b in bursts]
        check(
            "no_lateral_jog",
            (max(widths) - min(widths)) < 0.02,
            f"burst lon-width spread={max(widths) - min(widths):.5f} deg",
        )

    return {
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=DEFAULT_REFERENCE_DATE, help="representative acquisition date")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    GEOMETRY_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    aoi_geometry, aoi = load_aoi()
    aoi_wkt = wkt_of(aoi_geometry)

    print("=" * 88)
    print("PHASE B - GEOGRAPHIC REFERENCE BURST SELECTION")
    print("=" * 88)
    print(f"\nAOI area          : {aoi.area:.6f} deg^2")
    print(f"Reference date    : {args.date}")
    print(f"Constraints       : path {EXPECTED_PATH} / {EXPECTED_DIRECTION} / {EXPECTED_POLARIZATION} / {EXPECTED_BEAM_MODE}")

    bursts = search_bursts_for_date(args.date, aoi_wkt)
    print(f"\nBursts intersecting AOI on {args.date}: {len(bursts)}")
    for b in bursts:
        geom = shape(b["geometry"])
        print(
            f"  {b['full_burst_id']:16s} rel={b['relative_burst_id']:>6} "
            f"idx={str(b['burst_index']):>2} {b['subswath']:4s} "
            f"{b['platform']:12s} aoi_cov={geom.intersection(aoi).area / aoi.area:7.4f}"
        )

    best, rejected_smaller = select_minimum_collection(bursts, aoi)

    print("\n" + "-" * 88)
    print("MINIMUM FULLY-COVERING CONTIGUOUS COLLECTION")
    print("-" * 88)
    print(f"  K = {best['k']}")
    print(f"  bursts              : {[b['full_burst_id'] for b in best['bursts']]}")
    print(f"  AOI coverage        : {best['coverage_fraction'] * 100:.4f} %")
    print(f"  union / AOI area    : {best['union_area_ratio']:.3f}")

    if rejected_smaller:
        print("\n  Smaller collections rejected for incomplete AOI coverage:")
        for e in sorted(rejected_smaller, key=lambda x: x["k"]):
            print(
                f"    K={e['k']} {[b['full_burst_id'] for b in e['bursts']]} "
                f"-> uncovered {e['uncovered_fraction'] * 100:.4f} % "
                f"at {e['uncovered_bounds']}"
            )

    validation = validate_collection(best["bursts"], aoi)

    print("\n" + "-" * 88)
    print("HARD VALIDATION CHECKS")
    print("-" * 88)
    for c in validation["checks"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['check']:32s} {c['detail']}")

    selected = best["bursts"]

    # ------------------------------------------------------------------
    # Freeze: geographic_reference_bursts.csv
    # ------------------------------------------------------------------
    ref_rows = []
    for b in selected:
        geom = shape(b["geometry"])
        ref_rows.append(
            {
                "full_burst_id": b["full_burst_id"],
                "relative_burst_id": b["relative_burst_id"],
                "absolute_burst_id": b["absolute_burst_id"],
                "burst_index": b["burst_index"],
                "samples_per_burst": b["samples_per_burst"],
                "subswath": b["subswath"],
                "relative_orbit": b["relative_orbit"],
                "flight_direction": b["flight_direction"],
                "polarization": b["polarization"],
                "platform": b["platform"],
                "reference_date": args.date,
                "reference_azimuth_time": b["azimuth_time"],
                "reference_scene_name": b["scene_name"],
                "reference_url": b["url"],
                "geometry_area_deg2": round(geom.area, 6),
                "aoi_coverage_fraction": round(geom.intersection(aoi).area / aoi.area, 6),
                "aoi_fully_inside_burst": bool(geom.contains(aoi)),
            }
        )
    ref_df = pd.DataFrame(ref_rows)
    ref_path = MANIFEST_DIR / "geographic_reference_bursts.csv"
    ref_df.to_csv(ref_path, index=False)

    # ------------------------------------------------------------------
    # Freeze: selected_bursts.geojson
    # ------------------------------------------------------------------
    features = []
    for b in selected:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "full_burst_id": b["full_burst_id"],
                    "relative_burst_id": b["relative_burst_id"],
                    "absolute_burst_id": b["absolute_burst_id"],
                    "burst_index": b["burst_index"],
                    "subswath": b["subswath"],
                    "relative_orbit": b["relative_orbit"],
                    "flight_direction": b["flight_direction"],
                    "polarization": b["polarization"],
                    "platform": b["platform"],
                    "reference_date": args.date,
                    "reference_scene_name": b["scene_name"],
                    "role": "selected_geographic_reference_burst",
                },
                "geometry": b["geometry"],
            }
        )
    geojson = {
        "type": "FeatureCollection",
        "name": "delhi_ncr_selected_bursts",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    (GEOMETRY_DIR / "selected_bursts.geojson").write_text(json.dumps(geojson, indent=2))

    # ------------------------------------------------------------------
    # Freeze: coverage_report.json
    # ------------------------------------------------------------------
    coverage_report = {
        "phase": "B",
        "reference_date": args.date,
        "constraints": {
            "relative_orbit": EXPECTED_PATH,
            "flight_direction": EXPECTED_DIRECTION,
            "polarization": EXPECTED_POLARIZATION,
            "beam_mode": EXPECTED_BEAM_MODE,
        },
        "aoi": {"wkt": aoi_wkt, "area_deg2": round(aoi.area, 6)},
        "candidate_bursts_intersecting_aoi": [
            {
                "full_burst_id": b["full_burst_id"],
                "relative_burst_id": b["relative_burst_id"],
                "subswath": b["subswath"],
                "burst_index": b["burst_index"],
                "aoi_coverage_fraction": round(
                    shape(b["geometry"]).intersection(aoi).area / aoi.area, 6
                ),
            }
            for b in bursts
        ],
        "selected": {
            "k": best["k"],
            "full_burst_ids": [b["full_burst_id"] for b in selected],
            "aoi_coverage_fraction": best["coverage_fraction"],
            "uncovered_fraction": best["uncovered_fraction"],
            "union_area_ratio": round(best["union_area_ratio"], 4),
        },
        "rejected_smaller_collections": [
            {
                "k": e["k"],
                "full_burst_ids": [b["full_burst_id"] for b in e["bursts"]],
                "uncovered_fraction": e["uncovered_fraction"],
                "uncovered_bounds": e["uncovered_bounds"],
            }
            for e in sorted(rejected_smaller, key=lambda x: x["k"])
        ],
        "validation": validation,
        "accepted": validation["passed"] and best["contains_aoi"],
    }
    (GEOMETRY_DIR / "coverage_report.json").write_text(json.dumps(coverage_report, indent=2))

    print("\n" + "=" * 88)
    if coverage_report["accepted"]:
        print(f"PHASE B COMPLETE - {best['k']} bursts frozen on ascending path {EXPECTED_PATH}.")
        print(f"AOI coverage: 100% (union/AOI area {best['union_area_ratio']:.3f}).")
        print("Collection validity: PASSED.")
    else:
        print("PHASE B FAILED - do not proceed to stack discovery.")
    print("=" * 88)
    print(f"\n  {ref_path}")
    print(f"  {GEOMETRY_DIR / 'selected_bursts.geojson'}")
    print(f"  {GEOMETRY_DIR / 'coverage_report.json'}")

    return 0 if coverage_report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
