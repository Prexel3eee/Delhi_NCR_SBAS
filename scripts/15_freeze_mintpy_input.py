#!/usr/bin/env python
"""
Freeze the MintPy-loaded 336-pair / 119-date input as `mintpy_input_v1`.

What is frozen
--------------
The exact interferometric input MintPy ingested from the authoritative HyP3
corpus:

    mintpy/production_work/inputs/ifgramStack.h5      (~19.7 GB)
    mintpy/production_work/inputs/geometryGeo.h5      (~47 MB)

plus the small, human-readable artefacts (template, resolved config).

How it is frozen
----------------
The two HDF5 files are far too large to copy, so they are **hash-pinned**
rather than duplicated: a SHA-256 is recorded for each and the network itself is
fingerprinted (a hash over the canonical sorted pair list). Any in-place change
to the stack changes either a file hash or the network fingerprint, so
`scripts/verify_mintpy_input_v1.py` detects it. The small files are copied into
`freeze/mintpy_input_v1/` and marked read-only.

The authoritative HyP3 corpus (`data/production_*`) is never modified by this
or any downstream script.

Usage
-----
    python scripts/15_freeze_mintpy_input.py
    python scripts/15_freeze_mintpy_input.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK = PROJECT_ROOT / "mintpy" / "production_work"
INPUTS = WORK / "inputs"
FREEZE_DIR = PROJECT_ROOT / "freeze" / "mintpy_input_v1"

FREEZE_VERSION = "mintpy_input_v1"

LARGE_FILES = [
    ("mintpy/production_work/inputs/ifgramStack.h5", "interferogram stack loaded by MintPy"),
    ("mintpy/production_work/inputs/geometryGeo.h5", "geocoded geometry (DEM, incidence, azimuth)"),
]
SMALL_FILES = [
    "mintpy/production_work/inputs/mintpy_production.txt",
    "mintpy/production_work/inputs/smallbaselineApp.cfg",
    "mintpy/mintpy_production.txt",
]

EXPECTED_PAIRS = 336
EXPECTED_DATES = 119


def sha256_of(path: Path, *, chunk: int = 1 << 22) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def read_network() -> tuple[list[tuple[str, str]], list[str], int, int]:
    """Extract the loaded network from the stack itself (not from a manifest)."""
    import h5py
    import numpy as np

    with h5py.File(INPUTS / "ifgramStack.h5", "r") as handle:
        dates = np.array(handle["date"]).astype(str)
        bperp = np.array(handle["bperp"]) if "bperp" in handle else None
        flag = np.array(handle["dropIfgram"]) if "dropIfgram" in handle else None
        shape = handle["unwrapPhase"].shape

    pairs = [(min(a, b), max(a, b)) for a, b in dates]
    unique_dates = sorted({d for pair in pairs for d in pair})

    # `dropIfgram` is INVERTED relative to its name. In mintpy/objects/stack.py:
    #     get_date12_list(dropIfgram=True) -> dates[dropIfgram]    (the USED ones)
    #     get_drop_date12_list()           -> dates[~dropIfgram]   (the DROPPED ones)
    # So True means "in use". All-True therefore means nothing has been removed.
    n_in_use = int(flag.sum()) if flag is not None else len(pairs)
    n_excluded = int((~flag).sum()) if flag is not None else 0

    n_finite_bperp = int(np.isfinite(bperp).sum()) if bperp is not None else 0
    return pairs, unique_dates, (n_in_use, n_excluded), (n_finite_bperp, shape)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if FREEZE_DIR.exists() and any(FREEZE_DIR.iterdir()) and not args.force:
        print(f"REFUSING: {FREEZE_DIR} already exists and is not empty (use --force to rebuild).")
        return 2

    missing = [rel for rel, _ in LARGE_FILES if not (PROJECT_ROOT / rel).exists()]
    if missing:
        print("FAIL: missing input files:")
        for rel in missing:
            print(f"  {rel}")
        return 1

    print("=" * 88)
    print(f"FREEZING {FREEZE_VERSION}")
    print("=" * 88)

    # ---- network identity from the stack itself --------------------------
    pairs, dates, (n_in_use, n_excluded), extra = read_network()
    n_finite_bperp, shape = extra
    fingerprint = hashlib.sha256(
        canonical({"pairs": sorted(pairs), "dates": dates}).encode()
    ).hexdigest()

    print(f"\n  interferograms : {len(pairs)}")
    print(f"  dates          : {len(dates)}  ({dates[0]} -> {dates[-1]})")
    print(f"  unwrapPhase    : {shape}")
    print(f"  in use         : {n_in_use}/{len(pairs)}  (MintPy dropIfgram==True means IN USE)")
    print(f"  excluded       : {n_excluded}  (must be 0 - nothing removed before the baseline)")
    print(f"  bperp finite   : {n_finite_bperp}/{len(pairs)}")
    print(f"  network fingerprint: {fingerprint}")

    problems = []
    if len(pairs) != EXPECTED_PAIRS:
        problems.append(f"expected {EXPECTED_PAIRS} pairs, found {len(pairs)}")
    if len(dates) != EXPECTED_DATES:
        problems.append(f"expected {EXPECTED_DATES} dates, found {len(dates)}")
    if n_excluded != 0:
        problems.append(f"{n_excluded} interferograms already excluded before the baseline")
    if n_in_use != len(pairs):
        problems.append(f"only {n_in_use}/{len(pairs)} interferograms are in use")
    if n_finite_bperp != len(pairs):
        problems.append(f"only {n_finite_bperp}/{len(pairs)} finite perpendicular baselines")
    if "20250518" in dates:
        problems.append("2025-05-18 must not be present (v1 exclusion)")
    if problems:
        print("\nFAIL: input is not the expected v1 network:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("  [PASS] network is exactly the v1 336-pair / 119-date stack")

    # ---- hash the large files -------------------------------------------
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    file_entries = []
    for rel, description in LARGE_FILES:
        path = PROJECT_ROOT / rel
        print(f"\n  hashing {rel} ({path.stat().st_size / 1e9:.2f} GB)...")
        digest = sha256_of(path)
        file_entries.append(
            {
                "path": rel,
                "description": description,
                "bytes": path.stat().st_size,
                "sha256": digest,
                "frozen_as": "hash-pinned (not copied: size)",
            }
        )
        print(f"    {digest}")

    # ---- copy the small files -------------------------------------------
    for rel in SMALL_FILES:
        source = PROJECT_ROOT / rel
        if not source.exists():
            continue
        target = FREEZE_DIR / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        file_entries.append(
            {
                "path": rel,
                "description": "configuration",
                "bytes": source.stat().st_size,
                "sha256": sha256_of(source),
                "frozen_as": str(target.relative_to(PROJECT_ROOT)),
            }
        )

    decision = {
        "freeze_version": FREEZE_VERSION,
        "network_fingerprint": fingerprint,
        "pairs": len(pairs),
        "dates": len(dates),
        "first_date": dates[0],
        "last_date": dates[-1],
        "unwrap_phase_shape": list(shape),
        "large_file_hashes": {e["path"]: e["sha256"] for e in file_entries if "large" not in e["frozen_as"]},
        "policy": {
            "authoritative_corpus_modified": False,
            "pairs_removed_before_baseline": 0,
            "excluded_2025_05_18": True,
        },
    }
    freeze_id = hashlib.sha256(canonical(decision).encode()).hexdigest()

    manifest = {
        "freeze_version": FREEZE_VERSION,
        "freeze_id": freeze_id,
        "freeze_id_method": "sha256 over canonical JSON of the 'decision' block",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "project": "delhi_ncr_multiburst_sbas",
        "role": "authoritative MintPy input for all scientific processing",
        "verification": "python scripts/verify_mintpy_input_v1.py",
        "decision": decision,
        "network": {
            "pairs": sorted(pairs),
            "dates": dates,
            "note": "dates are YYYYMMDD as MintPy stores them; manifests use YYYY-MM-DD",
        },
        "files": file_entries,
    }
    manifest_path = FREEZE_DIR / "FREEZE.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    (FREEZE_DIR / "PIPELINE_IMMUTABILITY.md").write_text(
        "# PIPELINE IMMUTABILITY\n\n"
        "Everything upstream of this line is **immutable**. No scientific-processing\n"
        "step may modify, re-clip, re-generate or re-download any of it.\n\n"
        "| Layer | Path | Status |\n"
        "|---|---|---|\n"
        "| HyP3 corpus (ZIPs + extracted) | `data/production_zips/`, `data/production_extracted/` | immutable, hash-inventoried |\n"
        "| Frozen network (336 pairs) | `freeze/v1/` | immutable, read-only, `freeze_id cf2bdbfd...` |\n"
        "| MintPy input (336 pairs / 119 dates) | this directory | immutable, hash-pinned |\n"
        "| Clipped rasters | `mintpy/production_clipped/` | derived, regenerable from the corpus |\n"
        "| MintPy working dirs | `mintpy/<branch>_work/` | mutable, one per branch |\n\n"
        "The HyP3 corpus is never altered by any downstream step.\n\n"
        f"## Freeze\n\n**freeze_id:** `{freeze_id}`\n\n"
        "```text\n"
        f"interferograms  {len(pairs)}\n"
        f"dates           {len(dates)}\n"
        f"unwrapPhase     {tuple(shape)}\n"
        f"first / last    {dates[0]} / {dates[-1]}\n"
        f"network fp      {fingerprint}\n"
        "```\n\n"
        "Verify with `python scripts/verify_mintpy_input_v1.py`.\n",
        encoding="utf-8",
    )

    for path in FREEZE_DIR.rglob("*"):
        if path.is_file():
            path.chmod(path.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)

    print("\n" + "=" * 88)
    print(f"{FREEZE_VERSION} CREATED")
    print("=" * 88)
    print(f"  freeze_id : {freeze_id}")
    print(f"  manifest  : {manifest_path}")
    print(f"  network   : {len(pairs)} pairs / {len(dates)} dates")
    print(f"  files     : {len(file_entries)} pinned")
    print("\n  HyP3 corpus untouched. Verify: python scripts/verify_mintpy_input_v1.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
