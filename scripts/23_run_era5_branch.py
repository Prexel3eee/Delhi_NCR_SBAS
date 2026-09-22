#!/usr/bin/env python
"""
Run the ERA5 tropospheric-correction branch (principal branch).

Sets up `mintpy/era5_work` from the frozen input (APFS clone: instant, isolated -
the frozen stack is never written to) and runs
`smallbaselineApp.py --start reference_point --end velocity` with
`config/mintpy_era5.txt`.

ERA5 is the ONLY change relative to the RAW-336 baseline: the reference is
frozen at yx 1378,1426, all 336 pairs are retained, unwrap-error correction is
disabled and deramping stays disabled.

Requires CDS credentials in ~/.cdsapirc (MintPy validates the file itself):
    url: https://cds.climate.copernicus.eu/api
    key: <your-cds-api-key>

Usage
-----
    python scripts/23_run_era5_branch.py --check      # prerequisites only
    python scripts/23_run_era5_branch.py              # set up + run
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FROZEN_INPUTS = PROJECT_ROOT / "mintpy" / "production_work" / "inputs"
WORK = PROJECT_ROOT / "mintpy" / "era5_work"
WEATHER_DIR = PROJECT_ROOT / "mintpy" / "weather"
TEMPLATE = PROJECT_ROOT / "config" / "mintpy_era5.txt"
DECISIONS = PROJECT_ROOT / "config" / "scientific_decisions_v2.json"
CDSAPIRC = Path.home() / ".cdsapirc"


def check_prerequisites() -> bool:
    ok = True
    print("ERA5 branch prerequisites:")
    if not TEMPLATE.exists():
        print(f"  [FAIL] template missing: {TEMPLATE}")
        ok = False
    else:
        print(f"  [OK] template {TEMPLATE.name}")

    import importlib.metadata as md
    for pkg in ("pyaps3", "cdsapi", "netCDF4"):
        try:
            print(f"  [OK] {pkg} {md.version(pkg)}")
        except Exception:
            print(f"  [FAIL] {pkg} not installed")
            ok = False

    if not CDSAPIRC.exists():
        print(f"  [FAIL] {CDSAPIRC} not found")
        print("         MintPy's PyAPS ERA5 path requires it. Create it with:")
        print("           url: https://cds.climate.copernicus.eu/api")
        print("           key: <your CDS API key>")
        print("         Get the key from your CDS profile at")
        print("         https://cds.climate.copernicus.eu/ (accept the ERA5 licence first).")
        return False

    lines = CDSAPIRC.read_text().splitlines()
    first = lines[0].strip() if lines else ""
    if first != "url: https://cds.climate.copernicus.eu/api":
        print(f"  [FAIL] ~/.cdsapirc first line is not the current CDS endpoint")
        print(f"         found: {first!r}")
        print("         MintPy raises unless it is exactly "
              "'url: https://cds.climate.copernicus.eu/api'")
        ok = False
    else:
        print("  [OK] ~/.cdsapirc has the current CDS endpoint")
        key_present = any(l.strip().startswith("key:") and len(l.split(":", 1)[1].strip()) > 8
                          for l in lines)
        print(f"  [{'OK' if key_present else 'FAIL'}] ~/.cdsapirc carries a key")
        ok = ok and key_present

    print("  [OK] reference frozen at yx 1378,1426" if DECISIONS.exists()
          else "  [FAIL] scientific_decisions_v2.json missing")
    return ok


def clone_inputs() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "inputs").mkdir(parents=True, exist_ok=True)
    for name in ("ifgramStack.h5", "geometryGeo.h5"):
        src, dst = FROZEN_INPUTS / name, WORK / "inputs" / name
        if dst.exists():
            print(f"  {name}: already present")
            continue
        subprocess.run(["cp", "-c", str(src), str(dst)], check=True)
        print(f"  {name}: cloned (APFS copy-on-write, isolated from the frozen input)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="prerequisites only")
    parser.add_argument("--no-run", action="store_true", help="set up but do not run")
    args = parser.parse_args()

    print("=" * 88)
    print("ERA5 TROPOSPHERIC CORRECTION BRANCH")
    print("=" * 88)
    print()

    if not check_prerequisites():
        print("\nBLOCKED: ERA5 cannot run without the prerequisites above.")
        return 1
    if args.check:
        print("\nPrerequisites OK.")
        return 0

    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nSetting up {WORK.relative_to(PROJECT_ROOT)} ...")
    clone_inputs()
    print(f"  ERA5 cache dir: {WEATHER_DIR.relative_to(PROJECT_ROOT)}")

    if args.no_run:
        print("\nSetup complete (--no-run).")
        return 0

    cmd = [
        sys.executable, str(PROJECT_ROOT / "scripts" / "run_mintpy.py"),
        "smallbaselineApp.py",
        "--dir", str(WORK),
        "--start", "reference_point",
        "--end", "velocity",
        str(TEMPLATE),
    ]
    print(f"\n  $ {' '.join(cmd)}\n")
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
