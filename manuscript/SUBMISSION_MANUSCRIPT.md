# Selective reproducibility of localized LOS deformation in Delhi-NCR from ascending and descending Sentinel-1 InSAR

## Abstract

Interpreting urban interferometric synthetic-aperture radar (InSAR) observations requires separating repeatable geodetic structure from geometry-specific signals and from plausible but untested causes. We evaluated this separation over Delhi-NCR using a 119 acquisitions ascending Sentinel-1 stack comprising 336 interferograms and an independently constructed descending stack of 91 acquisitions and 219 interferograms. Both were processed as relative line-of-sight (LOS) time series, with no burst, pair, mask, acquisition list, or reference pixel shared between geometries. Five zones defined and frozen from the ascending product were then evaluated within the common valid domain. H001 and H004 were supported across geometries at the spatial and mean-rate level: ascending/descending mean relative LOS rates were -30.95/-36.02 and -14.31/-12.46 mm yr-1, respectively. H002 and H003, despite comparable ascending magnitudes and adequate descending quality, were not reproduced; H005 instead showed an unresolved sign-and-magnitude contradiction (-14.21 versus +61.39 mm yr-1). The supported zones total 6.66 km2, a sum of frozen polygon areas rather than a continuous validated footprint. Preregistered tests found NO EVIDENCE that groundwater-level variability, shallow soil texture, existing built intensity, or detected recent built-up expansion explained the supported-versus-control selectivity. Deep geological and aquifer-system susceptibility was NOT ADEQUATELY TESTED, and major construction loading was NOT TESTABLE with the retained data. Statistical, reference-systematic, processing-sensitivity, temporal, and structural uncertainties were therefore reported separately. Crucially, cross-geometry support applies to spatial pattern and mean-rate behavior, not matching time histories: the H001 cumulative series disagree substantially. The negative controls show that a coherent ascending anomaly need not survive an independent geometry, while the surviving observations do not by themselves establish vertical displacement or mechanism. Selective reproduction, rather than post hoc attribution, provides the defensible basis for inference.

## 1. Introduction

Urban InSAR can reveal localized surface motion at a scale difficult to obtain from sparse ground networks, but interpretive confidence does not follow automatically from a coherent velocity map. Relative LOS estimates depend on viewing geometry and reference choice, and can retain atmospheric, unwrapping, decorrelation, and temporal-sampling effects. Even where a feature is geodetically credible, spatial coincidence with pumping, sediments, or construction does not isolate a physical cause. The central scientific problem is therefore both observational and causal: which features survive an independent measurement design, and which proposed explanations distinguish those features from credible negative controls [@ferretti2001; @berardino2002; @crosetto2016]?

Delhi-NCR is a consequential setting for that problem because rapid urban growth and severe groundwater stress coincide with previously reported InSAR deformation. Garg et al. mapped pronounced localized deformation during 2014-2020 and interpreted its evolution in relation to groundwater decline, while Kumar et al. extended the regional context across ALOS-1 and Sentinel-1 eras [@garg2022; @kumar2022]. These studies establish that the region warrants sustained observation. They do not, however, transfer their physical interpretation to later observations with different dates, polygons, processing decisions, and reference frames.

Two gaps remain. First, a feature detected in one Sentinel-1 geometry may reflect true three-dimensional motion, geometry-dependent sensitivity, or residual processing structure; agreement must be evaluated using an independently assembled observation. Second, a regional explanatory variable can coincide with several anomalies yet fail to explain why only some reproduce. Reproducibility and causal selectivity thus require a common-domain comparison that preserves failures and contradictions rather than treating them as disposable validation detail.

We addressed these gaps with an asymmetric, evidence-frozen design. Five zones were defined from an authoritative ascending stack before the independent descending experiment. The descending acquisition inventory, interferogram network, mask, inversion, and reference were constructed without reusing ascending artefacts or selecting pairs by zone intersection. H002 and H003 were retained as negative controls when they did not reproduce, and H005 was retained as a contradiction. Candidate groundwater, substrate, and urban explanations were specified with fixed variables, thresholds, lags, falsification tests, and evidence-state language before interpretation.

