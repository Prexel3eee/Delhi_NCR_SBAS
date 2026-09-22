# Delhi-NCR SBAS - RAW-336 Scientific Report

Generated: 2026-09-22T05:10:37.281647+00:00

**Status: stopping point. No final deformation product is declared, and the
tropospheric and DEM-residual branches are not run yet** (they belong after the
network and reference are frozen).

## 1. Frozen input

| item | value |
|---|---|
| freeze | `freeze/mintpy_input_v1` (hash-pinned, verified) |
| network | 336 interferograms / 119 acquisitions |
| grid | 2407 x 2939 px @ 40 m, EPSG:32643 |
| period | 2021-10-06 to 2025-09-27 |
| HyP3 corpus | unchanged; 2025-05-18 remains excluded (fail-closed) |

**No pair was removed before the baseline inversion.** MintPy's `dropIfgram`
flag remains all-336-in-use afterwards (note: the flag is *inverted* relative
to its name - `True` means in use).

## 2. AOI-centric interferogram QC (all 336 pairs)

AOI polygon: **1226497 px = 1962.4 km²**, water fraction 0.018515.

| temporal baseline | n | median coherence | median largest component (AOI) |
|---|---|---|---|
| 12 d | 113 | 0.7490 | 0.9646 |
| 24 d | 113 | 0.5661 | 0.8489 |
| 36 d | 110 | 0.4467 | 0.6675 |

Coherence degrades cleanly with temporal baseline (0.3223 to 0.9285 across pairs). Unwrapped-phase validity over the AOI is uniform at 0.981491 - the missing ~1.85% is water, which the mask removes by design.

## 3. RAW-336 baseline inversion (uncorrected)

Corrections deliberately **disabled**: unwrap error, troposphere, deramp, DEM
residual. `keepMinSpanTree` forced off (MintPy defaults it to *yes* and would
have silently dropped pairs). Runtime 13m25s.

| quantity | median | p05 | p95 | std |
|---|---|---|---|---|
| raw LOS velocity (m/yr) | -0.0042 | -0.0342 | 0.0044 | 0.0125 |
| velocity uncertainty (m/yr) | 0.0012 | | | |
| temporal coherence | 0.7488 | 0.3177 | 0.9849 | 0.2386 |
| per-ifg residual RMS (rad) | 4.593 | | 18.762 | |

- 55.1% of the AOI exceeds temporal coherence 0.7.
- The velocity field is skewed negative: p05 = -0.0342 m/yr (-34 mm/yr) versus p95 = 0.0044 m/yr. That asymmetry is the LOS subsidence signature, but it is **relative** to the reference pixel and is not yet a deformation product.
- Residual model validated: Spearman(residual RMS, coherence) = -0.3716 (consistent).

## 4. Candidate bad-pair table (proposal only)

**39 of 336 pairs (11.6%)** are robust
outliers *within their own temporal-baseline class*. Absolute thresholds are
meaningless on an uncorrected baseline - an initial fixed 1 rad cut flagged
333/336 because unmodelled atmosphere and orbit ramps dominate the residual.

| pair | t (d) | coh median | largest comp | residual RMS (rad) | reasons |
|---|---|---|---|---|---|
| 20230330_20230411 | 12 | 0.421 | 0.723959 | 18.6066 | 2 |
| 20230809_20230821 | 12 | 0.454 | 0.70957 | 19.2274 | 2 |
| 20220721_20220802 | 12 | 0.5055 | 0.805925 | 18.9447 | 2 |
| 20230318_20230330 | 12 | 0.5276 | 0.803143 | 21.4537 | 2 |
| 20230728_20230902 | 36 | 0.3315 | 0.370652 | 43.9575 | 1 |
| 20230622_20230716 | 24 | 0.3417 | 0.480521 | 20.1895 | 1 |
| 20230222_20230330 | 36 | 0.3431 | 0.478212 | 34.9715 | 1 |
| 20220615_20220721 | 36 | 0.3455 | 0.456573 | 42.335 | 1 |
| 20230809_20230902 | 24 | 0.3601 | 0.53823 | 37.4955 | 1 |
| 20230716_20230728 | 12 | 0.364 | 0.569785 | 6.1247 | 1 |
| 20230809_20230914 | 36 | 0.368 | 0.542172 | 23.3572 | 1 |
| 20220814_20220907 | 24 | 0.3703 | 0.567749 | 22.191 | 1 |
| 20230529_20230704 | 36 | 0.3771 | 0.560232 | 21.3807 | 1 |
| 20250903_20250915 | 12 | 0.3895 | 0.586011 | 3.6227 | 1 |
| 20230330_20230423 | 24 | 0.3993 | 0.677298 | 22.315 | 1 |

