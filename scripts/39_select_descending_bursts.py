#!/usr/bin/env python
"""
Phase II, stage 2: select and freeze the DESCENDING geographic burst collection.

This is an independent validation product. It does not replace, extend, or
modify the frozen ascending `product_v1`, and it shares no burst, no pair, and
no mask with it. Pair selection is driven purely by the network rules below; in
particular, pairs are NOT chosen because they intersect the Phase-I hotspots.

A structural difference from the ascending selection
----------------------------------------------------
The ascending collection (path 27, K=4, IW2) fully contains the AOI. **The
descending collection cannot.** Descending path 136 is the only descending IW
track whose bursts intersect the AOI, and its sub-swath footprint leaves a
western strip (longitude below about 76.995 E) uncovered: 28.03 % of the AOI.

Consequently the selection criterion is changed from "contains the AOI" to
"contains every Phase-I hotspot footprint, and maximises AOI coverage". All five
Phase-I hotspot polygons lie 100 % inside the IW1 footprint, so all five are
validatable; the western strip is simply not addressable with descending data
from this orbit, and that is recorded as a limitation rather than papered over.

IW1 rather than IW2
-------------------
IW2 lies WEST of IW1 (IW2 spans about 75.99-77.05 E, IW1 about 76.89-77.90 E).
IW1 alone covers 71.97 % of the AOI and all five hotspots; IW2 alone covers
34.43 % and no hotspot. Their union covers 100 %, but a multi-burst job must be
a contiguous along-track run within ONE sub-swath, so a mixed-sub-swath job is
not a valid configuration. IW1 is therefore the correct and only choice.

Outputs
-------
geometry/descending/selected_bursts.geojson
geometry/descending/coverage_report.json
manifests/descending/geographic_reference_bursts.csv

Usage
-----
    python scripts/39_select_descending_bursts.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import asf_search as asf
import pandas as pd
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asf_client as ac  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_GEOMETRY = PROJECT_ROOT / "geometry" / "descending"
OUT_MANIFESTS = PROJECT_ROOT / "manifests" / "descending"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots.geojson"

MAX_BURSTS = 15
MAX_BURST_TIME_SPREAD_SECONDS = 120
EXPECTED_DIRECTION = "DESCENDING"
EXPECTED_POLARIZATION = "VV"
EXPECTED_BEAM_MODE = "IW"
DEFAULT_REFERENCE_DATE = "2025-09-23"


def load_aoi():
    payload = json.loads(AOI_PATH.read_text())
    return payload["features"][0]["geometry"], shape(payload["features"][0]["geometry"])


def wkt_of(geometry: dict) -> str:
    body = ",".join(f"{x} {y}" for x, y in geometry["coordinates"][0])
    return f"POLYGON(({body}))"


def search_bursts(day: str, aoi_wkt: str, *, tries: int = 5) -> list[dict]:
    def once():
        results = asf.geo_search(
            intersectsWith=aoi_wkt, dataset=asf.DATASET.SLC_BURST,
            start=f"{day}T00:00:00Z", end=f"{day}T23:59:59Z",
            polarization=EXPECTED_POLARIZATION,
            flightDirection=EXPECTED_DIRECTION,
            beamMode=EXPECTED_BEAM_MODE, maxResults=2000)
        results.raise_if_incomplete()
        return list(results)

    results = ac._retry(once, tries=tries, label=f"descending geo_search {day}")
    bursts = []
    for product in results:
        props = product.properties
        burst = props.get("burst") or {}
        bursts.append({
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
        })
    return sorted(bursts, key=lambda b: b["relative_burst_id"])


def contiguous_runs(bursts: list[dict]) -> list[list[dict]]:
    runs = []
    by_swath: dict[str, list[dict]] = {}
    for burst in bursts:
        by_swath.setdefault(burst["subswath"], []).append(burst)
    for swath_bursts in by_swath.values():
        ordered = sorted(swath_bursts, key=lambda b: b["relative_burst_id"])
        for i in range(len(ordered)):
            for j in range(i, len(ordered)):
                run = ordered[i:j + 1]
                ids = [b["relative_burst_id"] for b in run]
                if ids != list(range(ids[0], ids[0] + len(ids))):
                    continue
                if len(run) > MAX_BURSTS:
                    continue
                runs.append(run)
    return runs


def evaluate_run(run: list[dict], aoi, hotspot_shapes: dict) -> dict:
    union = unary_union([shape(b["geometry"]) for b in run])
    covered = union.intersection(aoi)
    uncovered = aoi.difference(union)
    contained = {hid: bool(union.contains(g)) for hid, g in hotspot_shapes.items()}
    return {
        "k": len(run),
        "bursts": run,
        "subswath": run[0]["subswath"],
        "contains_aoi": bool(union.contains(aoi)),
        "aoi_coverage_fraction": covered.area / aoi.area,
        "uncovered_fraction": uncovered.area / aoi.area,
        "uncovered_bounds": None if uncovered.is_empty else [round(v, 5) for v in uncovered.bounds],
        "union_area_ratio": union.area / aoi.area,
        "hotspots_contained": contained,
        "all_hotspots_contained": all(contained.values()),
        "hotspot_coverage": {hid: round(g.intersection(union).area / g.area, 6)
                             for hid, g in hotspot_shapes.items()},
    }


def validate_collection(bursts: list[dict], aoi, hotspot_shapes: dict) -> dict:
    checks = []

    def check(name, passed, detail):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    ids = [b["relative_burst_id"] for b in bursts]
    check("burst_count_1_to_15", 1 <= len(bursts) <= MAX_BURSTS, f"K={len(bursts)}")
    check("contiguous_gap_free", ids == list(range(ids[0], ids[0] + len(ids))),
          f"relative burst IDs {ids}")
    paths = {b["relative_orbit"] for b in bursts}
    check("single_relative_orbit", len(paths) == 1, f"paths={sorted(paths)}")
    directions = {b["flight_direction"] for b in bursts}
    check("single_flight_direction", directions == {EXPECTED_DIRECTION},
          f"directions={sorted(directions)}")
    pols = {b["polarization"] for b in bursts}
    check("single_polarization", pols == {EXPECTED_POLARIZATION},
          f"polarizations={sorted(pols)}")
    subswaths = sorted({b["subswath"] for b in bursts})
    check("single_subswath", len(subswaths) == 1,
          f"subswaths={subswaths} (mixed sub-swaths are not a valid along-track run)")
    times = pd.to_datetime([b["azimuth_time"] or b["start_time"] for b in bursts], utc=True)
    spread = (times.max() - times.min()).total_seconds()
    check("acquisition_within_2_minutes", spread <= MAX_BURST_TIME_SPREAD_SECONDS,
          f"spread={spread:.1f}s (limit {MAX_BURST_TIME_SPREAD_SECONDS}s)")
    lons = [xy[0] for b in bursts for xy in shape(b["geometry"]).exterior.coords]
    check("no_antimeridian_crossing", not any(abs(l) > 179.0 for l in lons),
          f"lon range {min(lons):.3f}..{max(lons):.3f}")
    if len(bursts) >= 2:
        widths = [shape(b["geometry"]).bounds[2] - shape(b["geometry"]).bounds[0]
                  for b in bursts]
        check("no_lateral_jog", (max(widths) - min(widths)) < 0.02,
              f"burst lon-width spread={max(widths) - min(widths):.5f} deg")

    union = unary_union([shape(b["geometry"]) for b in bursts])
    coverage = union.intersection(aoi).area / aoi.area
    # Recorded as a FAIL: this is the honest structural limitation of descending.
    check("aoi_fully_contained", bool(union.contains(aoi)),
          f"coverage={coverage:.6f}; descending path 136 cannot cover the AOI's western "
          f"strip and no configuration of this orbit can")
    contained = {hid: bool(union.contains(g)) for hid, g in hotspot_shapes.items()}
    check("all_phase1_hotspots_contained", all(contained.values()),
          f"{sum(contained.values())}/{len(contained)} hotspot polygons fully inside: "
          f"{contained}")

    return {"checks": checks, "passed": all(c["passed"] for c in checks)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=DEFAULT_REFERENCE_DATE)
    args = parser.parse_args()

    geometry, aoi = load_aoi()
    hotspot_shapes = {}
    if HOTSPOTS.exists():
        for feature in json.loads(HOTSPOTS.read_text())["features"]:
            hotspot_shapes[feature["properties"]["hotspot_id"]] = shape(feature["geometry"])
    if not hotspot_shapes:
        print("ERROR: Phase I hotspot polygons not found; run script 32 first.", file=sys.stderr)
        return 1

    print("=" * 88)
    print("PHASE II - DESCENDING BURST SELECTION")
    print("=" * 88)
    print(f"\n  reference date {args.date}")
    print(f"  AOI bounds {[round(v, 4) for v in aoi.bounds]}")

    bursts = search_bursts(args.date, wkt_of(geometry))
    paths = sorted({b["relative_orbit"] for b in bursts})
    print(f"  {len(bursts)} descending bursts over the AOI, relative orbit(s) {paths}")
    if len(paths) != 1:
        print(f"ERROR: expected exactly one descending orbit, found {paths}. "
              "Widen the search or choose explicitly.", file=sys.stderr)
        return 1

    runs = contiguous_runs(bursts)
    evaluated = [evaluate_run(run, aoi, hotspot_shapes) for run in runs]
    # Selection: must contain every hotspot, then maximise AOI coverage, then
    # minimise K, then tighten the footprint.
    candidates = [e for e in evaluated if e["all_hotspots_contained"]]
    if not candidates:
        print("ERROR: no contiguous run contains all Phase-I hotspots.", file=sys.stderr)
        return 1
    candidates.sort(key=lambda e: (-e["aoi_coverage_fraction"], e["k"], e["union_area_ratio"]))
    chosen = candidates[0]

    print(f"\n  {len(runs)} contiguous runs evaluated, {len(candidates)} contain every hotspot")
    print(f"  chosen: {chosen['subswath']} K={chosen['k']}  "
          f"AOI coverage {chosen['aoi_coverage_fraction'] * 100:.2f}%  "
          f"hotspots {sum(chosen['hotspots_contained'].values())}/{len(hotspot_shapes)}")

    report = validate_collection(chosen["bursts"], aoi, hotspot_shapes)
    order = {"aoi_fully_contained": 0, "all_phase1_hotspots_contained": 1}
    ordered = sorted(report["checks"], key=lambda c: order.get(c["check"], 2))
    for entry in ordered:
        mark = "PASS" if entry["passed"] else "FAIL"
        print(f"    [{mark}] {entry['check']:34s} {entry['detail']}")

    hard = [c for c in report["checks"]
            if c["check"] not in ("aoi_fully_contained",)]
    report["hard_rules_passed"] = all(c["passed"] for c in hard)
    if not report["hard_rules_passed"]:
        print("\nERROR: a hard rule failed. Refusing to freeze.", file=sys.stderr)
        return 1

    OUT_GEOMETRY.mkdir(parents=True, exist_ok=True)
    OUT_MANIFESTS.mkdir(parents=True, exist_ok=True)

    (OUT_GEOMETRY / "selected_bursts.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "properties": {"flight_direction": EXPECTED_DIRECTION,
                       "relative_orbit": chosen["bursts"][0]["relative_orbit"],
                       "subswath": chosen["subswath"], "k": chosen["k"],
                       "reference_date": args.date},
        "features": [{"type": "Feature", "properties": {k: v for k, v in b.items()
                                                        if k != "geometry"},
                      "geometry": b["geometry"]} for b in chosen["bursts"]],
    }, indent=1))

    rows = []
    for b in chosen["bursts"]:
        rows.append({
            "full_burst_id": b["full_burst_id"], "relative_burst_id": b["relative_burst_id"],
            "absolute_burst_id": b["absolute_burst_id"], "burst_index": b["burst_index"],
            "samples_per_burst": b["samples_per_burst"], "subswath": b["subswath"],
            "relative_orbit": b["relative_orbit"], "flight_direction": b["flight_direction"],
            "polarization": b["polarization"], "platform": b["platform"],
            "reference_date": args.date, "reference_azimuth_time": b["azimuth_time"],
            "reference_scene_name": b["scene_name"], "reference_url": b["url"],
        })
    pd.DataFrame(rows).to_csv(OUT_MANIFESTS / "geographic_reference_bursts.csv",
                              index=False)

    coverage_report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "reference_date": args.date,
        "flight_direction": EXPECTED_DIRECTION,
        "relative_orbit": chosen["bursts"][0]["relative_orbit"],
        "subswath": chosen["subswath"],
        "k": chosen["k"],
        "full_burst_ids": [b["full_burst_id"] for b in chosen["bursts"]],
        "relative_burst_ids": [b["relative_burst_id"] for b in chosen["bursts"]],
        "aoi_coverage_fraction": round(chosen["aoi_coverage_fraction"], 6),
        "aoi_fully_contained": chosen["contains_aoi"],
        "uncovered_fraction": round(chosen["uncovered_fraction"], 6),
        "uncovered_bounds_lonlat": chosen["uncovered_bounds"],
        "union_to_aoi_area_ratio": round(chosen["union_area_ratio"], 4),
        "hotspots_contained": chosen["hotspots_contained"],
        "hotspot_coverage_fraction": chosen["hotspot_coverage"],
        "rule_checks": report["checks"],
        "hard_rules_passed": report["hard_rules_passed"],
        "structural_limitation": (
            "Descending path 136 is the only descending IW track intersecting the AOI, and "
            f"its swath edge leaves {chosen['uncovered_fraction'] * 100:.2f}% of the AOI "
            "(the western strip, longitude below about 76.995 E) uncovered. No configuration "
            "of this orbit can cover it. All five Phase-I hotspot polygons are 100% inside "
            "the selected footprint, so all five remain validatable."),
        "candidate_runs": [
            {"k": e["k"], "subswath": e["subswath"],
             "aoi_coverage_fraction": round(e["aoi_coverage_fraction"], 6),
             "all_hotspots_contained": e["all_hotspots_contained"]}
            for e in sorted(evaluated, key=lambda x: (-x["aoi_coverage_fraction"], x["k"]))[:20]
        ],
        "ascending_comparison": {
            "ascending_orbit": 27, "ascending_subswath": "IW2", "ascending_k": 4,
            "ascending_aoi_coverage_fraction": 1.0,
            "note": "Independent collections: no shared burst, pair, or mask.",
        },
    }
    (OUT_GEOMETRY / "coverage_report.json").write_text(
        json.dumps(coverage_report, indent=2, default=str))

    print(f"\n  AOI coverage {chosen['aoi_coverage_fraction'] * 100:.2f}% "
          f"(ascending achieves 100%; descending structurally cannot)")
    print(f"  all hotspots contained: {chosen['all_hotspots_contained']}")
    print(f"\n  {OUT_MANIFESTS / 'geographic_reference_bursts.csv'}")
    print(f"  {OUT_GEOMETRY / 'coverage_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
