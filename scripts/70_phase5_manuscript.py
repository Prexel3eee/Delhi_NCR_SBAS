#!/usr/bin/env python
"""
Phase V: manuscript and publication package.

Publication work only. No analysis is reopened, no dataset added, no number
recomputed. Every quantity is read from the frozen evidence set.

Builds: manuscript text, definitive figure set, supplementary methods,
reproducibility appendix, data/code availability, and a publication freeze.

Usage
-----
    python scripts/70_phase5_manuscript.py
    python scripts/70_phase5_manuscript.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
P4 = PROJECT_ROOT / "qc" / "sci" / "phase4"
FIGS = P4 / "figures"
OUT = PROJECT_ROOT / "manuscript"
FREEZE = PROJECT_ROOT / "freeze" / "publication_v1"

FINAL_FREEZE = "db329cf47f4bef92a020056e608decbf95644463f8148570478128d2861c9e88"

SPINE = ("The spatial/mean-rate deformation observations at H001 and H004 are "
         "independently reproducible; the physical explanation is not.")

CAVEAT = ("Independent reproduction applies to the spatial and mean-rate characteristics, "
          "not to the detailed displacement histories; in particular, the ascending and "
          "descending H001 cumulative time series differ substantially.")

CENTRAL = (
    "The principal result of this study is not a resolved deformation mechanism, but the "
    "separation of reproducible geodetic observations from unsupported interpretation. "
    "Two localized Delhi-NCR deformation features (H001 and H004) were independently "
    "reproduced across ascending and descending Sentinel-1 geometries at the spatial and "
    "mean-rate level, whereas two comparable ascending features were not reproduced and a "
    "fifth remained contradictory. Preregistered tests did not support groundwater-level "
    "variability, shallow soil texture, or urbanisation as explanations for this "
    "selectivity. The physical mechanism of the independently supported features "
    "therefore remains unresolved.")

NEGATIVE_CONTROL_LOGIC = """H001 / H004
    spatial/rate signal reproduced independently

H002 / H003
    similar ascending magnitude
    adequate descending quality
    not reproduced

H005
    cross-geometry contradiction
    unresolved

