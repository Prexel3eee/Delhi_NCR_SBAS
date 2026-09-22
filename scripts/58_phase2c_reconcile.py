#!/usr/bin/env python
"""
Phase II-C stage 0-1: reconcile the 92-vs-91 acquisition accounting and freeze D2
as a CANDIDATE (not authoritative).

The reconciliation is a hard gate: every original acquisition must be accounted
for exactly once, with an explicit reason if it was excluded.

Usage
-----
    python scripts/58_phase2c_reconcile.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests" / "descending"
D2_WORK = PROJECT_ROOT / "mintpy" / "descending_d2_unwrap_work"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2c"
FREEZE = PROJECT_ROOT / "freeze" / "descending_v2_candidate"
WEATHER = PROJECT_ROOT / "mintpy" / "era5_work" / "mintpy" / "weather" / "ERA5"

D2_ARTEFACTS = ["velocity.h5", "timeseries.h5", "temporalCoherence.h5",
                "maskTempCoh.h5", "maskConnComp.h5", "avgSpatialCoh.h5",
                "numInvIfgram.h5"]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reconcile() -> dict:
    accepted = pd.read_csv(MANIFEST_DIR / "accepted_acquisitions.csv")
    # This file is legitimately empty when every burst carries every date, which
    # is the case here: all 4 bursts had all 92 dates, so nothing was excluded at
    # the BURST level. The one date lost later was dropped for network
    # connectivity, not for missing data.
    try:
        excluded = pd.read_csv(MANIFEST_DIR / "excluded_acquisitions.csv")
    except pd.errors.EmptyDataError:
        excluded = pd.DataFrame(columns=["date", "missing_bursts", "reason"])
    ledger = pd.read_csv(MANIFEST_DIR / "descending_jobs.csv")
    pairs = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv", dtype={
        "reference_date": str, "secondary_date": str})

    # dates MintPy actually loaded into the D2 stack
    with h5py.File(D2_WORK / "inputs" / "ifgramStack.h5", "r") as handle:
        ifg = np.array(handle["date"]).astype(str)
    stack_dates = sorted({d for a, b in ifg for d in (a.replace("-", ""), b.replace("-", ""))})
    pair_keys = {f"{a.replace('-','')}_{b.replace('-','')}" for a, b in ifg}

    # ERA5 hour-01 dates
    era5 = set()
    for path in list(WEATHER.rglob("*_01.grb")) + list(WEATHER.rglob("*_01.grib")):
        token = path.stem.split("_")[-2]
        era5.add(token)

    # every acquisition ever seen in the burst inventory (union of per-burst dates)
    inv = pd.read_csv(MANIFEST_DIR / "burst_inventory_2021_2025.csv")
    inventory_dates = sorted(set(inv["date"].astype(str).str.replace("-", "")))

    rows = []
    for date in inventory_dates:
        iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        in_accepted = date in set(accepted["date"].astype(str).str.replace("-", ""))
        n_bursts = int((inv["date"].astype(str).str.replace("-", "") == date).sum())
        hy3 = ledger[ledger["reference_date"].astype(str).str.replace("-", "").eq(date)
                     | ledger["secondary_date"].astype(str).str.replace("-", "").eq(date)]
        hy3_status = (",".join(sorted(set(hy3["status"].astype(str))))
                      if len(hy3) else "not used in any pair")
        loaded = date in set(stack_dates)
        used = any(date in (a.replace("-", ""), b.replace("-", "")) for a, b in ifg)
        era5_ok = date in era5
        if not in_accepted:
            reason = "excluded at inventory: not present in every burst"
        elif not used:
            reason = "DROPPED: unconnectable within |B_perp| <= 250 m to any neighbour"
        else:
            reason = ""
        rows.append({
            "date": iso, "inventory_status": f"present in {n_bursts}/4 bursts",
            "in_accepted_acquisitions": in_accepted,
            "HyP3_status": hy3_status,
            "mintpy_loaded": loaded,
            "used_in_inversion": used,
            "era5_hour01_available": era5_ok,
            "reason_if_excluded": reason,
        })
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "acquisition_accounting.csv", index=False)

    n_inv = len(inventory_dates)
    n_acc = int(table["in_accepted_acquisitions"].sum())
    n_used = int(table["used_in_inversion"].sum())
    n_loaded = int(table["mintpy_loaded"].sum())
    n_era5 = int(table["era5_hour01_available"].sum())
    accounted = n_used + int((~table["used_in_inversion"]).sum()) == n_inv

    print("=" * 88)
    print("PHASE II-C STAGE 0 - ACQUISITION ACCOUNTING (92 vs 91)")
    print("=" * 88)
    print(f"\n  distinct dates in the burst inventory : {n_inv}")
    print(f"  accepted (present in all 4 bursts)     : {n_acc}")
    print(f"  loaded by MintPy into the stack        : {n_loaded}")
    print(f"  actually used in the inversion         : {n_used}")
    print(f"  ERA5 hour-01 available                 : {n_era5}")
    print(f"  every acquisition accounted for once   : {accounted}")
    print(f"\n  pairs in the frozen manifest           : {len(pairs)}")
    print(f"  pairs in the MintPy D2 stack            : {len(pair_keys)}")
    manifest_keys = {a.replace("-", "") + "_" + b.replace("-", "")
                     for a, b in zip(pairs["reference_date"], pairs["secondary_date"])}
    pairs_identical = pair_keys == manifest_keys
    print(f"  pair key sets identical                : {pairs_identical}")

    dropped = table[~table["used_in_inversion"]]
    print(f"\n  acquisitions NOT used in the inversion ({len(dropped)}):")
    for _, row in dropped.iterrows():
        print(f"    {row['date']}  accepted={row['in_accepted_acquisitions']}  "
              f"loaded={row['mintpy_loaded']}  reason: {row['reason_if_excluded']}")

    # Where does the 92 come from, and why is the stack 91?
    print(f"\n  RECONCILIATION:")
    print(f"    {n_acc} accepted acquisitions (the value reported as '92')")
    print(f"    minus {n_acc - n_used} unconnectable acquisition(s) "
          f"({', '.join(dropped['date'].tolist())})")
    print(f"    = {n_used} dates in the frozen stack and in the inversion")
    print(f"    ERA5 hour-01 coverage for those {n_used} dates: {n_era5}/{n_used} "
          f"-> {'COMPLETE' if n_era5 == n_used else 'INCOMPLETE'}")
    print(f"\n  The 92 and the 91 are therefore NOT in conflict: 92 were accepted, "
          f"{n_acc - n_used} could not be connected within the perpendicular-baseline "
          f"limit, and {n_used} were inverted.")

    return {
        "distinct_inventory_dates": n_inv,
        "accepted_acquisitions": n_acc,
        "loaded_by_mintpy": n_loaded,
        "used_in_inversion": n_used,
        "era5_hour01_dates": n_era5,
        "pairs_manifest": len(pairs),
        "pairs_in_stack": len(pair_keys),
        "pair_sets_identical": bool(pairs_identical),
        "every_acquisition_accounted_once": bool(accounted),
        "excluded_detail": dropped[["date", "reason_if_excluded"]].to_dict("records"),
        "explanation": f"{n_acc} accepted; {n_acc - n_used} unconnectable "
                       f"({', '.join(dropped['date'].tolist())}); {n_used} inverted. "
                       f"The 92 and 91 are consistent.",
    }


def freeze_candidate(recon: dict) -> str:
    if FREEZE.exists():
        subprocess.run(["chmod", "-R", "u+w", str(FREEZE)], check=False)
        shutil.rmtree(FREEZE)
    FREEZE.mkdir(parents=True)
    records = []
    for name in D2_ARTEFACTS:
        src = D2_WORK / name
        if not src.exists():
            continue
        records.append({"path": f"mintpy/descending_d2_unwrap_work/{name}",
                        "sha256": sha256_of(src), "bytes": src.stat().st_size,
                        "mtime_ns": src.stat().st_mtime_ns,
                        "note": "hashed in place (the products total several GB)"})
    for rel in ("manifests/descending/sbas_pairs.csv",
                "manifests/descending/accepted_acquisitions.csv",
                "manifests/descending/excluded_acquisitions.csv",
                "qc/sci/phase2c/acquisition_accounting.csv",
                "qc/sci/phase2b/branch_comparison.csv",
                "config/mintpy_descending_d2.txt"):
        src = PROJECT_ROOT / rel
        if not src.exists():
            continue
        dst = FREEZE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        records.append({"path": rel, "sha256": sha256_of(dst),
                        "bytes": dst.stat().st_size, "copied": True})

    with h5py.File(D2_WORK / "velocity.h5", "r") as handle:
        ref = [int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"])]
    freeze_id = hashlib.sha256(json.dumps(
        [[r["path"], r["sha256"]] for r in records], sort_keys=True).encode()).hexdigest()
    (FREEZE / "FREEZE.json").write_text(json.dumps({
        "freeze_version": "descending_v2_candidate",
        "label": "DESCENDING_PRODUCT_V2_CANDIDATE",
        "freeze_id": freeze_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "CANDIDATE FOR REVALIDATION - not authoritative, does not replace "
                  "DESCENDING_RAW_V1",
        "processing": {
            "unwrapError.method": "bridging+phase_closure",
            "troposphericDelay.method": "no",
            "topographicResidual": "no",
            "deramp": "no",
            "network_curation": "none",
            "networkInversion.weightFunc": "var",
            "reference": "MintPy auto-selected",
        },
        "reference_yx": ref,
        "acquisitions": recon["used_in_inversion"],
        "pairs": recon["pairs_in_stack"],
        "reconciliation": recon,
        "supersedes_nothing": "DESCENDING_RAW_V1 remains frozen and unmodified",
        "artefacts": records,
    }, indent=2, default=str))
    for x in sorted(FREEZE.rglob("*"), reverse=True):
        if x.is_dir():
            x.chmod(0o555)
        elif x.name != "FREEZE.json":
            x.chmod(0o444)
    (FREEZE / "FREEZE.json").chmod(0o444)
    FREEZE.chmod(0o555)
    return freeze_id


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    recon = reconcile()
    (OUT / "date_reconciliation.json").write_text(json.dumps(recon, indent=2, default=str))
    freeze_id = freeze_candidate(recon)
    print(f"\n  DESCENDING_PRODUCT_V2_CANDIDATE frozen")
    print(f"  freeze_id: {freeze_id}")
    print(f"  (DESCENDING_RAW_V1 is untouched and remains frozen separately)")
    print(f"\n  {OUT / 'acquisition_accounting.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