The study had three objectives: (1) identify which frozen zones retain spatial and mean-rate support across independent ascending and descending geometries; (2) test whether candidate groundwater, shallow-texture, and urban variables discriminate the supported zones from the non-reproduced controls; and (3) define the resulting limits of inference, including the distinctions between relative LOS and vertical motion, mean-rate support and matching time histories, and negative evidence and an inadequate or unavailable test. The intended contribution is an auditable inference design for urban InSAR, not a mechanism assigned by plausibility alone.

## 2. Data and methods

### 2.1 Study design and observation period

The scientific area of interest (AOI) covers 1,962.4 km2 of Delhi-NCR in UTM zone 43N (EPSG:32643); water occupies 1.85% of the mask. Sentinel-1 observations span October 2021 to September 2025. The ascending record runs from 6 October 2021 to 27 September 2025 and the descending record from 2 October 2021 to 23 September 2025, with a common interval of 6 October 2021-23 September 2025. The study followed a sequential design: construct and freeze the ascending observation set, build a descending experiment independently, classify cross-geometry outcomes in their common valid domain, and only then apply preregistered mechanism tests. All velocities are relative LOS quantities; no vertical/east decomposition is published.

### 2.2 Ascending stack and time-series processing

The ascending inventory comprises four contiguous VV-polarized bursts on relative orbit 27, subswath IW2 (burst IDs 027_056011-IW2 through 027_056014-IW2). Identity intersection across all bursts yielded 119 common acquisitions and 336 interferograms under maximum temporal and perpendicular baselines of 36 days and 250 m. The final graph has one component, no isolated nodes, bridges, or articulation points, and minimum degree three. Interferograms were generated with the HyP3 `INSAR_ISCE_MULTI_BURST` product using 10 x 2 looks and approximately 40 m output spacing, then inverted with MintPy 1.6.4 using variance weighting, minimum-norm velocity, and all 336 pairs (`keepMinSpanTree = no`). Valid inversion pixels were defined by `velocityStd > 0` because non-inverted MintPy pixels can contain finite zero fills.

Correction branches were evaluated without pair curation. ERA5 and ERA5-plus-DEM-residual branches changed the field but did not improve the prespecified atmospheric diagnostics; ascending bridging-plus-phase-closure correction was also rejected. The authoritative RAW-336 branch therefore has unwrapping-error correction, tropospheric correction, DEM-residual correction, and deramping disabled. This choice is product-specific and is not a claim that corrections are generally unnecessary [@yunjun2019; @hersbach2020].

### 2.3 Frozen observations and hotspot definition

Phase-I zones were connected components meeting all three fixed conditions in RAW-336: absolute relative LOS velocity at least 10 mm yr-1, temporal coherence at least 0.80, and area at least 0.4 km2. Five polygons (H001-H005) passed. Their combined 22.6 km2 is a mask- and threshold-dependent operating extent, not a validated continuous deformation footprint. Geometry, identifiers, thresholds, rates, and classification inputs were frozen before descending interpretation. Sensitivity was evaluated across velocity thresholds of 5, 7.5, 10, 15, 20, and 25 mm yr-1 and coherence thresholds, but the primary definitions were not reselected. The 6.66 km2 later associated with H001 and H004 is only the sum of their original polygon areas.

### 2.4 Independent descending experiment

The descending inventory uses four contiguous VV bursts on relative orbit 136, subswath IW1 (136_290874-IW1 through 136_290877-IW1). It contains 91 common acquisitions and 219 interferograms. The same 36-day/250 m base rule was retained, with ten flagged longer-baseline pairs required by two observation gaps (108 and 48 days) and graph reliability; the resulting graph has one component, no bridges, minimum degree two, and one recorded articulation date. No ascending artefact was read during pair construction, and hotspot geometry was not used to accept dates or pairs. Descending coverage is incomplete, so inference is restricted to the overlap.

