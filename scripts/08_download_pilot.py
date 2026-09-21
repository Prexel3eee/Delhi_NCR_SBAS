#!/usr/bin/env python
"""
Phase F/G - pilot retrieval: poll, download immediately, reconcile, inventory.

Behaviour required by the project owner
--------------------------------------
* Poll until **every** pilot job reaches a terminal state.
* Download every successful product **immediately** (HyP3 Basic retains
  products for only 14 days).
* **Preserve both duplicate copies** - duplicates are deliberately not
  collapsed or deleted; they are used as a reproducibility test.
* Reconcile remote HyP3 truth against the **append-only** ledger, writing a
  report rather than rewriting history.

Layout (job_id-keyed, so duplicate names cannot collide)
-------------------------------------------------------
    data/hyp3_zips/<job_name>__<job_id8>/*.zip
    data/hyp3_extracted/<job_name>__<job_id8>/...

Every download is verified (zip CRC), hashed, and inventoried in
`manifests/product_inventory.csv`. Downloads are resumable: a job already
recorded as downloaded is skipped.

Production is not reachable from this script.

Usage
-----
    python scripts/08_download_pilot.py --once        # single pass
    python scripts/08_download_pilot.py --wait        # poll to terminal
    python scripts/08_download_pilot.py --reconcile   # ledger vs remote only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
QC_DIR = PROJECT_ROOT / "qc" / "pilot"
ZIP_DIR = PROJECT_ROOT / "data" / "hyp3_zips"
EXTRACT_DIR = PROJECT_ROOT / "data" / "hyp3_extracted"

JOB_NAME_PREFIX = "delhi_ncr_sbas_a27_v1_pilot"
TERMINAL = {"SUCCEEDED", "FAILED", "EXPIRED"}

#: Layers MintPy and the QC report care about.
KEY_LAYERS = (
    "_unw_phase.tif",
    "_corr.tif",
    "_conncomp.tif",
    "_dem.tif",
    "_lv_theta.tif",
    "_lv_phi.tif",
    "_water_mask.tif",
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


# ---------------------------------------------------------------------------
# Remote truth
# ---------------------------------------------------------------------------


def authenticate():
    import hyp3_sdk as sdk

    return sdk.HyP3()


def fetch_jobs(hyp3) -> list:
    """Every multi-burst job on the account, refreshed.

    NOTE: `Job.succeeded` / `Job.failed` are **methods**, not properties, so
    `if job.succeeded:` is always truthy (a bound method object) and would try to
    download jobs that are still RUNNING. All state checks in this module
    therefore compare `status_code` explicitly.
    """
    jobs = hyp3.find_jobs(job_type="INSAR_ISCE_MULTI_BURST")
    return [j for j in jobs if getattr(j, "name", None) and j.name.startswith(JOB_NAME_PREFIX)]


def refresh(hyp3, jobs: list) -> list:
    import hyp3_sdk as sdk

    try:
        return list(hyp3.refresh(sdk.Batch(jobs)))
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: refresh failed ({exc}); re-listing instead")
        return fetch_jobs(hyp3)


# ---------------------------------------------------------------------------
# Ledger reconciliation (never rewrites the ledger)
# ---------------------------------------------------------------------------


def reconcile_ledger(remote_jobs: list) -> dict:
    """Compare the append-only ledger with remote HyP3 truth.

    Writes a report and leaves `manifests/hyp3_jobs.csv` untouched, because an
    append-only ledger is only trustworthy if reconciliation cannot rewrite it.
    """
    ledger_path = MANIFEST_DIR / "hyp3_jobs.csv"
    ledger = pd.read_csv(ledger_path) if ledger_path.exists() else pd.DataFrame()

    remote = {}
    for j in remote_jobs:
        if not getattr(j, "job_id", None):
            continue
        try:
            cost = j.to_dict().get("credit_cost")
        except Exception:  # noqa: BLE001
            cost = None
        remote[j.job_id] = {"name": j.name, "status": j.status_code, "credit_cost": cost}
    ledger_ids = set(ledger["job_id"].dropna().astype(str)) if not ledger.empty else set()

    remote_ids = set(remote)
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ledger_path": str(ledger_path),
        "ledger_rows": int(len(ledger)),
        "ledger_distinct_job_ids": len(ledger_ids),
        "remote_jobs": len(remote),
        "in_ledger_not_remote": sorted(ledger_ids - remote_ids),
        "in_remote_not_ledger": sorted(remote_ids - ledger_ids),
        "status_by_ledger": {},
        "status_by_remote": {},
        "status_mismatches": [],
        "duplicate_names": {},
        "credit_cost_observed": {},
        "credit_cost_total": 0,
    }

    if not ledger.empty:
        report["status_by_ledger"] = (
            ledger["status"].astype(str).value_counts().to_dict()
        )
        for row in ledger.itertuples():
            jid = str(getattr(row, "job_id", ""))
            if jid in remote and remote[jid]["status"] != str(row.status):
                report["status_mismatches"].append(
                    {
                        "job_id": jid,
                        "job_name": remote[jid]["name"],
                        "ledger_status": str(row.status),
                        "remote_status": remote[jid]["status"],
                    }
                )

    counts: dict[str, int] = {}
    for job in remote_jobs:
        counts[job.status_code] = counts.get(job.status_code, 0) + 1
    report["status_by_remote"] = dict(sorted(counts.items()))

    names: dict[str, int] = {}
    for job in remote_jobs:
        names[job.name] = names.get(job.name, 0) + 1
    report["duplicate_names"] = {n: c for n, c in sorted(names.items()) if c > 1}

    cost_hist: dict[str, int] = {}
    total = 0
    for jid, meta in remote.items():
        cost = meta.get("credit_cost")
        if cost is None:
            continue
        cost_hist[str(cost)] = cost_hist.get(str(cost), 0) + 1
        total += int(cost)
    report["credit_cost_observed"] = dict(sorted(cost_hist.items(), key=lambda kv: int(kv[0])))
    report["credit_cost_total"] = total

    report["ledger_covers_remote"] = not report["in_remote_not_ledger"]
    report["remote_covers_ledger"] = not report["in_ledger_not_remote"]

    QC_DIR.mkdir(parents=True, exist_ok=True)
    (QC_DIR / "ledger_reconciliation.json").write_text(json.dumps(report, indent=2))
    return report


# ---------------------------------------------------------------------------
# Download + extract
# ---------------------------------------------------------------------------


def inventory_path() -> Path:
    return MANIFEST_DIR / "product_inventory.csv"


def load_inventory() -> pd.DataFrame:
    path = inventory_path()
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def already_downloaded() -> set[str]:
    """Job ids already downloaded successfully (resumability)."""
    frame = load_inventory()
    if frame.empty or "job_id" not in frame.columns or "download_ok" not in frame.columns:
        return set()
    ok = frame[frame["download_ok"].fillna(False).astype(bool)]
    return set(ok["job_id"].astype(str))


def download_and_extract(job) -> dict:
    """Download one job's products, verify, extract and measure."""
    key = f"{job.name}__{job.job_id[:8]}"
    zip_path = ZIP_DIR / key
    extract_path = EXTRACT_DIR / key
    zip_path.mkdir(parents=True, exist_ok=True)

    record: dict = {
        "job_id": job.job_id,
        "job_name": job.name,
        "pair_id": job.name.replace(f"{JOB_NAME_PREFIX}_", "").replace("_nomask", ""),
        "apply_water_mask": not job.name.endswith("_nomask"),
        "status": job.status_code,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "download_ok": False,
        "zip_dir": str(zip_path.relative_to(PROJECT_ROOT)),
        "extract_dir": str(extract_path.relative_to(PROJECT_ROOT)),
        "zip_count": 0,
        "zip_bytes": 0,
        "zip_sha256": None,
        "extracted_bytes": 0,
        "extracted_files": 0,
        "layers_present": "",
        "layers_missing": "",
        "error": None,
    }

    try:
        paths = job.download_files(location=zip_path)
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"download failed: {type(exc).__name__}: {exc}"
        return record

    zips = sorted(Path(p) for p in paths if str(p).endswith(".zip"))
    if not zips:
        zips = sorted(zip_path.glob("*.zip"))
    if not zips:
        record["error"] = "no zip returned by download_files"
        return record

    record["zip_count"] = len(zips)
    record["zip_bytes"] = sum(z.stat().st_size for z in zips)
    record["zip_sha256"] = sha256_of(zips[0]) if len(zips) == 1 else ";".join(
        f"{z.name}:{sha256_of(z)[:16]}" for z in zips
    )

    # verify archive integrity before trusting it
    for archive in zips:
        try:
            with zipfile.ZipFile(archive) as zf:
                bad = zf.testzip()
                if bad is not None:
                    record["error"] = f"corrupt member {bad} in {archive.name}"
                    return record
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"zip verify failed for {archive.name}: {exc}"
            return record

    extract_path.mkdir(parents=True, exist_ok=True)
    for archive in zips:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extract_path)

    files = [p for p in extract_path.rglob("*") if p.is_file()]
    record["extracted_files"] = len(files)
    record["extracted_bytes"] = sum(p.stat().st_size for p in files)

    names = {p.name for p in files}
    present = [layer for layer in KEY_LAYERS if any(n.endswith(layer) for n in names)]
    record["layers_present"] = ",".join(present)
    record["layers_missing"] = ",".join(l for l in KEY_LAYERS if l not in present)
    record["download_ok"] = True
    return record


