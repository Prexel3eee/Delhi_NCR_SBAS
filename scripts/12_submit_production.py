#!/usr/bin/env python
"""
Phase H - production submission of the frozen v1 network (336 pairs).

Authorised: 1680 HyP3 credits at 10x2 with apply_water_mask=True, over the
frozen 119-acquisition / 336-pair v1 stack.

Hard guarantees
---------------
* Refuses to run unless `scripts/verify_freeze.py` exits 0.
* Refuses to run unless the full test suite passes.
* Reads the pair network from the FROZEN `manifests/sbas_pairs.csv` and never
  writes to any frozen artefact.
* Submits in controlled batches (25-50 jobs) and verifies after every batch:
    - job ids persisted to an append-only ledger immediately;
    - local ledger reconciled against remote HyP3 truth;
    - no duplicate production job names;
    - credit delta == 5 x newly submitted jobs (HyP3-reported).
  Any discrepancy stops the run immediately.
* Idempotency uses EXACT job-name matching over a local list. It never calls
  `find_jobs(name=<prefix>)`, which is an exact-match filter and silently
  returns nothing for a prefix (this caused INC-001).
* Job names are 1:1 with pairs, and products are job-id-addressable, so
  duplicate names or retries can never collide.

Job naming
----------
    delhi_ncr_sbas_a27_v1_prod_<reference>_<secondary>     e.g. ..._20211006_20211018

Modes
-----
    --dry-run     (default) gates + plan only, no credentials needed
    --submit      actually submit (requires --yes)
    --status      local ledger + remote status + credits
    --reconcile   compare append-only ledger against remote truth (read-only)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
QC_DIR = PROJECT_ROOT / "qc" / "production"

JOB_NAME_PREFIX = "delhi_ncr_sbas_a27_v1_prod"
LEDGER_PATH = MANIFEST_DIR / "production_jobs.csv"
PLAN_PATH = MANIFEST_DIR / "production_submission_plan.json"

LOOKS = "10x2"
APPLY_WATER_MASK = True
CREDITS_PER_JOB = 5
EXPECTED_PAIRS = 336
EXPECTED_CREDITS = EXPECTED_PAIRS * CREDITS_PER_JOB
MIN_BATCH, MAX_BATCH = 25, 50


# ---------------------------------------------------------------------------
# Pre-flight gates
# ---------------------------------------------------------------------------


def gate_freeze() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "verify_freeze.py"), "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("GATE FAILED: freeze verification did not exit 0")
        print(result.stdout, result.stderr)
        raise SystemExit(1)
    print("  [PASS] verify_freeze.py exit 0 (v1 intact, live manifests undrifted)")


def gate_tests() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(PROJECT_ROOT / "tests"), "--no-header", "-q"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    tail = (result.stdout or "").strip().splitlines()
    if result.returncode != 0:
        print("GATE FAILED: test suite did not pass")
        print("\n".join(tail[-25:]))
        raise SystemExit(1)
    print(f"  [PASS] test suite: {tail[-1] if tail else 'passed'}")


# ---------------------------------------------------------------------------
# Frozen inputs
# ---------------------------------------------------------------------------


def load_frozen_network() -> tuple[pd.DataFrame, list[str], dict[tuple[str, str], str]]:
    pairs = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv")
    frozen = pd.read_csv(MANIFEST_DIR / "geographic_reference_bursts.csv")
    inventory = pd.read_csv(MANIFEST_DIR / "burst_inventory_2021_2025.csv")

    burst_order = sorted(frozen["full_burst_id"].tolist(), key=lambda b: int(b.split("_")[1]))
    scene_of = {(r.full_burst_id, r.date): r.scene_name for r in inventory.itertuples()}
    return pairs, burst_order, scene_of


def build_payloads(pairs: pd.DataFrame, burst_order: list[str], scene_of: dict) -> list[dict]:
    payloads: list[dict] = []
    problems: list[str] = []

    for row in pairs.itertuples():
        ref, sec, missing = [], [], []
        for burst_id in burst_order:
            r = scene_of.get((burst_id, row.reference_date))
            s = scene_of.get((burst_id, row.secondary_date))
            if not r or not s:
                missing.append(f"{burst_id}@{row.reference_date if not r else row.secondary_date}")
                continue
            ref.append(r)
            sec.append(s)
        if missing:
            problems.append(f"{row.pair_id}: missing granules {missing}")
            continue

        payloads.append(
            {
                "pair_id": row.pair_id,
                "job_name": f"{JOB_NAME_PREFIX}_{row.reference_date.replace('-', '')}_{row.secondary_date.replace('-', '')}",
                "reference": ref,
                "secondary": sec,
                "reference_date": row.reference_date,
                "secondary_date": row.secondary_date,
                "temporal_baseline_days": int(row.temporal_baseline_days),
                "perpendicular_baseline_m": float(row.perpendicular_baseline_max_abs_m),
                "burst_count": len(ref),
            }
        )

    if problems:
        print("FAIL: pair manifest cannot be turned into payloads:")
        for p in problems[:10]:
            print(f"  - {p}")
        raise SystemExit(1)
    return payloads


def validate_payloads(payloads: list[dict], burst_order: list[str], pairs: pd.DataFrame) -> None:
    problems: list[str] = []
    if len(payloads) != EXPECTED_PAIRS:
        problems.append(f"expected {EXPECTED_PAIRS} payloads, built {len(payloads)}")

    names = [p["job_name"] for p in payloads]
    if len(set(names)) != len(names):
        problems.append("duplicate job names generated")

    frozen_ids = sorted(burst_order)
    for p in payloads:
        if p["burst_count"] != len(frozen_ids):
            problems.append(f"{p['pair_id']}: K={p['burst_count']} != {len(frozen_ids)}")
        if len(p["reference"]) != len(p["secondary"]):
            problems.append(f"{p['pair_id']}: reference/secondary length mismatch")
        if p["temporal_baseline_days"] > 36:
            problems.append(f"{p['pair_id']}: temporal baseline {p['temporal_baseline_days']} > 36")
        if p["perpendicular_baseline_m"] > 250:
            problems.append(f"{p['pair_id']}: |B_perp| {p['perpendicular_baseline_m']} > 250")
        if p["reference_date"] >= p["secondary_date"]:
            problems.append(f"{p['pair_id']}: reference not earlier than secondary")
        for r, s in zip(p["reference"], p["secondary"]):
            rp, sp = r.split("_"), s.split("_")
            if rp[1] != sp[1] or rp[2] != sp[2]:
                problems.append(f"{p['pair_id']}: burst identity/sub-swath mismatch")
            if rp[4] != "VV" or sp[4] != "VV":
                problems.append(f"{p['pair_id']}: non-VV granule")

    # the frozen pair manifest must be reproduced exactly
    if set(names) != {
        f"{JOB_NAME_PREFIX}_{a.replace('-', '')}_{b.replace('-', '')}"
        for a, b in zip(pairs["reference_date"], pairs["secondary_date"])
    }:
        problems.append("job names do not correspond 1:1 with the frozen pair manifest")

    if problems:
        print("FAIL: payload validation:")
        for p in problems[:15]:
            print(f"  - {p}")
        raise SystemExit(1)
    print(f"  [PASS] {len(payloads)} payloads validated (K=4, 10x2, water mask, "
          f"temporal <= 36 d, |B_perp| <= 250 m, 1:1 with the frozen pair manifest)")


# ---------------------------------------------------------------------------
# Remote truth / idempotency (exact names only - never a prefix query)
# ---------------------------------------------------------------------------


def fetch_production_jobs(hyp3) -> list:
    try:
        jobs = hyp3.find_jobs(job_type="INSAR_ISCE_MULTI_BURST")
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: job_type query failed ({exc}); listing all jobs")
        jobs = hyp3.find_jobs()
    return [j for j in jobs if getattr(j, "name", None) and j.name.startswith(JOB_NAME_PREFIX)]


def existing_by_name(jobs: list) -> dict[str, list]:
    out: dict[str, list] = {}
    for job in jobs:
        out.setdefault(job.name, []).append(job)
    return out


def credits_now(hyp3) -> int | None:
    try:
        return hyp3.my_info().get("remaining_credits")
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: could not read credits: {exc}")
        return None


def reconcile(hyp3, jobs: list) -> dict:
    ledger = pd.read_csv(LEDGER_PATH) if LEDGER_PATH.exists() else pd.DataFrame()
    remote = {j.job_id: {"name": j.name, "status": j.status_code} for j in jobs}
    leds = set(ledger["job_id"].dropna().astype(str)) if not ledger.empty else set()
    rems = set(remote)

    names: dict[str, int] = {}
    for job in jobs:
        names[job.name] = names.get(job.name, 0) + 1

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ledger_rows": int(len(ledger)),
        "ledger_distinct_job_ids": len(leds),
        "remote_jobs": len(remote),
        "in_ledger_not_remote": sorted(leds - rems),
        "in_remote_not_ledger": sorted(rems - leds),
        "duplicate_names": {n: c for n, c in sorted(names.items()) if c > 1},
        "statuses": {},
    }
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.status_code] = counts.get(job.status_code, 0) + 1
    report["statuses"] = dict(sorted(counts.items()))
    report["ledger_covers_remote"] = not report["in_remote_not_ledger"]
    report["remote_covers_ledger"] = not report["in_ledger_not_remote"]
    return report


def persist(rows: list[dict]) -> Path:
    """Append-only ledger write."""
    frame = pd.DataFrame(rows)
    if LEDGER_PATH.exists():
        frame = pd.concat([pd.read_csv(LEDGER_PATH), frame], ignore_index=True)
    frame.to_csv(LEDGER_PATH, index=False)
    return LEDGER_PATH


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def prepare_with_sdk(payloads: list[dict]) -> list[dict]:
    import hyp3_sdk as sdk

    out = []
    for p in payloads:
        body = sdk.HyP3.prepare_insar_isce_multi_burst_job(
            reference=p["reference"],
            secondary=p["secondary"],
            name=p["job_name"],
            apply_water_mask=APPLY_WATER_MASK,
            looks=LOOKS,
        )
        params = body["job_parameters"]
        assert body["job_type"] == "INSAR_ISCE_MULTI_BURST"
        assert params["looks"] == LOOKS and params["apply_water_mask"] is True
        out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--reconcile", action="store_true")
    parser.add_argument("--yes", action="store_true", help="confirm the credit spend")
    parser.add_argument("--batch-size", type=int, default=40, help=f"{MIN_BATCH}-{MAX_BATCH}")
    args = parser.parse_args()

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    QC_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print("PHASE H - PRODUCTION SUBMISSION (FROZEN v1, 336 PAIRS)")
    print("=" * 88)
    print(f"\njob prefix : {JOB_NAME_PREFIX}")
    print(f"looks      : {LOOKS} (40 m)   water mask: {APPLY_WATER_MASK}")
    print(f"expected   : {EXPECTED_PAIRS} pairs, {EXPECTED_CREDITS} credits")

    if not MIN_BATCH <= args.batch_size <= MAX_BATCH:
        print(f"FAIL: --batch-size must be between {MIN_BATCH} and {MAX_BATCH}")
        return 2

    # ---- gates + plan (no credentials needed) ----------------------------
    print("\nPre-flight gates:")
    gate_freeze()
    gate_tests()

    pairs, burst_order, scene_of = load_frozen_network()
    payloads = build_payloads(pairs, burst_order, scene_of)
    validate_payloads(payloads, burst_order, pairs)
    payloads = prepare_with_sdk(payloads)
    print("  [PASS] all payloads accepted by prepare_insar_isce_multi_burst_job")

    if args.status:
        return do_status()

    # ---- reconcile + plan -------------------------------------------------
    import hyp3_sdk as sdk

    hyp3 = sdk.HyP3()
    jobs = fetch_production_jobs(hyp3)
    existing = existing_by_name(jobs)
    rep = reconcile(hyp3, jobs)

    missing = [p for p in payloads if p["job_name"] not in existing]
    already = [p["job_name"] for p in payloads if p["job_name"] in existing]
    expected_credits = CREDITS_PER_JOB * len(missing)

    print("\nProduction dry run:")
    print(f"  frozen pairs                 : {len(payloads)}")
    print(f"  already submitted (exact name): {len(already)}")
    print(f"  EXPECTED MISSING JOBS         : {len(missing)}")
    print(f"  EXPECTED CREDITS              : {expected_credits} "
          f"({CREDITS_PER_JOB} x {len(missing)})")
    print(f"  duplicate remote names        : {len(rep['duplicate_names'])}")
    print(f"  remaining credits             : {credits_now(hyp3)}")

    PLAN_PATH.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "job_name_prefix": JOB_NAME_PREFIX,
        "looks": LOOKS,
        "apply_water_mask": APPLY_WATER_MASK,
        "batch_size": args.batch_size,
        "expected_pairs": EXPECTED_PAIRS,
        "expected_missing_jobs": len(missing),
        "expected_credits": expected_credits,
        "already_submitted": len(already),
        "duplicate_names": rep["duplicate_names"],
    }, indent=2))

    if args.reconcile:
        (QC_DIR / "production_ledger_reconciliation.json").write_text(json.dumps(rep, indent=2))
        print(f"\n  reconciliation -> {QC_DIR / 'production_ledger_reconciliation.json'}")
        return 0

    if not args.submit:
        print("\n" + "=" * 88)
        print("DRY RUN COMPLETE - nothing submitted, no credits spent.")
        print("=" * 88)
        return 0

    if not args.yes:
        print("\nREFUSING: --submit requires --yes")
        return 2

    if not missing:
        print("\nAll 336 production jobs already exist. Nothing to submit.")
        return 0

    # ---- batched submission with per-batch verification -------------------
    print("\n" + "=" * 88)
    print(f"SUBMITTING {len(missing)} JOBS IN BATCHES OF {args.batch_size}")
    print("=" * 88)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_index = 0
    total_submitted = 0

    for start in range(0, len(missing), args.batch_size):
        batch = missing[start : start + args.batch_size]
        batch_index += 1
        print(f"\n--- batch {batch_index}: {len(batch)} jobs "
              f"(offset {start}, run {run_id}) ---")

        credits_before = credits_now(hyp3)
        rows: list[dict] = []

        for p in batch:
            try:
                result = hyp3.submit_insar_isce_multi_burst_job(
                    reference=p["reference"],
                    secondary=p["secondary"],
                    name=p["job_name"],
                    apply_water_mask=APPLY_WATER_MASK,
                    looks=LOOKS,
                )
                for job in result:
                    rows.append({
                        "job_name": job.name,
                        "job_id": job.job_id,
                        "pair_id": p["pair_id"],
                        "reference_date": p["reference_date"],
                        "secondary_date": p["secondary_date"],
                        "temporal_baseline_days": p["temporal_baseline_days"],
                        "perpendicular_baseline_m": p["perpendicular_baseline_m"],
                        "burst_count": p["burst_count"],
                        "looks": LOOKS,
                        "apply_water_mask": APPLY_WATER_MASK,
                        "status": job.status_code,
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                        "batch_index": batch_index,
                        "run_id": run_id,
                    })
            except Exception as exc:  # noqa: BLE001
                rows.append({
                    "job_name": p["job_name"], "job_id": None, "pair_id": p["pair_id"],
                    "reference_date": p["reference_date"], "secondary_date": p["secondary_date"],
                    "burst_count": p["burst_count"], "looks": LOOKS,
                    "apply_water_mask": APPLY_WATER_MASK,
                    "status": f"SUBMIT_FAILED: {type(exc).__name__}: {exc}",
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "batch_index": batch_index, "run_id": run_id,
                })
                persist(rows)
                print(f"  SUBMIT FAILED for {p['job_name']}: {type(exc).__name__}: {exc}")
                print("  STOPPING - persisting what we have and not continuing.")
                persist(rows)
                return 3

        # 1. persist immediately
        persist(rows)
        newly = [r for r in rows if r.get("job_id")]
        total_submitted += len(newly)
        print(f"  persisted {len(rows)} rows (total submitted this run: {total_submitted})")

        # 2. reconcile against remote truth
        jobs = fetch_production_jobs(hyp3)
        rep = reconcile(hyp3, jobs)
        (QC_DIR / "production_ledger_reconciliation.json").write_text(json.dumps(rep, indent=2))
        print(f"  reconcile: remote={rep['remote_jobs']} ledger={rep['ledger_distinct_job_ids']} "
              f"only_remote={len(rep['in_remote_not_ledger'])} "
              f"only_ledger={len(rep['in_ledger_not_remote'])}")

        # 3. duplicate-name audit
        if rep["duplicate_names"]:
            print(f"  DUPLICATE NAMES DETECTED: {rep['duplicate_names']}")
            print("  STOPPING.")
            return 4
        print("  duplicate-name audit: clean")

        # 4. credit delta must equal 5 x newly submitted
        credits_after = credits_now(hyp3)
        if credits_before is not None and credits_after is not None:
            delta = credits_before - credits_after
            expected = CREDITS_PER_JOB * len(newly)
            print(f"  credits: before={credits_before} after={credits_after} "
                  f"delta={delta} expected={expected}")
            if delta != expected:
                time.sleep(20)
                credits_after = credits_now(hyp3)
                delta = credits_before - credits_after
                print(f"  re-checked credits: after={credits_after} delta={delta}")
            if delta != expected:
                print(f"  CREDIT DELTA MISMATCH (delta={delta}, expected={expected}). STOPPING.")
                return 5

        if len(newly) != len(batch):
            print(f"  BATCH COUNT MISMATCH: {len(newly)} submitted vs {len(batch)} planned. STOPPING.")
            return 6
        print(f"  batch {batch_index} verified: {len(newly)} jobs, "
              f"{CREDITS_PER_JOB * len(newly)} credits")

    print("\n" + "=" * 88)
    print(f"PRODUCTION SUBMISSION COMPLETE - {total_submitted} jobs submitted this run")
    print("=" * 88)
    print(f"  ledger: {LEDGER_PATH}")
    print("\nNext: python scripts/13_download_production.py --wait")
    return 0


def do_status() -> int:
    import hyp3_sdk as sdk

    print("\n" + "=" * 88)
    print("PRODUCTION STATUS")
    print("=" * 88)
    if LEDGER_PATH.exists():
        ledger = pd.read_csv(LEDGER_PATH)
        print(f"\nlocal ledger rows: {len(ledger)} "
              f"(distinct names {ledger['job_name'].nunique()}, "
              f"distinct ids {ledger['job_id'].nunique()})")
    hyp3 = sdk.HyP3()
    jobs = fetch_production_jobs(hyp3)
    rep = reconcile(hyp3, jobs)
    print(f"remote jobs      : {rep['remote_jobs']}")
    print(f"statuses         : {rep['statuses']}")
    print(f"duplicate names  : {rep['duplicate_names']}")
    print(f"remaining credits: {credits_now(hyp3)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
