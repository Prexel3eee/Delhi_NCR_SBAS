#!/usr/bin/env python
"""
Phase V-B: figure provenance manifest and caption set.

For every final figure this records the frozen sources, their hashes, the
variables used, the transformations applied, and the output hash, so that
every displayed numerical annotation traces to a frozen source.

No science is performed here. This script reads, hashes and documents.

Usage
-----
    python scripts/74_phase5b_provenance.py
    python scripts/74_phase5b_provenance.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "qc" / "sci" / "phase4" / "figures"
OUT = ROOT / "manuscript"

# freeze that each source path belongs to
FREEZE_OF = {
    "geometry/": "freeze/v1",
    "products/product_v1/": "freeze/product_v1",
    "qc/sci/phase1/": "freeze/phase1_observations",
    "qc/sci/phase2b/": "freeze/phase2b_closeout_v1",
    "qc/sci/phase2c/": "freeze/descending_v2_candidate",
    "qc/sci/phase3/": "freeze/final_evidence_v1",
    "qc/sci/phase4/": "freeze/final_evidence_v1",
}
FREEZE_IDS = {
    "freeze/v1": "cf2bdbfd4fa722dd0df9608afba13bf7cd9361a0897dea14ea70e724c8b1924d",
    "freeze/product_v1": "2a1304e3521f1e176fba7e05",
    "freeze/phase1_observations": "122781a4a81bd49eb4781c76",
    "freeze/phase2b_closeout_v1": "16d36635a06d30182e0e5c84",
    "freeze/descending_v2_candidate": "ba99df90a6f15b3aaaf90fe30",
    "freeze/final_evidence_v1": "db329cf47f4bef92a020056e608decbf95644463f8148570478128d2861c9e88",
}

CAPTIONS = {
    "F1": (
        "**Study design and independent acquisition geometry.** "
        "(A) Frozen coverage geometry for the Delhi-NCR study area (1,962.4 km², EPSG:32643). "
        "Blue denotes the four ascending burst footprints (relative orbit 27, IW2); orange denotes "
        "the four descending footprints (relative orbit 136, IW1); black is the AOI boundary. "
        "The red hatched area is the 28.0 % of the AOI not covered by the descending track — a "
        "western strip containing no classification zone. White circles mark the five zones "
        "(H001–H005), which are small relative to the AOI; north arrow and 20 km scale refer to "
        "the EPSG:32643 projection. "
        "(B) Stack composition. The two stacks share no burst, interferogram, mask or acquisition "
        "list; no pair was selected because it intersected a zone. "
        "*Limitation:* descending coverage is partial, so the descending geometry cannot validate "
        "the entire ascending field."
    ),
    "F2": (
        "**Ascending relative LOS velocity field (authoritative product, RAW-336).** "
        "(A) Mean relative line-of-sight velocity, all 336 interferograms retained, no pair "
        "excluded. Units are mm yr⁻¹. Warm colours indicate motion toward the satellite; blue "
        "indicates motion away; the map display is saturated at ±20 mm yr⁻¹ while the underlying "
        "values are retained. (B) Distribution of the same field on a log count scale; dashed "
        "line is the median. "
        "*Quality mask:* water-masked; non-inverted pixels excluded (validity defined by "
        "velocityStd > 0, not by finiteness, because MintPy fills the non-inverted region with "
        "zeros). "
        "*Uncertainty:* values are **relative** LOS rates, not vertical displacement. The "
        "reference pixel carries a **4.78 mm yr⁻¹ systematic** that offsets the absolute zero "
        "level; spatial gradients are invariant to it. Formal measurement uncertainty is "
        "0.87 mm yr⁻¹; these terms are not combined."
    ),
    "F3": (
        "**Cross-geometry classification of the five zones.** Grouped mean relative LOS rates by "
        "zone and viewing geometry: ascending (solid blue) and descending (hatched orange). Units "
        "are mm yr⁻¹. The strip beneath the axis encodes the frozen cross-geometry status. "
        "*Sample definition:* mean rate over each zone's pixels within the 854,004-pixel final "
        "common valid domain. "
        "*Branches:* ascending = RAW-336; descending = unwrap-corrected candidate. "
        "*Limitation:* ascending and descending are separate LOS geometries and are never "
        "converted to vertical displacement here. H001/H004 are independently supported at the "
        "spatial and mean-rate level; H002/H003 are not reproduced; H005 is a cross-geometry "
        "contradiction."
    ),
    "F4": (
        "**Cross-track agreement and the selectivity of reproduction.** "
        "(A) Cross-track agreement between ascending and unwrap-corrected descending velocity, for "
        "the raw descending branch (D0) and the unwrap-corrected branch (D2). "
        "**These are retained aggregate agreement statistics over 854,321 shared-domain pixels — "
        "not a pixel-level scatter.** Paired per-pixel values were not retained in the frozen "
        "evidence set, so no scatter is shown and none has been synthesised. "
        "(B) Fraction of each ascending zone's area overlapped by a descending-detected component. "
        "*Quality mask:* common valid domain of both stacks. "
        "*Limitation:* agreement is moderate and spatially heterogeneous, not global; a "
        "plane-detrended coefficient is given because a long-wavelength offset remains between "
        "geometries."
    ),
    "F5": (
        "**Zones independently supported by the descending geometry (H001 and H004).** "
        "(A) Mean relative LOS rate by geometry; bars as in F3. (B) Ratio of descending to "
        "ascending magnitude; dashed line is exact agreement. "
        "*Units:* mm yr⁻¹ (A), dimensionless ratio (B). "
        "*What is reproduced:* the spatial pattern, the mean rate and the amplitude ratio. "
        "*What is NOT reproduced:* the detailed displacement histories — see F8. "
        "*Area statement:* 6.66 km² is the area of Phase-I zones independently supported at the "
        "zone level by the descending geometry. It is not a validated extent, is not extrapolated "
        "beyond these zones, and is not a vertical displacement rate."
    ),
    "F6": (
        "**H002 and H003 — negative controls.** Mean relative LOS rate by geometry for the two "
        "ascending zones that were not reproduced, alongside the one reproduced zone of comparable "
        "magnitude. Units are mm yr⁻¹. \"Matched-band contrast\" is the ascending contrast computed "
        "in a common temporal-coherence band. "
        "**H001 is omitted from this panel for plotting scale only:** at −30.9 / −36.0 mm yr⁻¹ it "
        "would compress the comparison shown here. It is reported in F5 and is not selectively "
        "excluded. "
        "*Quality:* the descending geometry is adequate at both controls (temporal coherence 0.900 "
        "and 0.886), so their absence is not a quality artefact. "
        "Any explanation acting across the affected terrain predicts all three zones similarly, "
        "and therefore fails on selectivity."
    ),
    "F7": (
        "**H005 — unresolved cross-geometry contradiction.** Mean relative LOS rate by geometry. "
        "Units are mm yr⁻¹. "
        "*Sample definition:* common-domain pixels within the H005 polygon. "
        "The two geometries disagree in both sign and magnitude, so this is not a reproduction "
        "failure but an active contradiction. H005 is retained in the main text as an unresolved "
        "result. No explanation for the contradiction is offered, and none is claimed."
    ),
    "F8": (
        "**Cumulative totals and the scope of independent reproduction.** "
        "(A) Retained total cumulative LOS displacement over the full stack by geometry; units are "
        "mm. **Per-epoch cumulative series were not retained in the frozen evidence set and are NOT "
        "reconstructed.** (B) Which characteristics are and are not independently reproduced. "
        "*Key limitation:* independent reproduction extends to the **spatial and mean-rate** "
        "characteristics only. The ascending and descending H001 cumulative series differ "
        "substantially (ascending −120.7 mm against descending +1.1 mm; detrended cross-geometry "
        "correlation r = 0.007). The descending series carries large opposing jumps."
    ),
    "F9": (
        "**Groundwater temporal forcing — lag and falsification diagnostic.** "
        "(A) Spearman ρ between the groundwater depth anomaly and the LOS series as a function of "
        "the lag applied to groundwater, per zone. Negative lags (grey field) are **falsification "
        "tests**, in which deformation leads groundwater; positive lags test the causal direction. "
        "(B) Mean |ρ| for forward against falsification lags. "
        "*Sample definition:* NWDP six-hourly depth-to-water telemetry, station-anomaly composited "
        "to daily medians; zones are H001, H004, H002 and H003 only — H005 has no groundwater "
        "composite and is absent. "
        "*Sign convention:* the protocol predicts a **negative** association (deeper groundwater → "
        "more negative LOS). "
        "*Significance:* circular block permutation, 90-day blocks; 0 of 16 forward-lag tests "
        "survive Benjamini–Hochberg FDR q = 0.05 (all permutation p ≥ 0.49). "
        "*Limitation:* this is **not** a refutation of groundwater as a mechanism. Aquifer "
        "metadata, well depths and screened intervals are unavailable, the H001 network has ~78-day "
        "outages and only two stations, and LOS is not vertical displacement."
    ),
    "F10": (
        "**Shallow substrate texture — direction opposite to prediction.** Clay at 0–5 cm (A) and "
        "100–200 cm (B), and sand at 0–5 cm (C), by zone. Units are % by mass. Dashed line is the "
        "AOI-minus-zones background. "
        "*Dataset:* SoilGrids v2.0 (ISRIC), 250 m, sampled on its native grid and never resampled "
        "to the 40 m InSAR grid. "
        "*Critical limitation:* this is a **shallow soil-texture surrogate**, not a geological "
        "map. It samples the upper ~2 m only and does not observe the compaction interval; "
        "lithology, formation and age are not identified. Deep geological / aquifer-system "
        "susceptibility is therefore **NOT ADEQUATELY TESTED**, not exonerated. "
        "H005 is shown for completeness and is not part of the supported/control contrast. The "
        "supported zones carry −5.0 percentage points less clay and +6.4 points more sand than the "
        "controls, opposite to the fine-sediment direction the hypothesis predicts."
    ),
    "F11": (
        "**Built intensity — a shared setting that does not discriminate.** "
        "(A) Built fraction from ESA WorldCover 2021; (B) built surface from JRC GHSL "
        "GHS-BUILT-S E2020. Dashed lines are AOI-minus-zones backgrounds. "
        "*Sample definition:* polygons rasterised onto each **source** grid (10 m and ~93 m); no "
        "coarse product was resampled to 40 m. "
        "All four classification zones are heavily built (70–79 %) against a 33.7 % AOI "
        "background. That is a genuine shared characteristic and precisely why it fails as an "
        "explanation: it **describes the common urban setting but does not separate the supported "
        "zones from the controls**. H001 and H002 rank differently between the two products, so the "
        "discriminator is not robust. "
        "*Limitation:* GHSL 2020→2025 built-up change is exactly zero at H001–H004, but post-2020 "
        "GHSL epochs are projections rather than observations, so this is an absence of detected "
        "change rather than a measured absence. No loading is estimated: height, footprint, "
        "construction type and foundation are unavailable."
    ),
    "F12": (
        "**Competing-hypothesis evidence matrix (frozen).** Evidence state assigned to each "
        "preregistered hypothesis. Swatches encode the category; the three categories are distinct "
        "and are never collapsed. "
        "**NO EVIDENCE** = a suitable test was conducted and did not support the hypothesis. "
        "**NOT ADEQUATELY TESTED** = available evidence does not observe the relevant physical "
        "domain. **NOT TESTABLE** = the necessary dataset was unavailable. "
        "None of these is equivalent to \"ruled out\", and no composite score is formed across "
        "rows. Grades are reproduced verbatim from the frozen evidence matrix."
    ),
}


def sha256_of(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as h:
        for c in iter(lambda: h.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def freeze_for(rel: str) -> str:
    for pre, fz in FREEZE_OF.items():
        if rel.startswith(pre):
            return fz
    return "UNMAPPED"


REGISTRY = {
    "F1": {
        "title": "Study design and independent acquisition geometry",
        "script": "scripts/73_phase5b_restyle.py::fig1",
        "sources": ["geometry/aoi.geojson", "geometry/selected_bursts.geojson",
                    "geometry/descending/selected_bursts.geojson",
                    "geometry/descending/coverage_report.json",
                    "qc/sci/phase1/hotspots_corrected.geojson"],
        "variables": ["AOI polygon", "ascending burst footprints",
                      "descending burst footprints", "zone polygons",
                      "descending coverage fraction"],
        "transformations": ["reproject to EPSG:32643",
                            "geometric difference: AOI minus descending union"],
        "statistics_displayed": ["descending AOI coverage 72.0 %",
                                 "uncovered area 28.0 %"],
    },
    "F2": {
        "title": "Ascending relative LOS velocity",
        "script": "scripts/73_phase5b_restyle.py::fig2",
        "sources": ["products/product_v1/los_velocity_mm_per_yr.tif"],
        "variables": ["per-pixel mean relative LOS velocity"],
        "transformations": ["raster mask applied", "histogram binning"],
        "statistics_displayed": ["median velocity", "distribution"],
    },
    "F3": {
        "title": "Cross-geometry classification of the five zones",
        "script": "scripts/73_phase5b_restyle.py::fig3",
        "sources": ["qc/sci/phase4/final_hotspot_table.csv"],
        "variables": ["ascending_rate_mm_per_yr", "descending_rate_mm_per_yr",
                      "cross_geometry_status"],
        "transformations": ["none"],
        "statistics_displayed": ["mean rate per zone per geometry"],
    },
    "F4": {
        "title": "Cross-track agreement and the selectivity of reproduction",
        "script": "scripts/73_phase5b_restyle.py::fig4",
        "sources": ["qc/sci/phase2b/revalidation_v2.json"],
        "variables": ["agreement_v1_phase2a.{pearson,spearman,plane_detrended}",
                      "agreement_v2.{pearson,spearman,plane_detrended}",
                      "hotspots[].overlap_fraction"],
        "transformations": ["none"],
        "statistics_displayed": ["aggregate cross-track agreement",
                                 "zone overlap fraction"],
        "explicit_restriction": "aggregate retained statistics only; "
                                "no pixel-level scatter, none synthesised",
    },
    "F5": {
        "title": "Zones independently supported by the descending geometry",
        "script": "scripts/73_phase5b_restyle.py::fig5",
        "sources": ["qc/sci/phase4/final_hotspot_table.csv"],
        "variables": ["ascending_rate_mm_per_yr", "descending_rate_mm_per_yr"],
        "transformations": ["ratio of descending to ascending magnitude"],
        "statistics_displayed": ["magnitude ratios 1.16 / 0.87"],
    },
    "F6": {
        "title": "H002 and H003 - negative controls",
        "script": "scripts/73_phase5b_restyle.py::fig6",
        "sources": ["qc/sci/phase4/final_hotspot_table.csv"],
        "variables": ["ascending_rate_mm_per_yr", "descending_rate_mm_per_yr"],
        "transformations": ["none"],
        "statistics_displayed": ["matched-band contrasts -12.13 / -11.60 / -10.93"],
        "explicit_exclusion": "H001 omitted for plotting scale only; reported in F5",
    },
    "F7": {
        "title": "H005 - unresolved cross-geometry contradiction",
        "script": "scripts/73_phase5b_restyle.py::fig7",
        "sources": ["qc/sci/phase4/final_hotspot_table.csv"],
        "variables": ["ascending_rate_mm_per_yr", "descending_rate_mm_per_yr"],
        "transformations": ["none"],
        "statistics_displayed": ["H005 rates -14.21 / +61.39"],
    },
    "F8": {
        "title": "Cumulative totals and the scope of independent reproduction",
        "script": "scripts/73_phase5b_restyle.py::fig8",
        "sources": ["qc/sci/phase2c/hotspot_reconciliation.json"],
        "variables": ["temporal.<zone>.ascending_total_mm",
                      "temporal.<zone>.descending_total_mm",
                      "temporal.H001.pearson_detrended"],
        "transformations": ["none"],
        "statistics_displayed": ["retained cumulative endpoint totals"],
        "explicit_restriction": "per-epoch series not retained; NOT reconstructed",
    },
    "F9": {
        "title": "Groundwater temporal forcing - lag and falsification diagnostic",
        "script": "scripts/72_phase5b_figures.py::fig9",
        "sources": ["qc/sci/phase3/groundwater_lag_results.csv",
                    "qc/sci/phase3/groundwater_control_comparison.csv"],
        "variables": ["lag_days", "spearman", "p_block", "role",
                      "mean_positive_rho", "mean_negative_rho"],
        "transformations": ["absolute value of mean rho for panel B"],
        "statistics_displayed": ["lag correlations", "forward vs falsification |rho|"],
    },
    "F10": {
        "title": "Shallow substrate texture",
        "script": "scripts/72_phase5b_figures.py::fig10",
        "sources": ["qc/sci/phase3/geology_hotspot_summary.csv"],
        "variables": ["clay_0-5cm", "clay_100-200cm", "sand_0-5cm"],
        "transformations": ["none"],
        "statistics_displayed": ["zone mean texture percentages"],
        "report_transcribed_constants": {
            "background_clay_0-5cm": 22.76,
            "background_clay_100-200cm": 24.64,
            "background_sand_0-5cm": 43.92,
            "source": "qc/sci/PHASE_IIIB_GEOLOGICAL_EVIDENCE_REPORT.md, "
                      "section 3 substrate summary table (AOI minus all zones)",
        },
    },
    "F11": {
        "title": "Built intensity",
        "script": "scripts/72_phase5b_figures.py::fig11",
        "sources": ["qc/sci/phase3/urban_hotspot_summary.csv"],
        "variables": ["wc_builtfrac_2021", "ghsl_2020", "ghsl_change"],
        "transformations": ["none"],
        "statistics_displayed": ["zone built fraction and built surface"],
        "report_transcribed_constants": {
            "background_worldcover_built_pct": 33.74,
            "background_ghsl_built_surface": 225.0,
            "source": "qc/sci/PHASE_IIIC_URBAN_EVIDENCE_REPORT.md, section C "
                      "U1 table (AOI minus zones)",
        },
    },
    "F12": {
        "title": "Competing-hypothesis evidence matrix",
        "script": "scripts/73_phase5b_restyle.py::fig12",
        "sources": ["qc/sci/phase4/final_evidence_matrix.csv"],
        "variables": ["hypothesis", "evidence_state"],
        "transformations": ["none"],
        "statistics_displayed": ["frozen evidence grades"],
    },
}

CAP_FOR = {
    "F1": "F01_study_design", "F2": "F02_ascending_velocity",
    "F3": "F03_hotspot_classification",
    "F4": "F04_cross_geometry_agreement",
    "F5": "F05_supported_features", "F6": "F06_negative_controls",
    "F7": "F07_H005_contradiction", "F8": "F08_rate_vs_history",
    "F9": "F09_groundwater_falsification", "F10": "F10_soil_texture",
    "F11": "F11_urban_intensity", "F12": "F12_evidence_matrix",
}


def build() -> int:
    recs = []
    for fid, meta in REGISTRY.items():
        stem = CAP_FOR[fid]
        srcs = []
        for rel in meta["sources"]:
            p = ROOT / rel
            fz = freeze_for(rel)
            srcs.append({
                "path": rel,
                "exists": p.exists(),
                "sha256": sha256_of(p) if p.exists() else None,
                "bytes": p.stat().st_size if p.exists() else None,
                "freeze": fz,
                "freeze_id": FREEZE_IDS.get(fz, None),
            })
        outs = []
        for ext in ("png", "pdf"):
            op = FIGS / f"{stem}.{ext}"
            if op.exists():
                outs.append({"path": str(op.relative_to(ROOT)),
                             "sha256": sha256_of(op),
                             "bytes": op.stat().st_size})
        recs.append({
            "figure_id": fid,
            "title": meta["title"],
            "caption": CAPTIONS[fid],
            "sources": srcs,
            "source_freeze": sorted({s["freeze"] for s in srcs}),
            "variables_used": meta["variables"],
            "transformations_applied": meta["transformations"],
            "statistics_displayed": meta["statistics_displayed"],
            "report_transcribed_constants": meta.get("report_transcribed_constants"),
            "explicit_exclusion": meta.get("explicit_exclusion"),
            "explicit_restriction": meta.get("explicit_restriction"),
            "script": meta["script"],
            "outputs": outs,
            "manually_edited": False,
            "rendering": "fully scripted; no manual or vector-editor editing",
        })

    manifest = {
        "manifest_version": "figure_provenance_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "every_displayed_value_traces_to_frozen_source": True,
            "unretained_samples_not_synthesised": True,
            "manual_editing_of_scientific_values": False,
            "cosmetic_vector_edits_permitted": "only if data geometry and "
                                               "labels are unchanged; none performed",
        },
        "figures": recs,
    }
    (OUT / "FIGURE_PROVENANCE.json").write_text(
        json.dumps(manifest, indent=2, default=str))

    # ---- captions ----
    L = ["# Figure Captions", "",
         "Each caption is self-contained: geometry/branch, units, quality mask, "
         "sample definition, uncertainty meaning, exclusions and limitations are "
         "stated where relevant. No caption contains a causal interpretation.", ""]
    for fid in [f"F{i}" for i in range(1, 13)]:
        L += [f"## {fid} — {REGISTRY[fid]['title']}", "", CAPTIONS[fid], "",
              f"*Source data:* "
              + ", ".join(f"`{s}`" for s in REGISTRY[fid]["sources"]),
              "", f"*Rendered by:* `{REGISTRY[fid]['script']}`", ""]
    (OUT / "FIGURE_CAPTIONS.md").write_text("\n".join(L) + "\n")

    missing = [(r["figure_id"], s["path"]) for r in recs
               for s in r["sources"] if not s["exists"]]
    print("=" * 88)
    print("PHASE V-B - FIGURE PROVENANCE")
    print("=" * 88)
    print(f"  figures documented     : {len(recs)}")
    print(f"  source files hashed    : {sum(len(r['sources']) for r in recs)}")
    print(f"  output files hashed    : {sum(len(r['outputs']) for r in recs)}")
    print(f"  missing source files   : {len(missing)}")
    for f, p in missing:
        print(f"      MISSING {f}: {p}")
    print(f"  unmapped freezes       : "
          f"{sorted({s['freeze'] for r in recs for s in r['sources'] if s['freeze'] == 'UNMAPPED'})}")
    return 0


def verify() -> int:
    p = OUT / "FIGURE_PROVENANCE.json"
    if not p.exists():
        print("ERROR: FIGURE_PROVENANCE.json missing.")
        return 1
    m = json.loads(p.read_text())
    bad = []
    for r in m["figures"]:
        for o in r["outputs"]:
            fp = ROOT / o["path"]
            if not fp.exists() or sha256_of(fp) != o["sha256"]:
                bad.append(o["path"])
    print(f"  figures        : {len(m['figures'])}")
    print(f"  outputs drifted: {len(bad)}")
    for b in bad:
        print(f"      DRIFT {b}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true")
    g.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    return verify() if a.verify else build()


if __name__ == "__main__":
    raise SystemExit(main())
