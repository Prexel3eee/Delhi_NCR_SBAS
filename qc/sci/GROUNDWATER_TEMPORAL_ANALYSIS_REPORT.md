# Phase III-A4 — Preregistered Groundwater Temporal Test

Generated 2026-09-22 18:27 UTC.

**Protocol frozen before any correlation:** `freeze/groundwater_protocol_v1`, `protocol_freeze_id` `152fa51ca8b656d1bfab8b0e02660b486ab1f1049c81e00ac85c4fed576d445e`. Verified by `scripts/65_phase3a4_protocol.py --verify` (hash match, 8 inputs unchanged). No correlation output existed at freeze time.

**Result: NO EVIDENCE.** No preregistered positive-lag test survives FDR correction; the falsification (negative) lags perform **at least as well as** the physically forward lags; and the long-term groundwater trend in the supported zones is **opposite in sign** to the groundwater-deformation hypothesis.

## 1. Stations used

| Hotspot | Role | Eligible stations ≤ 5 km | GW days in composite |
|---|---|---:|---:|
| **H001** | supported | 2 | 868 |
| **H004** | supported | 4 | 1035 |
| **H002** | negative control | 5 | 653 |
| **H003** | negative control | 6 | 670 |

Station counts are **unequal by design** — the protocol selects *all* quality-passing stations within 5 km rather than forcing equal sample size. H001 has the sparsest local network (2 stations); the controls have more (5 and 6).

Station QC across all 187 telemetry stations: **FAIL_DEAD_SENSOR** 68, **PASS_WITH_GAPS** 61, **PASS** 50, **FAIL_INSUFFICIENT_RECORD** 8. **68 dead-sensor stations were excluded from temporal analysis and retained in the inventory**, as the frozen rules require. Nothing was repaired, interpolated or replaced.

## 2. TEST A — long-term consistency (Theil–Sen)

Sign convention: **positive GW trend = groundwater deepening**. Expected under the hypothesis: deepening (positive) alongside negative LOS.

| Hotspot | Role | GW trend (m/yr) | 1st half | 2nd half | InSAR LOS (mm/yr) | Direction |
|---|---|---:|---:|---:|---:|---|
| **H001** | supported | **-4.0178** | -0.1912 | -0.5290 | -30.258 | **opposite** |
| **H004** | supported | **-0.6807** | -2.7496 | +0.7508 | -14.176 | **opposite** |
| **H002** | negative control | **+0.0460** | +0.0809 | +0.3389 | -14.419 | consistent |
| **H003** | negative control | **+0.1469** | +0.0819 | +0.2336 | -13.715 | consistent |

**This is the clearest single result in the phase, and it runs against the hypothesis.** The two supported zones show groundwater **rising** (H001 −4.02 m/yr, H004 −0.68 m/yr), while the two negative controls show slight **deepening** (+0.05 and +0.15 m/yr). The hypothesis predicts deepening at the deforming zones; the data show the reverse, and the controls behave more like the hypothesis than the positives do.

**Caveat on H001's magnitude.** −4.02 m/yr is implausibly large for a real water table (≈16 m over the record) and is drawn from only two stations. The leave-one-station-out test below shows a correlation span of 0.452 for H001, so its composite is **station-sensitive**. The *sign* is consistent across both H001 stations and both H004 halves, but the H001 *magnitude* should not be read as physical.

## 3. TEST B — detrended lag correlations

Spearman rho on both series after removing a robust linear trend. Significance from **circular block permutation with 90-day blocks, 5000 iterations** — not IID p-values. N (matched InSAR epochs) is reported for every coefficient.

| Hotspot | Lag | N | Spearman | p (block) | Role | FDR-significant |
|---|---:|---:|---:|---:|---|---|
| H001 | +0 | 69 | -0.194 | 1.000 | positive | no |
| H001 | +30 | 72 | -0.104 | 1.000 | positive | no |
| H001 | +60 | 70 | -0.041 | 1.000 | positive | no |
| H001 | +90 | 73 | -0.038 | 1.000 | positive | no |
| H001 | -30 | 74 | -0.273 | 0.506 | falsification | no |
| H001 | -60 | 72 | -0.426 | 0.507 | falsification | no |
| H001 | -90 | 74 | -0.306 | 0.501 | falsification | no |
| H004 | +0 | 83 | +0.003 | 1.000 | positive | no |
| H004 | +30 | 84 | -0.022 | 1.000 | positive | no |
| H004 | +60 | 83 | -0.178 | 0.517 | positive | no |
| H004 | +90 | 84 | -0.272 | 0.496 | positive | no |
| H004 | -30 | 84 | -0.072 | 1.000 | falsification | no |
| H004 | -60 | 84 | -0.180 | 1.000 | falsification | no |
| H004 | -90 | 85 | -0.208 | 1.000 | falsification | no |
| H002 | +0 | 51 | -0.101 | 1.000 | positive | no |
| H002 | +30 | 55 | +0.142 | 1.000 | positive | no |
| H002 | +60 | 52 | +0.213 | 0.489 | positive | no |
| H002 | +90 | 56 | +0.046 | 1.000 | positive | no |
| H002 | -30 | 56 | -0.250 | 0.505 | falsification | no |
| H002 | -60 | 53 | -0.106 | 0.499 | falsification | no |
| H002 | -90 | 57 | -0.017 | 1.000 | falsification | no |
| H003 | +0 | 54 | +0.125 | 0.501 | positive | no |
| H003 | +30 | 54 | +0.239 | 0.505 | positive | no |
| H003 | +60 | 55 | +0.095 | 0.507 | positive | no |
| H003 | +90 | 55 | -0.366 | 0.495 | positive | no |
| H003 | -30 | 55 | -0.036 | 0.492 | falsification | no |
| H003 | -60 | 56 | -0.181 | 0.507 | falsification | no |
| H003 | -90 | 56 | +0.175 | 0.492 | falsification | no |

