#!/usr/bin/env python
"""
Verify the immutable v1 production freeze.

Two independent things are checked:

1. **Snapshot integrity** - every file under ``freeze/v1/`` must still hash to
   the value recorded in ``FREEZE_v1.json``, and the recomputed ``freeze_id``
   must equal the recorded one. This detects tampering or accidental edits to
   the frozen baseline.

2. **Working-tree agreement** - the live ``manifests/``, ``qc/`` and ``config/``
   files must still match the frozen snapshot. This detects the realistic
   accident: someone re-runs ``03``/``04``/``05`` (which rewrite those files) and
   silently changes the network that a paid HyP3 submission would be based on.

Exit codes
----------
0  freeze intact and working tree agrees
1  drift detected - do not submit anything until resolved
2  freeze missing - run scripts/06_freeze_v1.py

Usage
-----
    python scripts/verify_freeze.py
    python scripts/verify_freeze.py --quiet
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DIR = PROJECT_ROOT / "freeze" / "v1"
MANIFEST_PATH = FREEZE_DIR / "FREEZE_v1.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    def say(*parts: object) -> None:
        if not args.quiet:
            print(*parts)

    if not MANIFEST_PATH.exists():
        print(f"FAIL: {MANIFEST_PATH} not found. Run scripts/06_freeze_v1.py first.")
        return 2

    import pandas as pd

    manifest = json.loads(MANIFEST_PATH.read_text())
    recorded_id = manifest["freeze_id"]
    decision = manifest["decision"]
    artefacts = manifest["artefacts"]

    failures: list[str] = []
    warnings: list[str] = []

    say("=" * 88)
    say(f"VERIFYING FREEZE {manifest['freeze_version']}")
    say("=" * 88)
    say(f"\nrecorded freeze_id : {recorded_id}")

    # ---- 1. recompute freeze_id ------------------------------------------
    recomputed_id = hashlib.sha256(canonical_json(decision).encode()).hexdigest()
    say(f"recomputed         : {recomputed_id}")
    if recomputed_id != recorded_id:
        failures.append(
            "freeze_id mismatch: the 'decision' block in FREEZE_v1.json was modified"
        )
    else:
        say("  -> decision block intact")

    # ---- 2. snapshot hashes ----------------------------------------------
    say("\nSnapshot integrity:")
    for entry in artefacts:
        snapshot = PROJECT_ROOT / entry["snapshot"]
        if not snapshot.exists():
            failures.append(f"missing snapshot file: {entry['snapshot']}")
            continue
        actual = sha256_of(snapshot)
        if actual != entry["sha256"]:
            failures.append(
                f"snapshot tampered: {entry['snapshot']} "
                f"(expected {entry['sha256'][:16]}..., got {actual[:16]}...)"
            )
        else:
            say(f"  [OK] {entry['snapshot']}")

    # ---- 3. working tree agreement ---------------------------------------
    say("\nWorking tree vs frozen snapshot:")
    for entry in artefacts:
        live = PROJECT_ROOT / entry["path"]
        if not live.exists():
            message = f"live file missing: {entry['path']}"
            (failures if entry["critical"] else warnings).append(message)
            continue
        actual = sha256_of(live)
        if actual != entry["sha256"]:
            message = f"DRIFT: {entry['path']} differs from the frozen baseline"
            (failures if entry["critical"] else warnings).append(message)
            say(f"  [{'FAIL' if entry['critical'] else 'WARN'}] {message}")
        else:
            say(f"  [OK] {entry['path']}")

    # ---- 4. re-assert the v1 decision ------------------------------------
    say("\nDecision re-assertion:")
    accepted = pd.read_csv(PROJECT_ROOT / "manifests/accepted_acquisitions.csv")
    pairs = pd.read_csv(PROJECT_ROOT / "manifests/sbas_pairs.csv")
    excluded = pd.read_csv(PROJECT_ROOT / "manifests/excluded_acquisitions.csv")
    checks = [
        ("accepted acquisitions", len(accepted), decision["accepted_acquisitions"]),
        ("pairs", len(pairs), decision["pairs"]),
        ("K", int(pairs["burst_count"].iloc[0]), decision["k"]),
        ("excluded dates", sorted(excluded["date"].tolist()), decision["excluded_acquisitions"]),
    ]
    for label, actual, expected in checks:
        if actual != expected:
            failures.append(f"{label}: live={actual} frozen={expected}")
            say(f"  [FAIL] {label}: live={actual} frozen={expected}")
        else:
            say(f"  [OK] {label} = {actual}")

    if not decision["policy"]["recover_2025_05_18"]:
        say("  [OK] policy: 2025-05-18 excluded from v1 and not to be recovered")

    # ---- verdict ---------------------------------------------------------
    say("\n" + "=" * 88)
    if failures:
        say(f"FREEZE VERIFICATION FAILED - {len(failures)} problem(s)")
        for problem in failures:
            say(f"  - {problem}")
        say("=" * 88)
        say("\nDo NOT submit HyP3 jobs against a drifted baseline.")
        return 1

    say(f"FREEZE {manifest['freeze_version']} VERIFIED - freeze_id {recorded_id[:16]}... intact")
    if warnings:
        say(f"\n{len(warnings)} non-critical provenance warning(s):")
        for warning in warnings:
            say(f"  - {warning}")
    say(f"\naccepted={len(accepted)}  pairs={len(pairs)}  K={decision['k']}")
    say("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
