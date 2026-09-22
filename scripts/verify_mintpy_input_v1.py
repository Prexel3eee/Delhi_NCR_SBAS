#!/usr/bin/env python
"""
Verify the `mintpy_input_v1` freeze.

Checks, in order:

1. schema - `FREEZE.json` is present and its `decision` block hashes to the
   recorded `freeze_id`;
2. large-file integrity - every hash-pinned HDF5 still hashes as recorded
   (this is a full re-read of ~19.7 GB, so expect it to take a minute);
3. network identity - the network currently in `ifgramStack.h5` still matches
   the frozen fingerprint, and nothing has been flagged `dropIfgram`;
4. small-file integrity - copied config files are untouched;
5. corpus immutability - the authoritative HyP3 corpus inventories are unchanged.

Exit 0 only if all pass.

Usage
-----
    python scripts/verify_mintpy_input_v1.py
    python scripts/verify_mintpy_input_v1.py --skip-large   # fast schema/network check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DIR = PROJECT_ROOT / "freeze" / "mintpy_input_v1"
MANIFEST_PATH = FREEZE_DIR / "FREEZE.json"


def sha256_of(path: Path, *, chunk: int = 1 << 22) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-large", action="store_true", help="skip the ~20 GB re-hash")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"FAIL: {MANIFEST_PATH} not found. Run scripts/15_freeze_mintpy_input.py.")
        return 2

    manifest = json.loads(MANIFEST_PATH.read_text())
    decision = manifest["decision"]
    failures: list[str] = []

    print("=" * 88)
    print(f"VERIFYING {manifest['freeze_version']}")
    print("=" * 88)
    print(f"\nrecorded freeze_id : {manifest['freeze_id']}")

    # ---- 1. freeze_id ----------------------------------------------------
    recomputed = hashlib.sha256(canonical(decision).encode()).hexdigest()
    if recomputed != manifest["freeze_id"]:
        failures.append("freeze_id mismatch: the decision block was modified")
    print(f"recomputed         : {recomputed}  {'OK' if recomputed == manifest['freeze_id'] else 'MISMATCH'}")

    # ---- 2. large file hashes -------------------------------------------
    print("\nLarge-file integrity:")
    for entry in manifest["files"]:
        if "hash-pinned" not in entry.get("frozen_as", ""):
            continue
        path = PROJECT_ROOT / entry["path"]
        if not path.exists():
            failures.append(f"missing: {entry['path']}")
            continue
        if args.skip_large:
            print(f"  [SKIP] {entry['path']}")
            continue
        actual = sha256_of(path)
        ok = actual == entry["sha256"]
        if not ok:
            failures.append(f"hash changed: {entry['path']}")
        print(f"  [{'OK' if ok else 'FAIL'}] {entry['path']}  {actual[:16]}...")

    # ---- 3. network identity --------------------------------------------
    print("\nNetwork identity:")
    import h5py
    import numpy as np

    stack = PROJECT_ROOT / "mintpy" / "production_work" / "inputs" / "ifgramStack.h5"
    if not stack.exists():
        failures.append("ifgramStack.h5 missing")
    else:
        with h5py.File(stack, "r") as handle:
            dates = np.array(handle["date"]).astype(str)
            # inverted name: True means IN USE (see mintpy/objects/stack.py)
            used = int(np.array(handle["dropIfgram"]).sum()) if "dropIfgram" in handle else 0
        pairs = [(min(a, b), max(a, b)) for a, b in dates]
        unique = sorted({d for pair in pairs for d in pair})
        fingerprint = hashlib.sha256(
            canonical({"pairs": sorted(pairs), "dates": unique}).encode()
        ).hexdigest()
        ok = fingerprint == decision["network_fingerprint"]
        if not ok:
            failures.append("network fingerprint changed")
        print(f"  [{'OK' if ok else 'FAIL'}] fingerprint {fingerprint[:16]}...")
        n_ok = len(pairs) == decision["pairs"] and len(unique) == decision["dates"]
        if not n_ok:
            failures.append(f"network size changed: {len(pairs)} pairs / {len(unique)} dates")
        print(f"  [{'OK' if n_ok else 'FAIL'}] {len(pairs)} pairs / {len(unique)} dates")
        n_used = len(pairs)
        if used != n_used:
            failures.append(f"{n_used - used} interferograms excluded from the inversion")
        print(f"  [{'OK' if used == n_used else 'FAIL'}] in use = {used}/{n_used}")

    # ---- 4. small files --------------------------------------------------
    print("\nFrozen config files:")
    for entry in manifest["files"]:
        if "hash-pinned" in entry.get("frozen_as", ""):
            continue
        path = PROJECT_ROOT / entry["frozen_as"]
        if not path.exists():
            failures.append(f"missing snapshot: {entry['frozen_as']}")
            continue
        ok = sha256_of(path) == entry["sha256"]
        if not ok:
            failures.append(f"snapshot altered: {entry['frozen_as']}")
        print(f"  [{'OK' if ok else 'FAIL'}] {entry['frozen_as']}")

    # ---- 5. corpus immutability -----------------------------------------
    print("\nAuthoritative HyP3 corpus (must be untouched):")
    pairs_csv = PROJECT_ROOT / "manifests" / "sbas_pairs.csv"
    inv_csv = PROJECT_ROOT / "manifests" / "production_product_inventory.csv"
    if pairs_csv.exists() and inv_csv.exists():
        import pandas as pd

        n_pairs = len(pd.read_csv(pairs_csv))
        inv = pd.read_csv(inv_csv)
        n_ok = int(inv["download_ok"].fillna(False).astype(bool).sum())
        ok = n_pairs == decision["pairs"] and n_ok == decision["pairs"]
        if not ok:
            failures.append(f"corpus inventory changed: {n_pairs} pairs, {n_ok} downloaded")
        print(f"  [{'OK' if ok else 'FAIL'}] {n_pairs} pairs, {n_ok} products downloaded")
    else:
        print("  [SKIP] corpus inventories not found")

    print("\n" + "=" * 88)
    if failures:
        print(f"{manifest['freeze_version']} VERIFICATION FAILED - {len(failures)} problem(s)")
        for problem in failures:
            print(f"  - {problem}")
        print("=" * 88)
        return 1
    print(f"{manifest['freeze_version']} VERIFIED - freeze_id {manifest['freeze_id'][:16]}... intact")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
