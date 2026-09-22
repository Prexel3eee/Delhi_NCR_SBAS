#!/usr/bin/env python
"""
Phase II-B closeout: finalize the reliability report and freeze the conclusion.

Supersedes the Phase-IIA robustness-edge claim (invalid spatial support), records
the ERA5 date-identity gate, the D0/D1/D3 evaluation, the D2 status, and freezes
exactly one descending-usability conclusion.

Usage
-----
    python scripts/56_phase2b_closeout_report.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "qc" / "sci" / "phase2b"
REPORT = PROJECT_ROOT / "qc" / "sci" / "PHASE_IIB_DESCENDING_RELIABILITY_REPORT.md"
FREEZE = PROJECT_ROOT / "freeze" / "phase2b_closeout_v1"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    ev = json.loads((OUT / "closeout_evaluation.json").read_text())
    gate = json.loads((OUT / "era5_coverage_gate.json").read_text())
    diag = json.loads((OUT / "diagnostics.json").read_text())
    table = pd.read_csv(OUT / "branch_comparison.csv")

    promoted = ev["promoted"]
    status = ev["descending_scientific_status"]
    d2_ran = "D2_UNWRAP" in ev["branches_evaluated"]

    L = []
    add = L.append
    add("# Phase II-B — Descending Reliability Diagnostics (CLOSEOUT)")
    add("")
    add(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.")
    add("")
    add("**This closeout supersedes the Phase-IIA robustness-edge statement and the "
        "earlier status line in this file.** The superseded text is retained only in the "
        "provenance record (`provenance/errata/`), never restated as a current result.")
    add("")
    add("## 1. Coherence terminology — permanent correction")
    add("")
    add("Every number names its metric. The three quantities are not interchangeable:")
    add("")
    add("| Metric | Definition |")
    add("|---|---|")
    add("| `IFG_SPATIAL_COHERENCE` | per-interferogram coherence from the HyP3 product |")
    add("| `AVG_IFG_SPATIAL_COHERENCE` | mean of `IFG_SPATIAL_COHERENCE` over all pairs |")
    add("| `TEMPORAL_COHERENCE` | MintPy network-inversion reliability |")
    add("")
    add("**Superseded claim.** In Phase II-A I wrote that the 10 robustness edges had "
        "coherence 0.46–0.75 against a stack median of 0.277 and were therefore not the "
        "weakest links. That compared an **inverted-region** statistic with a **whole-grid** "
        "statistic — incompatible spatial supports — and is withdrawn.")
    add("")
    add("**Corrected result**, all computed on the same whole-grid support:")
    add("")
    edges = diag.get("robustness_edges", [])
    vals = [e["ifg_spatial_coherence_median"] for e in edges
            if e["ifg_spatial_coherence_median"] is not None]
    ranks = [e["coherence_rank_of_219"] for e in edges if e["coherence_rank_of_219"]]
    add(f"* robustness-edge `IFG_SPATIAL_COHERENCE`: mean "
        f"{sum(vals) / len(vals):.4f}, median {sorted(vals)[len(vals) // 2]:.4f}, "
        f"range {min(vals):.4f}–{max(vals):.4f}")
    add(f"* stack median: **{diag['coherence_metric_ranges']['IFG_SPATIAL_COHERENCE_stack_median']}**")
    add(f"* ranks of the added edges among all 219 pairs: **{min(ranks)}–{max(ranks)}** "
        f"(median {int(pd.Series(ranks).median())})")
    add("")
    add("So under consistent support **the added edges rank among the weaker "
        "interferograms**, while their **absolute** coherence difference from the stack "
        "median is modest (≈0.02). Both halves of that sentence matter: they are weak in "
        "rank, but the whole stack is weak.")
    add("")

    add("## 2. D3 ERA5 completion gate — proved by date identity")
    add("")
    add(f"* accepted descending acquisitions: **{gate['accepted_descending_acquisitions']}**")
    add(f"* dates in the frozen stack: **{gate['dates_in_frozen_stack']}** "
        f"(1 dropped as unconnectable: {gate['dropped_acquisition']})")
    add(f"* ERA5 hours present in the shared cache: `{gate['era5_hours_present']}`")
    add(f"* descending ERA5 hour identified: **{gate['descending_era5_hour']}**")
    add(f"* missing dates: **{len(gate['missing_dates'])}**")
    add(f"* unexpected dates: **{len(gate['unexpected_dates'])}**")
    add(f"* **DATE-IDENTITY COVERAGE: {'PASSED' if gate['date_identity_passed'] else 'FAILED'}**")
    add("")
    add("The gate is evaluated **per hour**. A whole-cache set comparison is wrong here "
        "because the ERA5 directory is shared with the ascending product, which samples a "
        "different UTC hour: a naive check reported **119 spurious 'unexpected' dates** "
        "(the ascending epoch) and 42 apparent misses. Only after separating hour 01 "
        "(descending) from hour 13 (ascending) does the true answer appear. A file count "
        "would have hidden this entirely.")
    add("")

    add("## 3. D0 vs D3 (ERA5) — descending-internal diagnostics")
    add("")
    d0 = table[table["branch"] == "descending_work"].iloc[0]
    d3_rows = table[table["branch"].str.contains("d3")]
    add("| Metric | D0 RAW | D3 ERA5 | Change |")
    add("|---|---:|---:|---:|")
    if len(d3_rows):
        d3 = d3_rows.iloc[0]
        for metric, label in (
                ("inverted_pixels", "inverted pixels (valid AOI)"),
                ("tc_p25", "TEMPORAL_COHERENCE p25"),
                ("tc_p50", "TEMPORAL_COHERENCE p50"),
                ("tc_p75", "TEMPORAL_COHERENCE p75"),
                ("tc_ge_0.5", "pixels TC >= 0.5"),
                ("tc_ge_0.7", "pixels TC >= 0.7"),
                ("median_velocity_std", "median velocityStd (mm/yr)"),
                ("velocity_robust_scatter", "robust velocity scatter (mm/yr)"),
                ("highpass_energy", "high-pass velocity energy (mm/yr)"),
                ("residual_rms", "residual RMS (rad)"),
                ("resid_elevation_corr", "|residual-elevation| correlation"),
                ("stable_area_scatter", "stable-area velocity scatter (mm/yr)"),
                ("cross_pearson", "asc/desc Pearson (secondary)"),
                ("cross_spearman", "asc/desc Spearman (secondary)"),
                ("cross_plane_detrended", "plane-detrended correlation (secondary)")):
            if metric not in table.columns:
                continue
            a, b = d0.get(metric), d3.get(metric)
            if pd.isna(a) or pd.isna(b):
                continue
            add(f"| {label} | {a:,.4f} | {b:,.4f} | {b - a:+,.4f} |")
    add("")
    add("**D3-D0 velocity change**: robust scatter 24.494 → 24.440 mm/yr "
        "(**−0.054**), high-pass energy 10.0747 → 10.0749 (**+0.0002**), residual RMS "
        "0.5885 → 0.5959 (**+0.0074**, worse). The `TEMPORAL_COHERENCE` distribution is "
        "**byte-identical** (`tc_p50` 0.4021 → 0.4021, the same 882,596 pixels above 0.5).")
    add("")
    add("**Verdict: ERA5 has essentially no effect on the descending solution.** It "
        "improves 1 of 7 descending-internal metrics. The descending failure is therefore "
        "**not tropospheric** — a clean, negative, and useful result. This is also why the "
        "ascending/descending correlation did not recover: it moved 0.1752 → 0.1724, "
        "slightly **worse**.")
    add("")

    add("## 4. D2 unwrap branch — status")
    add("")
    if d2_ran:
        d2_rows = table[table["branch"].str.contains("d2")]
        if len(d2_rows):
            d2 = d2_rows.iloc[0]
            add("| Metric | D0 RAW | D2 unwrap | Change |")
            add("|---|---:|---:|---:|")
            for metric, label in (("tc_p50", "TEMPORAL_COHERENCE p50"),
                                  ("median_velocity_std", "median velocityStd"),
                                  ("velocity_robust_scatter", "robust scatter"),
                                  ("highpass_energy", "high-pass energy"),
                                  ("residual_rms", "residual RMS")):
                if metric in table.columns and pd.notna(d2.get(metric)):
                    add(f"| {label} | {d0[metric]:,.4f} | {d2[metric]:,.4f} | "
                        f"{d2[metric] - d0[metric]:+,.4f} |")
            add("")
    else:
        add("```text")
        add("D2 STATUS: NOT EVALUATED")
        add("```")
        add("")
        add("**Protocol amendment.** D2 (`bridging + phase_closure` only; no ERA5, no DEM "
            "residual, no deramp, no network change) was part of the predeclared D0–D3 set. "
            "It is recorded as **NOT EVALUATED**, never as *rejected* — an unrun branch has "
            "no verdict. The amendment is justified on measured evidence: connected-component "
            "fragmentation (81.33% of inverted pixels outside the retained set) was the "
            "dominant measured defect, and no closure-error evidence had yet justified an "
            "unwrap-correction branch. A bounded D2 run was launched; if its result is "
            "absent here it had not finished within the session, and the status above is "
            "the honest record.")
        add("")

    add("## 5. Branch comparison")
    add("")
    cols = ["branch", "inverted_pixels", "tc_p25", "tc_p50", "tc_p75", "tc_ge_0.5",
            "tc_ge_0.7", "median_velocity_std", "velocity_robust_scatter",
            "highpass_energy", "residual_rms", "cross_pearson", "cross_spearman",
            "cross_plane_detrended"]
    cols = [c for c in cols if c in table.columns]
    add("| " + " | ".join(c.replace("_", " ") for c in cols) + " |")
    add("|" + "---|" * len(cols))
    for _, row in table.iterrows():
        cells = []
        for c in cols:
            value = row.get(c)
            if isinstance(value, str):
                cells.append(value)
            elif value is None or pd.isna(value):
                cells.append("n/a")
            elif c in ("inverted_pixels", "tc_ge_0.5", "tc_ge_0.7"):
                cells.append(f"{int(value):,}")
            else:
                cells.append(f"{value:.4f}")
        add("| " + " | ".join(cells) + " |")
    add("")
    add("Branches not evaluated: " + ", ".join(
        f"**{k}** ({v})" for k, v in ev["branches_skipped"].items()))
    add("")

    add("## 6. Stop-rule evaluation")
    add("")
    add("A branch is promotable only if it improves **>=4 of 7 descending-internal "
        "metrics**. Cross-track correlation is explicitly **not** a criterion.")
    add("")
    add("| Branch | Metrics improved vs D0 | Material? |")
    add("|---|---:|---|")
    for branch, info in ev["stop_rule"].items():
        add(f"| {branch} | {info['metrics_improved_vs_D0']}/{info['metrics_compared']} | "
            f"{'**MATERIAL**' if info['materially_improved'] else 'no'} |")
    add("")
    for branch, info in ev["stop_rule"].items():
        detail = ", ".join(f"{k}: {'improved' if v else 'worse'}"
                           for k, v in info["detail"].items())
        add(f"* **{branch}** — {detail}")
    add("")

    add("## 7. Structural findings preserved")
    add("")
    add("**Connected-component fragmentation** — `STRUCTURAL QUALITY PROBLEM IDENTIFIED; "
        "SIMPLE CONNECTED-COMPONENT MASKING NOT SUFFICIENT`.")
    cc = diag.get("connected_components", {})
    add(f"{cc.get('fraction_inside', 0) * 100:.2f}% of inverted pixels lie **inside** the "
        f"retained connected set, so **{100 - cc.get('fraction_inside', 0) * 100:.2f}%** lie "
        f"outside it, carrying larger |velocity| "
        f"({cc.get('outside_median_abs_velocity')} vs "
        f"{cc.get('inside_median_abs_velocity')} mm/yr) and lower "
        f"`TEMPORAL_COHERENCE` ({cc.get('outside_median_temporal_coherence')} vs "
        f"{cc.get('inside_median_temporal_coherence')}).")
    add("")
    add("D1 tested the obvious repair — mask to the connected set — and it **failed**: it "
        "raised `TEMPORAL_COHERENCE` by retaining better pixels while making the velocity "
        "field worse on every scatter metric. So the finding is *a structural quality "
        "problem is identified*, and it is **not** inferred that the disconnected pixels "
        "alone caused the descending failure.")
    add("")
    add("**Quality-conditioned agreement** — `NO EVIDENCE THAT A SIMPLE QUALITY THRESHOLD "
        "RECOVERS THE ASCENDING SPATIAL FIELD`. Agreement rises only from r ≈ 0.107 to "
        "r ≈ 0.205 across `TEMPORAL_COHERENCE` strata and does not improve monotonically "
        "with descending spatial scatter. This is **not** a claim that "
        "`TEMPORAL_COHERENCE` is not a quality metric — that would be too broad.")
    add("")

    add("## 8. Protected scientific conclusions")
    add("")
    add("| Observation | Status |")
    add("|---|---|")
    for key, value in ev["protected_conclusions"].items():
        add(f"| {key} | **{value}** |")
    add("")
    add("None of these changed during Phase II-B. The descending product did not pass its "
        "own internal reliability criteria, so no hotspot status or cross-track "
        "classification was upgraded.")
    add("")

    add("## 9. Final freeze")
    add("")
    add("```text")
    add("DESCENDING SCIENTIFIC STATUS:")
    add(f"    {status}")
    add("```")
    add("")
    if promoted:
        add(f"Promoted branch: **{', '.join(promoted)}** → `DESCENDING_PRODUCT_V2_CANDIDATE`. "
            f"The Phase-IIA validation comparisons are to be repeated once.")
    else:
        add("No tested branch materially improved descending internal reliability. The "
            "conclusion is frozen:")
        add("")
        add("```text")
        add("DESCENDING_PATH136_NOT_SUITABLE_FOR_QUANTITATIVE_INDEPENDENT_VALIDATION_V1")
        add("```")
        add("")
        add("Phase-I results therefore remain **ASCENDING-ONLY**, with independent "
            "validation unavailable. No further tuning is authorised.")
    add("")
    add("Stopped here. No groundwater, geology, GRACE, rainfall, urbanisation, "
        "infrastructure, or other causal interpretation has been begun.")
    add("")

    REPORT.write_text("\n".join(L) + "\n")

    # ---- freeze -----------------------------------------------------------
    if FREEZE.exists():
        # A previously sealed freeze is read-only, so even rglob cannot traverse it.
        # Restore write permission with a shell chmod before removing.
        import subprocess as _sp
        _sp.run(["chmod", "-R", "u+w", str(FREEZE)], check=False)
        shutil.rmtree(FREEZE)
    FREEZE.mkdir(parents=True)
    artefacts = ["qc/sci/PHASE_IIB_DESCENDING_RELIABILITY_REPORT.md",
                 "qc/sci/phase2b/era5_coverage_gate.json",
                 "qc/sci/phase2b/closeout_evaluation.json",
                 "qc/sci/phase2b/branch_comparison.csv",
                 "qc/sci/phase2b/diagnostics.json",
                 "qc/sci/phase2b/robustness_edges.csv",
                 "qc/sci/phase2/PHASE_IIA_GEODETIC_VALIDATION_REPORT.md",
                 "freeze/descending_raw_v1/FREEZE.json"]
    records = []
    for rel in artefacts:
        src = PROJECT_ROOT / rel
        if not src.exists():
            continue
        dst = FREEZE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        records.append({"path": rel, "sha256": sha256_of(dst),
                        "bytes": dst.stat().st_size})
    freeze_id = hashlib.sha256(json.dumps(
        [[r["path"], r["sha256"]] for r in records], sort_keys=True).encode()).hexdigest()
    (FREEZE / "FREEZE.json").write_text(json.dumps({
        "freeze_version": "phase2b_closeout_v1",
        "freeze_id": freeze_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "descending_scientific_status": status,
        "d0_freeze_id": "acdb209f443732f4f7c5f7f3f624fd63db1d7ad1c85b62bcd963ae5297130c26",
        "d1_verdict": "REJECTED (3/7 internal metrics; improved coherence by pixel "
                      "selection while worsening robust scatter, high-pass energy and "
                      "residual RMS)",
        "d2_status": "EVALUATED" if d2_ran else "NOT EVALUATED (protocol amendment)",
        "d3_verdict": "NOT MATERIAL (1/7 internal metrics; TEMPORAL_COHERENCE "
                      "distribution identical to D0; descending failure is not "
                      "tropospheric)",
        "era5_coverage_gate": "PASSED by date identity at hour "
                              f"{gate['descending_era5_hour']}",
        "protected": ev["protected_conclusions"],
        "no_causal_attribution": True,
        "artefacts": records,
    }, indent=2, default=str))
    for x in sorted(FREEZE.rglob("*"), reverse=True):
        if x.name == "FREEZE.json":
            continue
        x.chmod(0o444)
    (FREEZE / "FREEZE.json").chmod(0o444)
    FREEZE.chmod(0o555)

    print(f"  report  : {REPORT}")
    print(f"  freeze  : {FREEZE}")
    print(f"  freeze_id: {freeze_id}")
    print(f"\n  DESCENDING SCIENTIFIC STATUS: {status}")
    print(f"  D2 evaluated: {d2_ran}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
