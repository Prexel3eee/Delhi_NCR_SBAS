# Phase II-B — Descending Reliability Diagnostics (CLOSEOUT)

Generated 2026-09-22 17:27 UTC.

**This closeout supersedes the Phase-IIA robustness-edge statement and the earlier status line in this file.** The superseded text is retained only in the provenance record (`provenance/errata/`), never restated as a current result.

## 1. Coherence terminology — permanent correction

Every number names its metric. The three quantities are not interchangeable:

| Metric | Definition |
|---|---|
| `IFG_SPATIAL_COHERENCE` | per-interferogram coherence from the HyP3 product |
| `AVG_IFG_SPATIAL_COHERENCE` | mean of `IFG_SPATIAL_COHERENCE` over all pairs |
| `TEMPORAL_COHERENCE` | MintPy network-inversion reliability |

**Superseded claim.** In Phase II-A I wrote that the 10 robustness edges had coherence 0.46–0.75 against a stack median of 0.277 and were therefore not the weakest links. That compared an **inverted-region** statistic with a **whole-grid** statistic — incompatible spatial supports — and is withdrawn.

**Corrected result**, all computed on the same whole-grid support:

* robustness-edge `IFG_SPATIAL_COHERENCE`: mean 0.2637, median 0.2638, range 0.2578–0.2709
* stack median: **0.2767**
* ranks of the added edges among all 219 pairs: **1–79** (median 30)

So under consistent support **the added edges rank among the weaker interferograms**, while their **absolute** coherence difference from the stack median is modest (≈0.02). Both halves of that sentence matter: they are weak in rank, but the whole stack is weak.

## 2. D3 ERA5 completion gate — proved by date identity

* accepted descending acquisitions: **92**
* dates in the frozen stack: **91** (1 dropped as unconnectable: 2024-04-13)
* ERA5 hours present in the shared cache: `['01', '13']`
* descending ERA5 hour identified: **01**
* missing dates: **0**
* unexpected dates: **0**
* **DATE-IDENTITY COVERAGE: PASSED**

The gate is evaluated **per hour**. A whole-cache set comparison is wrong here because the ERA5 directory is shared with the ascending product, which samples a different UTC hour: a naive check reported **119 spurious 'unexpected' dates** (the ascending epoch) and 42 apparent misses. Only after separating hour 01 (descending) from hour 13 (ascending) does the true answer appear. A file count would have hidden this entirely.

## 3. D0 vs D3 (ERA5) — descending-internal diagnostics

| Metric | D0 RAW | D3 ERA5 | Change |
|---|---:|---:|---:|
| inverted pixels (valid AOI) | 4,017,547.0000 | 4,017,547.0000 | +0.0000 |
| TEMPORAL_COHERENCE p25 | 0.2891 | 0.2891 | +0.0000 |
| TEMPORAL_COHERENCE p50 | 0.4021 | 0.4021 | +0.0000 |
| TEMPORAL_COHERENCE p75 | 0.4911 | 0.4911 | +0.0000 |
| pixels TC >= 0.5 | 882,596.0000 | 882,596.0000 | +0.0000 |
| pixels TC >= 0.7 | 11,013.0000 | 11,013.0000 | +0.0000 |
| median velocityStd (mm/yr) | 5.2104 | 5.2773 | +0.0669 |
| robust velocity scatter (mm/yr) | 24.4940 | 24.4400 | -0.0540 |
| high-pass velocity energy (mm/yr) | 10.0747 | 10.0749 | +0.0002 |
| residual RMS (rad) | 0.5885 | 0.5959 | +0.0074 |
| |residual-elevation| correlation | -0.0357 | -0.0124 | +0.0233 |
| stable-area velocity scatter (mm/yr) | 29.7280 | 29.6910 | -0.0370 |
| asc/desc Pearson (secondary) | 0.1752 | 0.1724 | -0.0028 |
| asc/desc Spearman (secondary) | 0.2068 | 0.2030 | -0.0038 |
| plane-detrended correlation (secondary) | 0.1269 | 0.1274 | +0.0005 |

**D3-D0 velocity change**: robust scatter 24.494 → 24.440 mm/yr (**−0.054**), high-pass energy 10.0747 → 10.0749 (**+0.0002**), residual RMS 0.5885 → 0.5959 (**+0.0074**, worse). The `TEMPORAL_COHERENCE` distribution is **byte-identical** (`tc_p50` 0.4021 → 0.4021, the same 882,596 pixels above 0.5).

**Verdict: ERA5 has essentially no effect on the descending solution.** It improves 1 of 7 descending-internal metrics. The descending failure is therefore **not tropospheric** — a clean, negative, and useful result. This is also why the ascending/descending correlation did not recover: it moved 0.1752 → 0.1724, slightly **worse**.

## 4. D2 unwrap branch — status

| Metric | D0 RAW | D2 unwrap | Change |
|---|---:|---:|---:|
| TEMPORAL_COHERENCE p50 | 0.4021 | 0.4376 | +0.0355 |
| median velocityStd | 5.2104 | 3.0703 | -2.1401 |
| robust scatter | 24.4940 | 24.4340 | -0.0600 |
| high-pass energy | 10.0747 | 5.9160 | -4.1587 |
| residual RMS | 0.5885 | 0.4569 | -0.1316 |

