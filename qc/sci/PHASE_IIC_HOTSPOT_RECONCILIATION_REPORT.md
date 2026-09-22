# Phase II-C — Hotspot-Level Cross-Geometry Reconciliation

Generated 2026-09-22 17:47 UTC.

**Scope.** Determine, hotspot by hotspot, which Phase-I observations survive the independent descending geometry. No tuning of either product. No causal interpretation of any kind.

## 0. The 92-vs-91 acquisition accounting

The discrepancy is resolved and is **not** a conflict:

| Stage | Count |
|---|---:|
| distinct dates in the burst inventory | 92 |
| accepted (present in all 4 bursts) | **92** |
| dropped as unconnectable | 1 |
| **used in the inversion / frozen stack** | **91** |
| ERA5 hour-01 available | 91 |
| pairs in manifest vs in stack | 219 vs 219 (identical: True) |

The single excluded acquisition is **2024-04-13**: it is present in all four bursts and was accepted, but every neighbour is 572–649 m away in perpendicular baseline, outside the 250 m limit, so **no pair could connect it to the network**. It was dropped rather than forced in. `burst_inventory_2021_2025.csv` reports the same figure.

Every original acquisition is accounted for exactly once (`acquisition_accounting.csv`, True), and ERA5 hour-01 coverage is 91/91 = COMPLETE. **92 accepted − 1 unconnectable = 91 inverted.**

## 1. D2 candidate freeze

```text
DESCENDING_PRODUCT_V2_CANDIDATE   mintpy/descending_d2_unwrap_work
freeze_id                          ba99df90a6f15b3aaaf90fe3042511ddef3e0f9864f03aab122a541b5d3d6d13
status                             CANDIDATE FOR REVALIDATION
```

`DESCENDING_RAW_V1` (`acdb209f…`) is **not** overwritten and remains frozen and authoritative for the D0 record.

## 2. Global agreement is not validation

The improvement from D0 to D2 was real (Pearson 0.1752 → 0.3626) but it is not uniform:

```text
CROSS-GEOMETRY AGREEMENT: MODERATE / SPATIALLY HETEROGENEOUS
```

The hotspot table below shows why: two zones reproduce strongly, two do not reproduce at all, and one is contradicted. The full ascending field is **not** independently validated.

## 3. Reference alignment (one convention)

Both tracks were re-referenced to a **common stable-control region** of 100,188 pixels inside the common valid domain (high quality in both tracks, |v| ≤ 3 mm/yr). Ascending was shifted by -0.004 mm/yr and descending by +0.246 mm/yr. **Every velocity below is relative to that shared control** — raw absolute offsets from independently referenced products are never compared.

INC-007 remains visible: ascending authoritative reference [1384, 1451], ascending intended reference [1378, 1426] (**not used**), descending D2 reference [394, 2149].

## 4. Hotspot validation table

| Zone | Asc median | D2 median | Same sign | Ratio | Asc p25/p75 | D2 p25/p75 | Asc unc | D2 unc | Asc TC | D2 TC | Valid | IoU |
|---|---:|---:|:---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| **H001** | -30.95 | -36.02 | yes | 1.16 | -54.0/-17.9 | -63.3/-19.5 | 0.96 | 1.77 | 0.925 | 0.906 | 100% | 0.357 |
| **H002** | -13.58 | -1.15 | yes | 0.09 | -15.8/-11.8 | -3.3/+0.4 | 1.28 | 1.62 | 0.863 | 0.900 | 100% | 0.023 |
| **H003** | -12.86 | -0.75 | yes | 0.06 | -14.9/-11.4 | -2.5/+0.5 | 1.25 | 1.57 | 0.861 | 0.886 | 100% | 0.009 |
| **H004** | -14.31 | -12.46 | yes | 0.87 | -17.4/-12.1 | -16.3/-10.1 | 0.73 | 1.80 | 0.963 | 0.909 | 100% | 0.052 |
| **H005** | -14.21 | +61.39 | **NO** | 4.32 | -17.1/-12.2 | +38.9/+77.2 | 1.40 | 4.09 | 0.865 | 0.851 | 100% | 0.183 |

## 5. H001 and H004 — confirmation across masks

Support is **not** an artefact of one threshold or one raster mask:

| Zone | Mask | n | Ascending | D2 | Same sign | Ratio |
|---|---|---:|---:|---:|:---:|---:|
| H001 | ascending_primary | 3,494 | -30.95 | -36.02 | yes | 1.16 |
| H001 | descending_primary | 3,161 | -32.81 | -37.35 | yes | 1.14 |
| H001 | stricter_both | 2,138 | -33.54 | -38.29 | yes | 1.14 |
| H001 | hotspot_core | 505 | -23.47 | -23.83 | yes | 1.01 |
| H001 | full_polygon | 3,494 | -30.95 | -36.02 | yes | 1.16 |
| H004 | ascending_primary | 670 | -14.31 | -12.46 | yes | 0.87 |
| H004 | descending_primary | 664 | -14.32 | -12.48 | yes | 0.87 |
| H004 | stricter_both | 522 | -14.87 | -13.17 | yes | 0.89 |
| H004 | hotspot_core | 99 | -20.29 | -19.07 | yes | 0.94 |
| H004 | full_polygon | 670 | -14.31 | -12.46 | yes | 0.87 |

Both zones hold the same sign, comparable magnitude and a consistent ratio across every mask, including the shrunken core (H001 ratio 1.01, H004 0.94). Neither is called vertical subsidence; that determination belongs to decomposition.

## 6. H002 and H003 — NOT_REPRODUCED, not partial support

Under a purely vertical signal the expected descending LOS is the ascending value scaled by the ratio of vertical sensitivities (×1.0743). `descending_uncertainty` is the formal `velocityStd`.

| Zone | Ascending | Expected D2 | Measured D2 | D2 unc | Gap | Desc TC | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| H001 | -30.95 | -33.25 | -36.02 | 1.77 | **1.6σ** | 0.906 | **consistent** |
| H002 | -13.58 | -14.59 | -1.15 | 1.62 | **8.3σ** | 0.900 | **NOT_REPRODUCED** |
| H003 | -12.86 | -13.82 | -0.75 | 1.57 | **8.3σ** | 0.886 | **NOT_REPRODUCED** |
| H004 | -14.31 | -15.37 | -12.46 | 1.80 | **1.6σ** | 0.909 | **consistent** |
| H005 | -14.21 | -15.27 | +61.39 | 4.09 | **18.7σ** | 0.851 | **NOT_REPRODUCED** |

H002 and H003 have **adequate** descending quality (`TEMPORAL_COHERENCE` 0.900 and 0.886, valid fraction 100 % and 99.9 %) yet the measured magnitude is **8.3σ** from the expected response — near zero while ascending shows ≈ −13 mm/yr. A matching sign with a magnitude ratio of 0.09 and 0.06 is **not** partial support. Both are **NOT_REPRODUCED**.

## 7. H005 — dedicated contradiction analysis

Consistent across every mask, so this is not a threshold artefact:

| Mask | n | Ascending | D2 | Same sign | Ratio |
|---|---:|---:|---:|:---:|---:|
| ascending_primary | 522 | -14.21 | +61.39 | **NO** | 4.32 |
| descending_primary | 416 | -13.93 | +65.59 | **NO** | 4.71 |
| stricter_both | 77 | -11.78 | +69.63 | **NO** | 5.91 |
| hotspot_core | too few | | | | |
| full_polygon | 522 | -14.21 | +61.39 | **NO** | 4.32 |

* D0 at the same footprint: -35.51 mm/yr; D2: +61.39 mm/yr — the reversal is introduced by the unwrap correction, not inherited from D0.
* Surrounding ring (outside the polygon): +30.81 mm/yr.
* Largest single-date steps in the D2 series: 20230630→20230712 -119.4 mm, 20240928→20241010 -100.0 mm, 20240823→20240904 +90.8 mm.
* Implied components if both LOS values are real (diagnostic only, north-south = 0 assumed):

| Assumed Vy | Implied vertical | Implied east-west |
|---|---:|---:|
| -5.0 | +33.19 | -63.44 |
| -2.0 | +32.71 | -63.51 |
| +0.0 | +32.39 | -63.55 |
| +2.0 | +32.07 | -63.60 |
| +5.0 | +31.59 | -63.67 |

The implied east-west component is **≈ −64 mm/yr** across the whole north-south family — essentially independent of the assumption. A westward horizontal rate of that magnitude exceeds any plausible natural or anthropogenic signal, so the contradiction is **not geometrically explainable**. Nor is it a simple processing artefact, since it survives every mask and is introduced coherently by the unwrap correction. The D2 series there also carries ±90–120 mm single-date jumps. Classification: **UNRESOLVED_CONTRADICTION** — not forced to a resolution. This is a diagnostic calculation and is **not** published as a decomposition product.