Distribution by temporal baseline: {12: 28, 24: 6, 36: 5}. The candidates **cluster in mid-2023**, which is itself diagnostic.

## 5. Unwrap-correction comparison

Bridging + phase closure, identical in every other respect. Runtime 23m33s.

| metric | RAW | bridging+phase_closure |
|---|---|---|
| velocity median (m/yr) | -0.004151 | -0.002491 |
| temporal coherence median | 0.748842 | 0.740092 |
| per-ifg residual RMS median (rad) | 4.593 | 5.1076 |
| pairs improved / worsened | - | 134 / 202 |

Velocity changes by **2.62 mm/yr RMS** (max |delta| 35.8 mm/yr), so the correction is materially changing ambiguities. However it **degrades** the fit: residual RMS median rises 4.593 -> 5.1076 rad, only 134 of 336 pairs improve, and temporal coherence falls -0.010475 on median.

**Recommendation: do not enable unwrap correction for production in this
configuration.** Its benefit is not demonstrated, and it may require parameter
tuning (`connCompMinArea`, `numSample`, `bridgePtsRadius`) for this 40 m
4-burst dataset before it can be reconsidered.

## 6. Reference sensitivity

Candidates were selected on coherence and velocity **uncertainty** only. Velocity
was deliberately **not** a selection criterion: choosing the reference because its
velocity is near zero is circular and would hide the systematic.

| region | lon | lat | median tc | velocity (mm/yr) | uncertainty (mm/yr) |
|---|---|---|---|---|---|
| R1 | 77.09504 | 28.64256 | | -0.14 (vs baseline) | |
| R2 | 77.16955 | 28.68469 | | +0.14 (vs baseline) | |
| R3 | 77.02101 | 28.62202 | | -2.95 (vs baseline) | |
| R4 | 77.26775 | 28.68308 | | -0.32 (vs baseline) | |
| R5 | 77.2409 | 28.57526 | | +1.83 (vs baseline) | |

**Velocity spread across candidates: 4.78 mm/yr (sd 1.716).**

That spread is the systematic uncertainty the reference imposes on **absolute** LOS
velocity across the whole AOI. For a study whose signals are tens of mm/yr this is
material and must be reported. **Relative spatial gradients are unaffected** by the
reference choice, so hotspot *contrast* is robust even while the absolute offset is not.

Recommended: **lon 77.09504, lat 28.64256** (median tc 0.9905, uncertainty-derived std -0.00014 m/yr). Geographic plausibility (bedrock/ridge versus floodplain) is for the owner to confirm.

## 7. Proposed curated network and graph audit

| network | pairs | components | bridges | articulation pts | min degree | accepted |
|---|---|---|---|---|---|---|
| FULL | 336 | 1 | 0 | 0 | 3 | True |
| CURATED (naive) | 297 | 1 | 1 | 2 | 1 | False |

**Naive exclusion is rejected.** Removing all 39 candidates keeps the network
connected but introduces a bridge, two articulation points and a node of degree 1
(2023-08-09 falls from degree 4 to 1).

- Greedy repair restoring the fewest pairs: 1 restored -> 298 pairs, still **not accepted**.
- Alternative (prune under-supported acquisitions): 8 dates dropped (2023-03-30, 2023-07-16, 2023-08-09, 2023-09-02, 2023-07-04, 2023-07-28, 2023-06-22, 2023-08-21) -> 282 pairs / 111 dates, **accepted = False**.

The candidates cluster in mid-2023, so removing them strips redundancy exactly where
the network is weakest. Combined with the unwrap result above, the defensible
position is: **retain all 336 pairs** and treat exclusion as unnecessary for now.

## 8. What is deliberately NOT done

- No final deformation product is declared.
- ERA5 tropospheric correction and DEM-residual correction are **not** run: the brief
  places them after the network and reference are frozen, and both are still open.
- Spatial deramping is not enabled by default and was not run; it remains a
  sensitivity experiment only, because broad subsidence gradients may be genuine.
- The production reference is not frozen.

## 9. Decisions requested

1. **Reference:** confirm or replace `lon 77.0950, lat 28.6426`; accept the ~5 mm/yr
   absolute-velocity systematic and interpret gradients.
2. **Network:** confirm retaining all 336 pairs, or choose a curation strategy with
   the graph consequences stated above.
3. **Unwrap correction:** confirm leaving it disabled.
4. Only then: authorise the ERA5 branch, then the DEM-residual branch.