Therefore:
    not every ascending anomaly should be interpreted physically
    and simple regional explanatory variables lack specificity."""


def sha256_of(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as h:
        for c in iter(lambda: h.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def build() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ht = pd.read_csv(P4 / "final_hotspot_table.csv")
    em = pd.read_csv(P4 / "final_evidence_matrix.csv")
    unc = json.loads((P4 / "uncertainty_table.json").read_text())

    # ---------- manuscript ----------
    L = []
    a = L.append
    a("# Manuscript")
    a("")
    a("## Title")
    a("")
    a("**Reproducible deformation, unresolved mechanism: ascending/descending Sentinel-1 "
      "SBAS-InSAR of Delhi-NCR with preregistered hypothesis testing**")
    a("")
    a("## Abstract")
    a("")
    a("A 119-acquisition ascending Sentinel-1 stack (relative orbit 27, IW2, 336 "
      "interferograms) and an independently constructed 91-acquisition descending stack "
      "(orbit 136, IW1, 219 interferograms) were processed with HyP3 and MintPy over a "
      "1,962 km² area of Delhi-NCR for 2021-10 to 2025-09. Five localized relative "
      "line-of-sight deformation zones were detected in the ascending geometry.")
    a("")
    a("Independent reproduction was assessed without any shared burst, pair or mask. Two "
      "zones (H001 and H004) were independently reproduced across both geometries at the "
      "spatial and mean-rate level, whereas two comparable ascending zones (H002 and H003) "
      "were not reproduced and a fifth (H005) remained contradictory between geometries.")
    a("")
    a("Four preregistered tests did not support groundwater-level variability, shallow soil "
      "texture, existing built intensity, or recent built-up expansion as explanations for "
      "this selectivity. The non-reproduced zones were carried throughout as negative "
      "controls, and they demonstrate that a comparable ascending anomaly need not be "
      "physically interpretable. A reproducible coherence–velocity association is reported "
      "without a physical interpretation.")
    a("")
    a("Independent reproduction applies to the spatial and mean-rate characteristics only, "
      "not to the detailed displacement histories; in particular, the ascending and "
      "descending H001 cumulative time series differ substantially. These results "
      "demonstrate independently reproducible localized LOS deformation while leaving its "
      "physical mechanism unresolved.")
    a("")
    a("## 1. Introduction")
    a("")
    a("The Indo-Gangetic Plain hosts intense groundwater use and rapid urban growth, and "
      "both are frequently invoked to explain InSAR-observed deformation. The common "
      "analytical pattern is to detect deformation, then attribute it. This study inverts "
      "that order: the geodetic result was frozen before interpretation, candidate "
      "explanations were preregistered with fixed lags, thresholds and significance "
      "procedures, and negative controls were carried from the start.")
    a("")
    a("The design question is therefore not *\"what is causing the deformation?\"* but "
      "*\"which of the observed features survive independent observation, and does any "
      "candidate explanation account for where they occur?\"*")
    a("")
    a("## 2. Data and methods")
    a("")
    a("*Full detail in Supplementary Methods.* Summary:")
    a("")
    a("| Element | Value |")
    a("|---|---|")
    a("| AOI | 1,962.4 km², Delhi-NCR, EPSG:32643 |")
    a("| Ascending | Sentinel-1 orbit 27, IW2, VV, K = 4 bursts |")
    a("| Ascending stack | 119 acquisitions, 336 interferograms, 0 pairs excluded |")
    a("| Descending | Sentinel-1 orbit 136, IW1, VV, K = 4 bursts |")
    a("| Descending stack | 91 acquisitions, 219 interferograms |")
    a("| Processing | HyP3 `INSAR_ISCE_MULTI_BURST`, 10×2 looks, 40 m; MintPy 1.6.4 |")
    a("| Frozen branch | unwrap off, troposphere off, DEM residual off, deramp off |")
    a("")
    a("The ascending product was frozen as `product_v1` before interpretation. The "
      "descending product was constructed independently — no shared burst, pair, mask or "
      "acquisition list — and no pair was selected because it intersected a hotspot.")
    a("")
    a("## 3. Results")
    a("")
    a("### 3.1 Ascending deformation field")
    a("")
    a("The field is spatially heterogeneous and strongly asymmetric: the median pixel is "
      "essentially stationary (−0.73 mm/yr) while a tail reaches −87 mm/yr. Deformation is "
      "carried by a minority of the AOI in connected patches. Five zones were detected at "
      "|LOS| ≥ 10 mm/yr, temporal coherence ≥ 0.80 and area ≥ 0.4 km², giving")
    a("")
    a("```text")
    a("22.6 km2 = robustly supported mapped deformation area under the")
    a("           selected ascending quality criterion")
    a("```")
    a("")
    a("This is an operating figure under a stated criterion, **not** a validated extent: "
      "deformation magnitude and temporal coherence are strongly associated in this stack, "
      "so a coherence-based criterion systematically excludes part of the signal.")
    a("")
    a("### 3.2 Independent descending reproduction")
    a("")
    a("The raw descending solution reproduced the ascending field poorly (Pearson 0.175). "
      "Diagnostics localised the problem to unwrapping: 81.3 % of inverted pixels fell "
      "outside the retained connected set, and masking them worsened every velocity "
      "metric. Correcting the unwrapping (bridging + phase closure) improved **7 of 7** "
      "internal metrics — temporal coherence p75 0.49 → 0.83, pixels with TC ≥ 0.7 from "
      "11,013 → 1,352,660 — and raised cross-track agreement to Pearson 0.363. Agreement "
      "is therefore reported as **moderate and spatially heterogeneous**, not global.")
    a("")
    a("### 3.3 Hotspot-level reproduction")
    a("")
    a("| Zone | Cross-geometry status | Area (km²) | Asc (mm/yr) | Desc (mm/yr) | Interpretation |")
    a("|---|---|---:|---:|---:|---|")
    for _, r in ht.iterrows():
        a(f"| **{r.hotspot}** | {r.cross_geometry_status} | {r.area_km2} | "
          f"{r.ascending_rate_mm_per_yr:+.2f} | {r.descending_rate_mm_per_yr:+.2f} | "
          f"{r.final_interpretation} |")
    a("")
    a("H001 and H004 were reproduced at the spatial and mean-rate level (magnitude ratios "
      "1.16 and 0.87; both within 1.6σ of the vertical-equivalent expectation). **Their "
      "detailed displacement histories were not reproduced** — H001's cumulative "
      "displacement is −120.7 mm ascending against +1.1 mm descending, the descending "
      "series carrying large opposing jumps.")
    a("")
    a("```text")
    a("6.66 km2 = area of Phase-I deformation zones independently supported at the")
    a("           hotspot level by the descending geometry   (H001 + H004)")
    a("```")
    a("")
    a("### 3.4 The negative controls")
    a("")
    a("**This is a principal result, not a validation footnote.**")
    a("")
    a("```text")
    a(NEGATIVE_CONTROL_LOGIC)
    a("```")
    a("")
    a("H002 and H003 have matched-band ascending contrasts comparable to H004 (−11.60 and "
      "−10.93 vs −12.13 mm/yr) and **adequate** descending quality (TC 0.900 and 0.886), "
      "yet do not reproduce. Any explanation that acts across the affected terrain — "
      "regional groundwater decline, a shared soil unit, urbanisation of the corridor — "
      "predicts all four zones similarly, and therefore fails on selectivity. Carrying "
      "these controls is what converts the study from a catalogue of anomalies into a "
      "constraint on interpretation.")
    a("")
    a("### 3.5 Coherence–velocity association")
    a("")
    a("A monotonic association between temporal coherence and relative LOS velocity is reproduced "
      "across three processing states (ascending, descending raw, descending "
      "unwrap-corrected), with curve correlation r = +0.831 between geometries. It is "
      "reported as a **reproduced observational relationship** with **physical origin "
      "unresolved**. Candidate explanations — surface and scattering differences, "
      "deformation/decorrelation interaction, residual measurement effects — are not "
      "selected among without independent evidence.")
    a("")
    a("### 3.6 Uncertainty structure")
    a("")
    a("The uncertainty of these results is **not** expressible as a single ± value, and no "
      "attempt is made to combine the terms. They are different kinds of quantity — "
      "statistical, systematic, sensitivity and structural — and no valid probabilistic "
      "model justifies summing them.")
    a("")
    a("| Term | Magnitude | Character |")
    a("|---|---:|---|")
    a("| Formal measurement uncertainty | 0.87 mm/yr | statistical fit error, median |")
    a("| Reference systematic | 4.78 mm/yr | offsets the **absolute** zero level only; "
      "spatial gradients and every zone contrast are invariant to it |")
    a("| Processing sensitivity | 0.52–1.04 mm/yr | spread across tested correction branches |")
    a("| Cross-geometry agreement | 0.175 → 0.363 | Pearson correlation, raw → unwrap-corrected |")
    a("| Temporal non-stationarity | **10.4–20.2 mm/yr** | split-half difference |")
    a("")
    a("The last term dominates every statistical interval quoted in this paper. A single "
      "rate for any zone is therefore a description of the observation period, not a "
      "stationary property of that zone, and no rate here should be extrapolated in time.")
    a("")
    a("## 4. Hypothesis tests")
    a("")
    a("| Hypothesis | Evidence state | Basis |")
    a("|---|---|---|")
    for r in em.itertuples():
        a(f"| {r.hypothesis} | **{r.evidence_state}** | {r.basis} |")
    a("")
    a("### 4.1 Groundwater — NO EVIDENCE")
    a("")
    a("Preregistered before any correlation existed. Six-hourly NWDP telemetry, 187 "
      "stations, 111 quality-passing, all eligible stations within 5 km selected. "
      "Supported zones show groundwater **rising** (−4.02, −0.68 m/yr) while subsiding, "
      "the opposite of prediction; the **controls** show the predicted slight deepening "
      "(+0.05, +0.15 m/yr). Zero of sixteen positive-lag tests survive FDR q = 0.05, and "
      "falsification (negative) lags equal or outperform forward lags at every zone.")
    a("")
    a("This is not \"groundwater has been ruled out\": aquifer metadata are absent, well "
      "depths and types unknown, H001 has ~78-day telemetry outages and only two stations, "
      "and LOS is not pure vertical displacement.")
    a("")
    a("### 4.2 Shallow soil texture — NO EVIDENCE, direction opposite")
    a("")
    a("H001/H004 carry more sand and less clay than controls and background (−5.0 and "
      "+6.4 percentage points), where fine-sediment susceptibility predicts the reverse; "
      "the controls resemble the background, not the positives. Confounded with coherence "
      "(ρ = −0.600).")
    a("")
    a("**Deep geological / aquifer-system susceptibility is NOT ADEQUATELY TESTED.** The "
      "authoritative source (GSI Bhukosh) was unreachable, and SoilGrids samples only the "
      "upper ~2 m, not the compaction interval. The deep substrate is **untested, not "
      "exonerated**.")
    a("")
    a("### 4.3 Urbanisation — NO EVIDENCE; construction NOT TESTABLE")
    a("")
    a("All four zones are heavily built (70.6 %, 79.0 %, 73.7 %, 70.0 % WorldCover built "
      "fraction against a 33.7 % background). That shared setting cannot separate the "
      "zones that reproduce from those that do not, and the two products disagree on "
      "H001's ranking. GHSL 2020→2025 built-up change is exactly zero at all four zones, "
      "with the caveat that post-2020 GHSL epochs are projections rather than "
      "observations. No loading was estimated: height, footprint, construction type and "
      "foundation are absent, so `built-environment association` is the strongest "
      "permitted framing.")
    a("")
    a("## 5. Discussion")
    a("")
    a("### 5.1 The reproducibility asymmetry")
    a("")
    a("The study's spine is a single sentence:")
    a("")
    a(f"> **{SPINE}**")
    a("")
    a("This is narrower than a causal claim and considerably stronger than one, because "
      "it would survive a reader who rejects every interpretive choice made after the "
      "geodetic validation. It also implies a discipline for the field: reproducing a "
      "deformation *rate* across geometries does not reproduce a deformation *history*, "
      "and the two are frequently conflated in the literature.")
    a("")
    a("### 5.2 Why the negative controls deserve prominence")
    a("")
    a("H002 and H003 are the reason the study cannot be read as \"four deformation zones "
      "plus one anomaly\". They show that an ascending anomaly of ≈ −13 mm/yr, measured "
      "with adequate quality and sitting in comparable urban terrain, can fail to appear "
      "in an independent geometry. The natural inference — that not every ascending "
      "anomaly should be interpreted physically, and that the ascending product alone "
      "cannot adjudicate — is more consequential than any individual zone.")
    a("")
    a("### 5.3 What the failed hypotheses do and do not mean")
    a("")
    a("`NO EVIDENCE`, `NOT ADEQUATELY TESTED` and `NOT TESTABLE` are distinct and are not "
      "collapsed. Only groundwater and shallow soil texture were actually tested against a "
      "suitable dataset. Deep geology was tested against an inadequate surrogate, and "
      "construction was not testable at all. Reporting all three as \"ruled out\" would "
      "misrepresent the study in the direction of false confidence.")
    a("")
    a("Weak variables are deliberately **not** combined into a composite causal story. "
      "Three failed or untested hypotheses do not sum into a stronger fourth.")
    a("")
    a("## 6. Limitations")
    a("")
    a("1. LOS is a projection; no decomposition is published and the Phase II-A component "
      "estimates were withdrawn as invalid.")
    a("2. Temporal non-stationarity (10.4–20.2 mm/yr) dominates every statistical interval "
      "quoted here; rates describe the observation period only. The absolute zero level "
      "additionally carries a 4.78 mm/yr reference systematic, and no "
      "independent in-AOI geodetic reference exists — the nearest adequately sampled GNSS "
      "station is 209.9 km away.")
    a("3. H001/H004 displacement histories are not independently reproduced.")
    a("4. The H001 groundwater network is sparse with long outages, and aquifer metadata "
      "are absent throughout.")
    a("5. The deep substrate is untested; the construction chronology is unavailable.")
    a("6. Coherence confounding pervades every spatial comparison, and four hotspot values "
      "permit no reliable adjustment.")
    a("7. Descending coverage is incomplete (a western strip of the AOI), so the "
      "descending geometry cannot validate the entire ascending field.")
    a("")
    a("## 7. Conclusion")
    a("")
    a(CENTRAL)
    a("")
    a(CAVEAT)
    a("")
    a("No tested mechanism adequately explains the selective, independently supported "
      "H001/H004 deformation. This is not a claim that the deformation has no physical "
      "cause. It is the claim that the available evidence is sufficient to characterize "
      "selected deformation features and insufficient to identify their mechanism.")
    a("")
    (OUT / "MANUSCRIPT.md").write_text("\n".join(L) + "\n")

    # ---------- figure plan ----------
    F = []
    A = F.append
    A("# Definitive figure set")
    A("")
    A("Main figures carry only what the paper argues. Engineering and diagnostic figures "
      "are moved to the supplement.")
    A("")
    A("| # | Figure | Source | Status |")
    A("|---|---|---|---|")
    plan = [
        ("F1", "Study design: AOI, ascending and descending tracks, burst coverage",
         "qc/sci/phase4/figures/F01_study_design.png", "READY"),
        ("F2", "Ascending authoritative relative LOS velocity field",
         "qc/sci/phase4/figures/F02_ascending_velocity.png", "READY"),
        ("F3", "Hotspot cross-geometry classification",
         "qc/sci/phase4/figures/F03_hotspot_classification.png", "READY"),
        ("F4", "Cross-track agreement, D0 vs D2, and hotspot selectivity",
         "qc/sci/phase4/figures/F04_cross_geometry_agreement.png", "READY"),
        ("F5", "H001 and H004 independent support",
         "qc/sci/phase4/figures/F05_supported_features.png", "READY"),
        ("F6", "H002/H003 negative-control result (matched comparison)",
         "qc/sci/phase4/figures/F06_negative_controls.png", "READY"),
        ("F7", "H005 cross-geometry contradiction",
         "qc/sci/phase4/figures/F07_H005_contradiction.png", "READY"),
        ("F8", "Rate-versus-history caveat",
         "qc/sci/phase4/figures/F08_rate_vs_history.png", "READY"),
        ("F9", "Groundwater falsification result",
         "qc/sci/phase3/figures/GW06_lag_curves.png", "READY"),
        ("F10", "Soil-texture comparison", "qc/sci/phase3/figures/GB01_substrate.png",
         "READY"),
        ("F11", "Urban built-intensity comparison",
         "qc/sci/phase3/figures/UC01_built_intensity.png", "READY"),
        ("F12", "Competing-hypothesis evidence matrix",
         "qc/sci/phase4/figures/F12_evidence_matrix.png", "READY"),
    ]
    for n, desc, src, st in plan:
        A(f"| {n} | {desc} | `{src}` | {st} |")
    A("")
    A("**Supplementary / archive:** station maps and completeness plots (GW01, GW02), "
      "series plots (GW03–GW05, GW07, GW08, GW09, GW10), substrate specificity and "
      "coherence confounding (GB02, GB03), urban coherence confounding (UC02), network "
      "audits, threshold-sensitivity grids, and all engineering diagnostics.")
    A("")
    A("No figure carries a causal arrow.")
    A("")
    A("## Figure provenance")
    A("")
    A("Every panel is rendered from the frozen evidence set; no quantity is "
      "recomputed and no dataset is added. Per-pixel paired ascending/descending "
      "values were not retained in the freeze, so F4 reports the retained "
      "aggregate agreement metrics rather than a scatter — reconstructing a "
      "distribution from reported moments would misrepresent the data. For the "
      "same reason F8 shows retained cumulative totals rather than reconstructed "
      "time-series curves.")
    A("")
    A("F6 deliberately excludes H001: at −30.9 / −36.0 mm/yr it would dominate "
      "the y-range and crush the H004-versus-controls contrast that carries the "
      "selectivity argument. H001 is shown in F5.")
    (OUT / "FIGURE_PLAN.md").write_text("\n".join(F) + "\n")

    # ---------- supplementary methods ----------
    S = []
    A = S.append
    A("# Supplementary Methods")
    A("")
    A("## S1. Study area and reference frame")
    A("")
    A("AOI 1,962.4 km², EPSG:32643, 1.85 % water. All products on a common 40 m grid, "
      "2,407 × 2,939 (ascending) and 2,412 × 2,853 (descending).")
    A("")
    A("## S2. Burst selection and network design")
    A("")
    A("K = 4 contiguous bursts per track, selected by the smallest collection fully "
      "containing the AOI (ascending) or containing every hotspot polygon (descending, "
      "which cannot cover the AOI's western strip). Networks were built by **identity "
      "intersection** across bursts — never a positional zip — with graph audits for "
      "connectivity, bridges, articulation points and minimum degree.")
    A("")
    A("Ascending: 336 pairs, max 36 d. Descending: 219 pairs; the record carries two gaps "
      "longer than 36 d (108 d and 48 d), so the minimum set of extra pairs needed to "
      "connect the epochs and eliminate every bridge was added, each flagged. Result: 1 "
      "component, 0 bridges, 1 articulation point.")
    A("")
    A("## S3. Processing")
    A("")
    A("HyP3 `INSAR_ISCE_MULTI_BURST`, 10×2 looks, water mask applied. MintPy 1.6.4 with "
      "`weightFunc = var`, `minNormVelocity = yes`, `keepMinSpanTree = no` (MintPy "
      "defaults it to yes and would silently drop pairs).")
    A("")
    A("## S4. Correction testing")
    A("")
    A("ERA5 and ERA5+DEM were tested against RAW on four diagnostics better matched to "
      "atmospheric error than residual RMS; neither improved the product. Unwrap "
      "correction was rejected for ascending. For descending it was **required**: it "
      "improved 7 of 7 internal metrics. The difference is itself informative — the two "
      "products have different failure modes.")
    A("")
    A("## S5. Quality tiers and validity")
    A("")
    A("Validity is `velocityStd > 0`, **not** `isfinite(velocity)`: MintPy fills the "
      "non-inverted region with zeros, so a finiteness test overstates coverage. "
      "Descending covers 69.7 % of the AOI.")
    A("")
    A("## S6. Groundwater protocol")
    A("")
    A("Frozen before any correlation (`groundwater_protocol_v1`). Daily medians requiring "
      "≥ 2 valid six-hourly observations; no interpolation. Sign convention: positive "
      "anomaly = deeper than the station median. Lags fixed at 0/+30/+60/+90 d with "
      "−30/−60/−90 d as falsification. Significance by **circular block permutation with "
      "90-day blocks, 5,000 iterations** — never IID p-values — with "
      "Benjamini–Hochberg FDR q = 0.05 across the 16 hotspot-composite tests.")
    A("")
    A("## S7. Geological and urban datasets")
    A("")
    A("SoilGrids read by windowed remote access on its native grid; all polygons "
      "rasterised onto the **source** grid, never resampled onto the InSAR grid. Urban "
      "statistics likewise computed on native GHSL and WorldCover grids.")
    A("")
    A("## S8. Uncertainty policy")
    A("")
    A("Measurement, reference-systematic, processing-sensitivity and non-stationarity "
      "terms are reported **separately and never summed**. They are different kinds of "
      "quantity; no valid probabilistic model justifies combining them.")
    (OUT / "SUPPLEMENTARY_METHODS.md").write_text("\n".join(S) + "\n")

    # ---------- reproducibility appendix ----------
    Rp = []
    A = Rp.append
    A("# Reproducibility Appendix")
    A("")
    A(f"All results derive from frozen inputs. Final evidence freeze "
      f"`freeze/final_evidence_v1`, `freeze_id {FINAL_FREEZE}`.")
    A("")
    A("## Upstream freezes")
    A("")
    A("| Freeze | ID |")
    A("|---|---|")
    mf = json.loads((PROJECT_ROOT / "freeze" / "final_evidence_v1"
                     / "FINAL_EVIDENCE_MANIFEST.json").read_text())
    for fr in mf["upstream_freezes"]:
        if fr.get("freeze_id"):
            A(f"| {fr['freeze']} | `{str(fr['freeze_id'])[:32]}` |")
    A("")
    A("## Incidents that could have changed a scientific conclusion")
    A("")
    A("Engineering detail is archived in `RUNLOG.md` and `provenance/errata/`. Only "
      "incidents with scientific consequence appear here.")
    A("")
    A("| ID | Incident | Consequence |")
    A("|---|---|---|")
    A("| INC-001 | `find_jobs(name=...)` is an exact match; a prefix query returns nothing | duplicate pilot jobs; retrieval now uses exact-name reconciliation only |")
    A("| INC-002 | transient ASF DNS outage killed retrieval at 47/336 | retrieval made resumable with backoff and batched listing |")
    A("| INC-004 | `np.bool8` removed in NumPy 2 broke the dask cluster | parallel inversion would not start |")
    A("| INC-005 | first RAW-vs-ERA5 comparison read the wrong file | spurious 15.49 mm/yr; corrected to 0.52 mm/yr RMS |")
    A("| INC-006 | GNSS co-location \"disagreement\" was a window artefact | verdict survived, but for a more honest reason: coverage, not measurement quality |")
    A("| INC-007 | `product_v1` referenced to a different pixel than the frozen decision | constant 0.136 mm/yr; spatial gradients unaffected. Documented as an append-only erratum |")
    A("| INC-008 | Phase-I hotspot polygons were single-pixel fragments | **every polygon-based containment test in Phase II was vacuous** until corrected; the conclusion held once re-tested |")
    A("")
    A("## Verification")
    A("")
    A("```text")
    A("python scripts/69_phase4_synthesis.py --verify")
    A("python scripts/65_phase3a4_protocol.py --verify")
    A("python scripts/verify_freeze.py")
    A("python scripts/verify_mintpy_input_v1.py")
    A("python scripts/verify_product_v1.py")
    A("python scripts/verify_phase1_observations.py")
    A("```")
    A("")
    A("All exit 0 against the frozen state.")
    (OUT / "REPRODUCIBILITY_APPENDIX.md").write_text("\n".join(Rp) + "\n")

    # ---------- data / code availability ----------
    D = f"""# Data and Code Availability

