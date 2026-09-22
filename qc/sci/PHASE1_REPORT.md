# Phase I — Final Scientific Results Characterization

Generated 2026-09-22 10:17 UTC from the frozen `product_v1` solution. Every figure below is read programmatically from the stage outputs in `qc/sci/phase1/`.

**Scope.** This phase characterizes the existing frozen solution. It does not improve, tune, smooth, correct, or modify it, and it does not attribute any observation to a physical mechanism. Causal interpretation requires independent datasets and belongs to a later phase.

## 0. Authoritative state

| Item | Value |
|---|---|
| Product freeze | `product_v1` |
| freeze_id | `2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37` |
| Principal solution | RAW-336 |
| Acquisitions / interferograms | 119 / 336 |
| Excluded pairs | 0 |
| Date span | 20211006 – 20250927 |
| Unwrap correction | disabled |
| Troposphere / DEM residual | disabled in the principal branch |
| Deramp | disabled |

All deformation quantities in this report are **line-of-sight (LOS)** and **relative** to the processing reference pixel. Sentinel-1 measures a projection of the full 3-D displacement; LOS is not vertical motion.

### 0.1 Provenance defect found during this phase (INC-007)

The frozen decision records reference pixel `y=1378, x=1426`, but the frozen product is actually referenced to `y=1384, x=1451`. `config/mintpy_baseline_raw.txt` sets only `mintpy.reference.minCoherence`, so MintPy auto-selected the reference; the ERA5 and ERA5+DEM configs do set `mintpy.reference.yx`.

Verification: `timeseries[:, 1384, 1451]` is identically zero at all 119 dates, while `timeseries[:, 1378, 1426]` is not.

**Impact.** The RAW velocity at the frozen pixel is +0.1362 mm/yr, so the v1 product carries that constant offset relative to the frozen decision. Re-basing shifts every velocity by the same constant, so **spatial gradients and hotspot contrast are unaffected**. The offset is far smaller than the 4.78 mm/yr reference-selection systematic. It also introduced a constant +0.136 mm/yr term into the published RAW-vs-ERA5 branch comparison; re-aligning the references moves the ERA5−RAW median from +0.013 to +0.149 mm/yr and the RMS from 0.521 to 0.549 mm/yr, which does not change any branch verdict.

## 1. Where reliably supported relative LOS deformation occurs

Within the AOI (1,226,497 pixels, 1,203,788 land), the primary quality mask (temporal coherence ≥ 0.80) retains 541,511 pixels. Deformation is not uniformly distributed: it is concentrated in spatially connected patches rather than scattered pixel noise.

Detected with |LOS velocity| ≥ 10 mm/yr, coherence ≥ 0.80 and a 0.4 km² minimum area: **5 hotspots covering 22.6 km²** (2.61% of eligible pixels). All are in the `away_from_satellite` sense (ground moving away from the satellite along the LOS).

| ID | Area km² | Median LOS mm/yr | Peak \|LOS\| mm/yr | Vertical-equiv mm/yr | Coherence | Longitude | Latitude |
|---|---:|---:|---:|---:|---:|---:|---:|
| H001 | 5.59 | -30.95 | 87.39 | -39.91 | 0.925 | 77.0813 | 28.5212 |
| H002 | 12.83 | -13.59 | 31.54 | -17.60 | 0.863 | 77.0735 | 28.8152 |
| H003 | 2.25 | -12.87 | 29.80 | -16.67 | 0.860 | 77.0810 | 28.8033 |
| H004 | 1.07 | -14.31 | 23.65 | -18.42 | 0.963 | 77.0554 | 28.5333 |
| H005 | 0.84 | -14.21 | 26.13 | -18.56 | 0.865 | 77.1735 | 28.8249 |

The vertical-equivalent column divides LOS by cos(incidence) and assumes the displacement is **purely vertical**. It is context only; no horizontal motion was measured or ruled out.

## 2. How large the measured deformation is

| Statistic | LOS velocity (mm/yr), primary mask |
|---|---:|
| median | -0.73 |
| mean | -1.60 |
| std | 5.34 |
| p01 | -17.37 |
| p05 | -10.18 |
| p25 | -3.32 |
| p75 | +1.26 |
| p95 | +4.17 |
| p99 | +6.82 |
| min | -87.39 |
| max | +25.86 |

The distribution is strongly asymmetric: the bulk sits near zero while a tail extends to strongly negative values. The median pixel is essentially stationary; the deformation is carried by a minority of the AOI.

Per-hotspot totals over the record:

| ID | Cumulative LOS displacement (mm) | Rate from series (mm/yr) | Rate from field (mm/yr) |
|---|---:|---:|---:|
| H001 | -120.7 | -27.09 | -30.95 |
| H002 | -48.0 | -14.42 | -13.59 |
| H003 | -46.8 | -14.07 | -12.87 |
| H004 | -59.6 | -12.55 | -14.31 |
| H005 | -44.5 | -16.12 | -14.21 |

## 3. How spatially extensive the deformation is

The extent depends strongly on the quality mask, and that dependence is itself a result. Detected hotspot area:

| \|v\| threshold (mm/yr) | coh ≥ 0.70 | coh ≥ 0.80 | coh ≥ 0.90 |
|---|---:|---:|---:|
| 5 | 164.1 | 74.6 | 12.0 |
| 7.5 | 91.9 | 38.7 | 6.2 |
| 10 | 49.5 | 22.6 | 4.5 |
| 15 | 12.8 | 5.1 | 3.2 |
| 20 | 4.4 | 3.9 | 2.6 |
| 25 | 3.7 | 3.3 | 2.0 |

At the working threshold of 10 mm/yr the detected area roughly **doubles** when coherence is relaxed from 0.80 (22.6 km²) to 0.70 (49.5 km²). Relaxing to a 5 mm/yr threshold at coherence 0.70 raises the detected area to 164.1 km² — roughly seven times the working-mask figure.

This is reinforced by the AOI-wide coherence stratification, which shows a strong monotonic relationship:

| Coherence band | Pixels | Median LOS mm/yr | p05 mm/yr | Fraction ≤ −10 mm/yr |
|---|---:|---:|---:|---:|
| 0.50–0.55 | 71,643 | -17.06 | -36.49 | 72.4% |
| 0.55–0.60 | 63,419 | -13.99 | -32.90 | 63.5% |
| 0.60–0.65 | 61,297 | -10.72 | -29.47 | 52.5% |
| 0.65–0.70 | 61,875 | -7.70 | -26.07 | 41.6% |
| 0.70–0.75 | 63,475 | -5.33 | -21.79 | 31.2% |
| 0.75–0.80 | 70,202 | -3.77 | -17.82 | 22.2% |
| 0.80–0.85 | 82,860 | -2.81 | -14.93 | 15.0% |
| 0.85–0.90 | 109,174 | -1.79 | -12.52 | 9.5% |
| 0.90–0.95 | 167,583 | -0.38 | -7.40 | 2.3% |
| 0.95–1.00 | 181,894 | -0.29 | -4.34 | 0.8% |

The lowest-coherence band has a median of -17.1 mm/yr with 72.4% of pixels beyond −10 mm/yr, while the highest-coherence band has a median of -0.3 mm/yr and 0.8%. **A high-coherence mask therefore selects against the deformation signal**, which is why the conservative hotspot catalogue is a lower bound on extent, not an estimate of it.

This relationship has two readings that these data alone cannot separate: the low-coherence terrain may genuinely deform faster, or low coherence may coincide with a coherent bias (unwrapping or atmosphere) that pushes velocity negative. The offset is far too large to be random pixel noise — the short-wavelength noise floor is 1.19 mm/yr against a 17.1 mm/yr median — so if it is an artefact it is a structured one, not scatter. Resolving this is a stated open item.

## 4. How the deformation evolves through time

Temporal form from nested linear / linear+seasonal / linear+step models over 119 dates:

`{"approximately_linear": 3, "linear_with_seasonal": 2}`

| ID | Rate mm/yr | Total mm | Annual amplitude mm | RMS linear mm | RMS seasonal mm | Form |
|---|---:|---:|---:|---:|---:|---|
| H001 | -27.09 | -120.7 | 2.73 | 12.54 | 13.33 | approximately_linear |
| H002 | -14.42 | -48.0 | 7.46 | 15.38 | 13.57 | linear_with_seasonal |
| H003 | -14.07 | -46.8 | 6.52 | 15.31 | 13.43 | linear_with_seasonal |
| H004 | -12.55 | -59.6 | 1.78 | 9.18 | 9.09 | approximately_linear |
| H005 | -16.12 | -44.5 | 3.35 | 17.43 | 16.70 | approximately_linear |

**No hotspot is well described by a single constant rate.** Splitting the record in half, the two halves disagree at every hotspot:

| ID | First half mm/yr | Second half mm/yr | Difference mm/yr |
|---|---:|---:|---:|
| H001 | -21.59 | -40.57 | -18.98 |
| H002 | -16.60 | +0.43 | +17.03 |
| H003 | -14.98 | +1.28 | +16.26 |
| H004 | -9.63 | -20.06 | -10.44 |
| H005 | -19.33 | +0.91 | +20.24 |

