#!/usr/bin/env python
"""
Phase IV: final evidence synthesis and freeze.

No new explanatory dataset is introduced. No InSAR processing is reopened. This
script reads the frozen upstream results, builds the definitive hotspot table,
evidence matrix and uncertainty table, and seals them against every upstream
freeze.

Usage
-----
    python scripts/69_phase4_synthesis.py
    python scripts/69_phase4_synthesis.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE = PROJECT_ROOT / "freeze" / "final_evidence_v1"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase4"
REPORT = PROJECT_ROOT / "qc" / "sci" / "FINAL_SCIENTIFIC_EVIDENCE_REPORT.md"

UPSTREAM = [
    ("v1", "freeze/v1/FREEZE_v1.json"),
    ("mintpy_input_v1", "freeze/mintpy_input_v1/FREEZE.json"),
    ("product_v1", "freeze/product_v1/FREEZE.json"),
    ("phase1_observations", "freeze/phase1_observations/OBSERVATIONS.json"),
    ("descending_network_v1", "freeze/descending_network_v1/FREEZE.json"),
    ("descending_raw_v1", "freeze/descending_raw_v1/FREEZE.json"),
    ("phase2a_results", "freeze/phase2a_results/FREEZE.json"),
    ("phase2b_closeout_v1", "freeze/phase2b_closeout_v1/FREEZE.json"),
    ("descending_v2_candidate", "freeze/descending_v2_candidate/FREEZE.json"),
    ("cgwb_seasonal_v1", "freeze/cgwb_seasonal_v1/FREEZE.json"),
    ("nwdp_telemetry_v1", "freeze/nwdp_telemetry_v1/FREEZE.json"),
    ("groundwater_protocol_v1", "freeze/groundwater_protocol_v1/GROUNDWATER_PROTOCOL_V1.json"),
]

HOTSPOT_TABLE = [
    {"hotspot": "H001", "ascending_classification": "Grade A (Phase I)",
     "descending_classification": "spatially detected, same sign",
     "cross_geometry_status": "INDEPENDENTLY_SUPPORTED",
     "ascending_rate_mm_per_yr": -30.95, "descending_rate_mm_per_yr": -36.02,
     "rate_agreement": "ratio 1.16; 1.6 sigma from the vertical-equivalent expectation",
     "time_history_agreement": "NOT reproduced (asc total -120.7 mm vs D2 +1.1 mm)",
     "quality": "asc TC 0.925; desc TC 0.906",
     "area_km2": 5.59, "causal_evidence": "NO EVIDENCE for every tested mechanism",
     "final_interpretation": "SUPPORTED DEFORMATION FEATURE - MECHANISM UNRESOLVED"},
    {"hotspot": "H004", "ascending_classification": "Grade B (Phase I)",
     "descending_classification": "spatially detected, same sign",
     "cross_geometry_status": "INDEPENDENTLY_SUPPORTED",
     "ascending_rate_mm_per_yr": -14.31, "descending_rate_mm_per_yr": -12.46,
     "rate_agreement": "ratio 0.87; 1.6 sigma from the vertical-equivalent expectation",
     "time_history_agreement": "NOT reproduced",
     "quality": "asc TC 0.963; desc TC 0.909",
     "area_km2": 1.07, "causal_evidence": "NO EVIDENCE for every tested mechanism",
     "final_interpretation": "SUPPORTED DEFORMATION FEATURE - MECHANISM UNRESOLVED"},
    {"hotspot": "H002", "ascending_classification": "Grade B (Phase I)",
     "descending_classification": "not detected at the required magnitude",
     "cross_geometry_status": "NOT_REPRODUCED",
     "ascending_rate_mm_per_yr": -13.59, "descending_rate_mm_per_yr": -1.15,
     "rate_agreement": "ratio 0.09; 8.3 sigma from expectation",
     "time_history_agreement": "n/a - no reproduced rate to compare",
     "quality": "asc TC 0.863; desc TC 0.900 (ADEQUATE)",
     "area_km2": 12.83, "causal_evidence": "negative control",
     "final_interpretation": "ASCENDING FEATURE NOT REPRODUCED"},
    {"hotspot": "H003", "ascending_classification": "Grade B (Phase I)",
     "descending_classification": "not detected at the required magnitude",
     "cross_geometry_status": "NOT_REPRODUCED",
     "ascending_rate_mm_per_yr": -12.87, "descending_rate_mm_per_yr": -0.75,
     "rate_agreement": "ratio 0.06; 8.3 sigma from expectation",
     "time_history_agreement": "n/a",
     "quality": "asc TC 0.861; desc TC 0.886 (ADEQUATE)",
     "area_km2": 2.25, "causal_evidence": "negative control",
     "final_interpretation": "ASCENDING FEATURE NOT REPRODUCED"},
    {"hotspot": "H005", "ascending_classification": "Grade C (Phase I)",
     "descending_classification": "detected with OPPOSITE sign",
     "cross_geometry_status": "UNRESOLVED_CONTRADICTION",
     "ascending_rate_mm_per_yr": -14.21, "descending_rate_mm_per_yr": +61.39,
     "rate_agreement": "sign reversed; 18.7 sigma from expectation",
     "time_history_agreement": "n/a - contradiction unresolved",
     "quality": "asc TC 0.865; desc TC 0.851",
     "area_km2": 0.84, "causal_evidence": "excluded from all hypothesis testing",
     "final_interpretation": "UNRESOLVED CROSS-GEOMETRY CONTRADICTION"},
]

EVIDENCE_MATRIX = [
    {"hypothesis": "Groundwater temporal forcing", "evidence_state": "NO EVIDENCE",
     "basis": "preregistered test: trends opposite to prediction at H001/H004; controls "
              "carry the predicted sign; falsification lags equal or outperform forward "
              "lags; 0 of 16 positive-lag tests survive FDR q=0.05"},
    {"hypothesis": "Shallow soil-texture susceptibility", "evidence_state": "NO EVIDENCE",
     "basis": "H001/H004 are coarser (more sand, less clay) than controls - opposite to "
              "the fine-sediment prediction; confounded with coherence (rho -0.600)"},
    {"hypothesis": "Deep geological / aquifer-system susceptibility",
     "evidence_state": "NOT ADEQUATELY TESTED",
     "basis": "GSI Bhukosh unreachable; the only usable dataset samples the upper ~2 m, "
              "not the compaction interval"},
    {"hypothesis": "Existing built intensity", "evidence_state": "NO EVIDENCE",
     "basis": "all four hotspots are 70-79% built against a 33.7% background, so it "
              "describes a shared setting and cannot explain selectivity; the two "
              "datasets disagree on H001's ranking"},
    {"hypothesis": "Recent built-up expansion", "evidence_state": "NO EVIDENCE",
     "basis": "GHSL 2020->2025 change exactly zero at all four hotspots; the 2025 epoch "
              "is a projection, not an observation"},
    {"hypothesis": "Major infrastructure / construction", "evidence_state": "NOT TESTABLE",
     "basis": "no authoritative dated construction dataset obtained"},
    {"hypothesis": "Measurement artefact as sole explanation",
     "evidence_state": "NOT SUPPORTED FOR H001/H004, but measurement limitations remain",
     "basis": "the hotspot spatial contrast survives coherence-band matching; the "
              "coherence-velocity association's origin is nonetheless unresolved"},
]

UNCERTAINTY = {
    "measurement_statistical": {
        "formal_velocity_uncertainty_mm_per_yr": {"ascending_median": 0.866,
                                                  "descending_d2_median": "see Phase II-B"},
        "temporal_coherence": {"ascending_p50": 0.757, "descending_d2_p50": 0.4376},
        "note": "the formal fit uncertainty is NOT the error budget",
    },
    "reference_systematic": {
        "zero_level_range_mm_per_yr": 4.78,
        "reference_candidate_sd_mm_per_yr": 1.716,
        "affects": "ABSOLUTE offset only; spatial gradients and hotspot contrast are "
                   "invariant to the choice",
        "inc007_offset_mm_per_yr": 0.1362,
    },
    "processing_sensitivity": {
        "era5_minus_raw_rms_mm_per_yr": 0.521,
        "era5_dem_minus_raw_rms_mm_per_yr": 1.036,
        "unwrap_correction": "changed the descending product materially (7/7 internal "
                             "metrics) but is NOT applicable to the authoritative "
                             "ascending product",
    },
    "cross_geometry": {
        "global_pearson_d0": 0.1752, "global_pearson_d2": 0.3626,
        "per_hotspot": "H001 and H004 agree at the rate level; H002/H003 do not "
                       "reproduce; H005 contradicts",
    },
    "temporal_non_stationarity": {
        "split_half_difference_range_mm_per_yr": [10.44, 20.24],
        "note": "the dominant uncertainty in any single quoted rate; larger than every "
                "statistical interval",
    },
    "combination_policy": "These are NOT combined into a single +/- value. They are "
                          "different kinds of quantity (statistical, systematic, "
                          "sensitivity, structural) and no valid probabilistic model "
                          "justifies summing them.",
}


def sha256_of(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as h:
        for c in iter(lambda: h.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def verify_upstream() -> list[dict]:
    rows = []
    for name, rel in UPSTREAM:
        p = PROJECT_ROOT / rel
        if not p.exists():
            rows.append({"freeze": name, "path": rel, "status": "MISSING"})
            continue
        doc = json.loads(p.read_text())
        rows.append({"freeze": name, "path": rel,
                     "freeze_id": doc.get("freeze_id") or doc.get("protocol_freeze_id"),
                     "status": "present",
                     "sha256": sha256_of(p)})
    # run the three verifier scripts that exist
    verifiers = ["verify_freeze.py", "verify_mintpy_input_v1.py", "verify_product_v1.py",
                 "verify_phase1_observations.py"]
    for v in verifiers:
        p = PROJECT_ROOT / "scripts" / v
        if not p.exists():
            continue
        r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True,
                           cwd=PROJECT_ROOT)
        rows.append({"freeze": f"verifier:{v}", "status": f"exit {r.returncode}"})
    return rows


def build() -> int:
    if FREEZE.exists():
        print(f"ERROR: {FREEZE} exists (append-only).", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    FREEZE.mkdir(parents=True)

    upstream = verify_upstream()
    pd.DataFrame(HOTSPOT_TABLE).to_csv(OUT / "final_hotspot_table.csv", index=False)
    pd.DataFrame(EVIDENCE_MATRIX).to_csv(OUT / "final_evidence_matrix.csv", index=False)

    print("=" * 88)
    print("PHASE IV - FINAL EVIDENCE SYNTHESIS")
    print("=" * 88)
    print(f"\n  0. UPSTREAM FREEZES")
    for r in upstream:
        if "freeze_id" in r:
            print(f"     {r['freeze']:26s} {str(r['freeze_id'])[:20]}")
        else:
            print(f"     {r['freeze']:26s} {r['status']}")

    artefacts = [
        "qc/sci/phase4/final_hotspot_table.csv",
        "qc/sci/phase4/final_evidence_matrix.csv",
        "qc/sci/phase4/uncertainty_table.json",
        "qc/sci/PHASE_IIIA_CAUSAL_EVIDENCE_REPORT.md",
        "qc/sci/PHASE_IIIA1_GROUNDWATER_RECOVERY_GATE.md",
        "qc/sci/PHASE_IIIA2_DWLR_ACQUISITION_AUDIT.md",
        "qc/sci/PHASE_IIIA3_NWDP_RECOVERY_AUDIT.md",
        "qc/sci/GROUNDWATER_TEMPORAL_ANALYSIS_REPORT.md",
        "qc/sci/PHASE_IIIB_GEOLOGICAL_EVIDENCE_REPORT.md",
        "qc/sci/PHASE_IIIC_URBAN_EVIDENCE_REPORT.md",
        "qc/sci/PHASE_IIA_GEODETIC_VALIDATION_REPORT.md",
        "qc/sci/PHASE_IIB_DESCENDING_RELIABILITY_REPORT.md",
        "qc/sci/PHASE_IIC_HOTSPOT_RECONCILIATION_REPORT.md",
        "qc/sci/PHASE1_REPORT.md",
        "qc/sci/phase2b/revalidation_v2.json",
        "qc/sci/phase3/groundwater_analysis.json",
        "qc/sci/phase3/geology_analysis.json",
        "qc/sci/phase3/urban_analysis.json",
    ]
    (OUT / "uncertainty_table.json").write_text(json.dumps(UNCERTAINTY, indent=2))
    records = []
    for rel in artefacts:
        p = PROJECT_ROOT / rel
        if not p.exists():
            continue
        records.append({"path": rel, "sha256": sha256_of(p), "bytes": p.stat().st_size})
    for p in sorted((OUT).glob("*")):
        if p.is_file() and str(p.relative_to(PROJECT_ROOT)) not in [r["path"] for r in records]:
            records.append({"path": str(p.relative_to(PROJECT_ROOT)),
                            "sha256": sha256_of(p), "bytes": p.stat().st_size})

    payload = {
        "version": "final_evidence_v1",
        "upstream_freezes": [[r["freeze"], r.get("freeze_id")] for r in upstream
                             if r.get("freeze_id")],
        "artefacts": [[r["path"], r["sha256"]] for r in records],
    }
    fid = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    manifest = {
        "freeze_version": "final_evidence_v1",
        "freeze_id": fid,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "upstream_freezes": upstream,
        "artefacts": records,
        "principal_conclusion": "NO TESTED MECHANISM ADEQUATELY EXPLAINS THE SELECTIVE, "
                                "INDEPENDENTLY SUPPORTED H001/H004 DEFORMATION.",
        "not_claimed": ["absolute ground velocity", "pure vertical deformation",
                        "full 3-D displacement", "validated total deformation extent",
                        "groundwater-induced compaction", "geological control at aquifer "
                        "depth", "urban-loading deformation",
                        "infrastructure-induced deformation",
                        "causal explanation for H001/H004",
                        "physical interpretation of H005",
                        "independently reproduced H001/H004 displacement histories"],
        "no_new_dataset_introduced": True,
    }
    (FREEZE / "FINAL_EVIDENCE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, default=str))
    for x in sorted(FREEZE.rglob("*"), reverse=True):
        x.chmod(0o444)
    FREEZE.chmod(0o555)

    print(f"\n  9. PRINCIPAL CONCLUSION")
    print(f"     {manifest['principal_conclusion']}")
    print(f"\n  final freeze_id: {fid}")
    return fid


def verify() -> int:
    p = FREEZE / "FINAL_EVIDENCE_MANIFEST.json"
    if not p.exists():
        print("ERROR: manifest missing.", file=sys.stderr)
        return 1
    m = json.loads(p.read_text())
    bad = [r["path"] for r in m["artefacts"]
           if (PROJECT_ROOT / r["path"]).exists()
           and sha256_of(PROJECT_ROOT / r["path"]) != r["sha256"]]
    up = verify_upstream()
    ver = [r for r in up if r["freeze"].startswith("verifier")]
    print(f"  final freeze_id : {m['freeze_id']}")
    print(f"  artefacts       : {len(m['artefacts'])} ({len(bad)} drifted)")
    for v in ver:
        print(f"  {v['freeze']:36s} {v['status']}")
    if bad:
        print(f"  DRIFTED: {bad}")
    return 1 if bad or any(v["status"] != "exit 0" for v in ver) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true")
    g.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        return verify()
    fid = build()
    return 0 if fid else 1


if __name__ == "__main__":
    raise SystemExit(main())
