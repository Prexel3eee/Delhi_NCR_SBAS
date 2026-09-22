# Phase II-B — Descending Reliability Diagnostics

Generated 2026-09-22 15:43 UTC.

**Scope.** Identify whether a specific, testable processing or data-quality issue explains the poor descending solution, and whether ONE defensible alternative can become suitable for independent validation. No new HyP3 jobs, no modification of ascending `product_v1`, no causal attribution.

## A. Frozen D0 baseline

`DESCENDING_RAW_V1` frozen, `freeze_id acdb209f443732f4f7c5f7f3f624fd63db1d7ad1c85b62bcd963ae5297130c26`. 91 acquisitions, 219 interferograms, 10 robustness edges, 0 bridges, 1 articulation point, reference [394, 2149]. Retained regardless of branch outcome.

## B. Coherence terminology audit

Three distinct quantities existed under the single word "coherence". Every number below now names its metric.

| Metric | Definition | Descending value |
|---|---|---:|
| `IFG_SPATIAL_COHERENCE` | per-interferogram coherence from the HyP3 product | stack median 0.2767 |
| `TEMPORAL_COHERENCE` | MintPy network-inversion reliability | p50 0.4021, p90 0.5409 |
| `AVG_SPATIAL_COHERENCE` | mean of IFG_SPATIAL_COHERENCE over pairs | p50 0.4504 |

Previously reported numbers, now resolved:

| Reported | Actually was | Recomputed |
|---|---|---:|
| `0.277` | IFG_SPATIAL_COHERENCE — median over all 219 pairs of each pair's AOI-median coherence | `0.2767` |
| `0.467` | TEMPORAL_COHERENCE — p50 over inverted (velocityStd>0) pixels | `0.4021` |
| `0.46-0.75` | IFG_SPATIAL_COHERENCE — range across the 10 added robustness edges | `[0.2578, 0.2709]` |
| `19 pixels above 0.7` | TEMPORAL_COHERENCE — count of pixels with TC >= 0.7 | `11013` |

**This audit caught an error of my own.** In Phase II-A I reported that the 10 robustness edges had coherence 0.46–0.75 against a stack median of 0.277, and concluded they were not the weakest links. Those two numbers were computed over **different pixel domains** — the edges over the inverted/AOI region, the stack median over the whole grid — so the comparison was invalid. Computed consistently over the whole grid, the edges have `IFG_SPATIAL_COHERENCE` 0.258–0.271 against a stack median of 0.277, giving them **ranks 1–79 of 219**. Section G below supersedes the Phase II-A claim.

## C. Quality-conditioned cross-track agreement

Agreement improves only marginally with descending quality, and never becomes good. Stratified by `TEMPORAL_COHERENCE` (equal-count quintiles):

| Stratum | n | Pearson | Spearman | Plane-detrended | Desc scatter |
|---|---:|---:|---:|---:|---:|
| q1_0.011_0.388 | 170,801 | +0.107 | +0.118 | +0.083 | 19.31 |
| q2_0.388_0.449 | 170,801 | +0.129 | +0.156 | +0.092 | 27.90 |
| q3_0.449_0.484 | 170,800 | +0.169 | +0.165 | +0.142 | 30.29 |
| q4_0.484_0.519 | 170,801 | +0.189 | +0.171 | +0.166 | 31.65 |
| q5_0.519_0.720 | 170,801 | +0.205 | +0.177 | +0.188 | 33.68 |

Progressively better quality subsets (thresholds were **not** lowered to gain pixels):

| Subset | n | Pearson | Spearman | Plane-detrended |
|---|---:|---:|---:|---:|
| TC>=0.4 | 661,442 | +0.179 | +0.177 | +0.148 |
| TC>=0.45 | 506,854 | +0.190 | +0.173 | +0.165 |
| TC>=0.5 | 257,394 | +0.202 | +0.174 | +0.183 |
| TC>=0.55 | 70,706 | +0.202 | +0.177 | +0.189 |
| TC>=0.6 | 9,185 | +0.183 | +0.163 | +0.175 |
| TC>=0.65 | 515 | +0.139 | +0.162 | +0.153 |
| TC>=0.7 | too few | | | |

**Answer to the posed question: no.** Agreement rises from r = 0.107 in the worst `TEMPORAL_COHERENCE` quintile to r = 0.205 in the best, and peaks at r = 0.202 for `TEMPORAL_COHERENCE` >= 0.55. Even the best-supported descending pixels reproduce the ascending structure at only r ≈ 0.20. Notably, descending scatter **increases** with quality stratum (25.1 -> 33.7 mm/yr), so the descending quality metrics do not behave as quality indicators.

## D. Inversion-setting audit

Read from the executed template, not assumed:

| Setting | Executed value |
|---|---|
| `mintpy.network.keepMinSpanTree` | `no` |
| `mintpy.network.coherenceBased` | `no` |
| `mintpy.network.areaRatioBased` | `no` |
| `mintpy.network.minCoherence` | `0.0` |
| `mintpy.network.minAreaRatio` | `0.0` |
| `mintpy.reference.minCoherence` | `0.85` |
| `mintpy.unwrapError.method` | `no` |
| `mintpy.troposphericDelay.method` | `no` |
| `mintpy.deramp` | `no` |
| `mintpy.topographicResidual` | `no` |
| `mintpy.residualRMS.deramp` | `no` |
| `mintpy.networkInversion.weightFunc` | `var` |
| `mintpy.networkInversion.minRedundancy` | `1` |
| `mintpy.networkInversion.maskDataset` | `no` |
| `mintpy.networkInversion.minNormVelocity` | `yes` |
| `mintpy.residualRMS.maskFile` | `no` |
| `mintpy.plot` | `no` |

`weightFunc` is already `var` (inverse-variance), so **no weighting branch was needed** — that diagnostic is closed by inspection. `maskDataset` was `no`, so a connected-component-masked branch (D1) was justified as a sensitivity experiment.

## E. Unwrapping / connected-component diagnostics

* inverted descending pixels: **4,017,547**
* inside the retained connected set: **750,143** (**18.67%**)
* outside the connected set: median |velocity| 36.609 mm/yr vs inside 27.779 mm/yr
* outside: `TEMPORAL_COHERENCE` 0.356 vs inside 0.4945

**81.3% of the inverted area lies outside the retained connected set**, and those pixels carry both larger |velocity| and lower `TEMPORAL_COHERENCE`. With `maskDataset = no` the D0 inversion used them anyway. This is the strongest single candidate cause, and it is directly testable as branch D1.

Residual burden on inverted pixels: median |residue| 0.5835 rad, p90 0.7631 rad. (velocity.h5 `residue` is the per-pixel median residual phase; this is a residual burden, not a true phase-closure count)

## F. ERA5 test

D3 was not available for evaluation.

## G. Long-gap / robustness-edge influence

| Reference | Secondary | dt | `IFG_SPATIAL_COHERENCE` | Rank of 219 | Percentile | Role |
|---|---|---:|---:|---:|---:|---|
| 2022-03-31 | 2022-05-30 | 60 | 0.2636 | 30 | 13.7 | remove_bridge |
| 2022-07-29 | 2022-11-26 | 120 | 0.2578 | 1 | 0.5 | remove_bridge |
| 2022-08-10 | 2022-11-26 | 108 | 0.2594 | 4 | 1.8 | connect_components |
| 2022-11-26 | 2023-01-25 | 60 | 0.2684 | 69 | 31.5 | remove_bridge |
| 2023-01-01 | 2023-05-01 | 120 | 0.2659 | 47 | 21.5 | remove_bridge |
| 2023-08-29 | 2023-12-27 | 120 | 0.2605 | 8 | 3.7 | remove_bridge |
| 2024-01-08 | 2024-03-08 | 60 | 0.2709 | 79 | 36.1 | remove_bridge |
| 2024-04-01 | 2024-05-19 | 48 | 0.2681 | 68 | 31.1 | reduce_articulation |
| 2024-05-19 | 2024-09-16 | 120 | 0.2586 | 2 | 0.9 | remove_bridge |
| 2024-05-31 | 2024-07-18 | 48 | 0.2638 | 31 | 14.2 | connect_components |

Computed consistently over the whole grid, the robustness edges rank **1–79 of 219** (median 30) — they ARE among the weakest pairs, contradicting the invalid Phase II-A comparison. However the absolute spread is small (0.258–0.271 against a stack median of 0.277): the whole stack is low-coherence, so the edges are weak largely because everything is weak. Their actual leverage on the velocity field is quantified by the D-branch comparison, not by rank alone.

## H. Coherence–velocity interpretation

Curve correlation across geometries: **r = 0.8311231664228349**.

Classification: **REPRODUCED ASSOCIATION**, not VALIDATED DEFORMATION.

The relationship recurs in an independent heading, incidence and network, so it is a property of the data rather than of one processing configuration. It does **not** distinguish physical deformation from a quality-dependent structured bias. Conditioning it on `TEMPORAL_COHERENCE`, `AVG_SPATIAL_COHERENCE`, velocity uncertainty and observation count is the discriminating test; land-cover stratification is not authorised in this phase. The association must not be overinterpreted.

## I. Branch comparison

