# Manuscript

## Title

**Reproducible deformation, unresolved mechanism: ascending/descending Sentinel-1 SBAS-InSAR of Delhi-NCR with preregistered hypothesis testing**

## Abstract

The principal result of this study is not a resolved deformation mechanism, but the separation of reproducible geodetic observations from unsupported interpretation. Two localized Delhi-NCR deformation features (H001 and H004) were independently reproduced across ascending and descending Sentinel-1 geometries at the spatial and mean-rate level, whereas two comparable ascending features were not reproduced and a fifth remained contradictory. Preregistered tests did not support groundwater-level variability, shallow soil texture, or urbanisation as explanations for this selectivity. The physical mechanism of the independently supported features therefore remains unresolved.

Independent reproduction applies to the spatial and mean-rate characteristics, not to the detailed displacement histories; in particular, the ascending and descending H001 cumulative time series differ substantially.

A 119-acquisition ascending Sentinel-1 stack (relative orbit 27, IW2, 336 interferograms) and an independently constructed 91-acquisition descending stack (orbit 136, IW1, 219 interferograms) were processed with HyP3 and MintPy over a 1,962 km² area for 2021-10 to 2025-09. Five ascending deformation zones were detected. Independent reproduction was assessed without any shared burst, pair or mask. Four preregistered tests were then applied to candidate explanations — groundwater-level variability, shallow soil texture, existing built intensity, and recent built-up change — with two non-reproduced ascending zones (H002, H003) carried throughout as negative controls. None of the tested explanations accounted for the selectivity of the supported features, and the controls themselves demonstrate that comparable ascending anomalies need not be physically interpretable. A reproducible coherence–velocity association is reported without a physical interpretation.

## 1. Introduction

The Indo-Gangetic Plain hosts intense groundwater use and rapid urban growth, and both are frequently invoked to explain InSAR-observed subsidence. The common analytical pattern is to detect deformation, then attribute it. This study inverts that order: the geodetic result was frozen before interpretation, candidate explanations were preregistered with fixed lags, thresholds and significance procedures, and negative controls were carried from the start.

The design question is therefore not *"what is causing the subsidence?"* but *"which of the observed features survive independent observation, and does any candidate explanation account for where they occur?"*

## 2. Data and methods

*Full detail in Supplementary Methods.* Summary:

| Element | Value |
|---|---|
| AOI | 1,962.4 km², Delhi-NCR, EPSG:32643 |
| Ascending | Sentinel-1 orbit 27, IW2, VV, K = 4 bursts |
| Ascending stack | 119 acquisitions, 336 interferograms, 0 pairs excluded |
| Descending | Sentinel-1 orbit 136, IW1, VV, K = 4 bursts |
| Descending stack | 91 acquisitions, 219 interferograms |
| Processing | HyP3 `INSAR_ISCE_MULTI_BURST`, 10×2 looks, 40 m; MintPy 1.6.4 |
| Frozen branch | unwrap off, troposphere off, DEM residual off, deramp off |

The ascending product was frozen as `product_v1` before interpretation. The descending product was constructed independently — no shared burst, pair, mask or acquisition list — and no pair was selected because it intersected a hotspot.

## 3. Results

### 3.1 Ascending deformation field

The field is spatially heterogeneous and strongly asymmetric: the median pixel is essentially stationary (−0.73 mm/yr) while a tail reaches −87 mm/yr. Deformation is carried by a minority of the AOI in connected patches. Five zones were detected at |LOS| ≥ 10 mm/yr, temporal coherence ≥ 0.80 and area ≥ 0.4 km², giving

```text
22.6 km2 = robustly supported mapped deformation area under the
           selected ascending quality criterion
```

This is an operating figure under a stated criterion, **not** a validated extent: deformation magnitude and temporal coherence are strongly associated in this stack, so a coherence-based criterion systematically excludes part of the signal.

### 3.2 Independent descending reproduction

The raw descending solution reproduced the ascending field poorly (Pearson 0.175). Diagnostics localised the cause to unwrapping: 81.3 % of inverted pixels fell outside the retained connected set, and masking them worsened every velocity metric. Correcting the unwrapping (bridging + phase closure) improved **7 of 7** internal metrics — temporal coherence p75 0.49 → 0.83, pixels with TC ≥ 0.7 from 11,013 → 1,352,660 — and raised cross-track agreement to Pearson 0.363. Agreement is therefore reported as **moderate and spatially heterogeneous**, not global.

### 3.3 Hotspot-level reproduction

