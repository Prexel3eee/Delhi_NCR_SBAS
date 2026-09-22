# Final Scientific Evidence Report

## Delhi-NCR SBAS-InSAR: what the observations establish, and what they do not

Synthesised 2026-09-22 18:50 UTC from the frozen evidence set. `final_evidence_v1`, `freeze_id` `db329cf47f4bef92a020056e608decbf95644463f8148570478128d2861c9e88`.

**Central conclusion.**

> Two localized relative LOS deformation features in Delhi-NCR were independently supported by ascending and descending Sentinel-1 observations at the spatial / mean-rate level, while two comparable ascending features were not reproduced and a fifth remained contradictory across viewing geometries. Preregistered tests found no evidence that groundwater-level variability, shallow soil texture, or existing or recent urbanisation explained the selectivity of the supported features. Their physical mechanism therefore remains unresolved with the available data.

In one line: **the deformation observations are more robust than their physical explanation.**

---

## 1. Research question

Does a spatially heterogeneous relative line-of-sight (LOS) deformation field exist over Delhi-NCR in the Sentinel-1 record for 2021-10 to 2025-09, and can any of the candidate physical explanations account for where it occurs?

The study was designed so that the second half of that question could fail. Hypothesis tests were preregistered, negative controls were carried throughout, and selectivity — not mere presence of a variable — was the acceptance criterion.

## 2. Data and study design

| Element | Value |
|---|---|
| AOI | Delhi-NCR, 1,962.4 km², EPSG:32643 |
| Ascending track | Sentinel-1 relative orbit 27, IW2, VV, K = 4 bursts |
| Ascending stack | 119 acquisitions, 336 interferograms, **0 pairs excluded** |
| Descending track | Sentinel-1 relative orbit 136, IW1, VV, K = 4 bursts |
| Descending stack | 91 acquisitions, 219 interferograms |
| Processing | HyP3 `INSAR_ISCE_MULTI_BURST` + MintPy 1.6.4, 10×2 looks, 40 m |
| Corrections in the frozen branch | unwrap off, troposphere off, DEM residual off, deramp off |
| Credits | 1,750 HyP3 (70 pilot + 1,680 production) + 1,095 descending |

The ascending product was frozen as `product_v1` before any scientific interpretation, so that later analysis could not tune it.

## 3. Ascending deformation result

The ascending field is spatially heterogeneous and strongly asymmetric: the median pixel is essentially stationary (−0.73 mm/yr) while a tail extends to −87 mm/yr. Deformation is carried by a minority of the AOI in spatially connected patches, not by scattered noise.

Five zones were detected at |LOS| ≥ 10 mm/yr, temporal coherence ≥ 0.80 and ≥ 0.4 km²:

```text
22.6 km2 = robustly supported mapped deformation area under the
           selected ascending quality criterion
```

**That phrase is load-bearing.** It is *not* a validated deformation area, *not* a true deformation extent, and *not* a subsidence area. Deformation magnitude and temporal coherence are strongly associated in this stack, so a coherence-based criterion systematically excludes part of the signal; the true extent is unresolved.

## 4. Independent descending validation

A second, independently constructed descending product was built — no burst, pair, mask or acquisition list shared with ascending, and no pair chosen because it intersected a hotspot.

Its first processing state (D0, raw) did **not** reproduce the ascending field (Pearson 0.175). Diagnostics located the cause: 81.3 % of inverted pixels lay outside the retained connected set. Masking them (D1) failed — coherence rose while every scatter metric worsened. **Unwrap correction (D2, bridging + phase closure) succeeded: 7 of 7 internal metrics improved**, including temporal coherence p75 0.49 → 0.83 and pixels with TC ≥ 0.7 from 11,013 → 1,352,660.

Against D2 the cross-track agreement roughly doubled (Pearson 0.175 → 0.363). That is a real improvement and it is **not** global validation:

```text
CROSS-GEOMETRY AGREEMENT:  MODERATE / SPATIALLY HETEROGENEOUS
```

## 5. Hotspot-level evidence

| Hotspot | Cross-geometry status | Area (km²) | Ascending (mm/yr) | Descending (mm/yr) | Final interpretation |
|---|---|---:|---:|---:|---|
| **H001** | INDEPENDENTLY_SUPPORTED | 5.59 | -30.95 | -36.02 | **SUPPORTED DEFORMATION FEATURE - MECHANISM UNRESOLVED** |
| **H004** | INDEPENDENTLY_SUPPORTED | 1.07 | -14.31 | -12.46 | **SUPPORTED DEFORMATION FEATURE - MECHANISM UNRESOLVED** |
| **H002** | NOT_REPRODUCED | 12.83 | -13.59 | -1.15 | **ASCENDING FEATURE NOT REPRODUCED** |
| **H003** | NOT_REPRODUCED | 2.25 | -12.87 | -0.75 | **ASCENDING FEATURE NOT REPRODUCED** |
| **H005** | UNRESOLVED_CONTRADICTION | 0.84 | -14.21 | +61.39 | **UNRESOLVED CROSS-GEOMETRY CONTRADICTION** |

