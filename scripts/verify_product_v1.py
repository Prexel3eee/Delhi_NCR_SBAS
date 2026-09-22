#!/usr/bin/env python
"""
Verify the frozen v1 deformation product (RAW-336).

Re-derives every hash recorded in `freeze/product_v1/FREEZE.json`, re-computes
the `freeze_id` over the same decision-defining payload, and fails loudly if the
snapshot was altered or if a pinned product changed underneath it.

Pinned products are checked on three axes — SHA-256, byte size and mtime_ns.
A size or mtime change without a hash change is reported as a warning rather
than a failure (it means the file was rewritten with identical content); a hash
change is always a failure.

Exit codes: 0 = valid, 1 = verification failed.

Usage
-----
    python scripts/verify_product_v1.py [--quiet]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DIR = PROJECT_ROOT / "freeze" / "product_v1"
MANIFEST = FREEZE_DIR / "FREEZE.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    def say(*parts):
        if not args.quiet:
            print(*parts)

    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST} not found.", file=sys.stderr)
        return 1

    manifest = json.loads(MANIFEST.read_text())
    failures: list[str] = []
    warnings: list[str] = []

    say("=" * 88)
    say("VERIFY PRODUCT v1 (RAW-336)")
    say("=" * 88)
    say(f"\n  freeze_version : {manifest.get('freeze_version')}")
    say(f"  principal      : {manifest.get('principal_branch')}")
    say(f"  created        : {manifest.get('created_utc')}")

    # ---- pinned products -------------------------------------------------
    say("\n  pinned products:")
    for entry in manifest.get("pinned_products", []):
        path = PROJECT_ROOT / entry["path"]
        if not path.exists():
            failures.append(f"missing pinned product: {entry['path']}")
            say(f"    MISSING  {entry['path']}")
            continue
        digest = sha256_of(path)
        stat = path.stat()
        if digest != entry["sha256"]:
            failures.append(f"hash mismatch: {entry['path']}")
            say(f"    CHANGED  {entry['path']}  {entry['sha256'][:16]} -> {digest[:16]}")
            continue
        if stat.st_size != entry["bytes"]:
            failures.append(f"size mismatch: {entry['path']}")
            say(f"    RESIZED  {entry['path']}  {entry['bytes']} -> {stat.st_size}")
            continue
        if stat.st_mtime_ns != entry["mtime_ns"]:
            warnings.append(f"mtime changed (content identical): {entry['path']}")
            say(f"    ok*      {entry['path']}  (mtime moved, content identical)")
            continue
        say(f"    ok       {entry['path']}")

    # ---- copied artefacts ------------------------------------------------
    say("\n  copied artefacts:")
    for entry in manifest.get("copied_artefacts", []):
        frozen = FREEZE_DIR / entry["path"]
        source = PROJECT_ROOT / entry["path"]
        if not frozen.exists():
            failures.append(f"missing frozen artefact: {entry['path']}")
            say(f"    MISSING  {entry['path']}")
            continue
        digest = sha256_of(frozen)
        if digest != entry["sha256"]:
            failures.append(f"frozen artefact altered: {entry['path']}")
            say(f"    CHANGED  {entry['path']}")
            continue
        if source.exists() and sha256_of(source) != entry["sha256"]:
            warnings.append(f"working tree drifted from freeze: {entry['path']}")
            say(f"    drift    {entry['path']}  (working copy differs; freeze intact)")
            continue
        say(f"    ok       {entry['path']}")

    # ---- freeze id -------------------------------------------------------
    payload = json.dumps({
        "version": manifest["freeze_version"],
        "principal_branch": manifest["principal_branch"],
        "pinned": [[p["path"], p["sha256"]] for p in manifest["pinned_products"]],
        "copied": [[c["path"], c["sha256"]] for c in manifest["copied_artefacts"]],
        "promoted": json.loads(
            (PROJECT_ROOT / "qc" / "sci" / "correction_validation.json").read_text()
        ).get("promoted") if (PROJECT_ROOT / "qc" / "sci" / "correction_validation.json").exists() else None,
        "decision": "RAW-336 frozen; ERA5 and ERA5+DEM tested but not beneficial",
    }, sort_keys=True).encode()
    freeze_id = hashlib.sha256(payload).hexdigest()

    say(f"\n  freeze_id  recorded : {manifest['freeze_id']}")
    say(f"  freeze_id  derived  : {freeze_id}")
    if freeze_id != manifest["freeze_id"]:
        failures.append("freeze_id mismatch")
        say("  -> FREEZE ID MISMATCH")
    else:
        say("  -> freeze_id OK")

    # ---- read-only check -------------------------------------------------
    if FREEZE_DIR.stat().st_mode & 0o222:
        warnings.append("freeze directory is writable")
        say("\n  WARNING: freeze directory is writable")

    # ---- summary ---------------------------------------------------------
    say("\n" + "-" * 88)
    for warning in warnings:
        say(f"  WARN  {warning}")
    for failure in failures:
        say(f"  FAIL  {failure}")
    if failures:
        say(f"\n  RESULT: FAILED ({len(failures)} failure(s), {len(warnings)} warning(s))")
        return 1
    say(f"\n  RESULT: VALID ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
