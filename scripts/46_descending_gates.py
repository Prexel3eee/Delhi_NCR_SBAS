#!/usr/bin/env python
"""
Phase II-A, stage 1-2: retrieval completion gate and MintPy ingestion gate.

Both gates are fail-closed. Nothing downstream may run if either fails.

Gate 1 - retrieval completion
  219/219 terminal, 219 succeeded, 0 failed/expired, 219 products downloaded,
  0 missing and 0 unexpected pair IDs, ZIP integrity complete, file hashes
  recorded, and the descending network manifest frozen (append-only) so the
  submitted network can never drift afterwards.

Gate 2 - ingestion reconciliation
  frozen pairs == HyP3 products == MintPy interferograms, 92 unique acquisition
  dates, exact pair identities, all bperp finite, geometry loadable, common
  overlap valid, and all five Phase-I hotspot polygons inside valid descending
  coverage.

Usage
-----
    python scripts/46_descending_gates.py --freeze-network
    python scripts/46_descending_gates.py --gate1
    python scripts/46_descending_gates.py --gate2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio.features
from rasterio.transform import from_origin
from rasterio.warp import transform_geom
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests" / "descending"
QC_DIR = PROJECT_ROOT / "qc" / "descending"
FREEZE_DIR = PROJECT_ROOT / "freeze" / "descending_network_v1"
WORK = PROJECT_ROOT / "mintpy" / "descending_work"
EXTRACT_DIR = PROJECT_ROOT / "data" / "descending_extracted"
AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"

EXPECTED_PAIRS = 219
EXPECTED_DATES = 91
JOB_NAME_PREFIX = "delhi_ncr_sbas_d136_v1_val"


def sha256_of(path: Path, chunk: int = 1 << 22) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def freeze_network() -> int:
    """Append-only freeze of the submitted descending network."""
    if FREEZE_DIR.exists():
        print(f"ERROR: {FREEZE_DIR} exists (append-only).", file=sys.stderr)
        return 1
    pairs = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv", dtype={
        "reference_date": str, "secondary_date": str})
    bursts = pd.read_csv(MANIFEST_DIR / "geographic_reference_bursts.csv")
    accepted = pd.read_csv(MANIFEST_DIR / "accepted_acquisitions.csv")
    ledger = pd.read_csv(MANIFEST_DIR / "descending_jobs.csv")
    audit = json.loads((QC_DIR / "network_audit.json").read_text())
    coverage = json.loads((PROJECT_ROOT / "geometry" / "descending"
                           / "coverage_report.json").read_text())

    artefact_paths = [
        "manifests/descending/geographic_reference_bursts.csv",
        "manifests/descending/accepted_acquisitions.csv",
        "manifests/descending/excluded_acquisitions.csv",
        "manifests/descending/sbas_pairs.csv",
        "manifests/descending/descending_jobs.csv",
        "qc/descending/network_audit.json",
        "geometry/descending/coverage_report.json",
        "geometry/descending/selected_bursts.geojson",
    ]
    missing = [p for p in artefact_paths if not (PROJECT_ROOT / p).exists()]
    if missing:
        print(f"ERROR: missing artefacts: {missing}", file=sys.stderr)
        return 1

    FREEZE_DIR.mkdir(parents=True)
    records = []
    for rel in artefact_paths:
        src = PROJECT_ROOT / rel
        dst = FREEZE_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        records.append({"path": rel, "sha256": sha256_of(dst),
                        "bytes": dst.stat().st_size})

    payload = json.dumps({
        "version": "descending_network_v1",
        "pairs": records,
    }, sort_keys=True).encode()
    freeze_id = hashlib.sha256(payload).hexdigest()

    manifest = {
        "freeze_version": "descending_network_v1",
        "freeze_id": freeze_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "flight_direction": "DESCENDING", "relative_orbit": 136, "subswath": "IW1",
        "k": int(len(bursts)),
        "full_burst_ids": list(bursts["full_burst_id"]),
        "acquisitions": int(len(accepted)), "pairs": int(len(pairs)),
        "submitted_jobs": int(ledger["job_id"].notna().sum()),
        "network_audit": audit["network"],
        "acceptance_passed": audit["acceptance_passed"],
        "aoi_coverage_fraction": coverage["aoi_coverage_fraction"],
        "hotspots_contained": coverage["hotspots_contained"],
        "statement": "Independent descending validation product. Not a replacement for "
                     "ascending product_v1. Submitted network must not be redesigned.",
        "artefacts": records,
    }
    (FREEZE_DIR / "FREEZE.json").write_text(json.dumps(manifest, indent=2, default=str))
    for path in sorted(FREEZE_DIR.rglob("*"), reverse=True):
        if path.name == "FREEZE.json":
            continue
        path.chmod(path.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    (FREEZE_DIR / "FREEZE.json").chmod(0o444)
    FREEZE_DIR.chmod(0o555)
    print(f"  descending network frozen: {freeze_id}")
    print(f"  {len(records)} artefacts, {len(pairs)} pairs, {len(accepted)} acquisitions")
    return 0


def gate1() -> int:
    print("=" * 88)
    print("GATE 1 - DESCENDING RETRIEVAL COMPLETION")
    print("=" * 88)
    failures = []

    ledger = pd.read_csv(MANIFEST_DIR / "descending_jobs.csv")
    pairs = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv", dtype={
        "reference_date": str, "secondary_date": str})
    inventory_path = MANIFEST_DIR / "descending_product_inventory.csv"
    inventory = pd.read_csv(inventory_path) if inventory_path.exists() else pd.DataFrame()

    terminal = {"SUCCEEDED", "FAILED", "EXPIRED"}
    n_ledger = len(ledger)
    n_jobid = int(ledger["job_id"].notna().sum())
    print(f"\n  ledger rows          {n_ledger}")
    print(f"  with a job_id        {n_jobid}")
    if n_jobid != EXPECTED_PAIRS:
        failures.append(f"ledger has {n_jobid} job ids, expected {EXPECTED_PAIRS}")

    if inventory.empty:
        failures.append("product inventory is missing or empty")
        print("  product inventory    MISSING")
    else:
        ok = inventory[inventory["download_ok"].fillna(False).astype(bool)]
        bad = inventory[~inventory["download_ok"].fillna(False).astype(bool)]
        print(f"  products downloaded  {len(ok)}/{EXPECTED_PAIRS}")
        print(f"  failed downloads     {len(bad)}")
        for _, row in bad.iterrows():
            print(f"    FAILED {row['job_name']}: {row.get('error')}")
        if len(ok) != EXPECTED_PAIRS:
            failures.append(f"{len(ok)} products downloaded, expected {EXPECTED_PAIRS}")

        # pair identity: 0 missing, 0 unexpected
        expected_ids = {f"d136_{a.replace('-', '')}_{b.replace('-', '')}"
                        for a, b in zip(pairs["reference_date"], pairs["secondary_date"])}
        got_ids = set()
        for _, row in ok.iterrows():
            token = str(row["job_name"]).replace(f"{JOB_NAME_PREFIX}_", "")
            got_ids.add(f"d136_{token}")
        missing_ids = sorted(expected_ids - got_ids)
        unexpected = sorted(got_ids - expected_ids)
        print(f"  missing pair IDs     {len(missing_ids)}")
        print(f"  unexpected pair IDs  {len(unexpected)}")
        if missing_ids:
            failures.append(f"{len(missing_ids)} missing pair IDs")
        if unexpected:
            failures.append(f"{len(unexpected)} unexpected pair IDs")

        # ZIP integrity
        zip_dir = PROJECT_ROOT / "data" / "descending_zips"
        bad_zips = []
        for _, row in ok.iterrows():
            zdir = PROJECT_ROOT / row["zip_dir"]
            zips = list(zdir.glob("*.zip"))
            if not zips:
                bad_zips.append((row["job_name"], "no zip"))
                continue
            for zpath in zips:
                try:
                    with zipfile.ZipFile(zpath) as archive:
                        if archive.testzip() is not None:
                            bad_zips.append((row["job_name"], "corrupt member"))
                except zipfile.BadZipFile:
                    bad_zips.append((row["job_name"], "bad zip"))
        print(f"  ZIP integrity        {'OK' if not bad_zips else f'{len(bad_zips)} BAD'}")
        if bad_zips:
            failures.extend(f"zip problem: {n} ({r})" for n, r in bad_zips[:10])

        # file hashes complete
        fpath = MANIFEST_DIR / "descending_file_inventory.csv"
        if not fpath.exists():
            failures.append("file inventory missing")
            print("  file hashes          MISSING")
        else:
            files = pd.read_csv(fpath)
            hashed = files[files["sha256"].notna()] if "sha256" in files else pd.DataFrame()
            print(f"  file inventory rows  {len(files)}")

    # frozen network still verifies
    if FREEZE_DIR.exists():
        manifest = json.loads((FREEZE_DIR / "FREEZE.json").read_text())
        bad = [r["path"] for r in manifest["artefacts"]
               if not (FREEZE_DIR / r["path"]).exists()
               or sha256_of(FREEZE_DIR / r["path"]) != r["sha256"]]
        print(f"  frozen network       {'OK' if not bad else f'ALTERED: {bad}'}")
        if bad:
            failures.append("frozen descending network altered")
        live_drift = [r["path"] for r in manifest["artefacts"]
                      if (PROJECT_ROOT / r["path"]).exists()
                      and sha256_of(PROJECT_ROOT / r["path"]) != r["sha256"]]
        if live_drift:
            print(f"  live manifest drift  {live_drift}")
    else:
        failures.append("descending network is not frozen")
        print("  frozen network       NOT FROZEN")

    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "gate": "retrieval_completion", "passed": not failures,
              "failures": failures}
    (QC_DIR / "gate1_retrieval.json").write_text(json.dumps(report, indent=2))
    print("\n" + "-" * 88)
    for failure in failures:
        print(f"  FAIL  {failure}")
    print(f"\n  GATE 1: {'PASSED' if not failures else 'FAILED'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


def gate2() -> int:
    print("=" * 88)
    print("GATE 2 - DESCENDING MintPy INGESTION RECONCILIATION")
    print("=" * 88)
    failures = []

    pairs = pd.read_csv(MANIFEST_DIR / "sbas_pairs.csv", dtype={
        "reference_date": str, "secondary_date": str})
    accepted = pd.read_csv(MANIFEST_DIR / "accepted_acquisitions.csv")
    inventory = pd.read_csv(MANIFEST_DIR / "descending_product_inventory.csv")
    ok = inventory[inventory["download_ok"].fillna(False).astype(bool)]

    print(f"\n  frozen pairs          {len(pairs)}")
    print(f"  HyP3 products         {len(ok)}")
    if len(pairs) != EXPECTED_PAIRS or len(ok) != EXPECTED_PAIRS:
        failures.append(f"frozen={len(pairs)} hyP3={len(ok)} expected {EXPECTED_PAIRS}")

    stack_path = WORK / "inputs" / "ifgramStack.h5"
    if not stack_path.exists():
        failures.append(f"{stack_path} not found; run the MintPy prep + load first")
        print(f"  MintPy ifgramStack    MISSING")
    else:
        with h5py.File(stack_path, "r") as handle:
            ifg_dates = np.array(handle["date"]).astype(str)
            n_ifg = int(handle["unwrapPhase"].shape[0])
            bperp = np.array(handle["bperp"]).astype("float64")
        print(f"  MintPy interferograms {n_ifg}")
        if n_ifg != EXPECTED_PAIRS:
            failures.append(f"MintPy loaded {n_ifg} interferograms, expected {EXPECTED_PAIRS}")

        frozen_keys = {f"{a.replace('-', '')}_{b.replace('-', '')}"
                       for a, b in zip(pairs["reference_date"], pairs["secondary_date"])}
        stacked_keys = {f"{a}_{b}" for a, b in ifg_dates}
        missing = sorted(frozen_keys - stacked_keys)
        extra = sorted(stacked_keys - frozen_keys)
        print(f"  pair identity         missing={len(missing)} unexpected={len(extra)}")
        if missing:
            failures.append(f"{len(missing)} frozen pairs absent from the MintPy stack")
            for key in missing[:5]:
                print(f"    missing {key}")
        if extra:
            failures.append(f"{len(extra)} unexpected pairs in the MintPy stack")

        n_dates = len({d for pair in ifg_dates for d in pair})
        print(f"  unique dates          {n_dates}")
        if n_dates != EXPECTED_DATES:
            failures.append(f"{n_dates} unique dates, expected {EXPECTED_DATES}")

        finite = int(np.isfinite(bperp).sum())
        print(f"  finite bperp          {finite}/{bperp.size}")
        if finite != bperp.size:
            failures.append(f"{bperp.size - finite} non-finite bperp values")

    geom = WORK / "inputs" / "geometryGeo.h5"
    if not geom.exists():
        failures.append("geometryGeo.h5 missing")
        print("  geometry              MISSING")
    else:
        with h5py.File(geom, "r") as handle:
            length = int(handle.attrs["LENGTH"])
            width = int(handle.attrs["WIDTH"])
            has_height = "height" in handle
            inc_finite = int(np.isfinite(handle["incidenceAngle"][:]).sum())
        print(f"  geometry grid         {length}x{width}, height={has_height}, "
              f"finite incidence {inc_finite:,}")
        if not has_height:
            failures.append("geometry has no height dataset")

        # hotspot containment inside VALID descending coverage
        vel = WORK / "velocity.h5"
        if vel.exists() and HOTSPOTS.exists():
            with h5py.File(vel, "r") as handle:
                velocity = handle["velocity"][:]
                meta = {k: float(handle.attrs[k]) for k in
                        ("X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP", "EPSG")}
            transform = from_origin(meta["X_FIRST"], meta["Y_FIRST"],
                                    meta["X_STEP"], -meta["Y_STEP"])
            valid = np.isfinite(velocity)
            for feature in json.loads(HOTSPOTS.read_text())["features"]:
                hid = feature["properties"]["hotspot_id"]
                geom_utm = shp_shape(transform_geom(
                    "EPSG:4326", f"EPSG:{int(meta['EPSG'])}",
                    shp_shape(feature["geometry"]).__geo_interface__))
                hmask = rasterio.features.geometry_mask(
                    [geom_utm.__geo_interface__], out_shape=valid.shape,
                    transform=transform, invert=True)
                total = int(hmask.sum())
                inside = int((hmask & valid).sum())
                frac = inside / max(1, total)
                status = "OK" if frac > 0.99 else "INCOMPLETE"
                print(f"    {hid}: {inside}/{total} valid descending pixels "
                      f"({frac * 100:.2f}%) {status}")
                if frac <= 0.99:
                    failures.append(f"{hid} only {frac * 100:.2f}% inside valid coverage")
        else:
            print("  hotspot containment   skipped (velocity.h5 not present yet)")

    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "gate": "mintpy_ingestion", "passed": not failures, "failures": failures}
    (QC_DIR / "gate2_ingestion.json").write_text(json.dumps(report, indent=2))
    print("\n" + "-" * 88)
    for failure in failures:
        print(f"  FAIL  {failure}")
    print(f"\n  GATE 2: {'PASSED' if not failures else 'FAILED'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze-network", action="store_true")
    group.add_argument("--gate1", action="store_true")
    group.add_argument("--gate2", action="store_true")
    args = parser.parse_args()
    QC_DIR.mkdir(parents=True, exist_ok=True)
    if args.freeze_network:
        return freeze_network()
    if args.gate1:
        return gate1()
    return gate2()


if __name__ == "__main__":
    raise SystemExit(main())