**The negative controls are a central result, not failed hotspots.** H002 and H003 carry ascending contrasts comparable to H004 (matched-band contrasts −11.60 and −10.93 vs −12.13 mm/yr), have **adequate** descending quality (TC 0.900 / 0.886), and still do not reproduce. Any simple regional explanation predicts all four zones similarly, and therefore fails on selectivity.

### 5.1 Rate versus history — a distinction that must survive

For H001 and H004 the **mean rate and spatial feature are independently supported**. Their **detailed displacement histories are not**: H001's ascending cumulative displacement is −120.7 mm against +1.1 mm descending. It is therefore correct to write *"the H001 spatial/rate signal was independently supported, while its detailed temporal evolution was not"* — and incorrect to write that the time series was validated by descending InSAR.

### 5.2 Independent areas

```text
3.17 km2 = area of Phase-I deformation zones independently supported at the
           hotspot level by the descending geometry   (H001 + H004)
```

This is not extrapolated beyond H001 and H004.

## 6. Groundwater hypothesis test

A preregistered protocol was frozen **before any correlation existed** (`groundwater_protocol_v1`, `152fa51ca8b656d1bfab`), using newly recovered NWDP six-hourly telemetry: 187 stations, 111 quality-passing, all eligible stations within 5 km selected.

```text
GROUNDWATER EVIDENCE:  NO EVIDENCE
```

| Test | Result |
|---|---|
| Groundwater trend, H001/H004 | **rising** (−4.02, −0.68 m/yr) while subsiding — opposite to prediction |
| Groundwater trend, H002/H003 | slight **deepening** (+0.05, +0.15 m/yr) — the predicted sign, in the *controls* |
| Positive-lag tests surviving FDR q = 0.05 | **0 of 16** |
| Falsification (negative) lags | equal or outperform forward lags at **every** hotspot; ~3× stronger at H001 |
| Quality-mask tightening | does not rescue the relationship |

**The controls carry the predicted directional behaviour better than the supported zones do.** That is the opposite of specificity.

This is **not** "groundwater has been ruled out". Aquifer metadata are absent, well depths and types are unknown, H001 telemetry has ~78-day outages, the station geometry is sparse (2 stations at H001), and LOS is not pure vertical displacement.

## 7. Geological susceptibility test

| | Result |
|---|---|
| GEO overall | **NO EVIDENCE** |
| Shallow soil-texture surrogate | **NO EVIDENCE**, direction opposite to prediction |
| Deep geological / aquifer-system | **NOT ADEQUATELY TESTED** |

H001/H004 carry **more sand and less clay** than both the controls and the background (−5.0 and +6.4 percentage points), where fine-sediment susceptibility predicts the reverse. The controls resemble the background rather than the positives.

Two limits prevent over-reading this. **GSI Bhukosh was unreachable**, so no formation- or age-level statement is possible; and **SoilGrids samples only the upper ~2 m**, not the tens-to-hundreds-of-metres interval relevant to aquifer-system compaction. The deep substrate is therefore **untested, not exonerated** — a distinction that must not be lost.

The shallow contrast is additionally confounded: Spearman(clay %, temporal coherence) = **−0.600**.

## 8. Urbanisation test

| Hypothesis | Grade |
|---|---|
| U1 existing built intensity | **NO EVIDENCE** |
| U2 recent built-up expansion | **NO EVIDENCE** |
| U3 major infrastructure / construction | **NOT TESTABLE** |

All four hotspots are heavily built — 70.6 %, 79.0 %, 73.7 %, 70.0 % WorldCover built fraction against a 33.7 % AOI background. That is a strong **shared setting**, and precisely why it fails: it cannot separate the zones that reproduce from those that do not. The two datasets also disagree on H001's ranking, so the difference flips sign between independent products.

GHSL 2020→2025 built-up change is **exactly zero** at all four hotspots — with the recorded caveat that post-2020 GHSL epochs are projections, not observations, so this cannot establish realised 2021–2025 expansion. Per protocol, **no structural loading was estimated**: building height, footprint, construction type and foundation are all absent, so `BUILT-ENVIRONMENT ASSOCIATION` is the strongest permitted framing.

