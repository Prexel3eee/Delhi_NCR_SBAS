#!/usr/bin/env python
"""
Phase F - pilot submission to HyP3 `INSAR_ISCE_MULTI_BURST`.

Scope is deliberately narrow: this script submits **only** the 7 frozen pilot jobs
(35 credits at 10x2). It cannot submit production. Production is gated behind a
separate script, pilot QC and explicit owner approval.

Safety properties
-----------------
* Refuses to run if `scripts/verify_freeze.py` reports drift, so a re-run of
  `03`/`04` cannot silently change what is about to be paid for.
* Reads the pilot definition from the frozen `manifests/pilot_pairs.csv`.
* Resolves every reference/secondary granule from the frozen burst inventory and
  fails closed if any pilot pair is missing a burst granule.
* Deterministic job names, so submission is **idempotent**: a job whose name
  already exists is skipped rather than re-submitted and re-charged.
* `--dry-run` (default) builds and validates every payload with
  `prepare_insar_isce_multi_burst_job`, which needs no credentials at all.
* Persists `manifests/hyp3_jobs.csv` immediately after submission, before any
  watching, so job ids survive an interruption.

Usage
-----
    python scripts/07_submit_pilot.py                 # dry run (no credentials needed)
    python scripts/07_submit_pilot.py --submit --yes  # actually submit (needs auth)
    python scripts/07_submit_pilot.py --status        # poll the submitted batch
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"

JOB_NAME_PREFIX = "delhi_ncr_sbas_a27_v1_pilot"
LOOKS = "10x2"
MAX_PILOT_JOBS = 7  # hard ceiling: the frozen pilot is exactly 7 jobs


def verify_freeze_or_die() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "verify_freeze.py"), "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("FAIL: freeze verification failed - refusing to submit.")
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(1)
    print("freeze verified: v1 intact")


def load_frozen_inputs() -> tuple[pd.DataFrame, list[str]]:
    pilot = pd.read_csv(MANIFEST_DIR / "pilot_pairs.csv")
    frozen = pd.read_csv(MANIFEST_DIR / "geographic_reference_bursts.csv")
    burst_order = sorted(frozen["full_burst_id"].tolist(), key=lambda b: int(b.split("_")[1]))
    return pilot, burst_order


def granule_lookup() -> dict[tuple[str, str], str]:
    inventory = pd.read_csv(MANIFEST_DIR / "burst_inventory_2021_2025.csv")
    return {(row.full_burst_id, row.date): row.scene_name for row in inventory.itertuples()}


def build_payloads(pilot: pd.DataFrame, burst_order: list[str]) -> list[dict]:
    lookup = granule_lookup()
    payloads: list[dict] = []

    for row in pilot.itertuples():
        reference: list[str] = []
        secondary: list[str] = []
        missing: list[str] = []

        for burst_id in burst_order:
            ref_scene = lookup.get((burst_id, row.reference_date))
            sec_scene = lookup.get((burst_id, row.secondary_date))
            if not ref_scene or not sec_scene:
                missing.append(f"{burst_id}@{row.reference_date if not ref_scene else row.secondary_date}")
                continue
            reference.append(ref_scene)
            secondary.append(sec_scene)

        if missing:
            raise SystemExit(
                f"FAIL: pilot pair {row.pair_id} is missing burst granules: {missing}. "
                "Fail closed rather than submitting a heterogeneous job."
            )

        suffix = "" if bool(row.apply_water_mask) else "_nomask"
        payloads.append(
            {
                "pair_id": row.pair_id,
                "job_name": f"{JOB_NAME_PREFIX}_{row.pair_id}{suffix}",
                "reference": reference,
                "secondary": secondary,
                "looks": LOOKS,
                "apply_water_mask": bool(row.apply_water_mask),
                "reference_date": row.reference_date,
                "secondary_date": row.secondary_date,
                "temporal_baseline_days": int(row.temporal_baseline_days),
                "perpendicular_baseline_m": float(row.perpendicular_baseline_max_abs_m),
                "burst_count": len(reference),
                "rationale": row.rationale,
            }
        )
    return payloads


def validate_payloads(payloads: list[dict], burst_order: list[str]) -> None:
    problems: list[str] = []

    if len(payloads) > MAX_PILOT_JOBS:
        problems.append(f"{len(payloads)} jobs exceeds the frozen pilot ceiling of {MAX_PILOT_JOBS}")
    if len(payloads) != MAX_PILOT_JOBS:
        problems.append(f"expected exactly {MAX_PILOT_JOBS} pilot jobs, got {len(payloads)}")

    for payload in payloads:
        if payload["burst_count"] != len(burst_order):
            problems.append(f"{payload['pair_id']}: burst count {payload['burst_count']}")
        if len(payload["reference"]) != len(payload["secondary"]):
            problems.append(f"{payload['pair_id']}: reference/secondary length mismatch")
        if payload["looks"] != LOOKS:
            problems.append(f"{payload['pair_id']}: looks {payload['looks']} != {LOOKS}")
        if payload["reference_date"] >= payload["secondary_date"]:
            problems.append(f"{payload['pair_id']}: reference not earlier than secondary")
        for ref_scene, sec_scene in zip(payload["reference"], payload["secondary"]):
            ref_parts, sec_parts = ref_scene.split("_"), sec_scene.split("_")
            if ref_parts[1] != sec_parts[1]:
                problems.append(f"{payload['pair_id']}: burst identity mismatch {ref_scene} vs {sec_scene}")
            if ref_parts[2] != sec_parts[2]:
                problems.append(f"{payload['pair_id']}: sub-swath mismatch")
            if ref_parts[4] != "VV" or sec_parts[4] != "VV":
                problems.append(f"{payload['pair_id']}: non-VV granule")

    if problems:
        print("FAIL: payload validation:")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)


def prepare_with_sdk(payloads: list[dict]) -> list[dict]:
    """Build the real HyP3 payloads. No credentials required."""
    import hyp3_sdk as sdk

    prepared = []
    for payload in payloads:
        body = sdk.HyP3.prepare_insar_isce_multi_burst_job(
            reference=payload["reference"],
            secondary=payload["secondary"],
            name=payload["job_name"],
            apply_water_mask=payload["apply_water_mask"],
            looks=payload["looks"],
        )
        prepared.append({**payload, "hyp3_payload": body})
    return prepared


def authenticate():
    """Authenticate to HyP3 using whichever credential source is available.

    Resolution order (nothing is ever echoed to stdout):
      1. ``EARTHDATA_TOKEN`` environment variable (Earthdata bearer token)
      2. ``EARTHDATA_USERNAME`` + ``EARTHDATA_PASSWORD`` environment variables
      3. ``~/.netrc`` (hyp3_sdk's default when no credentials are passed)
      4. interactive prompt, only when a TTY is attached

    The recommended local setup is a protected ``~/.netrc``:

        machine urs.earthdata.nasa.gov
            login <username>
            password <password>

        chmod 600 ~/.netrc
    """
    import os

    import hyp3_sdk as sdk

    print("\nAuthenticating to HyP3 (Earthdata Login)...")

    attempts: list[tuple[str, dict]] = []
    if os.environ.get("EARTHDATA_TOKEN"):
        attempts.append(("EARTHDATA_TOKEN", {"token": os.environ["EARTHDATA_TOKEN"]}))
    if os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"):
        attempts.append(
            (
                "EARTHDATA_USERNAME/EARTHDATA_PASSWORD",
                {
                    "username": os.environ["EARTHDATA_USERNAME"],
                    "password": os.environ["EARTHDATA_PASSWORD"],
                },
            )
        )
    attempts.append(("~/.netrc", {}))

    last_error: str | None = None
    for label, kwargs in attempts:
        try:
            hyp3 = sdk.HyP3(**kwargs)
            info = hyp3.my_info()
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            print(f"  [{label}] failed: {last_error}")
            continue
        print(f"  [{label}] authenticated")
        print(f"    user id          : {info.get('user_id')}")
        remaining = info.get("remaining_credits")
        if remaining is not None:
            print(f"    remaining credits: {remaining}")
        return hyp3

    if sys.stdin.isatty():
        try:
            hyp3 = sdk.HyP3(prompt="password")
            info = hyp3.my_info()
            print(f"  [interactive] authenticated; user id {info.get('user_id')}")
            return hyp3
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"

    print("\nFAIL: could not authenticate to HyP3.")
    print(f"  last error: {last_error}")
    print("\nProvide credentials in one of these ways, then re-run:")
    print("  1. ~/.netrc (recommended):")
    print("       machine urs.earthdata.nasa.gov")
    print("           login <earthdata_username>")
    print("           password <earthdata_password>")
    print("       chmod 600 ~/.netrc")
    print("  2. export EARTHDATA_TOKEN=<bearer token>")
    print("  3. export EARTHDATA_USERNAME=... EARTHDATA_PASSWORD=...")
    print("\n  No secret is stored in this repository.")
    raise SystemExit(1)


def find_existing(hyp3) -> dict[str, list]:
    """Map EXACT job name -> matching remote HyP3 jobs.

    Critical detail, learned the hard way: ``HyP3.find_jobs(name=...)`` performs
    an **exact** name match, not a prefix or substring match. Passing the project
    prefix (``delhi_ncr_sbas_a27_v1_pilot``) therefore returns zero jobs even
    when seven jobs with that prefix exist, silently defeating idempotency and
    causing duplicate, credit-consuming resubmission.

    Verified against the live API:
        find_jobs(name='delhi_ncr_sbas_a27_v1_pilot')             -> 0
        find_jobs(name='delhi_ncr_sbas_a27_v1_pilot_20250211_20250223') -> 2

    So we list jobs and match exact names locally. HyP3 permits duplicate job
    names, so this is a best-effort guard; the local ledger is the other half.
    """
    try:
        jobs = hyp3.find_jobs(job_type="INSAR_ISCE_MULTI_BURST")
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: job_type-filtered query failed ({exc}); listing all jobs")
        jobs = hyp3.find_jobs()

    existing: dict[str, list] = {}
    for job in jobs:
        name = getattr(job, "name", None)
        if name and name.startswith(JOB_NAME_PREFIX):
            existing.setdefault(name, []).append(job)
    return existing


def persist(job_rows: list[dict]) -> Path:
    """Append submission rows to the ledger.

    Deliberately append-only: collapsing rows by job name would hide exactly the
    accident that actually happened (a duplicate submission), and the ledger must
    remain an honest audit trail.
    """
    path = MANIFEST_DIR / "hyp3_jobs.csv"
    frame = pd.DataFrame(job_rows)
    if path.exists():
        existing = pd.read_csv(path)
        frame = pd.concat([existing, frame], ignore_index=True)
    frame.to_csv(path, index=False)
    return path


def reconcile(hyp3) -> Path:
    """Rebuild the ledger from remote HyP3 truth (authoritative job list)."""
    existing = find_existing(hyp3)
    rows: list[dict] = []
    for name in sorted(existing):
        for job in existing[name]:
            rows.append(
                {
                    "job_name": name,
                    "job_id": job.job_id,
                    "pair_id": name.replace(f"{JOB_NAME_PREFIX}_", "").replace("_nomask", ""),
                    "looks": "10x2",
                    "apply_water_mask": not name.endswith("_nomask"),
                    "status": job.status_code,
                    "submitted_at": getattr(job, "created", None),
                    "batch": "pilot",
                    "source": "reconciled_from_remote",
                }
            )
    path = MANIFEST_DIR / "hyp3_jobs.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="build/validate only (default)")
    mode.add_argument("--submit", action="store_true", help="actually submit the pilot")
    mode.add_argument("--status", action="store_true", help="poll the submitted pilot batch")
    mode.add_argument("--reconcile", action="store_true", help="rebuild the ledger from remote truth")
    parser.add_argument("--yes", action="store_true", help="confirm the 35-credit pilot spend")
    args = parser.parse_args()

    if args.status:
        return report_status()

    if args.reconcile:
        print("=" * 88)
        print("RECONCILING PILOT LEDGER FROM REMOTE HYP3 STATE")
        print("=" * 88)
        hyp3 = authenticate()
        path = reconcile(hyp3)
        frame = pd.read_csv(path)
        print(f"\n  {len(frame)} job(s) written to {path}")
        print(frame[["job_name", "job_id", "status"]].to_string(index=False))
        duplicates = frame["job_name"].value_counts()
        duplicates = duplicates[duplicates > 1]
        if not duplicates.empty:
            print("\n  WARNING: duplicate job names present on the account:")
            for name, count in duplicates.items():
                print(f"    {name}: {count}")
        return 0

    print("=" * 88)
    print("PHASE F - PILOT SUBMISSION (INSAR_ISCE_MULTI_BURST)")
    print("=" * 88)
    print(f"\njob name prefix : {JOB_NAME_PREFIX}")
    print(f"looks           : {LOOKS} (40 m pixel spacing)")
    print(f"scope           : pilot only - production is not reachable from this script")

    verify_freeze_or_die()

    pilot, burst_order = load_frozen_inputs()
    payloads = build_payloads(pilot, burst_order)
    validate_payloads(payloads, burst_order)

    prepared = prepare_with_sdk(payloads)

    print(f"\n{len(prepared)} pilot jobs prepared and validated:\n")
    for i, item in enumerate(prepared, 1):
        mask = "water_mask=ON " if item["apply_water_mask"] else "water_mask=OFF"
        print(f"  {i}. {item['job_name']}")
        print(f"     {item['reference_date']} -> {item['secondary_date']}  "
              f"t={item['temporal_baseline_days']}d  |B_perp|={item['perpendicular_baseline_m']}m  "
              f"K={item['burst_count']}  {mask}")
        print(f"     {item['rationale']}")
        body = item["hyp3_payload"]
        params = body["job_parameters"]
        assert body["job_type"] == "INSAR_ISCE_MULTI_BURST", body["job_type"]
        assert params["looks"] == LOOKS, params["looks"]
        assert len(params["reference"]) == len(params["secondary"]) == item["burst_count"]
        print(f"     hyp3 job_type={body['job_type']} looks={params['looks']} "
              f"mask={params['apply_water_mask']} "
              f"ref_bursts={len(params['reference'])} sec_bursts={len(params['secondary'])}")

    total_credits = 5 * len(prepared)  # 10x2, K=4 -> 5 credits/job

    plan = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "job_name_prefix": JOB_NAME_PREFIX,
        "looks": LOOKS,
        "job_count": len(prepared),
        "credits_per_job": 5,
        "total_credits": total_credits,
        "jobs": [
            {k: v for k, v in item.items() if k != "hyp3_payload"} for item in prepared
        ],
    }
    plan_path = MANIFEST_DIR / "pilot_submission_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    print(f"\n  plan written: {plan_path}")
    print(f"  total pilot cost: {total_credits} credits "
          f"({100.0 * total_credits / 8000:.3f}% of the 8000/month Basic allocation)")

    if not args.submit:
        print("\n" + "=" * 88)
        print("DRY RUN COMPLETE - nothing submitted, no credits spent.")
        print("=" * 88)
        print("\nTo submit (requires Earthdata credentials):")
        print("  python scripts/07_submit_pilot.py --submit --yes")
        return 0

    if not args.yes:
        print("\nREFUSING: --submit requires --yes to confirm the credit spend.")
        return 2

    hyp3 = authenticate()
    existing = find_existing(hyp3)

    print(f"\nChecking for already-submitted pilot jobs (exact-name match)...")
    print(f"  {len(existing)} distinct pilot job name(s) already on the account")
    for name in sorted(existing):
        statuses = ", ".join(j.status_code for j in existing[name])
        flag = "  <-- DUPLICATE" if len(existing[name]) > 1 else ""
        print(f"    {name}: {statuses}{flag}")

    to_submit = [item for item in prepared if item["job_name"] not in existing]
    skipped = [item["job_name"] for item in prepared if item["job_name"] in existing]
    if skipped:
        print(f"\nIdempotency: skipping {len(skipped)} already-submitted job(s)")
    if not to_submit:
        print("\nAll pilot jobs already exist. Nothing to submit. No credits spent.")
        return 0

    print(f"\nSubmitting {len(to_submit)} job(s)...")
    rows: list[dict] = []
    for item in to_submit:
        try:
            batch = hyp3.submit_insar_isce_multi_burst_job(
                reference=item["reference"],
                secondary=item["secondary"],
                name=item["job_name"],
                apply_water_mask=item["apply_water_mask"],
                looks=item["looks"],
            )
            for job in batch:
                rows.append(
                    {
                        "job_name": job.name,
                        "job_id": job.job_id,
                        "pair_id": item["pair_id"],
                        "reference_date": item["reference_date"],
                        "secondary_date": item["secondary_date"],
                        "burst_count": item["burst_count"],
                        "looks": item["looks"],
                        "apply_water_mask": item["apply_water_mask"],
                        "status": job.status_code,
                        "subscribed": True,
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                        "batch": "pilot",
                        "freeze_id": "cf2bdbfd4fa722dd0df9608afba13bf7cd9361a0897dea14ea70e724c8b1924d",
                    }
                )
                print(f"  submitted {job.name} -> job_id={job.job_id} status={job.status_code}")
            # Persist after every job so an interruption cannot lose ids.
            persist(rows)
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "job_name": item["job_name"],
                    "job_id": None,
                    "pair_id": item["pair_id"],
                    "reference_date": item["reference_date"],
                    "secondary_date": item["secondary_date"],
                    "burst_count": item["burst_count"],
                    "looks": item["looks"],
                    "apply_water_mask": item["apply_water_mask"],
                    "status": f"SUBMIT_FAILED: {type(exc).__name__}: {exc}",
                    "subscribed": False,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "batch": "pilot",
                    "freeze_id": None,
                }
            )
            persist(rows)
            print(f"  FAILED {item['job_name']}: {type(exc).__name__}: {exc}")

    path = persist(rows)
    ok = sum(1 for r in rows if r.get("subscribed"))
    print("\n" + "=" * 88)
    print(f"PILOT SUBMISSION COMPLETE - {ok}/{len(to_submit)} submitted")
    print("=" * 88)
    print(f"\n  job ledger: {path}")
    print("  Production remains BLOCKED pending pilot QC and explicit approval.")
    print("\nNext: python scripts/07_submit_pilot.py --status")
    return 0


def report_status() -> int:
    import hyp3_sdk as sdk

    ledger = MANIFEST_DIR / "hyp3_jobs.csv"
    if not ledger.exists():
        print("No pilot jobs have been submitted yet (manifests/hyp3_jobs.csv absent).")
        return 0

    frame = pd.read_csv(ledger)
    print("=" * 88)
    print("PILOT JOB STATUS (local ledger)")
    print("=" * 88)
    print(frame[["job_name", "job_id", "status", "submitted_at"]].to_string(index=False))

    try:
        import os

        import hyp3_sdk as sdk

        kwargs: dict = {}
        if os.environ.get("EARTHDATA_TOKEN"):
            kwargs = {"token": os.environ["EARTHDATA_TOKEN"]}
        elif os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"):
            kwargs = {
                "username": os.environ["EARTHDATA_USERNAME"],
                "password": os.environ["EARTHDATA_PASSWORD"],
            }
        hyp3 = sdk.HyP3(**kwargs)
        existing = find_existing(hyp3)
        print(f"\nRemote status for prefix {JOB_NAME_PREFIX} (exact-name match):")
        counts: dict[str, int] = {}
        for name in sorted(existing):
            for job in existing[name]:
                counts[job.status_code] = counts.get(job.status_code, 0) + 1
        for status, count in sorted(counts.items()):
            print(f"  {status}: {count}")
        if not counts:
            print("  (no remote multi-burst jobs found for this prefix)")
        duplicates = {n: len(j) for n, j in existing.items() if len(j) > 1}
        if duplicates:
            print("\n  WARNING: duplicate submissions detected:")
            for name, count in duplicates.items():
                print(f"    {name}: {count} jobs")
        try:
            info = hyp3.my_info()
            print(f"\n  remaining credits: {info.get('remaining_credits')}")
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        print(f"\nCould not query HyP3 (local ledger shown above): {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