| Zone | Cross-geometry status | Area (km²) | Asc (mm/yr) | Desc (mm/yr) | Interpretation |
|---|---|---:|---:|---:|---|
| **H001** | INDEPENDENTLY_SUPPORTED | 5.59 | -30.95 | -36.02 | SUPPORTED DEFORMATION FEATURE - MECHANISM UNRESOLVED |
| **H004** | INDEPENDENTLY_SUPPORTED | 1.07 | -14.31 | -12.46 | SUPPORTED DEFORMATION FEATURE - MECHANISM UNRESOLVED |
| **H002** | NOT_REPRODUCED | 12.83 | -13.59 | -1.15 | ASCENDING FEATURE NOT REPRODUCED |
| **H003** | NOT_REPRODUCED | 2.25 | -12.87 | -0.75 | ASCENDING FEATURE NOT REPRODUCED |
| **H005** | UNRESOLVED_CONTRADICTION | 0.84 | -14.21 | +61.39 | UNRESOLVED CROSS-GEOMETRY CONTRADICTION |

H001 and H004 were reproduced at the spatial and mean-rate level (magnitude ratios 1.16 and 0.87; both within 1.6σ of the vertical-equivalent expectation). **Their detailed displacement histories were not reproduced** — H001's cumulative displacement is −120.7 mm ascending against +1.1 mm descending, the descending series carrying large opposing jumps.

```text
3.17 km2 = area of Phase-I deformation zones independently supported at the
           hotspot level by the descending geometry   (H001 + H004)
```

### 3.4 The negative controls

**This is a principal result, not a validation footnote.**

```text
H001 / H004
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
    and simple regional explanatory variables lack specificity.
```

H002 and H003 have matched-band ascending contrasts comparable to H004 (−11.60 and −10.93 vs −12.13 mm/yr) and **adequate** descending quality (TC 0.900 and 0.886), yet do not reproduce. Any explanation that acts across the affected terrain — regional groundwater decline, a shared soil unit, urbanisation of the corridor — predicts all four zones similarly, and therefore fails on selectivity. Carrying these controls is what converts the study from a catalogue of anomalies into a constraint on interpretation.

### 3.5 Coherence–velocity association

A monotonic association between temporal coherence and LOS velocity is reproduced across three processing states (ascending, descending raw, descending unwrap-corrected), with curve correlation r = +0.831 between geometries. It is reported as a **reproduced observational relationship** with **physical origin unresolved**. Candidate explanations — surface and scattering differences, deformation/decorrelation interaction, residual measurement effects — are not selected among without independent evidence.

## 4. Hypothesis tests

| Hypothesis | Evidence state | Basis |
|---|---|---|
| Groundwater temporal forcing | **NO EVIDENCE** | preregistered test: trends opposite to prediction at H001/H004; controls carry the predicted sign; falsification lags equal or outperform forward lags; 0 of 16 positive-lag tests survive FDR q=0.05 |
| Shallow soil-texture susceptibility | **NO EVIDENCE** | H001/H004 are coarser (more sand, less clay) than controls - opposite to the fine-sediment prediction; confounded with coherence (rho -0.600) |
| Deep geological / aquifer-system susceptibility | **NOT ADEQUATELY TESTED** | GSI Bhukosh unreachable; the only usable dataset samples the upper ~2 m, not the compaction interval |
| Existing built intensity | **NO EVIDENCE** | all four hotspots are 70-79% built against a 33.7% background, so it describes a shared setting and cannot explain selectivity; the two datasets disagree on H001's ranking |
| Recent built-up expansion | **NO EVIDENCE** | GHSL 2020->2025 change exactly zero at all four hotspots; the 2025 epoch is a projection, not an observation |
| Major infrastructure / construction | **NOT TESTABLE** | no authoritative dated construction dataset obtained |
| Measurement artefact as sole explanation | **NOT SUPPORTED FOR H001/H004, but measurement limitations remain** | the hotspot spatial contrast survives coherence-band matching; the coherence-velocity association's origin is nonetheless unresolved |

### 4.1 Groundwater — NO EVIDENCE

Preregistered before any correlation existed. Six-hourly NWDP telemetry, 187 stations, 111 quality-passing, all eligible stations within 5 km selected. Supported zones show groundwater **rising** (−4.02, −0.68 m/yr) while subsiding, the opposite of prediction; the **controls** show the predicted slight deepening (+0.05, +0.15 m/yr). Zero of sixteen positive-lag tests survive FDR q = 0.05, and falsification (negative) lags equal or outperform forward lags at every zone.

