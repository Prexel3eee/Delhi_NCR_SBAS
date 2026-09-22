# Phase III-A — Causal-Evidence Testing (Evidence Synthesis)

Generated 2026-09-22 17:57 UTC.

**This report stops before any causal narrative.** It reports what could be tested, what could not, and what the evidence does not permit. No mechanism is declared.

## A. External dataset inventory

| Dataset | Priority | Decision |
|---|---|---|
| CGWB groundwater level time series (site level) | A | **NOT OBTAINABLE** |
| data.gov.in CGWB groundwater resources | A | **NOT OBTAINABLE and NOT SUITABLE** |
| ERA5 total precipitation (single levels) | D | **INCLUDED** |
| GRACE / GRACE-FO mascon (GSFC RL06 v2.0) | E | **INCLUDED AS REGIONAL CONTEXT ONLY** |
| Aquifer type / alluvium thickness / lithology / geomorphology | B | **NOT OBTAINABLE** |
| Built-up / land cover (GHSL, ESA WorldCover) | C | **NOT OBTAINED** |

### The binding limitation

**The highest-priority dataset is not obtainable.** Three independent routes to site-level groundwater were tried and all are down or gated:

* `indiawris.gov.in` — unreachable (curl code 000)
* `www.cgwb.gov.in` — unreachable; `gwdata.cgwb.gov.in` serves an HTML page titled **"Maintenance Mode"** on every path tried
* `data.gov.in` — the catalogue is searchable, but every resource query returns HTTP 400 `{"error": "Authorization field missing"}`; no API key is available. Even with one, the accessible CGWB resources are **state/district annual aggregates**, not the station-level monthly series a temporal test needs.

Consequently **HYPOTHESIS G (groundwater) and HYPOTHESIS GEO (geology) are UNTESTABLE in this phase — not unsupported.** That distinction is the single most important statement in this report. A negative result and an untested hypothesis are not the same thing, and no weight should be placed on either direction.

## B. Inclusion rules (fixed before any result was computed)

Decisions in the registry were made from endpoint reconnaissance **alone**, before any explanatory value was computed. No dataset was selected or rejected on the basis of agreement with the InSAR pattern. GRACE is admitted **as regional context only**: at 0.5° (~55 km) its footprint exceeds the entire AOI, so it is never used to discriminate hotspots.

## C-D. Groundwater

**NOT PERFORMED.** No site-level or station-level groundwater data could be obtained, so no distance-band analysis, no well selection, and no groundwater time series comparison was possible. Nothing is reported here as a proxy, because any proxy would have been chosen after seeing the InSAR pattern, which the protocol forbids.

## E. GRACE regional context

GSFC RL06 v2.0 mascon retrieved (True). mascon product retrieved; at 0.5 deg (~55 km) its footprint is larger than the entire AOI, so it is admitted as regional context only and is NOT used to discriminate hotspots No hotspot-level inference is drawn from it.

## F. Urbanisation / infrastructure

**NOT PERFORMED.** The Copernicus Data Space endpoint is reachable but no built-up raster was acquired in this session. HYPOTHESIS U is therefore testable only indirectly, through the coherence-confoundning test below.

## G. Hydrometeorological context

ERA5 total precipitation (`tp`), monthly means, 48 months covering the study period.

* monsoon climatology (Jul/Aug/Sep): **221 / 168 / 108 mm/month**
* driest month (Nov): **16 mm/month**
* linear trend over the record: **+11.5 mm/yr**

### Hotspot seasonal cycle vs precipitation (predefined lags 0–3 months)

| Zone | Class | Seasonal amplitude (mm) | Peak month | lag 0 | lag 1 | lag 2 | lag 3 |
|---|---|---:|---:|---:|---:|---:|---:|
| H001 | supported | 34.2 | 10 | -0.249 | -0.163 | -0.062 | +0.034 |
| H004 | supported | 18.2 | 11 | -0.246 | -0.155 | -0.050 | +0.078 |
| H002 | negative control | 27.3 | 7 | +0.161 | +0.010 | -0.206 | -0.201 |
| H003 | negative control | 27.1 | 7 | +0.176 | +0.024 | -0.200 | -0.203 |

