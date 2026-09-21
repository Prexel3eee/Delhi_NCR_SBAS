#!/usr/bin/env python
"""
Create the immutable v1 production freeze.

What "freeze" means here
------------------------
The pipeline scripts (`02`-`05`) are re-runnable and will happily rewrite
`manifests/` and `qc/`. That is desirable during development but unacceptable as
a production baseline: an unnoticed re-run could silently change which
acquisitions or pairs a paid HyP3 submission is based on.

This script therefore takes a **snapshot** of every freeze-relevant artefact
into `freeze/v1/`, records a SHA-256 for each, derives a single `freeze_id` over
the decision-defining content, and marks the snapshot read-only. From then on:

  * `freeze/v1/` is the authoritative v1 baseline;
  * `scripts/verify_freeze.py` re-derives every hash and the `freeze_id`, and
    fails loudly if the snapshot was altered or if the working `manifests/`
    have drifted away from the frozen baseline.

v1 decision (accepted by the project owner)
-------------------------------------------
    119 accepted acquisitions / 336 pairs, 2025-05-18 permanently excluded.
    No further attempts to recover 2025-05-18 will be made for v1.

Usage
-----
    python scripts/06_freeze_v1.py            # create (refuses to clobber)
    python scripts/06_freeze_v1.py --force    # rebuild snapshot
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
FREEZE_DIR = PROJECT_ROOT / "freeze" / "v1"

FREEZE_VERSION = "v1"

#: ``critical`` artefacts define the network that will be submitted and paid for.
#: Drift in any of them invalidates the freeze. ``provenance`` artefacts are kept
#: for audit; drift there is reported but is not a freeze failure.
ARTEFACTS: list[tuple[str, bool]] = [
    # --- critical: defines exactly what gets processed -------------------
    ("geometry/aoi.geojson", True),
    ("geometry/aoi.wkt", True),
    ("geometry/selected_bursts.geojson", True),
    ("manifests/geographic_reference_bursts.csv", True),
    ("manifests/accepted_acquisitions.csv", True),
    ("manifests/excluded_acquisitions.csv", True),
    ("manifests/acquisition_burst_matrix.csv", True),
    ("manifests/sbas_pairs.csv", True),
    ("manifests/pilot_pairs.csv", True),
    ("config/pilot.yaml", True),
    ("qc/network/network_summary.json", True),
    # --- provenance: audit trail ----------------------------------------
    ("geometry/coverage_report.json", False),
    ("manifests/burst_inventory_2021_2025.csv", False),
    ("manifests/burst_completeness_matrix.csv", False),
    ("manifests/acquisition_gaps.csv", False),
    ("manifests/burst_search_log.csv", False),
    ("qc/inventory/inventory_provenance.json", False),
    ("qc/network/network_edges.csv", False),
    ("qc/network/network_degree.csv", False),
    ("qc/network/baseline_table.csv", False),
    ("qc/cost_estimate.json", False),
]

PILOT_LOOKS = "10x2"
MAX_TEMPORAL_DAYS = 36
MAX_PERP_M = 250.0


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def read_csv_row_count(path: Path) -> int:
    with path.open() as handle:
        return max(0, sum(1 for _ in handle) - 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild an existing snapshot")
    args = parser.parse_args()

    if FREEZE_DIR.exists() and any(FREEZE_DIR.iterdir()) and not args.force:
        print(
            f"REFUSING: {FREEZE_DIR} already exists and is not empty.\n"
            "A freeze is immutable by intent. Use --force only if you are "
            "deliberately rebuilding v1 (which invalidates the previous freeze_id)."
        )
        return 2

    missing = [rel for rel, _ in ARTEFACTS if not (PROJECT_ROOT / rel).exists()]
    if missing:
        print("FAIL: required artefacts missing; run phases B-E first:")
        for rel in missing:
            print(f"  {rel}")
        return 1

    print("=" * 88)
    print("CREATING IMMUTABLE PRODUCTION FREEZE v1")
    print("=" * 88)

    # ---- validate the decision before freezing ---------------------------
    import pandas as pd

    accepted = pd.read_csv(PROJECT_ROOT / "manifests/accepted_acquisitions.csv")
    excluded = pd.read_csv(PROJECT_ROOT / "manifests/excluded_acquisitions.csv")
    pairs = pd.read_csv(PROJECT_ROOT / "manifests/sbas_pairs.csv")
    frozen_bursts = pd.read_csv(PROJECT_ROOT / "manifests/geographic_reference_bursts.csv")
    summary = json.loads((PROJECT_ROOT / "qc/network/network_summary.json").read_text())
    cost = json.loads((PROJECT_ROOT / "qc/cost_estimate.json").read_text())

    n_accepted = len(accepted)
    n_pairs = len(pairs)
    k = int(pairs["burst_count"].iloc[0])

    checks = [
        ("accepted acquisitions == 119", n_accepted == 119, n_accepted),
        ("pairs == 336", n_pairs == 336, n_pairs),
        ("K == 4", k == 4, k),
        ("exactly 1 excluded acquisition", len(excluded) == 1, len(excluded)),
        (
            "excluded acquisition is 2025-05-18",
            len(excluded) == 1 and str(excluded["date"].iloc[0]) == "2025-05-18",
            list(excluded["date"]) if len(excluded) else [],
        ),
        ("network acceptance passed", summary.get("acceptance_passed") is True, summary.get("acceptance_passed")),
        ("all pairs use the frozen burst set",
         all(json.loads(s) == sorted(frozen_bursts["full_burst_id"])
             for s in pairs["reference_burst_ids_json"]), True),
        ("no pair touches an excluded acquisition",
         not (pairs["reference_date"].isin(excluded["date"]).any()
              or pairs["secondary_date"].isin(excluded["date"]).any()), True),
        ("production not yet submitted", cost.get("production_submitted") is False, cost.get("production_submitted")),
    ]

    print("\nPre-freeze validation:")
    failed = False
    for label, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}  ({detail})")
        failed = failed or not passed
    if failed:
        print("\nFAIL: freeze aborted; the v1 decision is not satisfied.")
        return 1

    # ---- snapshot --------------------------------------------------------
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)

    entries = []
    for rel, critical in ARTEFACTS:
        source = PROJECT_ROOT / rel
        target = FREEZE_DIR / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        entries.append(
            {
                "path": rel,
                "snapshot": str(target.relative_to(PROJECT_ROOT)),
                "critical": critical,
                "bytes": source.stat().st_size,
                "sha256": sha256_of(source),
            }
        )
        print(f"  snapshotted {rel}  ({source.stat().st_size} bytes)")

    # ---- derive freeze_id over decision-defining content -----------------
    decision = {
        "freeze_version": FREEZE_VERSION,
        "aoi_sha256": next(e["sha256"] for e in entries if e["path"] == "geometry/aoi.geojson"),
        "bursts": sorted(frozen_bursts["full_burst_id"].tolist()),
        "k": k,
        "accepted_acquisitions": n_accepted,
        "excluded_acquisitions": sorted(excluded["date"].tolist()),
        "pairs": n_pairs,
        "thresholds": {
            "max_temporal_baseline_days": MAX_TEMPORAL_DAYS,
            "max_perpendicular_baseline_m": MAX_PERP_M,
        },
        "pilot_looks": PILOT_LOOKS,
        "critical_artefact_hashes": {
            e["path"]: e["sha256"] for e in entries if e["critical"]
        },
        "policy": {
            "recover_2025_05_18": False,
            "statement": (
                "v1 is frozen at 119 acquisitions / 336 pairs. The 2025-05-18 "
                "acquisition is excluded fail-closed and will NOT be re-queried or "
                "recovered for v1. Production remains blocked pending pilot QC and "
                "explicit owner approval."
            ),
        },
    }
    freeze_id = hashlib.sha256(canonical_json(decision).encode()).hexdigest()

    manifest = {
        "freeze_version": FREEZE_VERSION,
        "freeze_id": freeze_id,
        "freeze_id_method": "sha256 over canonical JSON of the 'decision' block (sorted keys, no whitespace)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "project": "delhi_ncr_multiburst_sbas",
        "status": "FROZEN_PENDING_PILOT_QC",
        "pi_policy": "immutable snapshot; verify with scripts/verify_freeze.py",
        "decision": decision,
        "artefacts": entries,
        "summary": {
            "accepted_acquisitions": n_accepted,
            "interferogram_pairs": n_pairs,
            "bursts_per_job_k": k,
            "full_burst_ids": sorted(frozen_bursts["full_burst_id"].tolist()),
            "platforms": sorted(accepted["platforms"].unique().tolist()),
            "first_acquisition": str(accepted["date"].iloc[0]),
            "last_acquisition": str(accepted["date"].iloc[-1]),
            "pilot_jobs": cost["pilot"]["job_count"],
            "pilot_credits": cost["pilot"]["total_credits"],
            "production_credits_10x2": cost["scenarios"]["10x2"]["total_credits"],
            "production_submitted": False,
        },
    }

    manifest_path = FREEZE_DIR / "FREEZE_v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False))

    # ---- mark the snapshot read-only -------------------------------------
    for entry in entries:
        target = PROJECT_ROOT / entry["snapshot"]
        target.chmod(target.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    manifest_path.chmod(manifest_path.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)

    (FREEZE_DIR / "README.md").write_text(
        f"""# Freeze {FREEZE_VERSION} — immutable production baseline

