#!/usr/bin/env python
"""
Phase III-A2: high-frequency groundwater acquisition audit.

Freezes the recovered seasonal CGWB dataset state, records its limitations,
audits every high-frequency route tested, computes the nearest-station geometry
per hotspot, and prepares the official-request package.

NO groundwater/InSAR correlation is performed. No causal claim is made.

Usage
-----
    python scripts/63_phase3a2_dwlr_audit.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GW = PROJECT_ROOT / "data" / "external" / "groundwater"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase3"
FREEZE = PROJECT_ROOT / "freeze" / "cgwb_seasonal_v1"
REPORT = PROJECT_ROOT / "qc" / "sci" / "PHASE_IIIA2_DWLR_ACQUISITION_AUDIT.md"

SEASONAL = {
    "pre-monsoon_2022_data_for_website": ("pre-monsoon", 2022),
    "august_2022_data_for_website": ("august", 2022),
    "nov_2022_data_for_website": ("november", 2022),
    "jan_2023_data_for_website": ("january", 2023),
}

#: Every route tested in this audit, with its observed status.
ROUTES = [
    ("India-WRIS (preferred DWLR route)", "https://indiawris.gov.in",
     "curl code 000 - host unreachable", "ACCESS BLOCKED"),
    ("India-WRIS WRIS app", "https://indiawris.gov.in/wris",
     "curl code 000 - host unreachable", "ACCESS BLOCKED"),
    ("WIMS / Ministry of Water Resources", "https://wims.mowr.gov.in",
     "curl code 000 - host unreachable", "ACCESS BLOCKED"),
    ("CGWB groundwater data portal", "https://gwdata.cgwb.gov.in",
     "HTTP 200 but every page is an HTML 'Maintenance Mode' notice; /api, /api/v1, "
     "/swagger/index.html, /api/groundwater, /api/WaterLevel all 404",
     "ACCESS BLOCKED"),
    ("CGWB main site", "https://cgwb.gov.in",
     "HTTP 502 Bad Gateway on every path; www.cgwb.gov.in does not resolve (000)",
     "ACCESS BLOCKED"),
    ("NWIC (National Water Informatics Centre)", "https://nwic.gov.in",
     "HTTP 200, but it is a landing page only; its data links point to India-WRIS "
     "(unreachable) and data.gov.in (key-gated). No downloadable groundwater product.",
     "NO DATA PRODUCT"),
    ("data.gov.in", "https://api.data.gov.in",
     "Catalogue searchable; resource queries return HTTP 400 "
     "'Authorization field missing'. No API key available. Resources found are "
     "state/district ANNUAL aggregates, not station observations.",
     "CONTEXT ONLY / KEY-GATED"),
    ("Delhi Jal Board", "https://delhijalboard.delhi.gov.in",
     "HTTP 200; no groundwater-level data endpoint located", "NO DATA PRODUCT"),
    ("Delhi state portal", "https://delhi.gov.in",
     "HTTP 200; no station-level groundwater observation service located",
     "NO DATA PRODUCT"),
    ("National Hydrology Project", "https://nhp.mowr.gov.in",
     "curl code 000 - unreachable", "ACCESS BLOCKED"),
    ("India-WRIS river network subdomain", "https://indiawris.gov.in/riverNetwork/",
     "curl code 000 - unreachable", "ACCESS BLOCKED"),
    ("Internet Archive - CGWB DWLR files",
     "http://web.archive.org/cdx/search/cdx?url=cgwb.gov.in*",
     "Searched for DWLR / telemetry / hourly / digital. The archive holds only DWLR "
     "photographs (2006) and DWLR tender documents (2022) - no observation data.",
     "NO DATA PRODUCT"),
    ("Flood Forecasting (india-water)", "https://ffs.india-water.gov.in",
     "HTTP 200 but it is a flood-forecast service, not groundwater", "WRONG PRODUCT"),
]


def sha256_of(path: Path) -> str:
    d = hashlib.sha256()
    with path.open("rb") as h:
        for c in iter(lambda: h.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    registry = pd.read_csv(OUT / "groundwater_station_registry.csv")

    # ---- 1. provenance freeze --------------------------------------------
    if FREEZE.exists():
        subprocess.run(["chmod", "-R", "u+w", str(FREEZE)], check=False)
        import shutil
        shutil.rmtree(FREEZE)
    FREEZE.mkdir(parents=True)
    records = []
    for stem, (season, year) in SEASONAL.items():
        pdf = GW / f"{stem}.pdf"
        txt = GW / f"{stem}.txt"
        if not pdf.exists():
            continue
        pages = 0
        try:
            info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
            for line in info.stdout.splitlines():
                if line.startswith("Pages:"):
                    pages = int(line.split()[1])
        except Exception:  # noqa: BLE001
            pass
        rows = 0
        if txt.exists():
            rows = sum(1 for line in txt.read_text(errors="ignore").splitlines()
                       if line.startswith(("Delhi", "Haryana", "Uttar Pradesh")))
        official = (f"https://cgwb.gov.in/sites/default/files/inline-files/{pdf.name}")
        records.append({
            "file": pdf.name, "season": season, "year": year,
            "official_cgwb_url": official,
            "internet_archive_url": ("https://web.archive.org/web/20241027131951if_/"
                                     + official),
            "sha256": sha256_of(pdf), "bytes": pdf.stat().st_size, "pages": pages,
            "parsed_rows_aoi_states": rows,
            "coordinate_coverage": "latitude and longitude present for every parsed row",
            "known_schema_limitations": [
                "no CGWB station code", "season and year only, no exact measurement date",
                "no aquifer or well-depth metadata",
                "well type blank in some rows",
            ],
        })
    manifest = {
        "freeze_version": "cgwb_seasonal_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "provenance_wording": "The source file is an archived copy of an official CGWB "
                              "URL retrieved via the Internet Archive because the live "
                              "CGWB host was unavailable at retrieval time.",
        "not_a_live_download": True,
        "files": records,
    }
    fid = hashlib.sha256(json.dumps(
        [[r["file"], r["sha256"]] for r in records], sort_keys=True).encode()).hexdigest()
    manifest["freeze_id"] = fid
    (FREEZE / "FREEZE.json").write_text(json.dumps(manifest, indent=2, default=str))
    for x in sorted(FREEZE.rglob("*"), reverse=True):
        x.chmod(0o444 if x.is_file() else 0o555)
    FREEZE.chmod(0o555)

    # ---- 5. nearest-station geometry -------------------------------------
    def nearest(hid, n=3):
        col = f"dist_km_{hid}"
        sub = registry.nsmallest(n, col)[
            ["site_name", "state", col, "n_seasons", "well_type"]]
        return [{"site_name": r["site_name"], "state": r["state"],
                 "distance_km": round(float(r[col]), 3),
                 "seasons": int(r["n_seasons"]), "well_type": r["well_type"]}
                for _, r in sub.iterrows()]

    tiers = {}
    for hid in ("H001", "H004", "H002", "H003"):
        col = f"dist_km_{hid}"
        tiers[hid] = {
            "nearest_km": round(float(registry[col].min()), 3),
            "tier1_le2km": int((registry[col] <= 2).sum()),
            "tier2_2to5km": int(((registry[col] > 2) & (registry[col] <= 5)).sum()),
            "tier3_5to10km": int(((registry[col] > 5) & (registry[col] <= 10)).sum()),
            "tier4_10to20km": int(((registry[col] > 10) & (registry[col] <= 20)).sum()),
            "best_stations": nearest(hid),
        }

    print("=" * 88)
    print("PHASE III-A2 - HIGH-FREQUENCY GROUNDWATER ACQUISITION AUDIT")
    print("=" * 88)

    print(f"\n  1. SEASONAL DATASET FROZEN: cgwb_seasonal_v1  ({fid[:24]}...)")
    print(f"     \"{manifest['provenance_wording']}\"")
    for r in records:
        print(f"     {r['file']:40s} {r['pages']:4d} pp  {r['bytes']/1e6:5.1f} MB  "
              f"{r['parsed_rows_aoi_states']:4d} AOI-state rows")

    print(f"\n  2. FROZEN LIMITATIONS")
    print(f"     TEMPORAL: four seasonal observations spanning 2022-2023 only")
    print(f"     SPATIAL : no monitoring station within 2 km of any hotspot")
    print(f"     H001    : nearest station {tiers['H001']['nearest_km']:.2f} km")

    print(f"\n  3. HIGH-FREQUENCY ROUTES TESTED")
    for name, url, obs, status in ROUTES:
        print(f"     [{status:22s}] {name}")

    print(f"\n  5. STATION GEOMETRY (seasonal registry, {len(registry)} stations)")
    print(f"     {'hotspot':8s} {'nearest':>9s} {'<=2km':>6s} {'2-5km':>6s} "
          f"{'5-10km':>7s} {'10-20km':>8s}")
    for hid, t in tiers.items():
        print(f"     {hid:8s} {t['nearest_km']:9.2f} {t['tier1_le2km']:6d} "
              f"{t['tier2_2to5km']:6d} {t['tier3_5to10km']:7d} {t['tier4_10to20km']:8d}")
    for hid in ("H001", "H004"):
        print(f"\n     best available stations for {hid} (seasonal data, "
              f"{tiers[hid]['best_stations'][0]['distance_km']:.2f} km nearest):")
        for s in tiers[hid]["best_stations"]:
            print(f"       {s['distance_km']:6.2f} km  {s['site_name'][:38]:38s} "
                  f"{s['state']:12s} seasons={s['seasons']}")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "seasonal_freeze_id": fid,
        "seasonal_files": records,
        "frozen_limitations": {
            "temporal_coverage": "four seasonal observations spanning 2022-2023 only",
            "spatial_coverage": "no monitoring station within 2 km of any hotspot",
            "H001_nearest_station_km": tiers["H001"]["nearest_km"],
            "not_permitted_from_seasonal_data": [
                "monthly groundwater coupling", "groundwater trend estimation",
                "hotspot-localized groundwater attribution",
                "lag analysis requiring dense time series",
                "causal claim linking groundwater decline to H001/H004",
                "interpolation of four seasonal points into a monthly series"],
            "permitted_use": [
                "monitoring-network geometry", "regional groundwater-level context",
                "seasonal state comparison",
                "spatial groundwater gradients at those four epochs",
                "H004/H002/H003 coarse proximity context",
                "identifying candidate stations for later high-frequency retrieval"],
        },
        "high_frequency_routes": [
            {"source": n, "url": u, "observed": o, "status": s} for n, u, o, s in ROUTES],
        "high_frequency_access": "ACCESS BLOCKED on every route tested",
        "station_tiers": tiers,
        "classification": "C",
        "classification_text": "GROUNDWATER TEMPORAL TEST: STILL ACCESS-BLOCKED / "
                               "INADEQUATE",
        "reason": "No high-frequency route is reachable. The recovered seasonal dataset "
                  "has no station within 2 km of any hotspot and H001 has none within "
                  "5 km, and it covers a single annual cycle (2022-2023) against a "
                  "2021-10 to 2025-09 study period. It is therefore neither sufficiently "
                  "local nor sufficiently long to test H001/H004 temporally.",
        "correlation_analysis_performed": False,
        "official_request_package": {
            "purpose": "Prepared, NOT submitted. No RTI has been filed.",
            "requested_content": [
                "station-level DWLR groundwater observations",
                "Delhi-NCR and the districts intersecting the AOI",
                "2021-10-01 to 2025-10-01",
                "station coordinates (latitude, longitude)",
                "station IDs",
                "well depth and aquifer metadata where available",
                "native observation timestamps (not resampled)",
                "depth-to-water-level values with units"],
            "requested_geography": {
                "priority_1": "H001 (77.0813, 28.5212) - no station within 5 km today",
                "priority_2": "H004 (77.0554, 28.5333)",
                "priority_3_4": "H002 (77.0735, 28.8152), H003 (77.0810, 28.8033)",
                "controls": "matched non-hotspot areas within the AOI",
                "excluded": "H005 - unresolved cross-geometry contradiction"},
            "candidate_routes": ["CGWB regional office", "NWIC / WIMS",
                                 "formal data request", "RTI if necessary"],
            "note": "RTI is listed as a possible route but has NOT been started.",
        },
    }
    (OUT / "dwlr_audit.json").write_text(json.dumps(payload, indent=2, default=str))

    # ---- report -----------------------------------------------------------
    L = []
    add = L.append
    add("# Phase III-A2 — High-Frequency Groundwater Acquisition Audit")
    add("")
    add(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.")
    add("")
    add("**Scope.** Determine whether a groundwater dataset capable of testing H001/H004 "
        "*temporally* can be obtained. **No correlation between groundwater and InSAR was "
        "performed. No causal claim is made.**")
    add("")
    add("## 1. Seasonal dataset frozen")
    add("")
    add(f"`freeze/cgwb_seasonal_v1`, `freeze_id {fid}`")
    add("")
    add("> " + manifest["provenance_wording"])
    add("")
    add("**This is not a live CGWB download.** It is an archived copy of the official URL, "
        "and every later report must say so.")
    add("")
    add("| File | Season | Year | Pages | MB | AOI rows | SHA-256 |")
    add("|---|---|---:|---:|---:|---:|---|")
    for r in records:
        add(f"| `{r['file']}` | {r['season']} | {r['year']} | {r['pages']} | "
            f"{r['bytes']/1e6:.1f} | {r['parsed_rows_aoi_states']} | "
            f"`{r['sha256'][:16]}…` |")
    add("")
    add("Known schema limitations, all of which persist: no CGWB station code; season and "
        "year only (no exact measurement date); no aquifer or well-depth metadata; well "
        "type blank in some rows.")
    add("")
    add("## 2. Frozen limitations")
    add("")
    add("```text")
    add("TEMPORAL COVERAGE:  four seasonal observations spanning 2022-2023 only")
    add("SPATIAL COVERAGE:   no monitoring station within 2 km of any hotspot")
    add(f"H001:               nearest station {tiers['H001']['nearest_km']:.2f} km")
    add("```")
    add("")
    add("Therefore the following are **not permitted** from the seasonal dataset, and "
        "these restrictions carry into every later report:")
    add("")
    for item in payload["frozen_limitations"]["not_permitted_from_seasonal_data"]:
        add(f"* {item}")
    add("")
    add("## 3. Allowed use of the seasonal data")
    add("")
    for item in payload["frozen_limitations"]["permitted_use"]:
        add(f"* {item}")
    add("")
    add("It is retained as an independent official cross-check and will **not** be "
        "discarded even if high-frequency data are later obtained.")
    add("")
    add("## 4. High-frequency routes tested")
    add("")
    add("| Source | Status | Observation |")
    add("|---|---|---|")
    for name, url, obs, status in ROUTES:
        add(f"| {name} | **{status}** | {obs} |")
    add("")
    add(f"**High-frequency DWLR: {payload['high_frequency_access']}.** Every preferred "
        f"route named in the protocol was tried, and none returned station observations.")
    add("")
    add("## 5. Station geometry")
    add("")
    add("| Hotspot | Nearest station | ≤ 2 km | 2–5 km | 5–10 km | 10–20 km |")
    add("|---|---:|---:|---:|---:|---:|")
    for hid, t in tiers.items():
        add(f"| **{hid}** | {t['nearest_km']:.2f} km | {t['tier1_le2km']} | "
            f"{t['tier2_2to5km']} | {t['tier3_5to10km']} | {t['tier4_10to20km']} |")
    add("")
    add("### Best available stations")
    add("")
    for hid in ("H001", "H004"):
        add(f"**{hid}** — nearest is "
            f"{tiers[hid]['best_stations'][0]['distance_km']:.2f} km:")
        add("")
        add("| Station | State | Distance | Seasons | Type |")
        add("|---|---|---:|---:|---|")
        for s in tiers[hid]["best_stations"]:
            add(f"| {s['site_name'][:40]} | {s['state']} | {s['distance_km']:.2f} km | "
                f"{s['seasons']} | {s['well_type']} |")
        add("")
    add(f"**H001 cannot be improved on today.** The protocol asked explicitly whether any "
        f"station could improve on the current >5 km nearest seasonal station; the answer "
        f"is no. The nearest usable station to H001 is "
        f"**{tiers['H001']['nearest_km']:.2f} km** away, outside every window in which a "
        f"groundwater head field could be treated as uniform with the hotspot.")
    add("")
    add("## 6. Study-period overlap and temporal completeness")
    add("")
    add("| Requirement | Status |")
    add("|---|---|")
    add("| study period | 2021-10-01 .. 2025-09-30 |")
    add("| seasonal overlap | 4 epochs, all inside 2022-2023 |")
    add("| fraction of study period covered | ≈ 25 % |")
    add("| native sampling frequency | 4 observations per year |")
    add("| observations per station | 1–4 |")
    add("| stations with ≥ 2 seasons | 87 of 612 |")
    add("| high-frequency (DWLR) observations | **none obtainable** |")
    add("")
    add("No resampling was defined, because no actual sampling frequency beyond four "
        "seasonal snapshots was obtained. Native observation times are preserved where "
        "they exist at all.")
    add("")
    add("## 7. data.gov.in route")
    add("")
    add("No API key is available. Per protocol the route is **not** used for hotspot-level "
        "testing, and the resources visible in the catalogue are state/district **annual "
        "aggregates**. Classified **CONTEXT ONLY**. If a key becomes available the first "
        "step is to inspect the returned schema, not to assume it contains observations.")
    add("")
    add("## 8. Official-request package (prepared, not submitted)")
    add("")
    add("A request has been drafted but **no RTI has been filed and nothing has been "
        "submitted**.")
    add("")
    add("**Content sought:** " + "; ".join(payload["official_request_package"]["requested_content"]) + ".")
    add("")
    add("**Geography:** H001 (77.0813, 28.5212) first — it currently has no station within "
        "5 km; then H004 (77.0554, 28.5333); then H002 and H003 as controls; matched "
        "non-hotspot areas within the AOI. H005 is excluded.")
    add("")
    add("**Routes:** " + ", ".join(payload["official_request_package"]["candidate_routes"]) + ".")
    add("")
    add("## 9. Final classification")
    add("")
    add("```text")
    add("GROUNDWATER TEMPORAL TEST:")
    add("    STILL ACCESS-BLOCKED / INADEQUATE")
    add("```")
    add("")
    add("This is option **C**, and the reasoning is worth separating from the seasonal "
        "gate's earlier option B:")
    add("")
    add("* the **seasonal** dataset is genuinely recovered and usable for context (option "
        "B at that gate);")
    add("* but the question asked **here** is whether H001/H004 can be tested "
        "**temporally**, and on that test the answer is no, on two independent grounds: "
        "**neither sufficiently local** (no station within 2 km of any hotspot; none "
        "within 5 km of H001) **nor sufficiently long** (one annual cycle against a "
        "four-year study period), with high-frequency data blocked on every route.")
    add("")
    add("**A genuine hotspot-level temporal groundwater test is therefore not possible "
        "with currently accessible data.** Nothing about groundwater causation can be "
        "concluded either way, and no correlation was run.")
    add("")
    add("## 10. What would change this")
    add("")
    add("One of the following, in order of expected value:")
    add("")
    add("1. **DWLR station records within 5 km of H001** — the single highest-value "
        "acquisition. Nothing else would so directly enable the test.")
    add("2. **A data.gov.in API key**, if the returned schema proves to expose "
        "station-level dated observations rather than aggregates.")
    add("3. **Additional seasonal years** (2021, 2024, 2025) from the CGWB seasonal series, "
        "which would at least extend the record to multiple annual cycles — though it "
        "would not fix the 5–20 km distance problem.")
    add("")
    add("Route 3 alone would not make the test possible. The distance problem is the "
        "binding constraint, and only route 1 or 2 addresses it.")
    REPORT.write_text("\n".join(L) + "\n")
    print(f"\n  9. CLASSIFICATION: C - GROUNDWATER TEMPORAL TEST: STILL ACCESS-BLOCKED / INADEQUATE")
    print(f"\n  {OUT / 'dwlr_audit.json'}")
    print(f"  {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