def append_inventory(record: dict) -> None:
    path = inventory_path()
    frame = pd.DataFrame([record])
    if path.exists():
        frame = pd.concat([pd.read_csv(path), frame], ignore_index=True)
    # one row per job_id: replace an earlier failed attempt on success
    if record.get("download_ok"):
        mask = frame["job_id"].astype(str) == str(record["job_id"])
        if mask.sum() > 1:
            keep = frame[~mask]
            frame = pd.concat([keep, pd.DataFrame([record])], ignore_index=True)
    frame.to_csv(path, index=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def report(remote_jobs: list, recon: dict) -> None:
    counts: dict[str, int] = {}
    for job in remote_jobs:
        counts[job.status_code] = counts.get(job.status_code, 0) + 1

    print("\n" + "=" * 88)
    print("REMOTE HYP3 TRUTH")
    print("=" * 88)
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")
    for job in sorted(remote_jobs, key=lambda x: (x.name, x.job_id)):
        note = ""
        if job.status_code == "FAILED":
            note = f"  :: {str(getattr(job, 'failure_reason', ''))[:70]}"
        print(f"    {job.status_code:10s} {job.name}{note}")

    print("\n" + "=" * 88)
    print("LEDGER RECONCILIATION (append-only ledger vs remote truth)")
    print("=" * 88)
    print(f"  ledger rows            : {recon['ledger_rows']}")
    print(f"  ledger distinct job_ids: {recon['ledger_distinct_job_ids']}")
    print(f"  remote jobs            : {recon['remote_jobs']}")
    print(f"  in ledger, not remote  : {len(recon['in_ledger_not_remote'])}")
    print(f"  in remote, not ledger  : {len(recon['in_remote_not_ledger'])}")
    print(f"  status mismatches      : {len(recon['status_mismatches'])}")
    print(f"  duplicate job names    : {len(recon['duplicate_names'])}")
    print(f"  ledger covers remote   : {recon['ledger_covers_remote']}")
    if recon.get("credit_cost_observed"):
        print(f"  credit cost per job    : {recon['credit_cost_observed']}")
        print(f"  credits charged (HyP3) : {recon['credit_cost_total']}")
    print(f"  remote covers ledger   : {recon['remote_covers_ledger']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="single pass")
    parser.add_argument("--wait", action="store_true", help="poll until all terminal")
    parser.add_argument("--reconcile", action="store_true", help="reconciliation only")
    parser.add_argument("--interval", type=int, default=60, help="poll seconds")
    parser.add_argument("--max-wait", type=int, default=10800, help="max poll seconds")
    args = parser.parse_args()

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    QC_DIR.mkdir(parents=True, exist_ok=True)
    ZIP_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print("PHASE F/G - PILOT RETRIEVAL")
    print("=" * 88)

    hyp3 = authenticate()
    jobs = fetch_jobs(hyp3)
    if not jobs:
        print("No pilot jobs found on the account.")
        return 1
    print(f"\nFound {len(jobs)} pilot jobs (prefix {JOB_NAME_PREFIX})")

    recon = reconcile_ledger(jobs)
    report(jobs, recon)
    if args.reconcile:
        print("\nReconciliation written. Ledger left untouched (append-only).")
        return 0

    started = time.time()
    downloaded: set[str] = already_downloaded()
    print(f"\nAlready downloaded: {len(downloaded)} job(s)")
    print(f"Polling (interval {args.interval}s, max {args.max_wait}s)...")

    while True:
        pending = [j for j in jobs if j.status_code not in TERMINAL]
        succeeded = [j for j in jobs if j.status_code == "SUCCEEDED"]

        # download immediately, before waiting for the rest
        for job in succeeded:
            if str(job.job_id) in downloaded:
                continue
            print(f"\n  DOWNLOADING {job.name} ({job.job_id[:8]}) status={job.status_code}")
            record = download_and_extract(job)
            append_inventory(record)
            if record["download_ok"]:
                downloaded.add(str(job.job_id))
                mb = record["zip_bytes"] / 1e6
                ext_mb = record["extracted_bytes"] / 1e6
                print(f"    OK  zip={mb:.1f} MB  extracted={ext_mb:.1f} MB  "
                      f"files={record['extracted_files']}")
                if record["layers_missing"]:
                    print(f"    layers missing: {record['layers_missing']}")
            else:
                print(f"    FAILED: {record['error']}")

        counts: dict[str, int] = {}
        for job in jobs:
            counts[job.status_code] = counts.get(job.status_code, 0) + 1
        elapsed = int(time.time() - started)
        print(f"  [{elapsed:5d}s] {dict(sorted(counts.items()))}  downloaded={len(downloaded)}")

        if not pending:
            print("\nAll jobs reached a terminal state.")
            break

        if not args.wait:
            print("\nNot all jobs are terminal. Re-run with --wait to poll to completion.")
            break

        if elapsed > args.max_wait:
            print(f"\nTimed out after {args.max_wait}s with {len(pending)} job(s) pending.")
            break

        time.sleep(args.interval)
        jobs = refresh(hyp3, jobs)

    recon = reconcile_ledger(jobs)
    report(jobs, recon)

    inv = load_inventory()
    if not inv.empty:
        ok = inv[inv["download_ok"] == True]  # noqa: E712
        print("\n" + "=" * 88)
        print("DOWNLOAD SUMMARY")
        print("=" * 88)
        print(f"  products downloaded : {len(ok)}")
        print(f"  total zip bytes     : {ok['zip_bytes'].sum() / 1e6:.1f} MB")
        print(f"  total extracted     : {ok['extracted_bytes'].sum() / 1e6:.1f} MB")
        print(f"  inventory           : {inventory_path()}")

    failures = [j for j in jobs if j.status_code == "FAILED"]
    pending = [j for j in jobs if j.status_code not in TERMINAL]
    if failures:
        print(f"\n  {len(failures)} FAILED job(s) require investigation.")
    if pending:
        print(f"\n  {len(pending)} job(s) still not terminal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
