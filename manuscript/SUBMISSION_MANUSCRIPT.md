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

| Zone | Ascending rate (mm/yr) | Descending rate (mm/yr) | Area (km2) | Status |
|---|---:|---:|---:|---|
| H001 | -30.95 | -36.02 | 5.59 | INDEPENDENTLY_SUPPORTED |
| H004 | -14.31 | -12.46 | 1.07 | INDEPENDENTLY_SUPPORTED |
| H002 | -13.59 | -1.15 | 12.83 | NOT_REPRODUCED |
| H003 | -12.87 | -0.75 | 2.25 | NOT_REPRODUCED |
| H005 | -14.21 | +61.39 | 0.84 | UNRESOLVED_CONTRADICTION |

## 4. Discussion

## 5. Limitations

## 6. Conclusions