The raw descending inversion showed connected-component fragmentation. A branch differing only by MintPy bridging-plus-phase-closure unwrapping correction improved all seven prespecified internal reliability metrics, including the temporal-coherence upper quartile and retained high-coherence area; it was therefore selected as the descending D2 product. Its tropospheric, DEM-residual, and deramp settings otherwise matched the uncorrected design. Ascending and descending correction choices were made separately because their diagnosed failure modes differed.

### 2.5 Cross-geometry comparison

Both rasters were aligned on the scientific AOI and restricted to pixels valid in both inversions, without imposing a common coherence cutoff on structurally different coherence distributions. This common domain contains 854,004 pixels (1,366.406 km2; 69.63% of the AOI) and covers essentially all five polygons. Each stack was re-referenced to the median of the same 3,692 stable-control pixels, producing identically defined relative zero levels while retaining independent native reference pixels. Comparisons used polygon means, matched-coherence-band contrasts, spatial overlap, magnitude ratios, global field correlation, split-period rates, and retained cumulative diagnostics. Separate native-record and common-period comparisons were preserved; dates were not interpolated to force identity. A zone could be supported at the spatial and mean-rate level without its detailed time history being supported.

### 2.6 Preregistered mechanism tests

Groundwater testing used National Water Data Portal six-hourly depth-to-water telemetry. Of 187 candidate stations, 111 passed quality screening; all eligible stations within 5 km of each zone were used. Daily station medians required at least two valid observations and were not interpolated; station anomalies were composited by day. Positive anomaly denotes deeper water. The fixed forward lags were 0, +30, +60, and +90 days, with -30, -60, and -90 days as falsification lags. Significance used 5,000 circular 90-day block permutations and Benjamini-Hochberg false-discovery-rate control at q = 0.05 across 16 forward-lag tests [@benjamini1995]. H005 was excluded because no valid groundwater composite existed and because it was already contradictory.

Shallow substrate tests used SoilGrids 2.0 clay and sand fractions at 0-5 cm and 100-200 cm on the native 250 m grid [@poggio2021]. These variables are shallow texture surrogates, not deep geology or aquifer architecture. Urban tests used ESA WorldCover 2021 built class at 10 m and GHSL built surface near 100 m on their native grids; no coarse product was resampled to the 40 m InSAR grid. Existing built intensity and detected 2020-2025 GHSL change were contrasted between H001/H004, H002/H003, and the AOI-minus-zones background. Building height, foundation, type, dated construction, and load were unavailable, so major construction loading was not tested.

### 2.7 Uncertainty and evidence states

Uncertainty was partitioned rather than collapsed. We report formal fit uncertainty (ascending median 0.866 mm yr-1), reference-systematic range (4.78 mm yr-1, affecting the absolute zero but not within-map contrasts), correction-branch sensitivity (0.521-1.036 mm yr-1), cross-geometry structure (global Pearson r = 0.175 before and 0.363 after descending correction), and temporal non-stationarity (split-half differences 10.44-20.24 mm yr-1). These are statistical, systematic, sensitivity, and structural quantities without a justified joint probability model and were never summed. `NO EVIDENCE` denotes a completed test that did not support its prespecified prediction; `NOT ADEQUATELY TESTED` denotes an unsuitable proxy or incomplete measurement; and `NOT TESTABLE` denotes absence of a suitable retained dataset. None means that a physical mechanism was disproved.

## 3. Results

### 3.1 Ascending field and frozen detections

The authoritative RAW-336 ascending field was spatially heterogeneous: the AOI median was -0.73 mm yr-1, whereas the negative tail reached approximately -87 mm yr-1. Applying the frozen absolute-rate, coherence, and area rules yielded five connected zones. Together they occupy 22.6 km2. This value is a quality- and threshold-dependent operating extent: it changes across the prespecified sensitivity grid and does not represent a continuous independently supported footprint. The velocity-coherence association also means that thresholding on temporal coherence changes which part of the velocity distribution remains observable. The five polygons were therefore treated as fixed test objects rather than as a complete inventory of surface motion.