| Branch | Inverted px | TC p25 | TC p50 | TC p75 | TC>=0.5 | TC>=0.6 | TC>=0.7 | med vStd | robust scatter | high-pass | resid RMS | asc/desc r | Spearman | plane-detrended |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **descending_work** | 4,017,547 | 0.289 | 0.402 | 0.491 | 882,596 | 76,567 | 11,013 | 5.210 | 24.494 | 10.075 | 0.589 | 0.175 | 0.207 | 0.127 |
| **descending_d1_conncomp_work** | 1,658,035 | 0.473 | 0.515 | 0.562 | 981,096 | 214,521 | 37,855 | 5.212 | 37.244 | 16.024 | 0.599 | 0.201 | 0.178 | 0.176 |

Per-zone velocity and `TEMPORAL_COHERENCE` by branch:

* **descending_work** — H001 -84.7 mm/yr (TC 0.501, n=3494), H002 -30.5 mm/yr (TC 0.473, n=8015), H003 -21.9 mm/yr (TC 0.469, n=1408), H004 -44.2 mm/yr (TC 0.490, n=670), H005 -35.5 mm/yr (TC 0.494, n=522)
* **descending_d1_conncomp_work** — H001 -85.6 mm/yr (TC 0.506, n=3493), H002 -30.0 mm/yr (TC 0.476, n=8004), H003 -21.4 mm/yr (TC 0.471, n=1408), H004 -44.2 mm/yr (TC 0.491, n=670), H005 -107.7 mm/yr (TC 0.531, n=521)

## J. Final descending usability decision

Branches not evaluable in this run: D2_UNWRAP (not run), D3_ERA5 (incomplete at evaluation time). They are reported as not evaluated rather than substituted by a stale clone.

* **descending_d1_conncomp_work**: 3/7 internal metrics improved vs D0 -> not material

Stop rule: a branch is promotable only if it materially improves its **own** internal quality (>=4 of 7 metrics), never on cross-track resemblance.

No branch produced a material, internally supported improvement. The predeclared conclusion is therefore frozen:

```text
DESCENDING_PATH136_NOT_SUITABLE_FOR_QUANTITATIVE_INDEPENDENT_VALIDATION_V1
```

### Protected statuses

H001 remains **PARTIALLY_SUPPORTED**; H002–H005 remain **NOT_RESOLVED**. No classification was upgraded during diagnostics. These are results of an *inconclusive validation experiment*, not evidence against the ascending hotspots.

The Phase II-A vertical/E-W decomposition remains **INVALID and unpublished**. Its condition number (κ = 1.384) is acceptable, but good matrix conditioning does not produce a good component estimate from an unreliable input. The −22 to −74 mm/yr vertical values are diagnostic artefacts.

---

```text
DESCENDING SCIENTIFIC STATUS:
    NOT SUITABLE FOR QUANTITATIVE INDEPENDENT VALIDATION
```

Stopped here. No groundwater, geology, GRACE, urbanisation or other causal interpretation has been begun.


---

## Addendum — branches not evaluable in this run

The predeclared branch set was D0–D3. At evaluation time:

| Branch | State | Consequence |
|---|---|---|
| D0 RAW | **complete** | evaluated, frozen as `DESCENDING_RAW_V1` |
| D1 connected-component masking | **complete** | evaluated — 3/7 internal metrics improved, **not material**, rejected |
| D2 unwrap (bridging + phase_closure) | **not run** | out of session budget; not evaluated |
| D3 ERA5 | **incomplete** | the 91-epoch ERA5 download had not finished, so its `velocity.h5` was still the cloned D0 file |

D3 was excluded by an explicit completion guard rather than evaluated from the stale
clone: a branch work directory is an APFS clonefile of D0, which preserves mtimes,
so an unfinished branch would otherwise have been silently reported as a result.
That guard is the reason the branch table has two rows and not four.

**The verdict does not rest on the missing branches.** D1 is the branch that the
diagnostics themselves identified as the strongest candidate — 81.33% of the
inverted area lies outside the retained connected set, and those pixels carry both
larger |velocity| and lower `TEMPORAL_COHERENCE`. D1 was run, and it failed on
internal quality: it raised `TEMPORAL_COHERENCE` (p50 0.402 -> 0.515) purely by
retaining better pixels, while making the velocity field **worse** on every
scatter metric (robust scatter 24.49 -> 37.24 mm/yr, high-pass energy
10.07 -> 16.02 mm/yr, residual RMS 0.589 -> 0.599 rad). Masking to the connected
set selects a cleaner-looking subset without making the inversion more reliable.

D3 (ERA5) remains the one genuinely untested hypothesis, and it is worth testing:
the descending pass samples ~00:52 UTC against ascending ~12:55 UTC, so the
atmospheric realisation can differ materially. D2 is a lower priority because
connected-component fragmentation, not closure error, is the measured dominant
issue.