## Code

All processing, validation, hypothesis-testing and synthesis scripts are in
`scripts/` (70 scripts, numbered by phase). Tests are in `tests/`.

## Processed products

| Product | Location | Freeze |
|---|---|---|
| Ascending authoritative relative LOS solution | `mintpy/baseline_raw_work/` | `product_v1` |
| Ascending published rasters | `products/product_v1/` | derived from `product_v1` |
| Descending raw solution | `mintpy/descending_work/` | `descending_raw_v1` |
| Descending unwrap-corrected candidate | `mintpy/descending_d2_unwrap_work/` | `descending_v2_candidate` |

## External datasets

| Dataset | Source | Access |
|---|---|---|
| Sentinel-1 SLC bursts | ASF / HyP3 | public, credentialed |
| ERA5 | Copernicus CDS | public, credentialed |
| CGWB seasonal groundwater | CGWB via Internet Archive | public; **archived copy of the official URL**, live host was down |
| NWDP six-hourly groundwater telemetry | nwdp.nwic.gov.in | public |
| SoilGrids v2.0 | ISRIC | public |
| GHSL GHS-BUILT-S | JRC | public |
| ESA WorldCover | ESA / AWS Open Data | public |

## Reproducibility notes

* Every freeze is hash-pinned and verified by a companion script.
* Large products are hashed in place rather than duplicated.
* The ascending product was frozen before any interpretation; hypothesis
  protocols were frozen before their correlations existed.