### 3.2 Descending reliability and correction decision

The raw descending inversion was not accepted at face value. Its valid field agreed weakly with the ascending field (Pearson r = 0.175), and 81.3% of inverted pixels lay outside the retained connected component; masking those pixels degraded every velocity-agreement metric. Bridging-plus-phase-closure correction improved seven of seven prespecified internal reliability measures. In particular, the temporal-coherence 75th percentile increased from 0.49 to 0.83 and the count of pixels with temporal coherence at least 0.70 increased from 11,013 to 1,352,660. The corrected D2 branch was therefore retained. This decision was based on descending internal diagnostics, not on maximizing agreement at the frozen zones.

### 3.3 Common-domain agreement

The common valid domain contains 854,004 pixels, covers 1,366.406 km2 (69.63% of the AOI), and includes virtually every pixel in all five frozen polygons. After alignment to the shared stable-control definition, field-wide ascending-descending agreement increased to Pearson r = 0.363. We interpret this as moderate and spatially heterogeneous agreement, not validation of the full ascending map: descending orbit 136 leaves the western AOI strip uncovered, and the two LOS geometries have different sensitivities. Hotspot-level outcomes were consequently classified separately from this global statistic.

### 3.4 Independently supported zones: H001 and H004

H001 (5.59 km2) had mean ascending and descending relative LOS rates of -30.95 and -36.02 mm yr-1. Its magnitude ratio was 1.16, 1.6 standard deviations from the vertical-equivalent expectation, and median temporal coherence was 0.925 ascending and 0.906 descending. H004 (1.07 km2) had corresponding rates of -14.31 and -12.46 mm yr-1, a magnitude ratio of 0.87, the same 1.6-standard-deviation departure, and median coherence of 0.963 and 0.909. Each zone was spatially detected with the same LOS sign in the independently processed descending product and was classified `INDEPENDENTLY_SUPPORTED` at the spatial and mean-rate level. Their combined 6.66 km2 is the sum of the original H001 and H004 polygon areas; it is not an extrapolated or continuous validated extent. Neither zone had an independently reproduced detailed displacement history, and both retain the interpretation `SUPPORTED DEFORMATION FEATURE - MECHANISM UNRESOLVED`.

| Zone | Ascending rate (mm/yr) | Descending rate (mm/yr) | Area (km2) | Status |
|---|---:|---:|---:|---|
| H001 | -30.95 | -36.02 | 5.59 | INDEPENDENTLY_SUPPORTED |
| H004 | -14.31 | -12.46 | 1.07 | INDEPENDENTLY_SUPPORTED |
| H002 | -13.59 | -1.15 | 12.83 | NOT_REPRODUCED |
| H003 | -12.87 | -0.75 | 2.25 | NOT_REPRODUCED |
| H005 | -14.21 | +61.39 | 0.84 | UNRESOLVED_CONTRADICTION |

### 3.5 Negative controls: H002 and H003

H002 is the largest frozen zone (12.83 km2). Its ascending mean was -13.59 mm yr-1, but the descending mean was -1.15 mm yr-1, giving a magnitude ratio of 0.09 and an 8.3-standard-deviation departure from the vertical-equivalent expectation. H003 covers 2.25 km2; its rates were -12.87 and -0.75 mm yr-1, with a ratio of 0.06 and the same 8.3-standard-deviation departure. These are not low-quality descending gaps: H002 and H003 descending median temporal coherence was 0.900 and 0.886, compared with ascending values of 0.863 and 0.861. Their ascending matched-coherence-band contrasts (-11.60 and -10.93 mm yr-1) were also comparable to H004 (-12.13 mm yr-1). Both were classified `NOT_REPRODUCED`, not as proof that no physical movement occurred. Their final interpretations are `ASCENDING FEATURE NOT REPRODUCED`, and no cross-geometry time-history comparison was warranted because no descending rate-level counterpart survived.

### 3.6 Unresolved contradiction: H005

