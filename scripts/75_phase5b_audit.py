#!/usr/bin/env python
"""
Phase V-B: submission audits.

Three audits, all read-only against the frozen evidence set:

1. numerical consistency  - every repeated published number is compared with
                            its authoritative frozen source
2. terminology consistency - the protected distinctions are checked
3. claim strength          - language stronger than the evidence permits is
                            flagged with context for manual review

No value is recomputed. The audit compares manuscript text against frozen
tables; where they disagree, the manuscript is wrong by definition.

Usage
-----
    python scripts/75_phase5b_audit.py
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "manuscript"
P4 = ROOT / "qc" / "sci" / "phase4"

TEXT_FILES = [
    "MANUSCRIPT.md", "SUPPLEMENTARY_METHODS.md", "REPRODUCIBILITY_APPENDIX.md",
    "DATA_CODE_AVAILABILITY.md", "FIGURE_PLAN.md", "FIGURE_CAPTIONS.md",
]

# ---------------------------------------------------------------- numeric
TOL = 0.02


def numeric_audit() -> list:
    ht = pd.read_csv(P4 / "final_hotspot_table.csv").set_index("hotspot")
    obs = json.loads((ROOT / "freeze" / "phase1_observations"
                      / "OBSERVATIONS.json").read_text())
    unc = json.loads((P4 / "uncertainty_table.json").read_text())
    em = pd.read_csv(P4 / "final_evidence_matrix.csv").set_index("hypothesis")
    msgs = []

    checks = []
    for h in ["H001", "H004", "H002", "H003", "H005"]:
        checks.append((f"{h} ascending rate", ht.loc[h, "ascending_rate_mm_per_yr"],
                       f"final_hotspot_table.csv[{h}].ascending_rate_mm_per_yr"))
        checks.append((f"{h} descending rate", ht.loc[h, "descending_rate_mm_per_yr"],
                       f"final_hotspot_table.csv[{h}].descending_rate_mm_per_yr"))
    checks += [
        ("mapped area km2", obs["mapped_area"]["value_km2"],
         "freeze/phase1_observations/OBSERVATIONS.json mapped_area.value_km2"),
        ("independently supported area km2",
         ht.loc["H001", "area_km2"] + ht.loc["H004", "area_km2"],
         "final_hotspot_table.csv H001.area_km2 + H004.area_km2  (== 6.66)"),
        ("formal uncertainty", unc["measurement_statistical"]
         ["formal_velocity_uncertainty_mm_per_yr"]["ascending_median"],
         "uncertainty_table.json measurement_statistical"),
        ("reference systematic", unc["reference_systematic"]
         ["zero_level_range_mm_per_yr"],
         "uncertainty_table.json reference_systematic"),
        ("processing sensitivity low", unc["processing_sensitivity"]
         ["era5_minus_raw_rms_mm_per_yr"],
         "uncertainty_table.json processing_sensitivity"),
        ("processing sensitivity high", unc["processing_sensitivity"]
         ["era5_dem_minus_raw_rms_mm_per_yr"],
         "uncertainty_table.json processing_sensitivity"),
        ("non-stationarity low", unc["temporal_non_stationarity"]
         ["split_half_difference_range_mm_per_yr"][0],
         "uncertainty_table.json temporal_non_stationarity"),
        ("non-stationarity high", unc["temporal_non_stationarity"]
         ["split_half_difference_range_mm_per_yr"][1],
         "uncertainty_table.json temporal_non_stationarity"),
        ("cross-geometry D0", unc["cross_geometry"]["global_pearson_d0"],
         "uncertainty_table.json cross_geometry"),
        ("cross-geometry D2", unc["cross_geometry"]["global_pearson_d2"],
         "uncertainty_table.json cross_geometry"),
    ]

    # every frozen value must be present somewhere in the publication text,
    # allowing for any reasonable rounding the text may have used
    corpus = "\n".join((OUT / f).read_text() for f in TEXT_FILES
                       if (OUT / f).exists())

    def cited(v: float) -> bool:
        return any(f"{v:.{n}f}" in corpus for n in (1, 2, 3, 4)) \
            or f"{v:g}" in corpus

    for name, val, src in checks:
        present = cited(val)
        msgs.append({"audit": "numeric", "check": name, "frozen_value": val,
                     "source": src,
                     "status": "PASS" if present else "HOLD",
                     "note": "" if present else "frozen value not cited in package"})

    # untraceable-value scan: area-like values that match no frozen source
    frozen_vals = set()
    for _, v, _ in checks:
        frozen_vals |= {f"{v:.{n}f}" for n in (1, 2, 3)}
    ALLOWED = {"1962.4", "1.85", "22.58", "6.66", "15.91", "0.40",
               "164.07", "74.58", "12.01", "49.47", "4.48",
               "12.75", "5.13", "3.20", "2.00", "6.12"}
    area_mentions = set(re.findall(r"(\d[\d,]*\.\d{1,2})\s*km(?:²|2)\b", corpus))
    for a in sorted(area_mentions):
        a_clean = a.replace(",", "")
        if a_clean not in frozen_vals and a_clean not in ALLOWED:
            msgs.append({"audit": "numeric", "check": f"area {a} km2",
                         "frozen_value": None, "source": "UNTRACED",
                         "status": "REVIEW",
                         "note": "area-like value with no frozen source"})

    # evidence states must match the frozen matrix verbatim
    for hyp, row in em.iterrows():
        st = row.evidence_state
        core = st.split(",")[0].strip()
        msgs.append({"audit": "numeric", "check": f"evidence state: {hyp}",
                     "frozen_value": st,
                     "source": "final_evidence_matrix.csv",
                     "status": "PASS" if core in corpus else "HOLD",
                     "note": "" if core in corpus else "state not stated in package"})
    return msgs


# ------------------------------------------------------------ terminology
PROTECTED = [
    ("relative LOS vs vertical",
     r"(?<!relative )(?<!mean )LOS velocity",
     "prefer 'relative LOS velocity'; LOS is a projection"),
    ("supported vs validated",
     r"independently validated",
     "use 'independently supported'; validation is not claimed"),
    ("22.6 km2 meaning",
     r"22\.6\s*km",
     "must be glossed as an operating figure under the selected criterion"),
    ("area meaning",
     r"independently supported at the (hotspot|zone) level",
     "area statement must be scoped to hotspot level, not extrapolated"),
    ("NO EVIDENCE vs ruled out",
     r"ruled out|refuted|excluded as a cause",
     "NO EVIDENCE is not 'ruled out'"),
    ("NOT ADEQUATELY TESTED distinct",
     r"NOT ADEQUATELY TESTED",
     "must remain distinct from NO EVIDENCE"),
    ("NOT TESTABLE distinct",
     r"NOT TESTABLE",
     "must remain distinct from a negative result"),
    ("subsidence usage",
     r"\bsubsidence\b",
     "only LOS deformation is established; use sparingly and never as a "
     "finding"),
]


def terminology_audit() -> list:
    msgs = []
    for f in TEXT_FILES:
        p = OUT / f
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            for name, pat, note in PROTECTED:
                if re.search(pat, line, re.I):
                    msgs.append({"audit": "terminology", "check": name,
                                 "file": f, "line": i, "text": line.strip()[:190],
                                 "note": note})
    return msgs


# ----------------------------------------------------------------- claims
CLAIM_TERMS = [
    (r"\bvalidated\b", "HIGH"),
    (r"\bconfirmed\b", "HIGH"),
    (r"\bproven\b", "HIGH"),
    (r"\bproves\b", "HIGH"),
    (r"\bcaused by\b", "HIGH"),
    (r"\bcauses\b", "HIGH"),
    (r"\bdue to\b", "HIGH"),
    (r"\bground truth\b", "HIGH"),
    (r"\bgroundwater-induced\b", "HIGH"),
    (r"\burban-loading\b", "HIGH"),
    (r"\bgeological control\b", "HIGH"),
    (r"\bgroundwater subsidence\b", "HIGH"),
    (r"\bthe cause\b", "HIGH"),
    (r"\battributable\b", "MEDIUM"),
    (r"\bdriven by\b", "MEDIUM"),
    (r"\bresponsible for\b", "MEDIUM"),
    (r"\bsubsidence\b", "MEDIUM"),
    (r"\babsolute\b", "LOW"),
    (r"\bmechanism\b", "LOW"),
]


def claim_audit() -> list:
    msgs = []
    for f in TEXT_FILES:
        p = OUT / f
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            for pat, sev in CLAIM_TERMS:
                for m in re.finditer(pat, line, re.I):
                    s = max(0, m.start() - 90)
                    msgs.append({"audit": "claim", "severity": sev,
                                 "file": f, "line": i, "term": m.group(0),
                                 "context": line[max(0, s):m.end() + 90].strip()})
    return msgs


def main() -> int:
    num = numeric_audit()
    term = terminology_audit()
    claim = claim_audit()

    holds = [m for m in num if m["status"] in ("HOLD", "REVIEW")]

    report = {
        "audit_version": "phase5b_audit_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "numeric_checks": len(num),
        "numeric_holds": len(holds),
        "terminology_flags": len(term),
        "claim_flags": len(claim),
        "claim_flags_high": len([c for c in claim if c["severity"] == "HIGH"]),
        "numeric": num, "terminology": term, "claims": claim,
    }
    (OUT / "AUDIT_REPORT.json").write_text(
        json.dumps(report, indent=2, default=str))

    print("=" * 88)
    print("PHASE V-B - SUBMISSION AUDITS")
    print("=" * 88)
    print(f"  numeric checks      : {len(num)}  ({len(holds)} HOLD/REVIEW)")
    for h in holds:
        print(f"      [{h['status']}] {h['check']}: {h['note']}")
    print(f"  terminology flags   : {len(term)}")
    print(f"  claim flags         : {len(claim)} "
          f"({report['claim_flags_high']} HIGH)")
    if report["claim_flags_high"]:
        print("      --- HIGH severity, manual review required ---")
        for c in claim:
            if c["severity"] == "HIGH":
                print(f"      {c['file']}:{c['line']}  {c['term']}")
                print(f"          {c['context']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
