#!/usr/bin/env python
"""
Phase II-B stages A, F, and branch execution: freeze DESCENDING_RAW_V1 and run
the predeclared diagnostic branches D1-D3.

Branches (bounded by design - no combinations unless two individuals both help):
  D1  connectComponent masking during inversion
  D2  unwrap correction: bridging + phase_closure
  D3  ERA5 tropospheric correction

weightFunc is already `var` in D0, verified from the executed config, so no
weighting branch is needed.

Each branch is an APFS clonefile of the D0 work directory (instant, copy-on-write)
so the 2.6 GB time series is not duplicated, then re-run with a modified template.

Usage
-----
    python scripts/53_descending_branches.py --freeze-d0
    python scripts/53_descending_branches.py --run D1
    python scripts/53_descending_branches.py --run D2
    python scripts/53_descending_branches.py --run D3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESC_WORK = PROJECT_ROOT / "mintpy" / "descending_work"
FREEZE_D0 = PROJECT_ROOT / "freeze" / "descending_raw_v1"
CONFIG_DIR = PROJECT_ROOT / "config"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2b"

BASE_CONFIG = CONFIG_DIR / "mintpy_descending_baseline.txt"
ERA5_WEATHER_DIR = PROJECT_ROOT / "mintpy" / "era5_work" / "mintpy" / "weather" / "ERA5"

BRANCHES = {
    "D1": {
        "work": PROJECT_ROOT / "mintpy" / "descending_d1_conncomp_work",
        "overrides": {
            "mintpy.networkInversion.maskDataset": "connectComponent",
            "mintpy.networkInversion.maskThreshold": "0.5",
        },
        "label": "connected-component masked inversion",
    },
    "D2": {
        "work": PROJECT_ROOT / "mintpy" / "descending_d2_unwrap_work",
        "overrides": {
            "mintpy.unwrapError.method": "bridging+phase_closure",
        },
        "label": "unwrap-corrected (bridging + phase_closure)",
    },
    "D3": {
        "work": PROJECT_ROOT / "mintpy" / "descending_d3_era5_work",
        "overrides": {
            "mintpy.troposphericDelay.method": "pyaps",
            "mintpy.troposphericDelay.weatherModel": "ERA5",
            "mintpy.troposphericDelay.weatherDir": str(ERA5_WEATHER_DIR),
            "mintpy.troposphericDelay.prefix": "ERA5",
        },
        "label": "ERA5 tropospheric correction",
    },
}

D0_ARTEFACTS = [
    "velocity.h5", "timeseries.h5", "temporalCoherence.h5", "maskTempCoh.h5",
    "maskConnComp.h5", "avgSpatialCoh.h5", "numInvIfgram.h5",
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def freeze_d0() -> int:
    if FREEZE_D0.exists():
        print(f"ERROR: {FREEZE_D0} exists (append-only).", file=sys.stderr)
        return 1
    missing = [a for a in D0_ARTEFACTS if not (DESC_WORK / a).exists()]
    if missing:
        print(f"ERROR: D0 is missing artefacts: {missing}", file=sys.stderr)
        return 1

    FREEZE_D0.mkdir(parents=True)
    records = []
    # Hash in place: the products total ~2.9 GB and are regenerable from the
    # frozen network, so copying them would add no provenance.
    for name in D0_ARTEFACTS:
        path = DESC_WORK / name
        records.append({"path": f"mintpy/descending_work/{name}",
                        "sha256": sha256_of(path), "bytes": path.stat().st_size,
                        "mtime_ns": path.stat().st_mtime_ns})
    for rel in ("manifests/descending/sbas_pairs.csv",
                "manifests/descending/descending_jobs.csv",
                "qc/descending/network_audit.json",
                "qc/descending/descending_qc.json",
                "qc/sci/phase2/cross_validation.json",
                "qc/sci/phase2/decomposition.json",
                "qc/sci/PHASE_IIA_GEODETIC_VALIDATION_REPORT.md"):
        src = PROJECT_ROOT / rel
        if src.exists():
            dst = FREEZE_D0 / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            records.append({"path": rel, "sha256": sha256_of(dst),
                            "bytes": dst.stat().st_size, "copied": True})

    with __import__("h5py").File(DESC_WORK / "velocity.h5", "r") as handle:
        ref = [int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"])]
    payload = json.dumps({"version": "descending_raw_v1",
                          "pinned": [[r["path"], r["sha256"]] for r in records]},
                         sort_keys=True).encode()
    freeze_id = hashlib.sha256(payload).hexdigest()
    manifest = {
        "freeze_version": "descending_raw_v1",
        "label": "DESCENDING_RAW_V1",
        "freeze_id": freeze_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "acquisitions": 91, "interferograms": 219, "robustness_edges": 10,
        "bridges": 0, "articulation_points": 1, "reference_yx": ref,
        "statement": "The Phase-IIA descending RAW solution exactly as produced. "
                     "Retained even if a later branch is better.",
        "artefacts": records,
    }
    (FREEZE_D0 / "FREEZE.json").write_text(json.dumps(manifest, indent=2, default=str))
    for path in sorted(FREEZE_D0.rglob("*"), reverse=True):
        if path.is_dir():
            path.chmod(0o555)
        elif path.name != "FREEZE.json":
            path.chmod(0o444)
    (FREEZE_D0 / "FREEZE.json").chmod(0o444)
    FREEZE_D0.chmod(0o555)
    print(f"  DESCENDING_RAW_V1 frozen: {freeze_id}")
    print(f"  reference {ref}; {len(records)} artefacts")
    return 0


def run_branch(name: str) -> int:
    spec = BRANCHES[name]
    work = spec["work"]
    if work.exists():
        print(f"ERROR: {work} exists. Remove it to re-run.", file=sys.stderr)
        return 1
    work.parent.mkdir(parents=True, exist_ok=True)

    # APFS clonefile: instant, copy-on-write, no 2.6 GB duplication.
    result = subprocess.run(["cp", "-c", str(DESC_WORK), str(work)],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  clonefile failed ({result.stderr.strip()}); falling back to copy")
        shutil.copytree(DESC_WORK, work)

    config = CONFIG_DIR / f"mintpy_descending_{name.lower()}.txt"
    lines = BASE_CONFIG.read_text().splitlines()
    lines = [ln for ln in lines
             if not any(ln.strip().startswith(k) for k in spec["overrides"])]
    lines.append("")
    lines.append(f"## ---- Phase II-B branch {name}: {spec['label']} ----")
    for key, value in spec["overrides"].items():
        lines.append(f"{key} = {value}" if value != "" else key)
    config.write_text("\n".join(lines) + "\n")

    work_inputs = work / "inputs"
    (work_inputs / config.name).write_text(config.read_text())

    print(f"  branch {name}: {spec['label']}")
    print(f"    work dir : {work}")
    print(f"    config   : {config}")
    for key, value in spec["overrides"].items():
        print(f"      {key} = {value}")

    env = dict(**__import__("os").environ)
    env["PATH"] = ("/opt/homebrew/Caskroom/miniforge/base/envs/delhi-mintpy/bin:"
                   + env.get("PATH", ""))
    log = OUT / f"branch_{name}.log"
    OUT.mkdir(parents=True, exist_ok=True)
    with log.open("w") as handle:
        proc = subprocess.run(
            ["python", "-u", "scripts/run_mintpy.py", "smallbaselineApp.py",
             str(config), "--dir", str(work)],
            cwd=PROJECT_ROOT, stdout=handle, stderr=subprocess.STDOUT, env=env)
    print(f"    exit {proc.returncode}; log {log}")
    return 0 if proc.returncode == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze-d0", action="store_true")
    group.add_argument("--run", choices=sorted(BRANCHES))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.freeze_d0:
        return freeze_d0()
    return run_branch(args.run)


if __name__ == "__main__":
    raise SystemExit(main())