This is not "groundwater has been ruled out": aquifer metadata are absent, well depths and types unknown, H001 has ~78-day telemetry outages and only two stations, and LOS is not pure vertical displacement.

### 4.2 Shallow soil texture — NO EVIDENCE, direction opposite

H001/H004 carry more sand and less clay than controls and background (−5.0 and +6.4 percentage points), where fine-sediment susceptibility predicts the reverse; the controls resemble the background, not the positives. Confounded with coherence (ρ = −0.600).

**Deep geological / aquifer-system susceptibility is NOT ADEQUATELY TESTED.** The authoritative source (GSI Bhukosh) was unreachable, and SoilGrids samples only the upper ~2 m, not the compaction interval. The deep substrate is **untested, not exonerated**.

### 4.3 Urbanisation — NO EVIDENCE; construction NOT TESTABLE

All four zones are heavily built (70.6 %, 79.0 %, 73.7 %, 70.0 % WorldCover built fraction against a 33.7 % background). That shared setting cannot separate the zones that reproduce from those that do not, and the two products disagree on H001's ranking. GHSL 2020→2025 built-up change is exactly zero at all four zones, with the caveat that post-2020 GHSL epochs are projections rather than observations. No loading was estimated: height, footprint, construction type and foundation are absent, so `built-environment association` is the strongest permitted framing.

## 5. Discussion

### 5.1 The reproducibility asymmetry

The study's spine is a single sentence:

> **The spatial/mean-rate deformation observations at H001 and H004 are independently reproducible; the physical explanation is not.**

This is narrower than a causal claim and considerably stronger than one, because it would survive a reader who rejects every interpretive choice made after the geodetic validation. It also implies a discipline for the field: reproducing a deformation *rate* across geometries does not reproduce a deformation *history*, and the two are frequently conflated in the literature.

### 5.2 Why the negative controls deserve prominence

H002 and H003 are the reason the study cannot be read as "four subsidence zones plus one anomaly". They show that an ascending anomaly of ≈ −13 mm/yr, measured with adequate quality and sitting in comparable urban terrain, can fail to appear in an independent geometry. The natural inference — that not every ascending anomaly should be interpreted physically, and that the ascending product alone cannot adjudicate — is more consequential than any individual zone.

### 5.3 What the failed hypotheses do and do not mean

`NO EVIDENCE`, `NOT ADEQUATELY TESTED` and `NOT TESTABLE` are distinct and are not collapsed. Only groundwater and shallow soil texture were actually tested against a suitable dataset. Deep geology was tested against an inadequate surrogate, and construction was not testable at all. Reporting all three as "ruled out" would misrepresent the study in the direction of false confidence.

Weak variables are deliberately **not** combined into a composite causal story. Three failed or untested hypotheses do not sum into a stronger fourth.

## 6. Limitations

1. LOS is a projection; no decomposition is published and the Phase II-A component estimates were withdrawn as invalid.
2. The absolute zero level carries a 4.78 mm/yr reference systematic, and no independent in-AOI geodetic reference exists — the nearest adequately sampled GNSS station is 209.9 km away.
3. H001/H004 displacement histories are not independently reproduced.
4. The H001 groundwater network is sparse with long outages, and aquifer metadata are absent throughout.
5. The deep substrate is untested; the construction chronology is unavailable.
6. Coherence confounding pervades every spatial comparison, and four hotspot values permit no reliable adjustment.
7. Descending coverage is incomplete (a western strip of the AOI), so the descending geometry cannot validate the entire ascending field.

## 7. Conclusion

The principal result of this study is not a resolved deformation mechanism, but the separation of reproducible geodetic observations from unsupported interpretation. Two localized Delhi-NCR deformation features (H001 and H004) were independently reproduced across ascending and descending Sentinel-1 geometries at the spatial and mean-rate level, whereas two comparable ascending features were not reproduced and a fifth remained contradictory. Preregistered tests did not support groundwater-level variability, shallow soil texture, or urbanisation as explanations for this selectivity. The physical mechanism of the independently supported features therefore remains unresolved.

Independent reproduction applies to the spatial and mean-rate characteristics, not to the detailed displacement histories; in particular, the ascending and descending H001 cumulative time series differ substantially.

No tested mechanism adequately explains the selective, independently supported H001/H004 deformation. This is not a claim that the deformation has no physical cause. It is the claim that the available evidence is sufficient to characterize selected deformation features and insufficient to identify their mechanism.