Three hotspots in the north (H002, H003, H005) accumulate most of their displacement in the first half and are nearly flat in the second; the southern hotspots (H001, H004) are faster in the second half. A single rate for the whole record is therefore a poor summary for any of them.

The independent stable-area control drifts -2.31 mm over the record with an epoch-to-epoch scatter of 3.53 mm. That control is common-mode: it does not average down with more pixels.

## 5. Which features persist under reasonable quality-mask choices

Each hotspot was re-detected under 14 mask scenarios (coherence cut 0.50–0.90, threshold 5–15 mm/yr, minimum area 0.4–5.0 km²). A hotspot counts as persisting only if at least half its pixels remain inside a single connected component that also meets that scenario's minimum area.

| ID | Scenarios survived | Outcome |
|---|---:|---|
| H001 | 14/14 | robust |
| H002 | 11/14 | moderate |
| H003 | 10/14 | moderate |
| H004 | 10/14 | moderate |
| H005 | 8/14 | moderate |

Only **H001** survives every scenario, including the strictest coherence cut and a 5 km² area floor. H002 and H003 survive most scenarios but disappear under coherence ≥ 0.90. H004 fails under `min_area_2.0`. H005 fails the strict coherence cuts and any area floor above 1 km².

## 6. Uncertainty and sensitivity

| Term | Value | Averages down with pixels? | What it supports |
|---|---:|---|---|
| formal fit uncertainty mm per yr | 0.8664 mm/yr | yes | relative contrast between neighbouring areas |
| short wavelength noise mm per yr | 1.1899 mm/yr | yes | detection of spatially coherent anomalies |
| common mode epoch scatter mm | 3.5324 mm | **no** | sets the practical limit on resolving the SHAPE of a time series; a few mm per epoch persists at any averaging |
| reference selection systematic mm per yr | 4.78 mm/yr | **no** | bounds the ABSOLUTE LOS offset only; relative spatial gradients and hotspot contrast are unaffected |

* Combined **relative** uncertainty (contrast between neighbouring areas): ~1.47 mm/yr.
* Combined **absolute** LOS uncertainty: ~5.00 mm/yr, dominated by the reference-selection systematic.

Sensitivity findings:

* **Reference re-basing** shifts every velocity by +0.136 mm/yr and changes no contrast. Hotspot values move together.
* **Epoch bootstrap** (resampling dates, refitting) gives 95% intervals a few mm/yr wide on each hotspot rate — narrower than the reference systematic, so it does not capture the dominant error.
* **Pixel bootstrap** intervals are tight (sub-mm/yr) because hotspot pixel counts are large. This confirms the median is well determined *given* the field, and says nothing about systematic error.
* **Split-half rates** disagree by 10–20 mm/yr, far exceeding every statistical interval. The dominant uncertainty in any single quoted rate is therefore **non-stationarity of the signal itself**, not measurement noise.

## 7. Are the oscillations localised or common-mode?

The stable-area control has a de-trended amplitude of 12.36 mm, so a real common-mode signal does exist at the few-mm level.

| ID | De-trended amplitude mm | Ratio to control | Corr. with control (linear) | Corr. (quadratic) |
|---|---:|---:|---:|---:|
| H001 | 52.98 | 4.29× | +0.343 | +0.248 |
| H002 | 59.45 | 4.81× | +0.261 | +0.401 |
| H003 | 60.76 | 4.92× | +0.297 | +0.437 |
| H004 | 33.98 | 2.75× | +0.265 | +0.188 |
| H005 | 68.28 | 5.52× | +0.251 | +0.388 |

Every hotspot oscillates 2.7–5.5× more than the stable control and correlates only weakly with it (r ≤ 0.44). The oscillations are therefore **not predominantly common-mode**.

They are, however, spatially organised. Cross-hotspot residual correlations:

| Pair | Linear de-trend | Quadratic de-trend |
|---|---:|---:|
| H001 vs H002 | -0.534 | -0.462 |
| H001 vs H003 | -0.497 | -0.422 |
| H001 vs H004 | +0.840 | +0.822 |
| H001 vs H005 | -0.503 | -0.427 |
| H002 vs H003 | +0.988 | +0.987 |
| H002 vs H004 | -0.411 | -0.344 |
| H002 vs H005 | +0.855 | +0.837 |
| H003 vs H004 | -0.402 | -0.336 |
| H003 vs H005 | +0.842 | +0.823 |
| H004 vs H005 | -0.442 | -0.379 |

