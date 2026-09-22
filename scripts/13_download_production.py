#!/usr/bin/env python
"""
Phase H - production retrieval: poll, download, hash, inventory.

Companion to `12_submit_production.py`. Downloads every successful production
product as soon as it completes (HyP3 Basic retains products for 14 days) and
records a hashed inventory.

Addressability
--------------
Every product is stored under a job-id-suffixed directory:

    data/production_zips/<job_name>__<job_id8>/
    data/production_extracted/<job_name>__<job_id8>/

so duplicate job names or retries can never collide, and any product can be
located from its job id alone.

Outputs
-------
manifests/production_product_inventory.csv   one row per job
manifests/production_file_inventory.csv      one row per extracted file, hashed
qc/production/production_ledger_reconciliation.json

Usage
-----
    python scripts/13_download_production.py --once
    python scripts/13_download_production.py --wait
    python scripts/13_download_production.py --status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
QC_DIR = PROJECT_ROOT / "qc" / "production"
ZIP_DIR = PROJECT_ROOT / "data" / "production_zips"
EXTRACT_DIR = PROJECT_ROOT / "data" / "production_extracted"

JOB_NAME_PREFIX = "delhi_ncr_sbas_a27_v1_prod"
LEDGER_PATH = MANIFEST_DIR / "production_jobs.csv"
INVENTORY_PATH = MANIFEST_DIR / "production_product_inventory.csv"
FILE_INVENTORY_PATH = MANIFEST_DIR / "production_file_inventory.csv"
TERMINAL = {"SUCCEEDED", "FAILED", "EXPIRED"}

#: Layers hashed individually (the rest are recorded by size only).
HASHED_SUFFIXES = (
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


class NetworkUnavailable(RuntimeError):
    """The HyP3 API could not be reached after repeated attempts."""


def connect_hyp3(*, tries: int = 6, base_delay: int = 15):
    """Construct an authenticated HyP3 client, retrying transient outages.

    Authentication itself reaches ASF hosts (urs.earthdata.nasa.gov ->
    cumulus.asf.alaska.edu), so a DNS outage raises *before* any job query runs.
    That is what turned a transient outage into a hard crash on the first
    retrieval attempt.
    """
    import hyp3_sdk as sdk

    last: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            return sdk.HyP3()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < tries:
                delay = min(base_delay * attempt, 120)
                print(f"  connect failed (attempt {attempt}/{tries}): "
                      f"{type(exc).__name__}; retrying in {delay}s")
                time.sleep(delay)
    raise NetworkUnavailable(f"could not authenticate: {type(last).__name__}: {last}")


def fetch_jobs(hyp3, *, tries: int = 6, base_delay: int = 15) -> list:
    """Production multi-burst jobs, with retries for transient network failure.

    Two deliberate choices:

    * State is read from `status_code`. `Job.succeeded` / `Job.failed` are
      METHODS, so they are always truthy when used as attributes.
    * The whole batch is listed with ONE call. `hyp3.refresh(Batch)` issues one
      HTTP request PER JOB (336 requests per poll cycle here), which is both
      slow and turns any transient DNS/network blip into a fatal error. A real
      outage of that shape killed the first retrieval run part-way through.
    """
    last: Exception | None = None
    for attempt in range(1, tries + 1):
        for kwargs in ({"job_type": "INSAR_ISCE_MULTI_BURST"}, {}):
            try:
                jobs = hyp3.find_jobs(**kwargs)
                return [j for j in jobs
                        if getattr(j, "name", None) and j.name.startswith(JOB_NAME_PREFIX)]
            except Exception as exc:  # noqa: BLE001
                last = exc
        if attempt < tries:
            delay = min(base_delay * attempt, 120)
            print(f"  network error (attempt {attempt}/{tries}): "
                  f"{type(last).__name__}; retrying in {delay}s")
            time.sleep(delay)
    raise NetworkUnavailable(f"{type(last).__name__}: {last}")


def reconcile(hyp3, jobs: list) -> dict:
    ledger = pd.read_csv(LEDGER_PATH) if LEDGER_PATH.exists() else pd.DataFrame()
    remote = {j.job_id: {"name": j.name, "status": j.status_code} for j in jobs}
    leds = set(ledger["job_id"].dropna().astype(str)) if not ledger.empty else set()
    rems = set(remote)
    names: dict[str, int] = {}
    for job in jobs:
        names[job.name] = names.get(job.name, 0) + 1
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.status_code] = counts.get(job.status_code, 0) + 1

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ledger_rows": int(len(ledger)),
        "ledger_distinct_job_ids": len(leds),
        "ledger_distinct_names": int(ledger["job_name"].nunique()) if not ledger.empty else 0,
        "remote_jobs": len(remote),
        "in_ledger_not_remote": sorted(leds - rems),
        "in_remote_not_ledger": sorted(rems - leds),
        "duplicate_names": {n: c for n, c in sorted(names.items()) if c > 1},
        "statuses": dict(sorted(counts.items())),
        "ledger_covers_remote": not (rems - leds),
        "remote_covers_ledger": not (leds - rems),
    }
    QC_DIR.mkdir(parents=True, exist_ok=True)
    (QC_DIR / "production_ledger_reconciliation.json").write_text(json.dumps(report, indent=2))
    return report


def load_inventory() -> pd.DataFrame:
    return pd.read_csv(INVENTORY_PATH) if INVENTORY_PATH.exists() else pd.DataFrame()


def downloaded_ids() -> set[str]:
    frame = load_inventory()
    if frame.empty or "download_ok" not in frame.columns:
        return set()
    return set(frame[frame["download_ok"].fillna(False).astype(bool)]["job_id"].astype(str))


def append_inventory(record: dict) -> None:
    frame = pd.DataFrame([record])
    if INVENTORY_PATH.exists():
        frame = pd.concat([pd.read_csv(INVENTORY_PATH), frame], ignore_index=True)
    if record.get("download_ok"):
        mask = frame["job_id"].astype(str) == str(record["job_id"])
        if mask.sum() > 1:
            frame = pd.concat([frame[~mask], pd.DataFrame([record])], ignore_index=True)
    frame.to_csv(INVENTORY_PATH, index=False)


def download_and_extract(job) -> tuple[dict, list[dict]]:
    key = f"{job.name}__{job.job_id[:8]}"
    zip_path = ZIP_DIR / key
    extract_path = EXTRACT_DIR / key
    zip_path.mkdir(parents=True, exist_ok=True)

    record: dict = {
        "job_id": job.job_id, "job_name": job.name,
        "pair_id": job.name.replace(f"{JOB_NAME_PREFIX}_", ""),
        "status": job.status_code,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "download_ok": False,
        "zip_dir": str(zip_path.relative_to(PROJECT_ROOT)),
        "extract_dir": str(extract_path.relative_to(PROJECT_ROOT)),
        "zip_count": 0, "zip_bytes": 0, "zip_sha256": None,
        "extracted_bytes": 0, "extracted_files": 0,
        "layers_present": "", "layers_missing": "", "error": None,
    }
    file_rows: list[dict] = []

    try:
        paths = job.download_files(location=zip_path)
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"download failed: {type(exc).__name__}: {exc}"
        return record, file_rows

    zips = sorted(Path(p) for p in paths if str(p).endswith(".zip")) or sorted(zip_path.glob("*.zip"))
    if not zips:
        record["error"] = "no zip returned"
        return record, file_rows

    record["zip_count"] = len(zips)
    record["zip_bytes"] = sum(z.stat().st_size for z in zips)
    record["zip_sha256"] = sha256_of(zips[0]) if len(zips) == 1 else ";".join(
        f"{z.name}:{sha256_of(z)}" for z in zips
    )

    for archive in zips:
        try:
            with zipfile.ZipFile(archive) as zf:
                bad = zf.testzip()
                if bad is not None:
                    record["error"] = f"corrupt member {bad}"
                    return record, file_rows
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"zip verify failed: {exc}"
            return record, file_rows

    extract_path.mkdir(parents=True, exist_ok=True)
    for archive in zips:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extract_path)

    files = sorted(p for p in extract_path.rglob("*") if p.is_file())
    record["extracted_files"] = len(files)
    record["extracted_bytes"] = sum(p.stat().st_size for p in files)

    names = {p.name for p in files}
    present = [s for s in HASHED_SUFFIXES if any(n.endswith(s) for n in names)]
    record["layers_present"] = ",".join(s.strip("_") for s in present)
    record["layers_missing"] = ",".join(
        s.strip("_") for s in HASHED_SUFFIXES
        if s not in present and not (s == "_water_mask.tif")
    )

    for path in files:
        row = {
            "job_id": job.job_id,
            "job_name": job.name,
            "file": str(path.relative_to(extract_path)),
            "bytes": path.stat().st_size,
            "sha256": None,
        }
        if any(path.name.endswith(s) for s in HASHED_SUFFIXES):
            row["sha256"] = sha256_of(path)
        file_rows.append(row)

    record["download_ok"] = True
    return record, file_rows


def append_file_inventory(rows: list[dict]) -> None:
    if not rows:
        return
    frame = pd.DataFrame(rows)
    if FILE_INVENTORY_PATH.exists():
        existing = pd.read_csv(FILE_INVENTORY_PATH)
        existing = existing[~existing["job_id"].astype(str).isin(frame["job_id"].astype(str))]
        frame = pd.concat([existing, frame], ignore_index=True)
    frame.to_csv(FILE_INVENTORY_PATH, index=False)


def reproject_storage() -> dict:
    """Project full production storage from what has actually been downloaded."""
    inv = load_inventory()
    ok = inv[inv["download_ok"].fillna(False).astype(bool)] if not inv.empty else pd.DataFrame()
    if ok.empty:
        return {}
    zip_total = int(ok["zip_bytes"].sum())
    ext_total = int(ok["extracted_bytes"].sum())
    return {
        "products_downloaded": int(len(ok)),
        "zip_bytes_total": zip_total,
        "extracted_bytes_total": ext_total,
        "zip_gb_total": round(zip_total / 1e9, 2),
        "extracted_gb_total": round(ext_total / 1e9, 2),
        "mean_zip_mb": round(zip_total / len(ok) / 1e6, 2),
        "mean_extracted_mb": round(ext_total / len(ok) / 1e6, 2),
        "mean_extracted_to_zip_ratio": round(ext_total / zip_total, 4) if zip_total else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--interval", type=int, default=180)
    parser.add_argument("--max-wait", type=int, default=86400)
    parser.add_argument("--max-outages", type=int, default=40,
                        help="consecutive unreachable polls before giving up")
    args = parser.parse_args()

    for d in (MANIFEST_DIR, QC_DIR, ZIP_DIR, EXTRACT_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print("PHASE H - PRODUCTION RETRIEVAL")
    print("=" * 88)

    # Wait for connectivity rather than failing fast. The retrieval is fully
    # resumable, so the correct behaviour during an ASF outage is to hold and
    # pick up automatically when the API returns.
    outage_count = 0
    hyp3 = None
    jobs: list = []
    while True:
        try:
            hyp3 = connect_hyp3(tries=2, base_delay=10)
            jobs = fetch_jobs(hyp3, tries=2)
            break
        except NetworkUnavailable as exc:
            outage_count += 1
            print(f"  OUTAGE {outage_count}/{args.max_outages}: {exc}")
            if outage_count >= args.max_outages:
                print("\nGiving up: ASF still unreachable. Progress is saved; re-run to resume.")
                return 1
            time.sleep(args.interval)

    print(f"\nproduction jobs on account: {len(jobs)}")

    rep = reconcile(hyp3, jobs)
    print(f"statuses      : {rep['statuses']}")
    print(f"reconcile     : remote={rep['remote_jobs']} ledger={rep['ledger_distinct_job_ids']} "
          f"only_remote={len(rep['in_remote_not_ledger'])} only_ledger={len(rep['in_ledger_not_remote'])}")
    print(f"duplicate names: {rep['duplicate_names'] or 'none'}")

    if args.status:
        inv = load_inventory()
        ok = inv[inv["download_ok"].fillna(False).astype(bool)] if not inv.empty else pd.DataFrame()
        print(f"downloaded products: {len(ok)}/{len(jobs)}")
        print(json.dumps(reproject_storage(), indent=2))
        return 0

    if not jobs:
        print("No production jobs found.")
        return 1

    started = time.time()
    done = downloaded_ids()
    print(f"already downloaded: {len(done)}")

    # A transient outage must not end the run: the retrieval is resumable, so we
    # back off and keep trying. Only a long unbroken outage gives up.
    consecutive_outages = 0
    MAX_CONSECUTIVE_OUTAGES = args.max_outages

    while True:
        succeeded = [j for j in jobs if j.status_code == "SUCCEEDED"]
        for job in succeeded:
            if str(job.job_id) in done:
                continue
            record, file_rows = download_and_extract(job)
            append_inventory(record)
            append_file_inventory(file_rows)
            if record["download_ok"]:
                done.add(str(job.job_id))
                print(f"  OK  {job.name}  zip={record['zip_bytes']/1e6:.1f} MB "
                      f"extracted={record['extracted_bytes']/1e6:.1f} MB "
                      f"files={record['extracted_files']}  (total {len(done)})")
            else:
                print(f"  FAILED {job.name}: {record['error']}")

        pending = [j for j in jobs if j.status_code not in TERMINAL]
        elapsed = int(time.time() - started)
        print(f"  [{elapsed:6d}s] {rep['statuses']} downloaded={len(done)}/{len(jobs)}")

        if not pending:
            print("\nAll production jobs reached a terminal state.")
            break
        if not args.wait:
            break
        if elapsed > args.max_wait:
            print(f"\nTimed out with {len(pending)} pending.")
            break
        time.sleep(args.interval)
        try:
            jobs = fetch_jobs(hyp3)
            rep = reconcile(hyp3, jobs)
            consecutive_outages = 0
        except NetworkUnavailable as exc:
            consecutive_outages += 1
            print(f"  OUTAGE {consecutive_outages}/{MAX_CONSECUTIVE_OUTAGES}: {exc}")
            if consecutive_outages >= MAX_CONSECUTIVE_OUTAGES:
                print("\nGiving up after repeated outages. Progress is saved; re-run to resume.")
                break
            # the session may have died too; rebuild it before the next cycle
            try:
                hyp3 = connect_hyp3(tries=2)
                jobs = fetch_jobs(hyp3, tries=2)
                rep = reconcile(hyp3, jobs)
                consecutive_outages = 0
            except NetworkUnavailable:
                pass

    rep = reconcile(hyp3, jobs)
    inv = load_inventory()
    ok = inv[inv["download_ok"].fillna(False).astype(bool)] if not inv.empty else pd.DataFrame()
    print("\n" + "=" * 88)
    print("RETRIEVAL SUMMARY")
    print("=" * 88)
    print(f"  remote statuses   : {rep['statuses']}")
    print(f"  downloaded        : {len(ok)}/{len(jobs)}")
    print(f"  storage           : {json.dumps(reproject_storage(), indent=2)}")
    print(f"  inventory         : {INVENTORY_PATH}")
    print(f"  file inventory    : {FILE_INVENTORY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
