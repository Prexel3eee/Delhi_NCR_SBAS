# Phase II-A — Independent Geodetic Validation Report

Generated 2026-09-22 14:55 UTC. Every figure is read programmatically from the stage outputs.

**Stopping condition.** This report ends Phase II-A. It does **not** begin groundwater, geological or any other causal attribution. Geodetic validation asks *whether the deformation is real*; causal interpretation asks *why* and is a separate, later stage.

## 0. Reference labelling (INC-007)

Per `provenance/errata/INC-007.json`, the two products in this report are referenced to **different pixels**, and the two must not be mixed:

| Solution | Reference pixel | Longitude | Latitude |
|---|---:|---:|---:|
| Ascending `product_v1` — **AUTHORITATIVE PRODUCT REFERENCE** | 1384, 1451 | 77.105024 | 28.640415 |
| Ascending `product_v1` — **INTENDED SCIENTIFIC REFERENCE** (not used) | 1378, 1426 | 77.094843 | 28.642739 |
| Descending validation stack (its own processing reference) | 394, 2149 | — | — |

The offset between the two ascending references is **+0.1362 mm/yr**, a constant on every pixel. All ascending values in this report are relative to the authoritative product reference. Ascending and descending values are relative to *different* pixels, so only differences *within* a track, or comparisons that account for geometry, are meaningful.

## 1. Descending-stack provenance

Independently constructed. No ascending burst, pair, mask or acquisition list was read during its construction, and no pair was selected because it intersects a Phase-I hotspot.

| Property | Descending (this stack) | Ascending `product_v1` |
|---|---|---|
| Flight direction | DESCENDING | ASCENDING |
| Relative orbit | 136 | 27 |
| Sub-swath | IW1 | IW2 |
| Bursts (K) | 4 | 4 |
| Acquisitions | 91 | 119 |
| Pairs | 219 | 336 |
| AOI coverage | 71.97 % | 100 % |

**Structural limitation.** Descending path 136 is the only descending IW track intersecting the AOI, and its swath edge leaves 28.03% of the AOI (the western strip, longitude below about 76.995 E) uncovered. No configuration of this orbit can cover it. All five Phase-I hotspot polygons are 100% inside the selected footprint, so all five remain validatable.

All five Phase-I hotspot polygons are **5/5 fully inside** the descending footprint, so every validation target remains addressable. The uncovered western strip carries no Phase-I hotspot.

## 2. Descending network and QC

| Network property | Value |
|---|---:|
| Connected components | 1 |
| Isolated nodes | 0 |
| Minimum degree | 2 |
| Median degree | 5.0 |
| Bridges | 0 |
| Articulation points | 1 |
| Temporal baselines (days) | {'12': 69, '24': 75, '36': 65, '48': 2, '60': 3, '108': 1, '120': 4} |
| Perpendicular baseline range (m) | -224.5 to 237.75 |
| Acceptance | PASSED |

The base rule was the ascending-equivalent **36-day / 250 m** network, which alone left the graph fragmented and bridge-rich. 0 pairs beyond the base rule were added, each flagged in `manifests/descending/sbas_pairs.csv`:

| Reference | Secondary | Δt (d) | Role | Reason |
|---|---|---:|---|---|

*Consequence:* the bridge pairs are the sole link between epochs, so the epoch-to-epoch offset depends on them; within-epoch temporal shape does not

### Descending solution quality

* Valid pixels: **854,698** (69.69 % of the AOI)
* LOS velocity percentiles (mm/yr): `{'p1': -114.452, 'p5': -85.607, 'p25': -52.694, 'p50': -34.181, 'p75': -15.686, 'p95': 10.865, 'p99': 27.416}`
* Reference-sensitivity spread: **None mm/yr**

### Critical-edge sensitivity

The robust network still rests on 10 pairs beyond the base rule and one articulation point. Because a single poor interferogram on one of those edges could distort part of the time series and manufacture a false disagreement, each is reported individually.

| Reference | Secondary | Δt (d) | Role | Median coherence | Median residual (rad) |
|---|---|---:|---|---:|---:|
| 2022-03-31 | 2022-05-30 | 60 | remove_bridge | 0.6034 | 0.6329 |
| 2022-07-29 | 2022-11-26 | 120 | remove_bridge | 0.4649 | 0.6329 |
| 2022-08-10 | 2022-11-26 | 108 | connect_components | 0.4999 | 0.6329 |
| 2022-11-26 | 2023-01-25 | 60 | remove_bridge | 0.6736 | 0.6329 |
| 2023-01-01 | 2023-05-01 | 120 | remove_bridge | 0.574 | 0.6329 |
| 2023-08-29 | 2023-12-27 | 120 | remove_bridge | 0.5167 | 0.6329 |
| 2024-01-08 | 2024-03-08 | 60 | remove_bridge | 0.7512 | 0.6329 |
| 2024-04-01 | 2024-05-19 | 48 | reduce_articulation | 0.6586 | 0.6329 |
| 2024-05-19 | 2024-09-16 | 120 | remove_bridge | 0.4769 | 0.6329 |
| 2024-05-31 | 2024-07-18 | 48 | connect_components | 0.638 | 0.6329 |