**Reading.** Seasonal amplitudes are comparable across all four zones (18–34 mm), including the two that descending failed to reproduce. The precipitation correlation is **weak at every predefined lag** (|r| ≤ 0.25) and its sign is **inconsistent**: the supported zones correlate negatively at lag 0 (−0.25) while the controls correlate positively (+0.16). Lag windows were fixed in advance; no lag search was performed.

The one structural feature is that the supported zones peak in **October/November** and the controls in **July**, i.e. post-monsoon versus monsoon onset. With four zones, weak correlations, and no independent hydrological series, this is a **hypothesis-generating observation, not evidence**.

## H. Coherence / confounding analysis — the decisive available test

This is the only test in this phase that can discriminate using data already in hand.

First, are the zones simply in lower-coherence terrain?

| Class | Median `TEMPORAL_COHERENCE` |
|---|---:|
| H001 | 0.9255 |
| H004 | 0.9630 |
| H002 | 0.8634 |
| H003 | 0.8604 |
| background | 0.7541 |

Then the discriminating test — **the contrast within a fixed coherence band**:

| Zone | Ascending median in TC 0.90–0.95 | Background in the same band | Contrast |
|---|---:|---:|---:|
| H001 | -23.55 | -0.31 | **-23.25** |
| H004 | -12.44 | -0.31 | **-12.13** |
| H002 | -11.91 | -0.31 | **-11.60** |
| H003 | -11.24 | -0.31 | **-10.93** |

**The spatial contrast is NOT a coherence artefact.** Every zone retains a large negative contrast against background *inside the same coherence band*, where measurement quality is by construction matched. For the spatial pattern, HYPOTHESIS ART is substantially weakened.

But this does **not** extend to the coherence–velocity *association* across the AOI, which is coherence-dependent by construction. That association remains **REPRODUCED ACROSS GEOMETRIES AND PROCESSING STATES** with **PHYSICAL ORIGIN UNRESOLVED**. The two statements are different and must not be merged: the first says the hotspots are not a quality artefact; the second says the association's origin is still open.

## I. Control comparison — the central structural finding

| Zone | Class | Ascending median | TC | Elevation (m) |
|---|---|---:|---:|---:|
| H001 | supported | -30.95 | 0.9255 | 179 |
| H004 | supported | -14.31 | 0.9630 | 171 |
| H002 | negative_control | -13.59 | 0.8634 | 166 |
| H003 | negative_control | -12.87 | 0.8604 | 166 |
| background | — | -4.30 | — | 164 |

**H002 and H003 carry essentially the same ascending contrast as H004** — −11.60 and −10.93 mm/yr versus −12.13 in the matched band — yet descending reproduced H004 and did not reproduce H002/H003, even though the descending quality there was adequate (TC 0.900 and 0.886, valid coverage 100 % and 99.9 %).

This is the most informative result in Phase III-A, and it is a constraint on every future hypothesis:

> Any mechanism that explains H001/H004 by a process operating across the affected terrain will equally predict H002/H003. It therefore cannot explain the **descending selectivity** — why two zones reproduce and two do not.

The supported zones also have systematically **higher** ascending coherence (0.944 vs 0.862) and slightly higher elevation (175 m vs 166 m). Neither is a mechanism; both are candidate confounders that any future test must control.

## J-K. H001 and H004 evidence matrices

| Hypothesis | H001 spatial | H001 temporal | H001 controls | H001 confounders | Grade |
|---|---|---|---|---|---|
| G groundwater | **untestable** | **untestable** | untestable | — | **NO EVIDENCE (untested)** |
| U urban loading | not tested | not tested | not tested | — | **NO EVIDENCE (untested)** |
| GEO geology | **untestable** | n/a | untestable | — | **NO EVIDENCE (untested)** |
| H hydrology | no spatial discriminator available | weak, sign-inconsistent seasonality | controls peak in a different month | 4 zones only | **WEAK** |
| ART measurement artefact | contrast survives coherence matching | non-stationarity unexplained | supported zones are the HIGHER-coherence ones | association origin unresolved |  **WEAK** |

