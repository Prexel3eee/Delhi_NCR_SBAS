#!/usr/bin/env python
"""
Phase C - burst-stack discovery through time (acquisition x burst matrix).

For every geographic reference burst frozen in Phase B, recover the complete
VV acquisition inventory over the study period, then build the
acquisition x burst matrix.

Critical requirement (brief section 10)
---------------------------------------
Every accepted acquisition date must contain the **same geographic burst
identities**. If a date is missing even one required burst the acquisition is
excluded (fail-closed) - a smaller burst set is never silently substituted for
that date, because HyP3 multi-burst requires matching reference/secondary burst
counts and identities.

Data source
-----------
CMR UMM-JSON in validated windows (see `asf_client.cmr_burst_inventory`), which
recovers granules that a single flat query silently omits. `asf_search` is run
as a cross-check and its failures are recorded, never allowed to alter results.

Outputs
-------
manifests/burst_inventory_2021_2025.csv
manifests/burst_completeness_matrix.csv
manifests/acquisition_burst_matrix.csv
manifests/accepted_acquisitions.csv
manifests/excluded_acquisitions.csv
manifests/acquisition_gaps.csv
manifests/burst_search_log.csv
qc/inventory/inventory_provenance.json

Usage
-----
    python scripts/03_inventory_bursts.py
"""

from __future__ import annotations

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asf_client as ac  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
QC_DIR = PROJECT_ROOT / "qc" / "inventory"

# --- frozen study definition ------------------------------------------------
START = "2021-10-01T00:00:00Z"
END = "2025-10-01T00:00:00Z"

EXPECTED_PATH = 27
EXPECTED_DIRECTION = "ASCENDING"
EXPECTED_POLARIZATION = "VV"
EXPECTED_SUBSWATH = "IW2"

#: Parallel CMR workers. The four burst stacks are independent.
MAX_WORKERS = 4

#: Documented, observed CMR serving anomalies. These are *evidence*, not data:
#: no record is manufactured from them. Each entry records what was actually
#: returned by the API during investigation.
KNOWN_CMR_ANOMALIES = [
    {
        "full_burst_id": "027_056011_IW2",
        "date": "2025-05-18",
        "failure_mode": "CMR reports CMR-Hits=2 for every window containing this "
        "acquisition but serves only the VH granule; the VV granule is counted "
        "in hits yet omitted from the response payload.",
        "observed_vv_granule": "S1_056011_IW2_20250518T125536_VV_6366-BURST",
        "observation_note": "The VV granule name above was returned by a direct "
        "CMR granules.umm_json query during investigation. It was NOT reproducible "
        "afterwards: 15 consecutive single-day retries and 5 different query forms "
        "(fullBurstID, relativeBurstID+orbit, absoluteBurstID, geo_search, "
        "ASFFProduct.stack) all failed to serve it again.",
        "independent_corroboration": [
            "The parent SLC S1A_IW_SLC__1SDV_20250518T125513_20250518T125543_059249_075A3B_6366 "
            "appears in the historic full-scene reconnaissance network (all 120 dates).",
            "A live ASF SLC search for 2025-05-18 / path 27 / ascending returns S1A SLC scenes.",
            "'1SDV' in the SLC name confirms dual-polarization (VV+VH) acquisition.",
            "Neighbouring 12-day dates 2025-05-06 and 2025-05-30 both return "
            "027_056011_IW2 normally.",
        ],
        "resolution": "EXCLUDED_FAIL_CLOSED",
        "recheck_before_production": True,
    }
]

#: Bursts whose inventory failed entirely; populated at runtime.
INVENTORY_ERRORS: list[dict] = []


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def load_frozen_bursts() -> pd.DataFrame:
    path = MANIFEST_DIR / "geographic_reference_bursts.csv"
    if not path.exists():
        raise SystemExit(
            f"FAIL: {path} not found. Run scripts/02_select_reference_bursts.py first."
        )
    frame = pd.read_csv(path)
    required = {"full_burst_id", "relative_burst_id", "subswath", "relative_orbit", "polarization"}
    missing = required - set(frame.columns)
    if missing:
        raise SystemExit(f"FAIL: frozen burst manifest missing columns: {sorted(missing)}")
    if frame["full_burst_id"].duplicated().any():
        raise SystemExit("FAIL: duplicate full_burst_id in frozen manifest")
    return frame


