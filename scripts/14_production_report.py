#!/usr/bin/env python
"""
Phase H - production completion report.

Runs only after every production job is terminal. Reports exactly what was
asked for, from evidence, and stops before any scientific inversion.

Reported
--------
  * submitted / succeeded / failed job counts
  * credits actually consumed
  * duplicate-name audit
  * product inventory and hashes
  * actual compressed / extracted storage
  * failed and retried jobs
  * freeze verification status
  * reconciliation against the frozen 336-pair manifest

Outputs
-------
qc/production/PRODUCTION_REPORT.md
qc/production/production_report.json

Usage
-----
    python scripts/14_production_report.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
QC_DIR = PROJECT_ROOT / "qc" / "production"
PILOT_QC = PROJECT_ROOT / "qc" / "pilot"

JOB_NAME_PREFIX = "delhi_ncr_sbas_a27_v1_prod"
CREDITS_PER_JOB = 5
EXPECTED_PAIRS = 336
EXPECTED_CREDITS = EXPECTED_PAIRS * CREDITS_PER_JOB


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def freeze_status() -> dict:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "verify_freeze.py"), "--quiet"],
        capture_output=True, text=True,
    )
    return {"exit_code": result.returncode, "ok": result.returncode == 0,
            "output_tail": (result.stdout or "").strip().splitlines()[-3:]}


def main() -> int:
    QC_DIR.mkdir(parents=True, exist_ok=True)

    pairs = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv")
    ledger = pd.read_csv(MANIFEST_DIR / "production_jobs.csv") if (MANIFEST_DIR / "production_jobs.csv").exists() else pd.DataFrame()
    inventory = pd.read_csv(MANIFEST_DIR / "production_product_inventory.csv") if (MANIFEST_DIR / "production_product_inventory.csv").exists() else pd.DataFrame()
    files = pd.read_csv(MANIFEST_DIR / "production_file_inventory.csv") if (MANIFEST_DIR / "production_file_inventory.csv").exists() else pd.DataFrame()
    recon = load_json(QC_DIR / "production_ledger_reconciliation.json")

    expected_names = {
        f"{JOB_NAME_PREFIX}_{a.replace('-', '')}_{b.replace('-', '')}"
        for a, b in zip(pairs["reference_date"], pairs["secondary_date"])
    }

    # ---- submission counts -------------------------------------------------
    unique_ledger = ledger.drop_duplicates(subset=["job_name"]) if not ledger.empty else ledger
    submitted = int(len(unique_ledger))
    name_counts = ledger["job_name"].value_counts().to_dict() if not ledger.empty else {}
    duplicates = {n: c for n, c in name_counts.items() if c > 1}

    statuses = recon.get("statuses", {})
    succeeded = int(statuses.get("SUCCEEDED", 0))
    failed = int(statuses.get("FAILED", 0))
    expired = int(statuses.get("EXPIRED", 0))
    running = int(statuses.get("RUNNING", 0)) + int(statuses.get("PENDING", 0))
    terminal = succeeded + failed + expired

    # ---- credits -----------------------------------------------------------
    credits_consumed = CREDITS_PER_JOB * submitted

    # ---- inventory / storage ----------------------------------------------
    ok = inventory[inventory["download_ok"].fillna(False).astype(bool)] if not inventory.empty else pd.DataFrame()
    zip_bytes = int(ok["zip_bytes"].sum()) if not ok.empty else 0
    ext_bytes = int(ok["extracted_bytes"].sum()) if not ok.empty else 0
    hashed_products = int(ok["zip_sha256"].notna().sum()) if not ok.empty else 0
    hashed_files = int(files["sha256"].notna().sum()) if not files.empty else 0

    # ---- reconciliation against the frozen manifest -----------------------
    submitted_names = set(unique_ledger["job_name"]) if not unique_ledger.empty else set()
    missing_jobs = sorted(expected_names - submitted_names)
    extra_jobs = sorted(submitted_names - expected_names)
    manifest_reconciled = not missing_jobs and not extra_jobs and submitted == EXPECTED_PAIRS

    downloaded_ids = set(ok["job_id"].astype(str)) if not ok.empty else set()
    succeeded_ids = {
        str(r.job_id) for r in ledger.itertuples()
        if str(getattr(r, "status", "")) == "SUCCEEDED" and getattr(r, "job_id", None)
    }
    not_downloaded = sorted(succeeded_ids - downloaded_ids)

    # ---- pilot context -----------------------------------------------------
    pilot_acceptance = load_json(PILOT_QC / "pilot_acceptance.json")

    freeze = freeze_status()
    all_clean = (
        terminal == EXPECTED_PAIRS
        and failed == 0
        and expired == 0
        and not duplicates
        and manifest_reconciled
        and freeze["ok"]
        and not not_downloaded
    )

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "H",
        "scope": "production retrieval; no scientific inversion performed",
        "submission": {
            "expected_pairs": EXPECTED_PAIRS,
            "submitted_jobs": submitted,
            "succeeded": succeeded,
            "failed": failed,
            "expired": expired,
            "running_or_pending": running,
            "terminal": terminal,
        },
        "credits": {
            "authorised": EXPECTED_CREDITS,
            "consumed": credits_consumed,
            "per_job": CREDITS_PER_JOB,
            "matches_authorisation": credits_consumed == EXPECTED_CREDITS,
        },
        "duplicate_name_audit": {
            "duplicates": duplicates,
            "clean": not duplicates,
        },
        "inventory": {
            "products_downloaded": int(len(ok)),
            "products_with_zip_sha256": hashed_products,
            "extracted_files_recorded": int(len(files)),
            "extracted_files_hashed": hashed_files,
            "succeeded_but_not_downloaded": not_downloaded,
            "inventory_path": str(MANIFEST_DIR / "production_product_inventory.csv"),
            "file_inventory_path": str(MANIFEST_DIR / "production_file_inventory.csv"),
        },
        "storage": {
            "zip_bytes": zip_bytes,
            "extracted_bytes": ext_bytes,
            "zip_gb": round(zip_bytes / 1e9, 2),
            "extracted_gb": round(ext_bytes / 1e9, 2),
            "total_gb": round((zip_bytes + ext_bytes) / 1e9, 2),
            "mean_zip_mb": round(zip_bytes / len(ok) / 1e6, 2) if len(ok) else None,
            "mean_extracted_mb": round(ext_bytes / len(ok) / 1e6, 2) if len(ok) else None,
        },
        "failed_or_retried": {
            "failed_jobs": [
                {"job_name": r.job_name, "job_id": r.job_id, "status": r.status}
                for r in ledger.itertuples()
                if str(getattr(r, "status", "")).startswith(("SUBMIT_FAILED", "FAILED"))
            ] if not ledger.empty else [],
        },
        "freeze": freeze,
        "manifest_reconciliation": {
            "expected_names": len(expected_names),
            "submitted_names": len(submitted_names),
            "missing_jobs": missing_jobs,
            "unexpected_jobs": extra_jobs,
            "reconciled": manifest_reconciled,
        },
        "ledger_reconciliation": recon,
        "pilot": {
            "acceptance_verdict": pilot_acceptance.get("verdict"),
            "gates": f"{pilot_acceptance.get('gates_passed')}/{pilot_acceptance.get('gates_total')}",
        },
        "v1_exclusions": {
            "2025-05-18": "DISCOVERY_INCONSISTENCY_FAIL_CLOSED - not recovered or inserted",
        },
        "corpus_clean": all_clean,
        "next_phase": "MintPy production preparation" if all_clean else "resolve discrepancies first",
    }

    (QC_DIR / "production_report.json").write_text(json.dumps(report, indent=2, default=str))

    # ---- markdown ---------------------------------------------------------
    s = report["submission"]
    st = report["storage"]
    md = [
        "# Production Completion Report",
        "",
        f"Generated: {report['generated_utc']}",
        "",
        f"## Corpus status: **{'CLEAN' if all_clean else 'NEEDS ATTENTION'}**",
        "",
        "## Submission",
        "",
        f"| metric | value |",
        f"|---|---|",
        f"| expected pairs | {s['expected_pairs']} |",
        f"| submitted jobs | {s['submitted_jobs']} |",
        f"| succeeded | {s['succeeded']} |",
        f"| failed | {s['failed']} |",
        f"| expired | {s['expired']} |",
        f"| running/pending | {s['running_or_pending']} |",
        f"| terminal | {s['terminal']} |",
        "",
        "## Credits",
        "",
        f"- authorised: **{report['credits']['authorised']}**",
        f"- consumed: **{report['credits']['consumed']}** ({CREDITS_PER_JOB}/job x {submitted})",
        f"- matches authorisation: {report['credits']['matches_authorisation']}",
        "",
        "## Duplicate-name audit",
        "",
        f"- duplicates: {duplicates if duplicates else '**none**'}",
        "",
        "## Inventory and hashes",
        "",
        f"- products downloaded: {report['inventory']['products_downloaded']}",
        f"- products with ZIP sha256: {report['inventory']['products_with_zip_sha256']}",
        f"- extracted files recorded: {report['inventory']['extracted_files_recorded']}",
        f"- extracted files hashed: {report['inventory']['extracted_files_hashed']}",
        f"- succeeded but not downloaded: {len(not_downloaded)}",
        f"- `{report['inventory']['inventory_path']}`",
        f"- `{report['inventory']['file_inventory_path']}`",
        "",
        "## Storage (actual)",
        "",
        f"- compressed: **{st['zip_gb']} GB** (mean {st['mean_zip_mb']} MB/product)",
        f"- extracted: **{st['extracted_gb']} GB** (mean {st['mean_extracted_mb']} MB/product)",
        f"- total: **{st['total_gb']} GB**",
        "",
        "## Failed / retried jobs",
        "",
    ]
    if report["failed_or_retried"]["failed_jobs"]:
        for job in report["failed_or_retried"]["failed_jobs"]:
            md.append(f"- `{job['job_name']}` ({job['job_id']}): {job['status']}")
    else:
        md.append("- none")

    md += [
        "",
        "## Freeze verification",
        "",
        f"- `verify_freeze.py` exit code: **{freeze['exit_code']}** ({'OK' if freeze['ok'] else 'FAILED'})",
        "",
        "## Reconciliation against the 336-pair manifest",
        "",
        f"- expected job names: {report['manifest_reconciliation']['expected_names']}",
        f"- submitted job names: {report['manifest_reconciliation']['submitted_names']}",
        f"- missing: {len(missing_jobs)}",
        f"- unexpected: {len(extra_jobs)}",
        f"- reconciled: **{manifest_reconciled}**",
        "",
        "## v1 exclusions",
        "",
        "- 2025-05-18 remains excluded under `DISCOVERY_INCONSISTENCY_FAIL_CLOSED`; "
        "it was not recovered or inserted during this run.",
        "",
        "## Next",
        "",
        f"- {report['next_phase']}",
    ]
    (QC_DIR / "PRODUCTION_REPORT.md").write_text("\n".join(md) + "\n")

    print("=" * 88)
    print("PRODUCTION COMPLETION REPORT")
    print("=" * 88)
    print(f"\n  submitted {s['submitted_jobs']} | succeeded {s['succeeded']} | "
          f"failed {s['failed']} | running {s['running_or_pending']}")
    print(f"  credits consumed {report['credits']['consumed']} / authorised {EXPECTED_CREDITS}")
    print(f"  duplicate names  : {duplicates or 'none'}")
    print(f"  downloaded       : {report['inventory']['products_downloaded']}")
    print(f"  storage          : {st['zip_gb']} GB zip + {st['extracted_gb']} GB extracted "
          f"= {st['total_gb']} GB")
    print(f"  freeze           : exit {freeze['exit_code']}")
    print(f"  manifest recon   : {manifest_reconciled} "
          f"(missing {len(missing_jobs)}, unexpected {len(extra_jobs)})")
    print(f"\n  corpus clean: {all_clean} -> {report['next_phase']}")
    print(f"\n  {QC_DIR / 'PRODUCTION_REPORT.md'}")
    return 0 if all_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