Stack-wide median pair coherence: **0.2767**. Pairs below 0.30 coherence: **0**.

## 3. Ascending / descending comparison

### 3.1 Viewing geometry (established before any velocity comparison)

| Track | Heading (°) | Incidence (°) | LOS unit vector (E, N, U) |
|---|---:|---:|---|
| Ascending | -12.586 | 39.287 | `[0.61799, 0.13798, 0.77399]` |
| Descending | -167.396 | 33.746 | `[-0.54212, 0.12122, 0.83151]` |

The tracks differ mainly in the sign of the east component, so **purely vertical motion gives the same sign in both, and purely east-west motion gives opposite signs.** That rule orders the comparison below; it is a consistency check, not a proof — a mixture of vertical and horizontal motion can produce either sign pair.

Common footprint: **854,069** AOI pixels covered by both tracks (69.63 %), of which **113,881** pass the quality threshold in both.

Independent detection on the common grid (|LOS| ≥ 10.0 mm/yr, coherence ≥ 0.8, ≥ 0.4 km²) found **5** ascending and **0** descending components.

### 3.2 Hotspot cross-validation

| ID | Asc LOS mm/yr | Desc LOS mm/yr | Same sign | Desc component found | IoU | Centroid sep (km) | Desc coverage | Classification |
|---|---:|---:|:---:|:---:|---:|---:|---:|---|
| H001 | -30.95 | -84.73 | yes | no | 0.000 | n/a | 100.0 % | **PARTIALLY_SUPPORTED** |
| H002 | -13.59 | -30.48 | yes | no | 0.000 | n/a | 100.0 % | **NOT_RESOLVED** |
| H003 | -12.87 | -21.89 | yes | no | 0.000 | n/a | 100.0 % | **NOT_RESOLVED** |
| H004 | -14.31 | -44.18 | yes | no | 0.000 | n/a | 100.0 % | **NOT_RESOLVED** |
| H005 | -14.21 | -35.51 | yes | no | 0.000 | n/a | 100.0 % | **NOT_RESOLVED** |

Reasons:

* **H001** — same sign in an independent geometry but the descending component is not detected at 274% of the ascending magnitude.
* **H002** — descending coherence is too low to test this hotspot (0.473).
* **H003** — descending coherence is too low to test this hotspot (0.469).
* **H004** — descending coherence is too low to test this hotspot (0.490).
* **H005** — descending coherence is too low to test this hotspot (0.494).

## 4. The coherence–velocity question

This was the highest-priority unresolved Phase-I issue: ascending showed much stronger negative LOS velocity in lower-coherence terrain, which is ambiguous between genuinely faster deformation and a coherent bias. The discriminating test is whether an independent viewing geometry reproduces the relationship.

| Coherence band | Asc n | Asc median (mm/yr) | Asc frac ≤ −10 | Desc n | Desc median (mm/yr) | Desc frac ≤ −10 |
|---|---:|---:|---:|---:|---:|---:|
| 0.50–0.55 | 71,651.0 | -17.06 | 0.724 | 186,854.0 | -28.41 | 0.729 |
| 0.55–0.60 | 63,426.0 | -13.99 | 0.635 | 61,606.0 | -26.39 | 0.692 |
| 0.60–0.65 | 61,299.0 | -10.72 | 0.525 | 8,725.0 | -24.43 | 0.654 |
| 0.65–0.70 | 61,882.0 | -7.70 | 0.416 | 515.0 | -23.93 | 0.619 |
| 0.70–0.75 | 63,481.0 | -5.33 | 0.312 | 17.0 | 10.20 | 0.294 |
| 0.75–0.80 | 70,211.0 | -3.77 | 0.222 | 2.0 | 22.86 | 0.000 |
| 0.80–0.85 | 82,873.0 | -2.81 | 0.149 | 0.0 | n/a | n/a |
| 0.85–0.90 | 109,190.0 | -1.79 | 0.095 | 0.0 | n/a | n/a |
| 0.90–0.95 | 167,609.0 | -0.38 | 0.023 | 0.0 | n/a | n/a |
| 0.95–1.00 | 181,908.0 | -0.29 | 0.008 | 0.0 | n/a | n/a |

Correlation of the two coherence–velocity curves across bands: **0.8311231664228349**

## 5. Temporal mode validation

The two tracks are on different relative orbits and their acquisition calendars only partially overlap: **119** ascending dates, **91** descending dates, **0** exactly shared.