The same table holds for H004; nothing in the data separates the two enough to justify different grades.

## L. H002/H003 negative-control findings

H002 and H003 are retained as **ASCENDING-ONLY OBSERVATION / NEGATIVE CONTROL**. They are not evidence of anything, but they are the sharpest available constraint: they establish that an ascending contrast of ≈ −12 mm/yr is **not sufficient** to guarantee descending reproduction, and that whatever distinguishes the two pairs is not the magnitude of the ascending signal.

## M. H005

**Excluded from all mechanism fitting**, per protocol. It participates in no regression, no vertical inference, no volume estimate and no classification. Its status remains **UNRESOLVED_CONTRADICTION** and it appears nowhere in the matrices above.

## N. Competing-hypothesis matrix

| Hypothesis | H001 | H004 | Basis |
|---|---|---|---|
| G groundwater | NO EVIDENCE (untested) | NO EVIDENCE (untested) | data not obtainable |
| U urban loading | NO EVIDENCE (untested) | NO EVIDENCE (untested) | no built-up raster acquired |
| GEO geology | NO EVIDENCE (untested) | NO EVIDENCE (untested) | no reachable source |
| H hydrology | WEAK | WEAK | weak, sign-inconsistent lag correlation; amplitudes present in controls too |
| ART measurement artefact | WEAK | WEAK | spatial contrast survives coherence matching; association origin still open |

**No winner is selected.** The matrix does not support choosing one, and the protocol forbids it until this table exists and is reviewed.

## O. Evidence grades

| Grade | Meaning here | Hypotheses |
|---|---|---|
| NO EVIDENCE | not tested, or tested and unsupported | G, U, GEO |
| WEAK | some consistency, but controls or confounders undermine it | H, ART |
| MODERATE | — | none |
| STRONG | — | none |

`PROVEN` is not used anywhere.

## P. Conclusions the evidence permits

1. The **spatial contrast** of H001, H004, H002 and H003 is **not** explained by temporal coherence or measurement quality: it survives inside a matched coherence band.
2. H001 and H004 have an **independently supported rate** from an independent viewing geometry. Their **displacement histories are not** independently reproduced (H001: −120.7 mm ascending versus +1.1 mm descending), so no temporal claim about them is supported.
3. The **coherence–velocity association is reproduced across geometries and processing states**, but its **physical origin remains unresolved**.
4. **The descending selectivity is unexplained**: H002/H003 carry the same ascending contrast as H004 yet did not reproduce, with adequate descending quality. This is the central open structure.
5. No explanatory dataset available in this phase is **spatially associated with** or **temporally coincident with** the supported zones at a strength that would support any hypothesis.

## Q. Conclusions the evidence does NOT permit

* **No causal statement of any kind.** Not "caused by", not "due to", not "results from".
* **No groundwater attribution**, in either direction. The data to test it do not exist in this environment, so it is neither supported nor refuted.
* **No geological or urbanisation attribution** — likewise untested.
* **No vertical rate.** LOS has not been converted to vertical, and no assumption of negligible horizontal motion has been established.
* **No volume, compaction, aquifer-storage or subsidence-volume estimate.**
* **No total-extent claim.** The 22.6 km² figure remains *"robustly supported mapped deformation area under the selected ascending quality criterion"*, and the independently supported area remains 3.17 km² (H001 + H004) at hotspot level only.
* **No statement about H005** beyond its unresolved status.

## Stopping point

Stopped before any definitive causal narrative, as required. The largest single obstacle is that the priority-A dataset could not be obtained; resolving that is a data-access problem, not an analysis problem, and no amount of further work on the current dataset set will substitute for it.