## 9. Competing-hypothesis synthesis

| Hypothesis | Evidence state |
|---|---|
| Groundwater temporal forcing | **NO EVIDENCE** |
| Shallow soil-texture susceptibility | **NO EVIDENCE** |
| Deep geological / aquifer-system susceptibility | **NOT ADEQUATELY TESTED** |
| Existing built intensity | **NO EVIDENCE** |
| Recent built-up expansion | **NO EVIDENCE** |
| Major infrastructure / construction | **NOT TESTABLE** |
| Measurement artefact as sole explanation | **NOT SUPPORTED FOR H001/H004, but measurement limitations remain** |

**Three categories are kept distinct and are not collapsed:** `NO EVIDENCE` means a suitable test was performed and did not support the hypothesis; `NOT ADEQUATELY TESTED` means only an inadequate surrogate or insufficient depth/scale was available; `NOT TESTABLE` means suitable data were unavailable.

No single cause score is computed. Groundwater, soil, urbanisation and measurement quality are **not commensurate quantities**, and combining them would manufacture confidence the data do not contain. Several NO-EVIDENCE and NOT-TESTABLE hypotheses are **not** summed into a synthetic causal story.

## 10. Uncertainty

| Class | Quantity | Value |
|---|---|---:|
| Measurement / statistical | ascending formal velocity uncertainty (median) | 0.87 mm/yr |
| | ascending temporal coherence (p50) | 0.757 |
| | descending D2 temporal coherence (p50) | 0.438 |
| Reference systematic | zero-level range across candidate references | **4.78 mm/yr** |
| | reference-candidate SD | 1.72 mm/yr |
| | INC-007 actual-vs-intended reference offset | 0.136 mm/yr |
| Processing sensitivity | ERA5 − RAW velocity RMS | 0.52 mm/yr |
| | ERA5+DEM − RAW velocity RMS | 1.04 mm/yr |
| Cross-geometry | global ascending/descending Pearson | 0.175 → 0.363 (D0 → D2) |
| Temporal non-stationarity | split-half rate differences | **10.4 – 20.2 mm/yr** |

**These are deliberately not combined into a single ± value.** They are statistical, systematic, sensitivity and structural quantities respectively, and no valid probabilistic model justifies summing them. The reference systematic bounds the *absolute* offset only — spatial gradients and hotspot contrast are invariant to the reference choice. The dominant uncertainty in any single quoted rate is **non-stationarity of the signal itself**, which exceeds every statistical interval.

## 11. What is established

### OBSERVATIONS WE CAN DEFEND

1. A spatially heterogeneous ascending relative LOS deformation field exists over the study period.
2. **H001 and H004 contain spatial / mean-rate deformation features that are independently supported** by a separately processed descending Sentinel-1 geometry.
3. **H002 and H003 ascending signals are not reproduced** despite adequate descending measurement quality.
4. **H005 presents a reproducible but unresolved cross-geometry contradiction.**
5. **Deformation is non-stationary**; a single linear rate does not fully characterize temporal behaviour.
6. **The coherence–velocity association is reproducible** across geometries and processing states.
7. The current groundwater telemetry test **does not support** groundwater-level variation as the explanation for H001/H004.
8. **Shallow soil texture does not support** the predefined fine-sediment susceptibility hypothesis.
9. **Existing urban intensity does not explain** the selectivity of H001/H004 relative to H002/H003.

## 12. What remains unresolved

### CLAIMS NOT SUPPORTED

This study does **not** establish: absolute ground velocity; pure vertical deformation; full 3-D displacement; a validated total deformation extent; groundwater-induced compaction; geological control at aquifer depth; urban-loading deformation; infrastructure-induced deformation; a causal explanation for H001/H004; a physical interpretation of H005; or independently reproduced detailed H001/H004 displacement histories.

These limitations appear here in the main text, **not only in supplementary material**.

### The coherence–velocity association

Classified as a **REPRODUCED OBSERVATIONAL RELATIONSHIP**, with **PHYSICAL ORIGIN UNRESOLVED**. Its persistence across three processing states is real, but it is not proof that low coherence causes deformation or the reverse. Candidate explanations — physical surface differences, scattering characteristics, deformation/decorrelation interaction, residual measurement effects — are **not selected among** without independent evidence.

## 13. Limitations

