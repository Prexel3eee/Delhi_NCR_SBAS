#!/usr/bin/env python
"""
Verify the frozen Phase-I observations.

Re-derives every hash and the `freeze_id` in `freeze/phase1_observations/`, and
re-checks the pinned conclusions against the live Phase-I outputs so that any
later revision of a Phase-I number surfaces as drift rather than passing
silently.

Exit codes: 0 = valid, 1 = failed.

Usage
-----
    python scripts/verify_phase1_observations.py [--quiet]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DIR = PROJECT_ROOT / "freeze" / "phase1_observations"
MANIFEST = FREEZE_DIR / "OBSERVATIONS.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
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
    failures, warnings = [], []

    say("=" * 88)
    say("VERIFY PHASE I OBSERVATIONS")
    say("=" * 88)
    say(f"\n  freeze_version : {manifest['freeze_version']}")

    say("\n  frozen artefacts:")
    for entry in manifest["source_artefacts"]:
        frozen = FREEZE_DIR / entry["path"]
        live = PROJECT_ROOT / entry["path"]
        if not frozen.exists():
            failures.append(f"missing: {entry['path']}")
            say(f"    MISSING  {entry['path']}")
            continue
        if sha256_of(frozen) != entry["sha256"]:
            failures.append(f"altered: {entry['path']}")
            say(f"    CHANGED  {entry['path']}")
            continue
        if live.exists() and sha256_of(live) != entry["sha256"]:
            warnings.append(f"live copy drifted from freeze: {entry['path']}")
            say(f"    drift    {entry['path']}")
            continue
        say(f"    ok       {entry['path']}")

    # Re-derive the freeze id over the same canonical payload.
    payload = json.dumps({
        "version": manifest["freeze_version"],
        "zones": [[z["zone_id"], z["area_km2"], z["los_velocity_median_mm_per_yr"],
                   z["grade"]] for z in manifest["deformation_zones"]],
        "mapped_area_km2": manifest["mapped_area"]["value_km2"],
        "findings": manifest["observational_findings"],
        "sources": [[c["path"], c["sha256"]] for c in manifest["source_artefacts"]],
    }, sort_keys=True).encode()
    derived = hashlib.sha256(payload).hexdigest()
    say(f"\n  freeze_id recorded : {manifest['freeze_id']}")
    say(f"  freeze_id derived  : {derived}")
    if derived != manifest["freeze_id"]:
        failures.append("freeze_id mismatch")
        say("  -> MISMATCH")
    else:
        say("  -> OK")

    # The pinned headline conclusions must still hold in the live outputs.
    live_hotspots = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots.csv"
    if live_hotspots.exists():
        import pandas as pd
        table = pd.read_csv(live_hotspots)
        frozen_area = manifest["mapped_area"]["value_km2"]
        live_area = round(float(table["area_km2"].sum()), 2)
        if abs(live_area - frozen_area) > 1e-6:
            failures.append(f"mapped area changed: {frozen_area} -> {live_area}")
            say(f"\n  FAIL mapped area {frozen_area} -> {live_area} km2")
        else:
            say(f"\n  mapped area still {live_area} km2")
        if not (table["los_velocity_median_mm_per_yr"] < 0).all():
            failures.append("a zone no longer has negative LOS velocity")
            say("  FAIL a zone is no longer negative-LOS")
        else:
            say("  all zones still negative-LOS")
    else:
        warnings.append("live Phase I hotspots.csv absent; content checks skipped")

    if FREEZE_DIR.stat().st_mode & 0o222:
        warnings.append("freeze directory is writable")
        say("\n  WARNING: freeze directory is writable")

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