Two mutually anti-correlated groups emerge, and the grouping is unchanged by switching from a linear to a quadratic de-trend — so it reflects phase, not long-term curvature:

* **Northern group** — H002, H003, H005 (mutual r = +0.82 to +0.99)
* **Southern group** — H001, H004 (mutual r = +0.82)
* **Between groups** — r = −0.34 to −0.46

A shared oscillation across hotspots ~30 km apart indicates a process or error with a regional spatial scale, while the sign reversal between north and south indicates a spatial gradient in phase or sign. Neither the amplitude ratios nor the correlations identify the mechanism.

## 8. Observations strong enough to carry forward

| ID | Area km² | LOS mm/yr | Grade | Basis |
|---|---:|---:|---|---|
| H001 | 5.59 | -30.95 | **A** | persists in 14/14 masks, coherence 0.925, |v| 30.9 mm/yr, field and series rates agree to 12% |
| H002 | 12.83 | -13.59 | **B** | persists in 11/14 masks, coherence 0.863, |v| 13.6 mm/yr |
| H003 | 2.25 | -12.87 | **B** | persists in 10/14 masks, coherence 0.860, |v| 12.9 mm/yr |
| H004 | 1.07 | -14.31 | **B** | persists in 10/14 masks, coherence 0.963, |v| 14.3 mm/yr |
| H005 | 0.84 | -14.21 | **C** | persists in only 8/14 masks; feature is mask-dependent and should not be carried forward unresolved |

**Grade A** — spatial extent, magnitude, coherence and persistence all hold, and the rate is corroborated independently by the field and by the time series. Safe to carry into interpretation.

**Grade B** — real and large, but mask-dependent in extent or coherence. Carry forward with the stated sensitivity.

**Grade C** — not resolvable at this stage.

Two further observations are strong enough to carry forward even though they are not single hotspots:

1. **Deformation is not temporally stationary.** Split-half rates differ by 10–20 mm/yr at every hotspot, far beyond any statistical interval. Any interpretation must explain a time-varying rate, not a constant one.
2. **The coherence–velocity relationship is a property of the dataset**, not of one hotspot, and it bounds how much of the AOI can ever be characterized from this stack.

## 9. What the InSAR data alone do not establish

* **No mechanism.** Nothing here identifies groundwater depletion, compaction, tectonics, construction or metro loading, lithology, or fault motion. A subsidence-shaped LOS signal is consistent with many mechanisms and discriminates none of them.
* **No vertical rate.** LOS is a projection. The vertical-equivalent column assumes purely vertical motion; horizontal components are unmeasured, so the true vertical rate is unknown and could be larger or smaller.
* **No absolute rate.** All values are relative to the processing reference. The absolute LOS offset is uncertain at 5.0 mm/yr, and no independent in-AOI geodetic reference exists to reduce it. Whether the AOI as a whole is subsiding, stable, or rising is **not determined**.
* **No validated total extent.** The high-coherence mask demonstrably excludes part of the signal, and whether the low-coherence signal is real or biased is unresolved.

### Open items

1. The coherence–velocity relationship must be adjudicated before any total-area or aggregate-volume statement is made.
2. The reference-pixel mismatch (INC-007) should be corrected at the next product revision, by setting `mintpy.reference.yx` explicitly in every branch config. It does not invalidate relative results in this product.
3. The north/south anti-correlated oscillation needs an independent dataset (GNSS, groundwater levels, or a weather-driven delay model) before interpretation.

## 10. Deliverables

Rasters (`products/product_v1/`):

* `los_velocity_mm_per_yr.tif`
* `los_velocity_uncertainty_mm_per_yr.tif`
* `los_displacement_mm.tif`
* `temporal_coherence.tif`
* `elevation_m.tif`
* `los_residue_rad.tif`
* `quality_mask.tif`

Tabular and structured results (`qc/sci/phase1/`):

* `coherence_stratification.csv`
* `deformation_map_summary.json`
* `evidence_grades.json`
* `hotspot_persistence.csv`
* `hotspot_persistence.json`
* `hotspot_threshold_sensitivity.csv`
* `hotspot_timeseries.csv`
* `hotspot_timeseries.json`
* `hotspot_timeseries_summary.csv`
* `hotspot_uncertainty.csv`
* `hotspots.csv`
* `hotspots.geojson`
* `hotspots.json`
* `oscillation_diagnostics.json`
* `stable_control_timeseries.csv`
* `uncertainty_budget.json`