H005 (0.84 km2) did not merely fail to appear. Its ascending mean relative LOS rate was -14.21 mm yr-1, whereas its descending mean was +61.39 mm yr-1, reversing sign and departing by 18.7 standard deviations from the vertical-equivalent expectation. Median temporal coherence was 0.865 ascending and 0.851 descending, so the contradiction was not removed by the primary quality screen. H005 was classified `UNRESOLVED_CONTRADICTION` and retains the interpretation `UNRESOLVED CROSS-GEOMETRY CONTRADICTION`. No physical explanation or preferred geometry is assigned. H005 was excluded from all causal-test samples because a contradictory observation cannot serve as either a supported case or a negative control.

### 3.7 Temporal behavior and uncertainty

Mean-rate support did not imply temporal reproduction. H001 accumulated -120.7 mm in the retained ascending summary but +1.1 mm in the descending summary, whose series contained large opposing jumps; the detrended cross-geometry correlation was r = 0.007. H004 was likewise classified as having no reproduced detailed history. Per-epoch series absent from the frozen evidence were not reconstructed.

| Uncertainty component | Frozen value | Consequence |
|---|---:|---|
| Formal ascending fit uncertainty | 0.866 mm yr-1 median | Statistical precision only; not a total error budget |
| Reference systematic | 4.78 mm yr-1 range | Shifts absolute zero; spatial contrasts remain invariant |
| Processing sensitivity | 0.521-1.036 mm yr-1 RMS | Dependence on tested correction branch |
| Cross-geometry structure | Pearson r = 0.175 to 0.363 | Agreement changes after descending correction and remains heterogeneous |
| Temporal non-stationarity | 10.44-20.24 mm yr-1 | Dominant split-half difference; rates are period-specific |

The components were not summed because they are not draws from a common probabilistic model. In particular, temporal non-stationarity exceeded the reported statistical fit scale, precluding extrapolation of a single rate beyond the observation interval.

### 3.8 Mechanism-test outcomes

The mechanism results preserve the exact evidence states assigned in the frozen synthesis.

| Hypothesis | Evidence state | Quantitative or procedural basis |
|---|---|---|
| Groundwater temporal forcing | **NO EVIDENCE** | Supported zones had groundwater trends opposite to the prediction, controls carried the predicted sign, falsification lags equaled or outperformed forward lags, and 0 of 16 forward-lag tests survived FDR q = 0.05 (all permutation p values at least 0.49). |
| Shallow soil-texture susceptibility | **NO EVIDENCE** | H001/H004 had 5.0 percentage points less clay and 6.4 points more sand than controls, opposite to the fine-sediment prediction; the contrast was confounded with coherence (Spearman rho = -0.600). |
| Deep geological / aquifer-system susceptibility | **NOT ADEQUATELY TESTED** | The accessible SoilGrids product samples only the upper approximately 2 m, not a compacting interval; authoritative deep-geology access was unavailable. |
| Existing built intensity | **NO EVIDENCE** | All four classification zones were 70-79% built against a 33.7% background, so built intensity described their shared setting but did not separate supported zones from controls; source products also disagreed on H001's ranking. |
| Recent built-up expansion | **NO EVIDENCE** | GHSL 2020-2025 change was exactly zero at H001-H004, with the qualification that the 2025 epoch is projected rather than observed. |
| Major infrastructure / construction | **NOT TESTABLE** | No authoritative, dated construction, foundation, or structural-loading dataset was retained. |
| Measurement artefact as sole explanation | **NOT SUPPORTED FOR H001/H004, but measurement limitations remain** | H001/H004 contrasts survived coherence-band matching, but the reproduced coherence-velocity association remained physically unresolved. |

`NO EVIDENCE` is limited to the specified test and does not rule out a mechanism. Deep susceptibility remains an inadequate test, construction remains unavailable, and none of the tested variables explains why H001/H004 reproduce while H002/H003 do not.

## 4. Discussion

## 5. Limitations

## 6. Conclusions