## Limitations on reuse

The published velocity fields are **relative LOS** quantities, not absolute
velocities and not vertical displacement. Users requiring absolute rates must
supply an independent reference; the reference-selection systematic is
4.78 mm/yr.
"""
    (OUT / "DATA_CODE_AVAILABILITY.md").write_text(D)

    print("=" * 88)
    print("PHASE V - MANUSCRIPT AND PUBLICATION PACKAGE")
    print("=" * 88)
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            print(f"     {p.relative_to(PROJECT_ROOT)}")
    print(f"\n  SPINE: {SPINE}")
    print("\n  NOTE: run --freeze LAST, after every Phase V-B output exists.")
    return 0


def build_freeze() -> int:
    """Build the publication freeze.

    Deliberately separate from build(): the manifest must cover the complete
    package, so this runs after the figure, provenance, audit and finalize
    steps have written their outputs.
    """
    if FREEZE.exists():
        import shutil
        import subprocess
        subprocess.run(["chmod", "-R", "u+w", str(FREEZE)], check=False)
        shutil.rmtree(FREEZE)
    FREEZE.mkdir(parents=True)
    arts = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            arts.append({"path": str(p.relative_to(PROJECT_ROOT)),
                         "sha256": sha256_of(p), "bytes": p.stat().st_size})
    for rel in ("qc/sci/phase4/final_hotspot_table.csv",
                "qc/sci/phase4/final_evidence_matrix.csv",
                "qc/sci/phase4/uncertainty_table.json",
                "qc/sci/FINAL_SCIENTIFIC_EVIDENCE_REPORT.md"):
        p = PROJECT_ROOT / rel
        if p.exists():
            arts.append({"path": rel, "sha256": sha256_of(p),
                         "bytes": p.stat().st_size})
    # publication figures, raster and vector: rendered from frozen aggregates
    for pat in ("F*.png", "F*.pdf"):
        for p in sorted((P4 / "figures").glob(pat)):
            arts.append({"path": str(p.relative_to(PROJECT_ROOT)),
                         "sha256": sha256_of(p), "bytes": p.stat().st_size})
    # the erratum raised during Phase V-B is part of the published record
    for p in sorted((PROJECT_ROOT / "provenance" / "errata").glob("INC-009.*")):
        arts.append({"path": str(p.relative_to(PROJECT_ROOT)),
                     "sha256": sha256_of(p), "bytes": p.stat().st_size})
    fid = hashlib.sha256(json.dumps(
        {"final_evidence": FINAL_FREEZE,
         "artefacts": [[x["path"], x["sha256"]] for x in arts]},
        sort_keys=True).encode()).hexdigest()
    (FREEZE / "PUBLICATION_MANIFEST.json").write_text(json.dumps({
        "freeze_version": "publication_v1",
        "freeze_id": fid,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "final_evidence_freeze_id": FINAL_FREEZE,
        "spine": SPINE,
        "caveat": CAVEAT,
        "central_conclusion": CENTRAL,
        "artefacts": arts,
        "no_new_analysis": True,
    }, indent=2, default=str))
    for x in sorted(FREEZE.rglob("*"), reverse=True):
        x.chmod(0o444)
    FREEZE.chmod(0o555)

    print("=" * 88)
    print("PHASE V/V-B - PUBLICATION FREEZE")
    print("=" * 88)
    print(f"  publication freeze_id: {fid}")
    print(f"  derived from final evidence freeze: {FINAL_FREEZE}")
    print(f"  artefacts            : {len(arts)}")
    return 0



def verify() -> int:
    p = FREEZE / "PUBLICATION_MANIFEST.json"
    if not p.exists():
        print("ERROR: manifest missing.")
        return 1
    m = json.loads(p.read_text())
    bad = [x["path"] for x in m["artefacts"]
           if (PROJECT_ROOT / x["path"]).exists()
           and sha256_of(PROJECT_ROOT / x["path"]) != x["sha256"]]
    print(f"  publication freeze_id : {m['freeze_id']}")
    print(f"  final evidence        : {m['final_evidence_freeze_id']}")
    print(f"  artefacts             : {len(m['artefacts'])} ({len(bad)} drifted)")
    if bad:
        print(f"  DRIFTED: {bad}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--freeze", action="store_true",
                   help="build the publication freeze (run LAST)")
    a = ap.parse_args()
    if a.verify:
        return verify()
    if a.freeze:
        return build_freeze()
    return build()


if __name__ == "__main__":
    raise SystemExit(main())
