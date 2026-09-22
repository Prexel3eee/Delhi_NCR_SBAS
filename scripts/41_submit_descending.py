#!/usr/bin/env python
"""
Phase II, stage 4: submit the DESCENDING HyP3 multi-burst jobs.

Independent validation product. Nothing here reads or writes the ascending
product, its manifests, its ledger, or its credits accounting beyond reading the
shared account balance.

Discipline carried over from the ascending production run
--------------------------------------------------------
  * exact-name reconciliation only - `find_jobs(name=...)` is an EXACT match in
    hyp3_sdk, and a prefix query silently returns nothing (INC-001). Names are
    therefore matched locally against the ledger, never by prefix.
  * submission in bounded batches (25-50) with a per-batch check that the credit
    delta equals 5 x the number of newly submitted jobs.
  * append-only ledger; the plan file records exactly what was submitted.
  * a failed submission is recorded as a row with no job_id rather than dropped.

Usage
-----
    python scripts/41_submit_descending.py                 # dry run (default)
    python scripts/41_submit_descending.py --submit --yes
    python scripts/41_submit_descending.py --status
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests" / "descending"
QC_DIR = PROJECT_ROOT / "qc" / "descending"

JOB_NAME_PREFIX = "delhi_ncr_sbas_d136_v1_val"
LEDGER_PATH = MANIFEST_DIR / "descending_jobs.csv"
PLAN_PATH = MANIFEST_DIR / "descending_submission_plan.json"

LOOKS = "10x2"
APPLY_WATER_MASK = True
CREDITS_PER_JOB = 5
MIN_BATCH, MAX_BATCH = 25, 50


def load_network():
    bursts = pd.read_csv(MANIFEST_DIR / "geographic_reference_bursts.csv")
    pairs = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv")
    inventory = pd.read_csv(MANIFEST_DIR / "burst_inventory_2021_2025.csv")
    if bursts["full_burst_id"].duplicated().any():
        raise SystemExit("FAIL: duplicate burst in descending manifest")
    # A reference date legitimately repeats; the PAIR must be unique.
    if pairs.duplicated(subset=["reference_date", "secondary_date"]).any():
        raise SystemExit("FAIL: duplicate (reference, secondary) pair in descending manifest")
    return bursts, pairs, inventory


def build_payloads(bursts, pairs, inventory):
    burst_order = list(bursts["full_burst_id"])
    scene_of = {(r.full_burst_id, r.date): r.scene_name for r in inventory.itertuples()}
    payloads, problems = [], []

    for row in pairs.itertuples():
        ref, sec, missing = [], [], []
        for bid in burst_order:
            r = scene_of.get((bid, row.reference_date))
            s = scene_of.get((bid, row.secondary_date))
            if not r or not s:
                missing.append(bid)
                continue
            ref.append(r)
            sec.append(s)
        if missing:
            problems.append(f"{row.reference_date}->{row.secondary_date}: missing {missing}")
            continue
        name = (f"{JOB_NAME_PREFIX}_{row.reference_date.replace('-', '')}"
                f"_{row.secondary_date.replace('-', '')}")
        payloads.append({
            "pair_id": f"d136_{row.reference_date.replace('-', '')}"
                       f"_{row.secondary_date.replace('-', '')}",
            "job_name": name,
            "reference": ref, "secondary": sec,
            "reference_date": row.reference_date, "secondary_date": row.secondary_date,
            "temporal_baseline_days": int(row.temporal_baseline_days),
            "perpendicular_baseline_m": float(row.perpendicular_baseline_max_abs_m),
            "burst_count": len(ref),
            "is_added_pair": bool(getattr(row, "is_bridge", False)),
        })

    if problems:
        print("FAIL: pairs cannot be turned into payloads:", file=sys.stderr)
        for problem in problems[:10]:
            print(f"  - {problem}", file=sys.stderr)
        raise SystemExit(1)
    return payloads


def validate_payloads(payloads, bursts, pairs):
    problems = []
    expected = len(pairs)
    if len(payloads) != expected:
        problems.append(f"expected {expected} payloads, built {len(payloads)}")
    names = [p["job_name"] for p in payloads]
    if len(set(names)) != len(names):
        problems.append("duplicate job names generated")
    k = len(bursts)
    for p in payloads:
        if p["burst_count"] != k:
            problems.append(f"{p['pair_id']}: K={p['burst_count']} != {k}")
        if len(p["reference"]) != len(p["secondary"]):
            problems.append(f"{p['pair_id']}: burst list length mismatch")
        if p["reference_date"] >= p["secondary_date"]:
            problems.append(f"{p['pair_id']}: reference not earlier than secondary")
        for r, s in zip(p["reference"], p["secondary"]):
            rp, sp = r.split("_"), s.split("_")
            if rp[1] != sp[1] or rp[2] != sp[2]:
                problems.append(f"{p['pair_id']}: burst identity/sub-swath mismatch")
            if rp[4] != "VV" or sp[4] != "VV":
                problems.append(f"{p['pair_id']}: non-VV granule")
    # 1:1 with the frozen descending manifest
    frozen = {f"{JOB_NAME_PREFIX}_{a.replace('-', '')}_{b.replace('-', '')}"
              for a, b in zip(pairs["reference_date"], pairs["secondary_date"])}
    if set(names) != frozen:
        problems.append("job names do not correspond 1:1 with the descending pair manifest")
    if problems:
        print("FAIL: payload validation:", file=sys.stderr)
        for problem in problems[:15]:
            print(f"  - {problem}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  [PASS] {len(payloads)} payloads validated (K={k}, {LOOKS}, water mask, "
          f"1:1 with the descending pair manifest)")


def existing_by_name(hyp3):
    """Exact-name matching only. Never a prefix query (INC-001)."""
    jobs = hyp3.find_jobs(job_type="INSAR_ISCE_MULTI_BURST")
    out = {}
    for job in jobs:
        name = getattr(job, "name", None)
        if name and name.startswith(JOB_NAME_PREFIX):
            out.setdefault(name, []).append(job)
    return out


def credits_now(hyp3):
    try:
        return hyp3.my_info().get("remaining_credits")
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: could not read credits: {exc}")
        return None


def persist(rows):
    frame = pd.DataFrame(rows)
    if LEDGER_PATH.exists():
        frame = pd.concat([pd.read_csv(LEDGER_PATH), frame], ignore_index=True)
    frame.to_csv(LEDGER_PATH, index=False)
    return LEDGER_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--status", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--batch-size", type=int, default=40)
    args = parser.parse_args()

    bursts, pairs, inventory = load_network()
    payloads = build_payloads(bursts, pairs, inventory)

    print("=" * 88)
    print("PHASE II - DESCENDING HyP3 SUBMISSION")
    print("=" * 88)
    print(f"\n  job prefix : {JOB_NAME_PREFIX}")
    print(f"  pairs      : {len(pairs)}  (added pairs: "
          f"{int(pairs['is_bridge'].sum()) if 'is_bridge' in pairs else 0})")
    print(f"  expected   : {len(payloads)} jobs, {len(payloads) * CREDITS_PER_JOB} credits")
    print(f"  settings   : looks={LOOKS}  apply_water_mask={APPLY_WATER_MASK}")

    if not MIN_BATCH <= args.batch_size <= MAX_BATCH:
        print(f"FAIL: --batch-size must be {MIN_BATCH}-{MAX_BATCH}", file=sys.stderr)
        return 1

    validate_payloads(payloads, bursts, pairs)

    import hyp3_sdk as sdk
    hyp3 = sdk.HyP3()

    # ---- idempotency: what already exists remotely ------------------------
    remote = existing_by_name(hyp3)
    duplicated = {n: len(j) for n, j in remote.items() if len(j) > 1}
    if duplicated:
        print(f"\n  WARNING: duplicate remote job names: {duplicated}")
    done = {n for n, jobs in remote.items()
            if any(j.status_code in ("SUCCEEDED", "RUNNING", "PENDING") for j in jobs)}
    missing = [p for p in payloads if p["job_name"] not in done]
    print(f"\n  remote jobs matching prefix : {len(remote)}")
    print(f"  already active/succeeded    : {len(done)}")
    print(f"  TO SUBMIT                   : {len(missing)}")
    print(f"  EXPECTED CREDITS            : {len(missing) * CREDITS_PER_JOB}")
    print(f"  remaining credits           : {credits_now(hyp3)}")

    plan = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "job_name_prefix": JOB_NAME_PREFIX,
        "flight_direction": "DESCENDING", "relative_orbit": 136, "subswath": "IW1",
        "burst_count": len(bursts),
        "pairs": len(payloads), "to_submit": len(missing),
        "credits_per_job": CREDITS_PER_JOB,
        "expected_credits": len(missing) * CREDITS_PER_JOB,
        "looks": LOOKS, "apply_water_mask": APPLY_WATER_MASK,
        "added_pairs": [p["pair_id"] for p in payloads if p["is_added_pair"]],
    }

    if args.status:
        print("\n  remote status by name:")
        for name in sorted(remote):
            codes = sorted({j.status_code for j in remote[name]})
            print(f"    {name}: {codes}")
        return 0

    if not args.submit:
        PLAN_PATH.write_text(json.dumps(plan, indent=2, default=str))
        print(f"\n  DRY RUN COMPLETE - nothing submitted, no credits spent.")
        print(f"  {PLAN_PATH}")
        return 0

    if not args.yes:
        print("\nFAIL: --submit requires --yes to confirm the credit spend.",
              file=sys.stderr)
        return 1

    print("\n" + "=" * 88)
    print(f"SUBMITTING {len(missing)} JOBS IN BATCHES OF {args.batch_size}")
    print("=" * 88)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    total = 0
    for index, start in enumerate(range(0, len(missing), args.batch_size), start=1):
        batch = missing[start:start + args.batch_size]
        print(f"\n--- batch {index}: {len(batch)} jobs (offset {start}, run {run_id}) ---")
        before = credits_now(hyp3)
        rows = []
        for payload in batch:
            try:
                result = hyp3.submit_insar_isce_multi_burst_job(
                    reference=payload["reference"], secondary=payload["secondary"],
                    name=payload["job_name"], apply_water_mask=APPLY_WATER_MASK,
                    looks=LOOKS)
                for job in result:
                    rows.append({
                        "job_name": job.name, "job_id": job.job_id,
                        "pair_id": payload["pair_id"],
                        "reference_date": payload["reference_date"],
                        "secondary_date": payload["secondary_date"],
                        "temporal_baseline_days": payload["temporal_baseline_days"],
                        "perpendicular_baseline_m": payload["perpendicular_baseline_m"],
                        "burst_count": payload["burst_count"], "is_added_pair":
                            payload["is_added_pair"],
                        "looks": LOOKS, "apply_water_mask": APPLY_WATER_MASK,
                        "status": job.status_code,
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                        "batch_index": index, "run_id": run_id,
                    })
            except Exception as exc:  # noqa: BLE001
                rows.append({"job_name": payload["job_name"], "job_id": None,
                             "pair_id": payload["pair_id"],
                             "reference_date": payload["reference_date"],
                             "secondary_date": payload["secondary_date"],
                             "is_added_pair": payload["is_added_pair"],
                             "looks": LOOKS, "apply_water_mask": APPLY_WATER_MASK,
                             "status": f"SUBMIT_FAILED: {type(exc).__name__}",
                             "submitted_at": datetime.now(timezone.utc).isoformat(),
                             "batch_index": index, "run_id": run_id})
        persist(rows)
        submitted = sum(1 for r in rows if r["job_id"])
        total += submitted
        after = credits_now(hyp3)
        expected_delta = CREDITS_PER_JOB * submitted
        actual_delta = (before - after) if (before is not None and after is not None) else None
        print(f"  submitted {submitted}/{len(batch)}   credits {before} -> {after}   "
              f"delta {actual_delta} (expected {expected_delta})")
        if actual_delta is not None and actual_delta != expected_delta:
            print(f"\nFAIL: credit delta {actual_delta} != expected {expected_delta}. "
                  f"Stopping.", file=sys.stderr)
            return 1
        failures = [r for r in rows if not r["job_id"]]
        if failures:
            print(f"  WARNING: {len(failures)} submission failure(s) recorded in the ledger")

    plan["submitted"] = total
    plan["run_id"] = run_id
    PLAN_PATH.write_text(json.dumps(plan, indent=2, default=str))
    print(f"\n  submitted {total} jobs; ledger {LEDGER_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