## 5. Branch comparison

| branch | inverted pixels | tc p25 | tc p50 | tc p75 | tc ge 0.5 | tc ge 0.7 | median velocity std | velocity robust scatter | highpass energy | residual rms | cross pearson | cross spearman | cross plane detrended |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| descending_work | 4,017,547 | 0.2891 | 0.4021 | 0.4911 | 882,596 | 11,013 | 5.2104 | 24.4940 | 10.0747 | 0.5885 | 0.1752 | 0.2068 | 0.1269 |
| descending_d1_conncomp_work | 1,658,035 | 0.4734 | 0.5147 | 0.5619 | 981,096 | 37,855 | 5.2120 | 37.2440 | 16.0239 | 0.5990 | 0.2014 | 0.1781 | 0.1760 |
| descending_d2_unwrap_work | 4,018,774 | 0.2911 | 0.4376 | 0.8346 | 1,787,340 | 1,352,660 | 3.0703 | 24.4340 | 5.9160 | 0.4569 | 0.3628 | 0.3465 | 0.3461 |
| descending_d3_era5_work | 4,017,547 | 0.2891 | 0.4021 | 0.4911 | 882,596 | 11,013 | 5.2773 | 24.4400 | 10.0749 | 0.5959 | 0.1724 | 0.2030 | 0.1274 |

Branches not evaluated: 

## 6. Stop-rule evaluation

A branch is promotable only if it improves **>=4 of 7 descending-internal metrics**. Cross-track correlation is explicitly **not** a criterion.

| Branch | Metrics improved vs D0 | Material? |
|---|---:|---|
| descending_d1_conncomp_work | 3/7 | no |
| descending_d2_unwrap_work | 7/7 | **MATERIAL** |
| descending_d3_era5_work | 1/7 | no |

* **descending_d1_conncomp_work** — tc_p50: improved, tc_ge_0.5: improved, tc_ge_0.7: improved, median_velocity_std: worse, velocity_robust_scatter: worse, highpass_energy: worse, residual_rms: worse
* **descending_d2_unwrap_work** — tc_p50: improved, tc_ge_0.5: improved, tc_ge_0.7: improved, median_velocity_std: improved, velocity_robust_scatter: improved, highpass_energy: improved, residual_rms: improved
* **descending_d3_era5_work** — tc_p50: worse, tc_ge_0.5: worse, tc_ge_0.7: worse, median_velocity_std: worse, velocity_robust_scatter: improved, highpass_energy: worse, residual_rms: worse

## 7. Structural findings preserved

**Connected-component fragmentation** — `STRUCTURAL QUALITY PROBLEM IDENTIFIED; SIMPLE CONNECTED-COMPONENT MASKING NOT SUFFICIENT`.
18.67% of inverted pixels lie **inside** the retained connected set, so **81.33%** lie outside it, carrying larger |velocity| (36.609 vs 27.779 mm/yr) and lower `TEMPORAL_COHERENCE` (0.356 vs 0.4945).

D1 tested the obvious repair — mask to the connected set — and it **failed**: it raised `TEMPORAL_COHERENCE` by retaining better pixels while making the velocity field worse on every scatter metric. So the finding is *a structural quality problem is identified*, and it is **not** inferred that the disconnected pixels alone caused the descending failure.

**Quality-conditioned agreement** — `NO EVIDENCE THAT A SIMPLE QUALITY THRESHOLD RECOVERS THE ASCENDING SPATIAL FIELD`. Agreement rises only from r ≈ 0.107 to r ≈ 0.205 across `TEMPORAL_COHERENCE` strata and does not improve monotonically with descending spatial scatter. This is **not** a claim that `TEMPORAL_COHERENCE` is not a quality metric — that would be too broad.

## 8. Protected scientific conclusions

| Observation | Status |
|---|---|
| H001 | **PARTIALLY_SUPPORTED** |
| H002 | **NOT_RESOLVED** |
| H003 | **NOT_RESOLVED** |
| H004 | **NOT_RESOLVED** |
| H005 | **NOT_RESOLVED** |
| coherence_velocity | **REPRODUCED ASSOCIATION** |
| physical_origin | **UNRESOLVED** |
| north_south_grouping | **NOT REPRODUCED** |
| spatial_gradients | **NOT REPRODUCED** |
| decomposition | **INVALID / UNPUBLISHED** |

None of these changed during Phase II-B. The descending product did not pass its own internal reliability criteria, so no hotspot status or cross-track classification was upgraded.

## 9. Final freeze

```text
DESCENDING SCIENTIFIC STATUS:
    CANDIDATE FOR REVALIDATION
```

Promoted branch: **descending_d2_unwrap_work** → `DESCENDING_PRODUCT_V2_CANDIDATE`. The Phase-IIA validation comparisons are to be repeated once.

Stopped here. No groundwater, geology, GRACE, rainfall, urbanisation, infrastructure, or other causal interpretation has been begun.