def collect_inventory(full_burst_id: str) -> tuple[str, ac.InventoryResult | None]:
    try:
        result = ac.burst_inventory(
            full_burst_id, START, END, EXPECTED_POLARIZATION, tries=4, cross_check_asf=True
        )
        return full_burst_id, result
    except Exception as exc:  # noqa: BLE001
        INVENTORY_ERRORS.append({"full_burst_id": full_burst_id, "error": f"{type(exc).__name__}: {exc}"})
        logging.error("inventory failed for %s: %s", full_burst_id, exc)
        return full_burst_id, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    QC_DIR.mkdir(parents=True, exist_ok=True)

    frozen = load_frozen_bursts()
    burst_ids = list(frozen["full_burst_id"])
    burst_order = sorted(burst_ids, key=lambda b: int(b.split("_")[1]))

    print("=" * 88)
    print("PHASE C - BURST STACK DISCOVERY (ACQUISITION x BURST MATRIX)")
    print("=" * 88)
    print(f"\nStudy period     : {START[:10]} -> {END[:10]}")
    print(f"Required bursts  : {len(burst_order)} (K={len(burst_order)})")
    for b in burst_order:
        print(f"  - {b}")

    print(f"\nQuerying CMR in validated windows ({MAX_WORKERS} parallel workers)...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = dict(pool.map(collect_inventory, burst_order))

    # ---------------- per-burst provenance ----------------
    search_log: list[dict] = []
    all_records: list[ac.BurstRecord] = []

    for burst_id in burst_order:
        result = results.get(burst_id)
        if result is None:
            continue
        prov = result.provenance
        all_records.extend(result.records)

        cmr = prov.get("cmr", {})
        asf = prov.get("asf_search", {})
        search_log.append(
            {
                "full_burst_id": burst_id,
                "records": prov.get("records"),
                "dates": prov.get("dates"),
                "first_date": prov.get("first"),
                "last_date": prov.get("last"),
                "platforms": ",".join(prov.get("platforms", [])),
                "cmr_windows_total": len(cmr.get("windows", []) or []),
                "cmr_windows_split": sum(
                    1 for w in (cmr.get("windows") or []) if w.get("status") == "split"
                ),
                "cmr_unresolved_windows": len(cmr.get("unresolved_windows", []) or []),
                "cmr_error": cmr.get("error"),
                "asf_records": asf.get("records"),
                "asf_error": asf.get("error"),
                "asf_agree": asf.get("agree"),
                "only_in_cmr": len(asf.get("only_in_cmr", []) or []),
                "only_in_asf": len(asf.get("only_in_asf", []) or []),
            }
        )

        print(
            f"\n  {burst_id}: {prov.get('records')} records, {prov.get('dates')} dates "
            f"({prov.get('first')} -> {prov.get('last')})"
        )
        print(f"    platform(s)          : {prov.get('platforms')}")
        print(f"    CMR windows          : {len(cmr.get('windows') or [])} "
              f"({sum(1 for w in (cmr.get('windows') or []) if w.get('status') == 'split')} split, "
              f"{len(cmr.get('unresolved_windows') or [])} unresolved)")
        print(f"    asf_search cross-check: records={asf.get('records')} agree={asf.get('agree')}")
        if asf.get("error"):
            print(f"      asf_search error   : {str(asf['error'])[:90]}")
        if cmr.get("unresolved_windows"):
            for w in cmr["unresolved_windows"]:
                print(f"      UNRESOLVED window  : {w['start'][:16]} -> {w['end'][:16]} ({w['reason']})")

    if not all_records:
        raise SystemExit("FAIL: no burst records retrieved.")

    df = pd.DataFrame([r.as_row() for r in all_records])

    # ---------------- metadata validation ----------------
    validation_errors: list[str] = []

    paths = set(pd.to_numeric(df["path"], errors="coerce").dropna().astype(int))
    if paths != {EXPECTED_PATH}:
        validation_errors.append(f"Unexpected path values: {sorted(paths)}")

    directions = set(df["direction"].dropna().astype(str))
    if directions != {EXPECTED_DIRECTION}:
        validation_errors.append(f"Unexpected flight directions: {sorted(directions)}")

    polarizations = set(df["polarization"].dropna().astype(str))
    if polarizations != {EXPECTED_POLARIZATION}:
        validation_errors.append(f"Unexpected polarization values: {sorted(polarizations)}")

    subswaths = set(df["subswath"].dropna().astype(str))
    if not subswaths.issubset({EXPECTED_SUBSWATH}):
        validation_errors.append(f"Unexpected subswaths: {sorted(subswaths)}")

    returned_ids = set(df["full_burst_id"].dropna().astype(str))
    missing_ids = set(burst_order) - returned_ids
    unexpected_ids = returned_ids - set(burst_order)
    if missing_ids:
        validation_errors.append(f"Missing complete burst stacks: {sorted(missing_ids)}")
    if unexpected_ids:
        validation_errors.append(f"Unexpected full burst IDs: {sorted(unexpected_ids)}")

    df = df.sort_values(["date", "relative_burst_id"]).reset_index(drop=True)

    duplicate_date_bursts = (
        df.groupby(["date", "full_burst_id"]).size().reset_index(name="count").query("count > 1")
    )

    # ---------------- acquisition x burst matrix ----------------
    matrix = (
        df.assign(present=1)
        .pivot_table(index="date", columns="full_burst_id", values="present", aggfunc="max", fill_value=0)
    )
    for burst_id in burst_order:
        if burst_id not in matrix.columns:
            matrix[burst_id] = 0
    matrix = matrix[burst_order]
    matrix["burst_count"] = matrix[burst_order].sum(axis=1)
    matrix["complete_acquisition"] = matrix["burst_count"] == len(burst_order)

    platforms_by_date = df.groupby("date")["platform"].apply(lambda s: ",".join(sorted(set(s))))
    orbits_by_date = df.groupby("date")["absolute_orbit"].apply(
        lambda s: ",".join(sorted({str(int(v)) for v in s.dropna()}))
    )
    missing_by_date = matrix.apply(
        lambda row: ",".join([b for b in burst_order if row[b] == 0]) or "", axis=1
    )

    matrix["missing_bursts"] = missing_by_date
    matrix["platforms"] = platforms_by_date
    matrix["absolute_orbit"] = orbits_by_date

    matrix = matrix.reset_index().sort_values("date").reset_index(drop=True)

    # ---------------- accepted / excluded ----------------
    accepted = matrix[matrix["complete_acquisition"]].copy()
    excluded = matrix[~matrix["complete_acquisition"]].copy()

    if accepted.empty:
        raise SystemExit("FAIL: no acquisition date contains the full burst set.")

    # Attach the actual granule identities per accepted acquisition.
    granule_map: dict[str, dict[str, str]] = {}
    for record in all_records:
        granule_map.setdefault(record.date_iso, {})[record.full_burst_id] = record.scene_name

    accepted["burst_scene_names_json"] = accepted["date"].map(
        lambda d: json.dumps(granule_map.get(d, {}), sort_keys=True)
    )
    accepted["acquisition_key"] = accepted.apply(
        lambda r: f"{EXPECTED_PATH}|{r['platforms']}|{r['date']}", axis=1
    )

    excluded["exclusion_reason"] = excluded.apply(
        lambda r: "INCOMPLETE_BURST_SET: missing " + r["missing_bursts"], axis=1
    )
    for anomaly in KNOWN_CMR_ANOMALIES:
        mask = (excluded["date"] == anomaly["date"]) & (
            excluded["missing_bursts"].str.contains(anomaly["full_burst_id"], regex=False)
        )
        excluded.loc[mask, "exclusion_reason"] = (
            f"CMR_SERVING_ANOMALY: {anomaly['failure_mode']} "
            f"(documented, recheck before production)"
        )

    # ---------------- temporal gaps ----------------
    def gap_frame(dates: pd.Series) -> pd.DataFrame:
        series = pd.to_datetime(sorted(dates))
        frame = pd.DataFrame({"date": series})
        frame["previous_date"] = frame["date"].shift(1)
        frame["gap_days"] = (frame["date"] - frame["previous_date"]).dt.days
        return frame

    ref_dates = gap_frame(accepted["date"])
    gap_distribution = (
        ref_dates["gap_days"].dropna().astype(int).value_counts().sort_index().to_dict()
    )

    # ---------------- write ----------------
    inventory_path = MANIFEST_DIR / "burst_inventory_2021_2025.csv"
    matrix_path = MANIFEST_DIR / "acquisition_burst_matrix.csv"
    accepted_path = MANIFEST_DIR / "accepted_acquisitions.csv"
    excluded_path = MANIFEST_DIR / "excluded_acquisitions.csv"
    gaps_path = MANIFEST_DIR / "acquisition_gaps.csv"
    log_path = MANIFEST_DIR / "burst_search_log.csv"
    completeness_path = MANIFEST_DIR / "burst_completeness_matrix.csv"

    df.to_csv(inventory_path, index=False)
    matrix.to_csv(matrix_path, index=False)
    accepted[
        [
            "date",
            "acquisition_key",
            "burst_count",
            "platforms",
            "absolute_orbit",
            "missing_bursts",
            "burst_scene_names_json",
        ]
    ].to_csv(accepted_path, index=False)
    if excluded.empty:
        pd.DataFrame(
            columns=["date", "burst_count", "missing_bursts", "exclusion_reason"]
        ).to_csv(excluded_path, index=False)
    else:
        excluded[
            ["date", "burst_count", "missing_bursts", "exclusion_reason"]
        ].to_csv(excluded_path, index=False)
    ref_dates.to_csv(gaps_path, index=False)
    pd.DataFrame(search_log).to_csv(log_path, index=False)
    matrix.drop(columns=["missing_bursts", "platforms", "absolute_orbit"]).to_csv(
        completeness_path, index=False
    )

    provenance = {
        "phase": "C",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "study_period": {"start": START, "end": END},
        "expected": {
            "path": EXPECTED_PATH,
            "direction": EXPECTED_DIRECTION,
            "polarization": EXPECTED_POLARIZATION,
            "subswath": EXPECTED_SUBSWATH,
            "burst_count": len(burst_order),
            "full_burst_ids": burst_order,
        },
        "per_burst": search_log,
        "inventory_errors": INVENTORY_ERRORS,
        "validation_errors": validation_errors,
        "duplicate_date_burst_records": duplicate_date_bursts.to_dict(orient="records"),
        "known_cmr_anomalies": KNOWN_CMR_ANOMALIES,
        "totals": {
            "records": int(len(df)),
            "unique_dates": int(matrix["date"].nunique()),
            "complete_acquisitions": int(len(accepted)),
            "incomplete_acquisitions": int(len(excluded)),
            "platforms": sorted(set(df["platform"].dropna().astype(str))),
        },
    }
    (QC_DIR / "inventory_provenance.json").write_text(json.dumps(provenance, indent=2, default=str))

    # ---------------- report ----------------
    print("\n" + "=" * 88)
    print("BURST INVENTORY SUMMARY")
    print("=" * 88)
    print(f"\nUnique burst records        : {len(df)}")
    print(f"Attributed granules          : {df['full_burst_id'].nunique()} burst stacks")
    print(f"Union of acquisition dates   : {matrix['date'].nunique()}")
    print(f"Complete {len(burst_order)}-burst acquisitions : {len(accepted)}")
    print(f"Incomplete acquisitions      : {len(excluded)}")
    print(f"Platforms                    : {sorted(set(df['platform'].dropna().astype(str)))}")
    print(f"\nFirst complete acquisition   : {accepted['date'].iloc[0]}")
    print(f"Last complete acquisition    : {accepted['date'].iloc[-1]}")
    print(f"\nAccepted-series gap distribution: {gap_distribution}")

    print("\nRecords per burst stack:")
    print(df["full_burst_id"].value_counts().sort_index().to_string())

    if not excluded.empty:
        print("\n" + "-" * 88)
        print("EXCLUDED ACQUISITIONS (fail-closed: burst set not homogeneous)")
        print("-" * 88)
        for row in excluded.itertuples():
            print(f"  {row.date}  missing=[{row.missing_bursts}]  {row.exclusion_reason[:80]}")

    if validation_errors:
        print("\n" + "-" * 88)
        print("METADATA VALIDATION FAILURES")
        print("-" * 88)
        for err in validation_errors:
            print(f"  - {err}")
    else:
        print("\nPASS: metadata validation (path / direction / polarization / sub-swath / burst IDs).")

    if not duplicate_date_bursts.empty:
        print("\nWARNING: duplicate date/burst records detected.")
        print(duplicate_date_bursts.to_string(index=False))

    print("\n" + "=" * 88)
    print("FILES WRITTEN")
    print("=" * 88)
    for path in (
        inventory_path,
        completeness_path,
        matrix_path,
        accepted_path,
        excluded_path,
        gaps_path,
        log_path,
        QC_DIR / "inventory_provenance.json",
    ):
        print(f"  {path}")

    # Fail-closed: an incomplete acquisition is excluded, not substituted, so a
    # non-empty exclusion list is an expected, documented outcome rather than a
    # hard pipeline failure. Metadata violations, however, are fatal.
    if validation_errors or not duplicate_date_bursts.empty:
        print("\nFAIL: resolve metadata violations before building the SBAS network.")
        return 1

    print(f"\nPASS: {len(accepted)} homogeneous {len(burst_order)}-burst acquisitions ready for Phase D.")
    if INVENTORY_ERRORS:
        print(f"WARNING: {len(INVENTORY_ERRORS)} burst stack(s) failed to inventory.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