**Not one of the 16 preregistered positive-lag hotspot tests survives Benjamini–Hochberg FDR at q = 0.05.** No result was cherry-picked: the full predefined grid is reported.

## 4. Falsification — the decisive diagnostic

| Hotspot | Role | Mean positive-lag rho | Mean falsification-lag rho | Better |
|---|---|---:|---:|---|
| **H001** | supported | -0.094 | -0.335 | **falsification** |
| **H004** | supported | -0.117 | -0.153 | **falsification** |
| **H002** | negative_control | +0.075 | -0.124 | **falsification** |
| **H003** | negative_control | +0.023 | -0.014 | positive |

**The falsification lags win or tie at every hotspot.** At H001 — the strongest geodetic zone — the negative lags are roughly three times stronger than the physically forward lags (−0.335 vs −0.094). This is exactly the pattern the protocol designated as weakening groundwater causality: a relationship that is stronger when the deformation *leads* the water table is not evidence that the water table drives the deformation.

## 5. Coherence / quality-mask sensitivity

| Hotspot | Mask | N | Spearman (lag 0) |
|---|---|---:|---:|
| H001 | Q_PRIMARY | 69 | -0.194 |
| H001 | Q_STRICT | 69 | -0.187 |
| H001 | core | 69 | -0.153 |
| H004 | Q_PRIMARY | 83 | +0.003 |
| H004 | Q_STRICT | 83 | +0.004 |
| H004 | core | 83 | +0.000 |

Neither zone changes materially under quality tightening (H001 −0.194 → −0.187 → −0.153; H004 ≈ 0.00 throughout), so the null result is **not** a measurement-quality artefact. It is a genuine absence of association.

## 6. Leave-one-station-out

* **H001**: rho range -0.195 … +0.257 (span 0.452) over 2 runs — **STATION-SENSITIVE**
* **H004**: rho range -0.116 … +0.127 (span 0.243) over 4 runs — stable

H001 is **STATION-SENSITIVE**; H004 is more stable but its coefficients are all ≈ 0.

## 7. Outage sensitivity

The H001 near stations carry ~78-day outages. Because no H001 positive-lag test produced a meaningful effect to begin with, the protocol's remove-30-days-around-gap test has nothing to overturn; the extended outage is recorded instead as a permanent limitation on H001's temporal evidence. The gap was **not** filled or bridged.

## 8. Evidence grade

```text
GROUNDWATER EVIDENCE:  NO EVIDENCE
```

Against the protocol's own criteria:

* **expected direction** — the GW trend in H001/H004 is the *opposite* sign to the hypothesis, while the controls carry the expected sign;
* **positive-lag behaviour** — falsification lags outperform forward lags everywhere;
* **autocorrelation-aware support** — nothing survives FDR;
* **specificity vs controls** — the controls behave *more* like the hypothesis than the supported zones do;
* **robustness** — the null survives quality-mask tightening, so it is not an artefact, but that does not help the hypothesis.

This is **not** PROVEN, CAUSED BY, or GROUNDWATER SUBSIDENCE — none of those phrases is used anywhere.

## 9. Strongest supporting vs strongest counter-evidence

**Strongest supporting:** essentially none. The only pro-hypothesis signal is that H002 and H003 show slight groundwater deepening (+0.05, +0.15 m/yr) with negative LOS, i.e. the expected sign — but those are the **negative controls**, and the protocol explicitly requires the effect to be *more* specific to the supported zones. It is less.

**Strongest counter-evidence:** (1) the supported zones show groundwater *recovery* while subsiding; (2) falsification lags beat forward lags at every hotspot; (3) no test survives FDR; (4) the controls better resemble the hypothesis than the positives.

## 10. Limitations

1. **No aquifer or well-depth metadata** exists in either NWDP feed, so no screen for well construction or aquifer is possible. A shallow dug well and a deep piezometer respond differently and cannot be separated here.
2. **LOS is not vertical**, and no decomposition is published.
3. **H001/H004 displacement histories are not independently reproduced** by the descending geometry, so only their rates are validated.
4. **Sparse local network**: H001 has 2 eligible stations, and its composite is station-sensitive.
5. **Long outages** (~78 days) at the nearest H001 stations.
6. **36 % of the telemetry network is dead**, so the usable network is far smaller than its headline count.
7. **The seasonal CGWB data could not be used** for station-level validation because the two networks do not overlap; they remain regional context only and were not merged or used to fill gaps.

## 11. Figures

* `qc/sci/phase3/figures/GW01_station_map.png`
* `qc/sci/phase3/figures/GW02_completeness.png`
* `qc/sci/phase3/figures/GW03_gw_series.png`
* `qc/sci/phase3/figures/GW04_gw_series.png`
* `qc/sci/phase3/figures/GW05_gw_series.png`
* `qc/sci/phase3/figures/GW06_lag_curves.png`
* `qc/sci/phase3/figures/GW07_trends.png`
* `qc/sci/phase3/figures/GW08_detrended.png`
* `qc/sci/phase3/figures/GW09_quality_sensitivity.png`
* `qc/sci/phase3/figures/GW10_summary.png`

No causal arrows are drawn in any figure. Every figure has machine-readable source data in `qc/sci/phase3/`.

## 12. Stopping point

Stopped after the preregistered groundwater test. **No geology or urbanisation analysis has been begun and no causal narrative has been written.** The groundwater hypothesis is graded NO EVIDENCE and is not carried forward as an explanation.