1. **LOS is a projection**, not vertical motion. No decomposition is published, and the Phase II-A component estimates were withdrawn as invalid.
2. **Reference systematic** of 4.78 mm/yr on the absolute zero level; no independent in-AOI geodetic reference exists. The nearest adequately sampled GNSS station is 209.9 km away.
3. **H001/H004 displacement histories are not independently reproduced** by descending.
4. **Sparse groundwater network** at H001 (2 stations) with ~78-day outages; 36 % of the telemetry network is dead; no aquifer or well-depth metadata.
5. **Deep substrate untested** — authoritative geological sources unreachable.
6. **Construction chronology unavailable**, so the loading hypothesis is untestable rather than refuted.
7. **Coherence confounding** pervades every spatial comparison, and with four hotspot values no reliable adjustment is possible.
8. **Descending coverage is incomplete** (western strip), so the descending geometry cannot validate the entire ascending field.

## 14. Future work — data-driven only

Each item maps to a specific unresolved limitation above; no generic dataset collection is recommended.

| Priority | Data | Resolves |
|---|---|---|
| 1 | **Deep borehole / lithologic logs, sediment thickness, aquifer architecture** | the NOT-ADEQUATELY-TESTED deep substrate question |
| 2 | **Local continuous GNSS or levelling inside the AOI** | absolute calibration and the 4.78 mm/yr systematic |
| 3 | **H005-focused unwrap / phase investigation** | the unresolved sign contradiction |
| 4 | **Better H001/H004 temporal validation** (dense independent geometry or geodetic time series) | the rate-vs-history gap |
| 5 | **Well metadata: aquifer, screened interval, depth** | whether the groundwater test was measuring the right interval |
| 6 | **Documented construction chronology** | U3, currently NOT TESTABLE |

## 15. Reproducibility

All results are reproducible from frozen inputs. Twelve upstream freezes are hash-verified by this synthesis, and four verifier scripts exit 0:

```text
v1                         cf2bdbfd4fa722dd0df9608a
mintpy_input_v1            0cbe4c4f38b8a20f38b2cb71
product_v1                 2a1304e3521f1e176fba7e05
phase1_observations        122781a4a81bd49eb4781c76
descending_network_v1      8f9eee9a6bdead7a6c8a80e4
descending_raw_v1          acdb209f443732f4f7c5f7f3
phase2a_results            09017dc3895f4c66ad680049
phase2b_closeout_v1        16d36635a06d30182e0e5c84
descending_v2_candidate    ba99df90a6f15b3aaaf90fe3
cgwb_seasonal_v1           db0636879f7566f9681be3b7
nwdp_telemetry_v1          731040b8ebdf56e20832de2e
groundwater_protocol_v1    152fa51ca8b656d1bfab8b0e
verifier:verify_freeze.py  exit 0
verifier:verify_mintpy_input_v1.py exit 0
verifier:verify_product_v1.py exit 0
verifier:verify_phase1_observations.py exit 0
```

Final freeze: `freeze/final_evidence_v1`, `db329cf47f4bef92a020056e608decbf95644463f8148570478128d2861c9e88`, 18 artefacts pinned.

### Appendix — incidents that could have changed scientific conclusions

| ID | Incident | Why it mattered |
|---|---|---|
| INC-001 | `find_jobs(name=...)` is an exact match; a prefix query silently returned nothing | produced 7 duplicate pilot jobs; fixed with exact-name matching |
| INC-002 | transient ASF DNS outage killed retrieval at 47/336 | retrieval is now resumable with backoff |
| INC-004 | `np.bool8` removed in NumPy 2 broke the dask cluster | parallel inversion would not start |
| INC-005 | first RAW-vs-ERA5 comparison used the wrong file | produced a spurious 15.49 mm/yr; corrected to 0.52 mm/yr RMS |
| INC-006 | GNSS co-location "disagreement" was a window artefact | the GNSS verdict survived, but for a different and more honest reason |
| INC-007 | `product_v1` referenced to a different pixel than the frozen decision | a constant 0.136 mm/yr; spatial gradients unaffected |
| INC-008 | Phase-I hotspot polygons were single-pixel fragments | **every polygon-based containment test in Phase II was vacuous** until corrected |

Engineering detail is archived in `RUNLOG.md` and `provenance/errata/`. This scientific text is not a software-debug diary; only incidents that could have changed a conclusion appear above.

---

## Principal Phase-IV conclusion

> **No tested mechanism adequately explains the selective, independently supported H001/H004 deformation.**

This is **not** a statement that the deformation has no physical cause. It is the statement that the available evidence is sufficient to characterize selected deformation features but insufficient to identify their physical mechanism.

**Stopped.** No further mechanism was introduced because the existing hypotheses failed. A negative result is not a licence to search until something fits.