## 8. Temporal cross-validation

Nearest-date matching with a 6-day tolerance; no aggressive interpolation. Matched epochs are reported, and correlation is not used where too few exist.

| Zone | Matched | r raw | r detrended | Spearman (detrended) | Asc total | D2 total |
|---|---:|---:|---:|---:|---:|---:|
| H001 | 89 | +0.049 | +0.007 | +0.012 | -120.7 | +1.1 |
| H002 | 89 | +0.142 | -0.046 | -0.038 | -48.0 | +4.6 |
| H003 | 89 | +0.280 | +0.101 | +0.107 | -46.8 | +11.9 |
| H004 | 89 | +0.026 | +0.073 | +0.032 | -59.6 | +9.8 |
| H005 | 89 | +0.525 | +0.004 | -0.022 | -44.5 | -177.3 |

**The temporal shape does not support the rate agreement.** Despite H001 and H004 reproducing the *rate*, the cumulative totals disagree in sign and magnitude (H001: ascending −120.7 mm vs D2 +1.1 mm). The D2 series contains large opposing single-date jumps, so a robust trend estimate and the endpoint difference diverge. This is a material caveat on the two INDEPENDENTLY_SUPPORTED classifications: the **rate** is independently supported, the **displacement history is not**.

## 9. North/south grouping with D2

| Track | Within-group | Between-group |
|---|---:|---:|
| Ascending | +0.8137 | -0.2589 |
| Descending D2 | +0.7443 | +0.4011 |

D2 does **not** reproduce the grouping (False): within-group similarity is high (0.744) but the between-group correlation is **+0.401**, not negative. The Phase-I signature required a meaningfully lower or opposite between-group value. North/south temporal grouping remains **NOT REPRODUCED**.

## 10. Coherence–velocity association with D2

| Form | Bins | Spearman(coherence, velocity) |
|---|---:|---:|
| ascending | 14 | +1.000 |
| descending_d0 | 8 | +1.000 |
| descending_d2 | 14 | +0.996 |

**The association survives the unwrap correction essentially unchanged.** If it had collapsed under D2 the original relation would have been substantially processing-driven. It did not: all three forms give ≈ +1.0. The association is therefore intrinsic to the observations. This still does not identify a physical mechanism, and the physical origin remains **UNRESOLVED**.

## 11. Decomposition eligibility

Design-matrix condition number κ = 1.3838 — globally good. That is **not** sufficient.

| Zone | Eligible | Implied vertical | ± | Implied E-W | Reason |
|---|---|---:|---:|---:|---|
| H001 | **YES** | -41.82 | 1.30 | +2.30 | all criteria met |
| H002 | **NO** | -8.65 | 1.30 | -11.14 | magnitude ratio 0.09 outside 0.5-2.0 |
| H003 | **NO** | -7.97 | 1.27 | -10.83 | magnitude ratio 0.06 outside 0.5-2.0 |
| H004 | **YES** | -16.56 | 1.26 | -2.42 | all criteria met |
| H005 | **NO** | +32.39 | 2.83 | -63.56 | sign disagreement between tracks; magnitude ratio 4.32 outside 0.5-2.0 |

**No decomposition product is produced.** Eligibility here means only that a component estimate would be meaningful to attempt; the H005 values are diagnostic and are explicitly not a deformation product.

## 12. Final classification

| Zone | Classification | Decomposition eligible |
|---|---|---|
| **H001** | **INDEPENDENTLY_SUPPORTED** | yes |
| **H002** | **NOT_REPRODUCED** | no |
| **H003** | **NOT_REPRODUCED** | no |
| **H004** | **INDEPENDENTLY_SUPPORTED** | yes |
| **H005** | **UNRESOLVED_CONTRADICTION** | no |

Independently supported mapped area: **6.66 km²** (H001 + H004), reported **separately** from the ascending mapped area.
Unresolved area: H002 + H003 + H005 = 15.91 km².

## 13. Extent

The ascending figure is unchanged and still means exactly what it said:

```text
22.6 km2 = robustly supported mapped deformation area under the
           selected ascending quality criterion
```

It is **not** a validated deformation area. Descending coverage remains incomplete (69.6% of the AOI in the common valid domain), so D2 cannot validate the entire ascending extent, and no total-extent claim is made.

## 14. Stopping point

Stopped here. No groundwater, geology, GRACE, rainfall, urbanisation, infrastructure, or other causal interpretation has been begun. No decomposition product has been created.