**freeze_id:** `{freeze_id}`

Created {manifest['created_utc']}.

This directory is a read-only snapshot. Do not edit files here: editing them
breaks the freeze and `scripts/verify_freeze.py` will fail.

## Decision

```text
accepted acquisitions   {n_accepted}
interferogram pairs     {n_pairs}
bursts per job (K)      {k}
pilot                   {cost['pilot']['job_count']} jobs @ {PILOT_LOOKS} = {cost['pilot']['total_credits']} credits
production @ {PILOT_LOOKS}       {cost['scenarios']['10x2']['total_credits']} credits
excluded                2025-05-18 (027_056011_IW2) — permanently, for v1
```

Production remains **blocked** pending pilot QC and explicit owner approval.

## Verify

```bash
python scripts/verify_freeze.py
```

Exit code 0 means the snapshot and the working manifests still agree with
`freeze_id`. Any other exit means drift: stop and investigate before spending
HyP3 credits.
""",
        encoding="utf-8",
    )
    (FREEZE_DIR / "README.md").chmod(0o444)

    print("\n" + "=" * 88)
    print(f"FREEZE v1 CREATED")
    print("=" * 88)
    print(f"  freeze_id   : {freeze_id}")
    print(f"  artefacts   : {len(entries)} ({sum(1 for e in entries if e['critical'])} critical)")
    print(f"  acquisitions: {n_accepted}")
    print(f"  pairs       : {n_pairs}")
    print(f"  manifest    : {manifest_path}")
    print("\n  Snapshot marked read-only. Verify with: python scripts/verify_freeze.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