The two tracks were acquired on different relative orbits and their acquisition calendars only partially overlap, so temporal comparison is restricted to the shared dates.

## 6. Required final classification

| Classification | Count |
|---|---:|
| PARTIALLY_SUPPORTED | 1 |
| NOT_RESOLVED | 4 |

Per Phase-I observation:

| Observation | Classification | Basis |
|---|---|---|
| H001 | **PARTIALLY_SUPPORTED** | same sign in an independent geometry but the descending component is not detected at 274% of the ascending magnitude |
| H002 | **NOT_RESOLVED** | descending coherence is too low to test this hotspot (0.473) |
| H003 | **NOT_RESOLVED** | descending coherence is too low to test this hotspot (0.469) |
| H004 | **NOT_RESOLVED** | descending coherence is too low to test this hotspot (0.490) |
| H005 | **NOT_RESOLVED** | descending coherence is too low to test this hotspot (0.494) |

Non-hotspot Phase-I observations:

| Observation | Status in Phase II-A |
|---|---|
| Coherence–velocity relationship | see section 4 |
| North/south temporal grouping | see section 5 |
| Non-stationarity (split-half [10.435, 20.245] mm/yr) | not re-tested; the descending record has different gaps and cannot resolve it |
| Spatial gradients | tested through the hotspot IoU and centroid separation in section 3.2 |
| Supported deformation extent (22.58 km²) | an ascending-only figure under its stated quality criterion; the descending stack cannot test it because it covers only 72.0 % of the AOI |

## 7. What this phase does not establish

* **No mechanism.** Nothing here identifies groundwater, tectonics, compaction, construction or metro loading, lithology, or fault motion.
* **No full 3-D displacement.** Two LOS observations cannot constrain three components. Any decomposition rests on an explicit assumption about north-south motion, which is unmeasured.
* **No volumetric inference.** No subsidence volume, compaction volume, groundwater-storage loss or aquifer volume change is computed, and the mapped area is not sufficient for one.
* **No absolute calibration.** Both tracks are relative to their own reference pixel, and the GNSS conclusion from Phase I stands unchanged: GNSS cannot discriminate the branch differences, `DLHI`/`GCP5`/`DELH`/`LIAA` are not usable as local validators given their sampling, and `DRDN` is not usable as an absolute calibration at 209.9 km separation.

## 8. Next stage (not started)

Causal attribution is explicitly **not** begun here. When authorised, it is a separate stage using explanatory variables — groundwater levels and extraction, geology, geomorphology, sediment thickness, land use, infrastructure, precipitation, hydrology, GRACE/regional storage — with inclusion rules defined **before** any correlation is computed.



---

# 9. Cross-track spatial agreement — the decisive test

Sections 1-8 above report each stage. This section states the single number that
determines how much the descending stack can validate, because it was computed
after the stage scripts were written and is the most important result in the
phase.

## 9.1 Do the two fields agree in shape?

Over `ASC_DESC_COMMON_VALID_DOMAIN` (854,004 pixels), after removing the constant
offset between the two reference levels:

| Quantity | Ascending | Descending |
|---|---:|---:|
| LOS velocity median (mm/yr) | -2.02 | -34.19 |
| p05 (mm/yr) | -28.36 | -85.60 |
| p95 (mm/yr) | +5.00 | +10.84 |
| spatial standard deviation (mm/yr) | 10.64 | **29.25** |

| Test | Result |
|---|---:|
| Pearson correlation, raw | **+0.175** |
| Pearson correlation, after median-offset removal | +0.175 |
| Pearson correlation, after removing a fitted plane from each | +0.127 |
| Spearman correlation | +0.207 |

Removing a plane makes the agreement **worse**, so the disagreement is not a
long-wavelength orbital ramp that could be deramped away. It is in the
short-wavelength structure: the descending field carries **3.5x** the
short-wavelength variability of the ascending field and correlates with it at
only r ~ 0.13-0.21.

**The descending product does not independently reproduce the ascending spatial
pattern.** It is substantially noisier.

## 9.2 The robustness edges are not the cause

