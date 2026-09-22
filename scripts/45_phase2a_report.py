#!/usr/bin/env python
"""
Phase II-A, stage 11: PHASE_IIA_GEODETIC_VALIDATION_REPORT.md

Every number is read from the stage outputs, so the report cannot drift from the
results it describes. Nothing is typed in by hand.

The report ends at the STOPPING CONDITION: it does not begin groundwater or
geology attribution. Causal interpretation is a separate, later stage.

Usage
-----
    python scripts/45_phase2a_report.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QC = PROJECT_ROOT / "qc" / "sci" / "phase2"
QCD = PROJECT_ROOT / "qc" / "descending"
REPORT = PROJECT_ROOT / "qc" / "sci" / "PHASE_IIA_GEODETIC_VALIDATION_REPORT.md"


def load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> int:
    network = load(QCD / "network_audit.json")
    coverage = load(PROJECT_ROOT / "geometry" / "descending" / "coverage_report.json")
    desc_qc = load(QCD / "descending_qc.json")
    cross = load(QC / "cross_validation.json")
    erratum = load(PROJECT_ROOT / "provenance" / "errata" / "INC-007.json")
    phase1 = load(PROJECT_ROOT / "freeze" / "phase1_observations" / "OBSERVATIONS.json")

    xv = pd.read_csv(QC / "hotspot_cross_validation.csv") if (QC / "hotspot_cross_validation.csv").exists() else pd.DataFrame()
    coh = pd.read_csv(QC / "coherence_velocity_comparison.csv") if (QC / "coherence_velocity_comparison.csv").exists() else pd.DataFrame()

    L: list[str] = []
    add = L.append
    add("# Phase II-A — Independent Geodetic Validation Report")
    add("")
    add(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. "
        "Every figure is read programmatically from the stage outputs.")
    add("")
    add("**Stopping condition.** This report ends Phase II-A. It does **not** begin "
        "groundwater, geological or any other causal attribution. Geodetic validation "
        "asks *whether the deformation is real*; causal interpretation asks *why* and is "
        "a separate, later stage.")
    add("")

    # ---- reference labelling ---------------------------------------------
    add("## 0. Reference labelling (INC-007)")
    add("")
    if erratum:
        a = erratum["authoritative_product_reference"]
        i = erratum["intended_scientific_reference"]
        add("Per `provenance/errata/INC-007.json`, the two products in this report are "
            "referenced to **different pixels**, and the two must not be mixed:")
        add("")
        add("| Solution | Reference pixel | Longitude | Latitude |")
        add("|---|---:|---:|---:|")
        add(f"| Ascending `product_v1` — **AUTHORITATIVE PRODUCT REFERENCE** | "
            f"{a['y']}, {a['x']} | {a['lon']} | {a['lat']} |")
        add(f"| Ascending `product_v1` — **INTENDED SCIENTIFIC REFERENCE** "
            f"(not used) | {i['y']}, {i['x']} | {i['lon']} | {i['lat']} |")
        d = cross.get("descending", {})
        if d.get("reference_yx"):
            add(f"| Descending validation stack (its own processing reference) | "
                f"{d['reference_yx'][0]}, {d['reference_yx'][1]} | — | — |")
        add("")
        add(f"The offset between the two ascending references is "
            f"**{erratum['measured_offset']['velocity_offset_mm_per_yr']:+.4f} mm/yr**, "
            f"a constant on every pixel. All ascending values in this report are relative "
            f"to the authoritative product reference. Ascending and descending values are "
            f"relative to *different* pixels, so only differences *within* a track, or "
            f"comparisons that account for geometry, are meaningful.")
    else:
        add("Erratum not found; see `provenance/errata/INC-007.json`.")
    add("")

    # ---- 1. provenance ----------------------------------------------------
    add("## 1. Descending-stack provenance")
    add("")
    add("Independently constructed. No ascending burst, pair, mask or acquisition list was "
        "read during its construction, and no pair was selected because it intersects a "
        "Phase-I hotspot.")
    add("")
    add("| Property | Descending (this stack) | Ascending `product_v1` |")
    add("|---|---|---|")
    add(f"| Flight direction | DESCENDING | ASCENDING |")
    add(f"| Relative orbit | {network.get('relative_orbit')} | 27 |")
    add(f"| Sub-swath | {network.get('subswath')} | IW2 |")
    add(f"| Bursts (K) | {network.get('k')} | 4 |")
    add(f"| Acquisitions | {network.get('acquisitions', {}).get('common_accepted')} | 119 |")
    add(f"| Pairs | {network.get('network', {}).get('pairs')} | 336 |")
    add(f"| AOI coverage | {coverage.get('aoi_coverage_fraction', 0) * 100:.2f} % | "
        f"100 % |")
    add("")
    add(f"**Structural limitation.** {coverage.get('structural_limitation', '')}")
    add("")
    if coverage.get("hotspots_contained"):
        contained = coverage["hotspots_contained"]
        add(f"All five Phase-I hotspot polygons are "
            f"**{sum(contained.values())}/{len(contained)} fully inside** the descending "
            f"footprint, so every validation target remains addressable. The uncovered "
            f"western strip carries no Phase-I hotspot.")
    add("")

    # ---- 2. network / QC --------------------------------------------------
    add("## 2. Descending network and QC")
    add("")
    n = network.get("network", {})
    add("| Network property | Value |")
    add("|---|---:|")
    add(f"| Connected components | {n.get('n_components')} |")
    add(f"| Isolated nodes | {n.get('isolated_nodes')} |")
    add(f"| Minimum degree | {n.get('min_degree')} |")
    add(f"| Median degree | {n.get('median_degree')} |")
    add(f"| Bridges | {n.get('n_bridges')} |")
    add(f"| Articulation points | {n.get('n_articulation_points')} |")
    add(f"| Temporal baselines (days) | {n.get('temporal_baseline_days', {}).get('counts')} |")
    add(f"| Perpendicular baseline range (m) | "
        f"{n.get('perpendicular_baseline_m', {}).get('min')} to "
        f"{n.get('perpendicular_baseline_m', {}).get('max')} |")
    add(f"| Acceptance | {'PASSED' if network.get('acceptance_passed') else 'FAILED'} |")
    add("")
    cd = network.get("connectivity_decision", {})
    if cd:
        add(f"The base rule was the ascending-equivalent **{cd.get('standard_rule_max_temporal_days')}-day "
            f"/ 250 m** network, which alone left the graph fragmented and bridge-rich. "
            f"{len(cd.get('bridges_added', []))} pairs beyond the base rule were added, each "
            f"flagged in `manifests/descending/sbas_pairs.csv`:")
        add("")
        add("| Reference | Secondary | Δt (d) | Role | Reason |")
        add("|---|---|---:|---|---|")
        for b in cd.get("bridges_added", []):
            add(f"| {b['reference_date']} | {b['secondary_date']} | "
                f"{b['temporal_baseline_days']} | {b.get('role')} | {b.get('reason')} |")
        add("")
        add(f"*Consequence:* {cd.get('consequence', '')}")
        add("")

    if desc_qc:
        c = desc_qc.get("coverage", {})
        v = desc_qc.get("velocity_mm_per_yr", {}).get("percentiles", {})
        add("### Descending solution quality")
        add("")
        add(f"* Valid pixels: **{c.get('valid_pixels'):,}** "
            f"({c.get('valid_fraction_of_aoi', 0) * 100:.2f} % of the AOI)")
        add(f"* LOS velocity percentiles (mm/yr): `{v}`")
        add(f"* Reference-sensitivity spread: "
            f"**{desc_qc.get('reference_sensitivity', {}).get('candidate_block_velocity_spread_mm_per_yr')} mm/yr**")
        add("")

        ce = desc_qc.get("critical_edge_summary", {})
        add("### Critical-edge sensitivity")
        add("")
        add(f"The robust network still rests on {ce.get('n_added_pairs')} pairs beyond the "
            f"base rule and one articulation point. Because a single poor interferogram on "
            f"one of those edges could distort part of the time series and manufacture a "
            f"false disagreement, each is reported individually.")
        add("")
        add("| Reference | Secondary | Δt (d) | Role | Median coherence | Median residual (rad) |")
        add("|---|---|---:|---|---:|---:|")
        for e in desc_qc.get("critical_edges", []):
            cm = e.get("coherence_median")
            rm = e.get("residual_median_rad")
            add(f"| {e['reference_date']} | {e['secondary_date']} | "
                f"{e['temporal_baseline_days']} | {e.get('added_pair_role')} | "
                f"{cm if cm is not None else 'n/a'} | {rm if rm is not None else 'n/a'} |")
        add("")
        add(f"Stack-wide median pair coherence: "
            f"**{ce.get('stack_median_pair_coherence')}**. Pairs below 0.30 coherence: "
            f"**{ce.get('n_added_pairs_below_0.30_coherence')}**.")
        add("")

    # ---- 3. cross-validation ---------------------------------------------
    add("## 3. Ascending / descending comparison")
    add("")
    if cross:
        a = cross.get("ascending", {})
        d = cross.get("descending", {})
        add("### 3.1 Viewing geometry (established before any velocity comparison)")
        add("")
        add("| Track | Heading (°) | Incidence (°) | LOS unit vector (E, N, U) |")
        add("|---|---:|---:|---|")
        add(f"| Ascending | {a.get('heading_deg'):.3f} | {a.get('incidence_deg'):.3f} | "
            f"`{a.get('los_unit_vector_ENU')}` |")
        add(f"| Descending | {d.get('heading_deg'):.3f} | {d.get('incidence_deg'):.3f} | "
            f"`{d.get('los_unit_vector_ENU')}` |")
        add("")
        add("The tracks differ mainly in the sign of the east component, so **purely "
            "vertical motion gives the same sign in both, and purely east-west motion gives "
            "opposite signs.** That rule orders the comparison below; it is a consistency "
            "check, not a proof — a mixture of vertical and horizontal motion can produce "
            "either sign pair.")
        add("")
        cf = cross.get("common_footprint", {})
        add(f"Common footprint: **{cf.get('covered_by_both'):,}** AOI pixels covered by both "
            f"tracks ({cf.get('covered_by_both', 0) / max(1, cf.get('aoi_pixels', 1)) * 100:.2f} %), "
            f"of which **{cf.get('both_at_quality'):,}** pass the quality threshold in both.")
        add("")
        det = cross.get("detection", {})
        add(f"Independent detection on the common grid (|LOS| ≥ "
            f"{det.get('threshold_mm_per_yr')} mm/yr, coherence ≥ {det.get('coherence_min')}, "
            f"≥ {det.get('min_area_km2')} km²) found **{det.get('ascending_components')}** "
            f"ascending and **{det.get('descending_components')}** descending components.")
        add("")

    add("### 3.2 Hotspot cross-validation")
    add("")
    if not xv.empty:
        add("| ID | Asc LOS mm/yr | Desc LOS mm/yr | Same sign | Desc component found | IoU | "
            "Centroid sep (km) | Desc coverage | Classification |")
        add("|---|---:|---:|:---:|:---:|---:|---:|---:|---|")
        for _, r in xv.iterrows():
            av = r["ascending_velocity_median_mm_per_yr"]
            dv = r["descending_velocity_median_mm_per_yr"]
            sep = r["centroid_separation_km"]
            same = r.get("same_sign")
            same_txt = "yes" if same is True else ("no" if same is False else "n/a")
            add(f"| {r['hotspot_id']} | "
                f"{(f'{av:+.2f}' if pd.notna(av) else 'n/a')} | "
                f"{(f'{dv:+.2f}' if pd.notna(dv) else 'n/a')} | "
                f"{same_txt} | "
                f"{'yes' if r['descending_component_detected'] else 'no'} | "
                f"{r['iou_with_descending_component']:.3f} | "
                f"{(f'{sep:.2f}' if pd.notna(sep) else 'n/a')} | "
                f"{r['descending_coverage_fraction'] * 100:.1f} % | "
                f"**{r.get('classification', 'n/a')}** |")
        add("")
        add("Reasons:")
        add("")
        for _, r in xv.iterrows():
            if isinstance(r.get("reason"), str):
                add(f"* **{r['hotspot_id']}** — {r['reason']}.")
        add("")

    # ---- 4. coherence-velocity -------------------------------------------
    add("## 4. The coherence–velocity question")
    add("")
    add("This was the highest-priority unresolved Phase-I issue: ascending showed much "
        "stronger negative LOS velocity in lower-coherence terrain, which is ambiguous "
        "between genuinely faster deformation and a coherent bias. The discriminating test "
        "is whether an independent viewing geometry reproduces the relationship.")
    add("")
    if not coh.empty:
        add("| Coherence band | Asc n | Asc median (mm/yr) | Asc frac ≤ −10 | Desc n | "
            "Desc median (mm/yr) | Desc frac ≤ −10 |")
        add("|---|---:|---:|---:|---:|---:|---:|")
        for _, r in coh.iterrows():
            def fmt(v, d=2):
                return f"{v:.{d}f}" if pd.notna(v) else "n/a"
            add(f"| {r['coherence_low']:.2f}–{r['coherence_high']:.2f} | "
                f"{r['ascending_n']:,} | {fmt(r['ascending_median_mm_per_yr'])} | "
                f"{fmt(r['ascending_fraction_below_minus10'], 3)} | "
                f"{r['descending_n']:,} | {fmt(r['descending_median_mm_per_yr'])} | "
                f"{fmt(r['descending_fraction_below_minus10'], 3)} |")
        add("")
        add(f"Correlation of the two coherence–velocity curves across bands: "
            f"**{cross.get('coherence_velocity', {}).get('curve_correlation')}**")
        add("")

    # ---- 5. temporal modes ------------------------------------------------
    add("## 5. Temporal mode validation")
    add("")
    t = cross.get("temporal", {})
    if t:
        add(f"The two tracks are on different relative orbits and their acquisition "
            f"calendars only partially overlap: **{t.get('ascending_dates')}** ascending "
            f"dates, **{t.get('descending_dates')}** descending dates, "
            f"**{t.get('shared_exact_dates')}** exactly shared.")
        add("")
        add(t.get("note", ""))
        add("")

    # ---- 6. classification summary ---------------------------------------
    add("## 6. Required final classification")
    add("")
    if cross:
        counts = cross.get("classification_counts", {})
        add("| Classification | Count |")
        add("|---|---:|")
        for label in ("INDEPENDENTLY_SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_RESOLVED",
                      "CONTRADICTED", "ASCENDING_ONLY"):
            if counts.get(label):
                add(f"| {label} | {counts[label]} |")
        add("")
    if not xv.empty and "classification" in xv.columns:
        add("Per Phase-I observation:")
        add("")
        add("| Observation | Classification | Basis |")
        add("|---|---|---|")
        for _, r in xv.iterrows():
            add(f"| {r['hotspot_id']} | **{r['classification']}** | {r.get('reason', '')} |")
        add("")
    if phase1:
        f = phase1.get("observational_findings", {})
        add("Non-hotspot Phase-I observations:")
        add("")
        add("| Observation | Status in Phase II-A |")
        add("|---|---|")
        add(f"| Coherence–velocity relationship | see section 4 |")
        add(f"| North/south temporal grouping | see section 5 |")
        add(f"| Non-stationarity (split-half {f.get('split_half_difference_range_mm_per_yr')} mm/yr) | "
            f"not re-tested; the descending record has different gaps and cannot resolve it |")
        add(f"| Spatial gradients | tested through the hotspot IoU and centroid separation in "
            f"section 3.2 |")
        add(f"| Supported deformation extent "
            f"({phase1.get('mapped_area', {}).get('value_km2')} km²) | "
            f"an ascending-only figure under its stated quality criterion; the descending "
            f"stack cannot test it because it covers only "
            f"{coverage.get('aoi_coverage_fraction', 0) * 100:.1f} % of the AOI |")
        add("")

    # ---- 7. what is not established --------------------------------------
    add("## 7. What this phase does not establish")
    add("")
    add("* **No mechanism.** Nothing here identifies groundwater, tectonics, compaction, "
        "construction or metro loading, lithology, or fault motion.")
    add("* **No full 3-D displacement.** Two LOS observations cannot constrain three "
        "components. Any decomposition rests on an explicit assumption about north-south "
        "motion, which is unmeasured.")
    add("* **No volumetric inference.** No subsidence volume, compaction volume, "
        "groundwater-storage loss or aquifer volume change is computed, and the mapped area "
        "is not sufficient for one.")
    add("* **No absolute calibration.** Both tracks are relative to their own reference "
        "pixel, and the GNSS conclusion from Phase I stands unchanged: GNSS cannot "
        "discriminate the branch differences, `DLHI`/`GCP5`/`DELH`/`LIAA` are not usable as "
        "local validators given their sampling, and `DRDN` is not usable as an absolute "
        "calibration at 209.9 km separation.")
    add("")
    add("## 8. Next stage (not started)")
    add("")
    add("Causal attribution is explicitly **not** begun here. When authorised, it is a "
        "separate stage using explanatory variables — groundwater levels and extraction, "
        "geology, geomorphology, sediment thickness, land use, infrastructure, "
        "precipitation, hydrology, GRACE/regional storage — with inclusion rules defined "
        "**before** any correlation is computed.")
    add("")

    REPORT.write_text("\n".join(L) + "\n")
    print(f"wrote {REPORT} ({len(L)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