The 10 pairs added beyond the base rule have median coherence **0.46-0.75**,
against a stack-wide median pair coherence of **0.2767**. The added edges are
therefore *better* than the average pair, not worse. The problem is the stack as
a whole, not the bridging decision: descending temporal coherence is p50 0.467
against ascending p50 ~0.757, and **no** descending pixel reaches the ascending
quality standard. `maskTempCoh` (MintPy's 0.7 temporal-coherence default) is true
for **19 pixels** in the whole AOI.

## 9.3 What DID reproduce: the coherence-velocity relationship

This is the one Phase-I result that an independent geometry confirms:

| Coherence band | Ascending median (mm/yr) | Descending median (mm/yr) |
|---|---:|---:|
| 0.50-0.55 | -17.06 | -28.41 |
| 0.55-0.60 | -13.99 | -26.39 |
| 0.60-0.65 | -10.72 | -24.43 |
| 0.65-0.70 | -7.70 | -23.93 |
| 0.70-0.75 | -5.33 | (sparse) |
| 0.95-1.00 | -0.29 | (no pixels) |

Both tracks show the same monotonic relationship: **lower temporal coherence
accompanies stronger negative LOS velocity**. The two curves correlate at
**r = +0.831**.

Because the reproducing geometry has a different heading, incidence and network,
this is meaningful independent evidence that the relationship is a property of
the data rather than of one processing configuration. It does not, by itself,
establish whether the low-coherence signal is real deformation or a coherent
bias — but it does establish that it is reproducible.

## 9.4 Why the decomposition, although well conditioned, is not usable

The design matrix is favourable:

```text
A = [[+0.77399, +0.61799],      singular values 1.13653, 0.82132
     [+0.83151, -0.54212]]      condition number 1.3838
```

and the north-south sensitivity is small (vertical swing **1.604 mm/yr** across
an assumed Vy of -5 to +5 mm/yr). The inferred vertical components are:

| Zone | Vertical (mm/yr) | E-W (mm/yr) |
|---|---:|---:|
| H001 | -74.07 | +42.68 |
| H002 | -28.07 | +13.18 |
| H003 | -21.96 | +6.69 |
| H004 | -37.56 | +23.89 |
| H005 | -31.76 | +16.79 |

**These are not credible deformation estimates.** They are 2.5-2.7x the ascending
LOS values because they inherit the descending product's large offset and its
3.5x scatter. A well-conditioned inversion of a contaminated input is still
contaminated: conditioning bounds how a *LOS error* maps into a *component
error*, and it cannot repair a systematic that is already in the data.

The formal 2-sigma flags on these values use only the inversion's `velocityStd`,
which excludes the reference systematic and the descending offset. They must not
be read as significance.

## 9.5 Effect on the required classification

Because the descending stack fails its own spatial-agreement test, most hotspots
cannot be tested by it. Following the instruction not to misclassify
low-quality absence as contradiction:

| Zone | Classification | Basis |
|---|---|---|
| H001 | **PARTIALLY_SUPPORTED** | same sign in an independent geometry, but no descending component is detected and the magnitude is 274% of ascending |
| H002 | **NOT_RESOLVED** | descending coherence 0.473, below the level at which this zone can be tested |
| H003 | **NOT_RESOLVED** | descending coherence 0.469 |
| H004 | **NOT_RESOLVED** | descending coherence 0.490 |
| H005 | **NOT_RESOLVED** | descending coherence 0.494 |

| Phase-I observation | Status |
|---|---|
| Coherence-velocity relationship | **INDEPENDENTLY SUPPORTED** (r = +0.831) |
| North/south temporal grouping | **NOT REPRODUCED** — descending within-group r = +0.99 but between-group r = **+0.96**, i.e. every zone moves together. This is common-mode domination, not a reproduced structure. The Phase-I signature was a *negative* between-group correlation. |
| Non-stationarity | **NOT TESTED** — the descending record has different gaps and cannot resolve it |
| Spatial gradients | **NOT REPRODUCED** (r = +0.175) |
| Supported deformation extent (22.6 km2) | **ASCENDING_ONLY** — descending covers 69.69% of the AOI and cannot test the western strip |

## 9.6 Correction to an earlier claim in this phase

An intermediate check reported descending AOI coverage of 100%, because it
tested `isfinite(velocity)`. That is wrong: **MintPy fills the region it did not
invert with zeros**, so a finiteness test reports full coverage for a partly
inverted product. The correct validity test is `velocityStd > 0`.

With the correct test, descending covers **69.69%** of the AOI, losing the
western strip (0% below 76.90 E, 18% at 76.90-76.95 E). This **confirms** the
original burst-geometry estimate of ~28% loss rather than contradicting it. The
common-domain and per-zone containment results above all use the corrected test.

## 9.7 What would be needed to make descending usable

The descending stack is not a failed acquisition; it is a stack that has not been
made to work. Candidate causes, none yet tested:

1. no tropospheric correction was applied to descending, and the descending
   pass is at ~00:52 UTC against ascending at ~12:55 UTC, so the two sample
   different atmospheric states;
2. the descending network spans two acquisition gaps and required 108- and
   120-day pairs, unlike the ascending 36-day network;
3. the descending incidence angle is 33.75 deg against ascending 39.29 deg
   (IW1 rather than IW2), so the two are not equivalent samplings;
4. no unwrap-error correction was applied.

Testing these is a new work item, not part of the approved Phase II-A scope.
