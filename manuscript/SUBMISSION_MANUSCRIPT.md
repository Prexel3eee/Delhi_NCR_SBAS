# Selective reproduction of localized line-of-sight deformation in Delhi-NCR using independent Sentinel-1 geometries

**Authors:** Vishal Kumar Chaubey; Harishankar Gangwar; Suresh Kannujiya

**Affiliation:** Indian Institute of Remote Sensing (IIRS), Indian Space Research Organisation (ISRO), Dehradun, Uttarakhand, India

**Corresponding author:** Vishal Kumar Chaubey (vishal.chaubey17@outlook.com)

## Abstract

Urban interferometric synthetic-aperture radar interpretation requires separating repeatable geodetic structure from geometry-specific signals and plausible but untested causes. We evaluated this problem over Delhi-NCR using an ascending Sentinel-1 stack of 119 acquisitions and 336 interferograms and an independently constructed descending stack of 91 acquisitions and 219 interferograms. Both were processed as relative line-of-sight (LOS) time series, without shared bursts, pairs, masks, acquisition lists, or reference pixels. Five zones frozen from the ascending product were evaluated within the common valid domain. H001 and H004 were supported at the spatial and mean-rate level; ascending/descending mean relative LOS rates were -30.95/-36.02 and -14.31/-12.46 mm yr-1, respectively. H002 and H003 were not reproduced despite adequate descending quality, while H005 showed an unresolved sign-and-magnitude contradiction (-14.21 versus +61.39 mm yr-1). The supported zones total 6.66 km2, a polygon-area sum rather than a continuous validated footprint. Preregistered tests found no evidence that groundwater-level variability, shallow soil texture, existing built intensity, or detected recent built-up expansion explained supported-versus-control selectivity. Deep geological and aquifer-system susceptibility was not adequately tested, and major construction loading was not testable. Uncertainty was separated into statistical, reference-systematic, processing-sensitivity, temporal, and structural components. Cross-geometry support applied to spatial pattern and mean-rate behavior, not matching time histories; H001 cumulative series disagreed substantially. Thus, negative controls show that a coherent ascending anomaly need not survive an independent geometry, while surviving observations do not establish vertical displacement or mechanism. Selective reproduction provides the defensible basis for inference.

**Keywords:** Sentinel-1; interferometry; deformation; reproducibility; Delhi-NCR; uncertainty

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

Independent acquisition geometry and coverage are summarized in (Figure F1). Operational paths, masks, registries, and parameter records are given in Supplementary Section S1, Supplementary Section S2, Supplementary Section S3, Supplementary Section S4, Supplementary Section S5, Supplementary Section S6, Supplementary Section S7, Supplementary Section S8, and Supplementary Section S9.

## 3. Results

### 3.1 Ascending field and frozen detections

The authoritative RAW-336 ascending field was spatially heterogeneous: the AOI median was -0.73 mm yr-1, whereas the negative tail reached approximately -87 mm yr-1 (Figure F2). Applying the frozen absolute-rate, coherence, and area rules yielded five connected zones. Together they occupy 22.6 km2. This value is a quality- and threshold-dependent operating extent: it changes across the prespecified sensitivity grid and does not represent a continuous independently supported footprint. The velocity-coherence association also means that thresholding on temporal coherence changes which part of the velocity distribution remains observable. The five polygons were therefore treated as fixed test objects rather than as a complete inventory of surface motion.

### 3.2 Descending reliability and correction decision

The raw descending inversion was not accepted at face value. Its valid field agreed weakly with the ascending field (Pearson r = 0.175), and 81.3% of inverted pixels lay outside the retained connected component; masking those pixels degraded every velocity-agreement metric. Bridging-plus-phase-closure correction improved seven of seven prespecified internal reliability measures. In particular, the temporal-coherence 75th percentile increased from 0.49 to 0.83 and the count of pixels with temporal coherence at least 0.70 increased from 11,013 to 1,352,660. The corrected D2 branch was therefore retained. This decision was based on descending internal diagnostics, not on maximizing agreement at the frozen zones.

### 3.3 Common-domain agreement

The common valid domain contains 854,004 pixels, covers 1,366.406 km2 (69.63% of the AOI), and includes virtually every pixel in all five frozen polygons. After alignment to the shared stable-control definition, field-wide ascending-descending agreement increased to Pearson r = 0.363. We interpret this as moderate and spatially heterogeneous agreement, not validation of the full ascending map: descending orbit 136 leaves the western AOI strip uncovered, and the two LOS geometries have different sensitivities. Hotspot-level outcomes were consequently classified separately from this global statistic.

### 3.4 Independently supported zones: H001 and H004

H001 (5.59 km2) had mean ascending and descending relative LOS rates of -30.95 and -36.02 mm yr-1. Its magnitude ratio was 1.16, 1.6 standard deviations from the vertical-equivalent expectation, and median temporal coherence was 0.925 ascending and 0.906 descending. H004 (1.07 km2) had corresponding rates of -14.31 and -12.46 mm yr-1, a magnitude ratio of 0.87, the same 1.6-standard-deviation departure, and median coherence of 0.963 and 0.909. Each zone was spatially detected with the same LOS sign in the independently processed descending product and was classified `INDEPENDENTLY_SUPPORTED` at the spatial and mean-rate level (Figure F3) (Figure F4). Their combined 6.66 km2 is the sum of the original H001 and H004 polygon areas; it is not an extrapolated or continuous validated extent. Neither zone had an independently reproduced detailed displacement history, and both retain the interpretation `SUPPORTED DEFORMATION FEATURE - MECHANISM UNRESOLVED`. Table 1 summarizes all five frozen cross-geometry outcomes.

**Table 1. Cross-geometry outcomes for the five frozen zones.**

| Zone | Ascending rate (mm/yr) | Descending rate (mm/yr) | Area (km2) | Status |
|---|---:|---:|---:|---|
| H001 | -30.95 | -36.02 | 5.59 | INDEPENDENTLY_SUPPORTED |
| H004 | -14.31 | -12.46 | 1.07 | INDEPENDENTLY_SUPPORTED |
| H002 | -13.59 | -1.15 | 12.83 | NOT_REPRODUCED |
| H003 | -12.87 | -0.75 | 2.25 | NOT_REPRODUCED |
| H005 | -14.21 | +61.39 | 0.84 | UNRESOLVED_CONTRADICTION |

### 3.5 Negative controls: H002 and H003

H002 is the largest frozen zone (12.83 km2). Its ascending mean was -13.59 mm yr-1, but the descending mean was -1.15 mm yr-1, giving a magnitude ratio of 0.09 and an 8.3-standard-deviation departure from the vertical-equivalent expectation. H003 covers 2.25 km2; its rates were -12.87 and -0.75 mm yr-1, with a ratio of 0.06 and the same 8.3-standard-deviation departure. These are not low-quality descending gaps: H002 and H003 descending median temporal coherence was 0.900 and 0.886, compared with ascending values of 0.863 and 0.861. Their ascending matched-coherence-band contrasts (-11.60 and -10.93 mm yr-1) were also comparable to H004 (-12.13 mm yr-1) (Figure F5). Both were classified `NOT_REPRODUCED`, not as proof that no physical movement occurred. Their final interpretations are `ASCENDING FEATURE NOT REPRODUCED`, and no cross-geometry time-history comparison was warranted because no descending rate-level counterpart survived.

### 3.6 Unresolved contradiction: H005

H005 (0.84 km2) did not merely fail to appear. Its ascending mean relative LOS rate was -14.21 mm yr-1, whereas its descending mean was +61.39 mm yr-1, reversing sign and departing by 18.7 standard deviations from the vertical-equivalent expectation (Figure F6). Median temporal coherence was 0.865 ascending and 0.851 descending, so the contradiction was not removed by the primary quality screen. H005 was classified `UNRESOLVED_CONTRADICTION` and retains the interpretation `UNRESOLVED CROSS-GEOMETRY CONTRADICTION`. No physical explanation or preferred geometry is assigned. H005 was excluded from all causal-test samples because a contradictory observation cannot serve as either a supported case or a negative control.

### 3.7 Temporal behavior and uncertainty

Mean-rate support did not imply temporal reproduction. H001 accumulated -120.7 mm in the retained ascending summary but +1.1 mm in the descending summary, whose series contained large opposing jumps; the detrended cross-geometry correlation was r = 0.007. H004 was likewise classified as having no reproduced detailed history. Per-epoch series absent from the frozen evidence were not reconstructed. Table 2 keeps the heterogeneous uncertainty components separate.

**Table 2. Uncertainty components retained as separate quantities.**

| Uncertainty component | Frozen value | Consequence |
|---|---:|---|
| Formal ascending fit uncertainty | 0.866 mm yr-1 median | Statistical precision only; not a total error budget |
| Reference systematic | 4.78 mm yr-1 range | Shifts absolute zero; spatial contrasts remain invariant |
| Processing sensitivity | 0.521-1.036 mm yr-1 RMS | Dependence on tested correction branch |
| Cross-geometry structure | Pearson r = 0.175 to 0.363 | Agreement changes after descending correction and remains heterogeneous |
| Temporal non-stationarity | 10.44-20.24 mm yr-1 | Dominant split-half difference; rates are period-specific |

The components were not summed because they are not draws from a common probabilistic model. In particular, temporal non-stationarity exceeded the reported statistical fit scale, precluding extrapolation of a single rate beyond the observation interval.

### 3.8 Mechanism-test outcomes

The mechanism results preserve the exact evidence states assigned in the frozen synthesis (Table 3).

**Table 3. Preregistered mechanism-test outcomes and evidence states.**

| Hypothesis | Evidence state | Quantitative or procedural basis |
|---|---|---|
| Groundwater temporal forcing | **NO EVIDENCE** | Supported zones had groundwater trends opposite to the prediction, controls carried the predicted sign, falsification lags equaled or outperformed forward lags, and 0 of 16 forward-lag tests survived FDR q = 0.05 (all permutation p values at least 0.49) (Figure F7). |
| Shallow soil-texture susceptibility | **NO EVIDENCE** | H001/H004 had 5.0 percentage points less clay and 6.4 points more sand than controls, opposite to the fine-sediment prediction; the contrast was confounded with coherence (Spearman rho = -0.600). |
| Deep geological / aquifer-system susceptibility | **NOT ADEQUATELY TESTED** | The accessible SoilGrids product samples only the upper approximately 2 m, not a compacting interval; authoritative deep-geology access was unavailable. |
| Existing built intensity | **NO EVIDENCE** | All four classification zones were 70-79% built against a 33.7% background, so built intensity described their shared setting but did not separate supported zones from controls; source products also disagreed on H001's ranking. |
| Recent built-up expansion | **NO EVIDENCE** | GHSL 2020-2025 change was exactly zero at H001-H004, with the qualification that the 2025 epoch is projected rather than observed. |
| Major infrastructure / construction | **NOT TESTABLE** | No authoritative, dated construction, foundation, or structural-loading dataset was retained. |
| Measurement artefact as sole explanation | **NOT SUPPORTED FOR H001/H004, but measurement limitations remain** | H001/H004 contrasts survived coherence-band matching, but the reproduced coherence-velocity association remained physically unresolved. |

`NO EVIDENCE` is limited to the specified test and does not rule out a mechanism. Deep susceptibility remains an inadequate test, construction remains unavailable, and none of the tested variables explains why H001/H004 reproduce while H002/H003 do not (Figure F8).

## 4. Discussion

### 4.1 What H001/H004 reproduction establishes

The most defensible positive result is deliberately narrow: H001 and H004 retain localized, same-sign relative LOS structure and comparable observation-period mean rates in separately assembled ascending and descending products. Independence matters here. The descending inventory, four-burst intersection, network, reference pixel, inversion, and correction decision were not inherited from the ascending branch, and no interferogram was selected because it intersected a zone. Agreement is therefore not a repeated calculation over the same observations. It is evidence that these two frozen polygons contain a spatial and mean-rate signal that is not unique to the original ascending processing chain. This supports their status as deformation features worth continued investigation. <!-- Claims: C001 C002 C020 -->

That result should not be expanded spatially or semantically. The 6.66 km2 quantity is the sum of two pre-existing polygon areas, not the output of a new dual-geometry segmentation and not a continuous validated footprint. Likewise, the observed agreement does not show that all pixels within either polygon move uniformly, that adjacent terrain is stable, or that the features persist outside 2021-2025. The stronger inference is comparative: among five frozen candidates subjected to the same cross-geometry logic, only H001 and H004 met the spatial and mean-rate support criteria. Their physical mechanism remains unresolved. <!-- Claims: C001 C002 C006 C019 -->

The reported magnitude ratios are supporting diagnostics rather than a kinematic inversion. Comparing each ratio with a vertical-equivalent expectation helps identify gross inconsistency, but the expectation assumes a motion direction that has not been measured. Agreement within that diagnostic therefore adds confidence to the cross-geometry classification without identifying the displacement vector. This hierarchy matters: spatial coincidence and compatible means are direct observations; vertical equivalence is a reference calculation; physical process is a separate hypothesis. Keeping those layers apart prevents the apparent precision of two rates from obscuring the structural uncertainty in what they represent. <!-- Claims: C001 C002 C014 -->

### 4.2 Why rate support is not vertical or temporal validation

Both products measure relative LOS motion, with different incidence and heading sensitivity. Similar negative means are compatible with a substantial vertical component, but they are not a vertical solution: two LOS observations cannot be interpreted safely without a valid decomposition, consistent sampling, and control of horizontal components. The project withdrew an earlier component estimate because its assumptions were not defensible. Reference uncertainty adds a separate limitation. The shared stable-control alignment makes spatial contrasts comparable, but it does not create an absolute geodetic datum. Consequently, neither the sign nor agreement of polygon means licenses the phrase vertical displacement. <!-- Claims: C014 C021 -->

Temporal evidence is even more restrictive. A four-year least-squares mean can agree when the underlying sequences differ in transients, gaps, seasonal structure, or step-like errors. H001 demonstrates this directly: the retained cumulative summaries and detrended series do not reproduce, despite close mean-rate magnitudes. Descending gaps and opposing jumps further weaken event-scale comparison. We therefore use the exact distinction that the data permit: support at the spatial and mean-rate level, but not validation of detailed time histories. This distinction prevents a rate comparison from being presented as replication of a physical process through time. <!-- Claims: C007 C012 C014 -->

### 4.3 Negative controls as scientific evidence

H002 and H003 were not reproduced. Their value lies precisely in that outcome. Both have ascending rates near H004, remain within the descending valid domain, and possess adequate descending temporal coherence. Their matched-coherence-band contrasts also remain similar to H004 in the ascending field. They therefore provide a more demanding comparison than arbitrary background pixels: they are plausible ascending anomalies exposed to the same independent geometry and quality logic as the supported zones. Treating them as negative controls makes the inference selective rather than merely confirmatory. <!-- Claims: C003 C016 -->

These controls change how regional explanations must be judged. A variable common to H001-H004 may describe the urban or hydrogeological setting, yet it cannot explain why only H001/H004 survive the independent observation. Conversely, non-reproduction does not prove that H002/H003 are artefacts or physically stationary; horizontal sensitivity, unresolved time dependence, and residual processing differences remain possible. The controls establish an epistemic boundary: an ascending rate of approximately the observed magnitude, even with good ascending coherence, is insufficient on its own for physical interpretation. <!-- Claims: C003 C016 C023 -->

### 4.4 H005 and the cost of unresolved contradiction

H005 remained an unresolved cross-geometry contradiction. Its descending result has adequate nominal coherence yet differs from the ascending result in both sign and magnitude. This outcome cannot be folded into a binary reproduced/not-reproduced scheme, because choosing either geometry would require an external reason not supplied by the data. It also cannot be used as a causal case: correlating an explanatory variable against a response whose direction is unresolved would make the mechanism result depend on an arbitrary measurement choice. Excluding H005 from the causal sample is therefore a consequence of its evidence state, not selective removal of an inconvenient point. <!-- Claims: C004 C017 -->

The contradiction also prevents a single simple interpretation of the complete ascending hotspot set. If all five zones had arisen from one regional forcing and were measured reliably by both geometries, the H005 sign reversal would require additional geometry-dependent motion, temporal behavior, or error. None is identified here. Preserving the contradiction in the main article is scientifically useful because it records where the observation design stops working and prevents the supported zones from lending unwarranted credibility to every detected anomaly. <!-- Claims: C004 C017 C023 -->

### 4.5 Comparison with prior Delhi-NCR studies

Garg et al. reported pronounced Delhi-NCR deformation during 2014-2020 and interpreted the evolution of several localities in relation to groundwater depletion; Kumar et al. provided a broader ALOS-1 and Sentinel-1 regional history with a similar groundwater-overexploitation interpretation [@garg2022; @kumar2022]. Those studies establish both the seriousness of regional groundwater stress and the precedent for spatially localized InSAR observations. The present study does not overturn that literature. It asks a different question during a later 2021-2025 interval: whether pre-frozen features survive a separately constructed viewing geometry and whether contemporary measured covariates explain the supported-versus-control contrast. <!-- Claims: C013 C015 -->

Direct equivalence would be misleading. Observation periods, zone boundaries, sensors or processing branches, reference conventions, and hydrogeological records differ. A previously reported locality can motivate scrutiny without proving that a present polygon shares its mechanism. The current groundwater result is therefore neither a replication of earlier attribution nor a refutation of groundwater-related compaction in Delhi-NCR. It is a negative result for a declared temporal-selectivity test, constrained by sparse stations, unknown screened intervals, and missing aquifer specificity. Regional continuity is plausible context; causal transfer is not demonstrated. <!-- Claims: C008 C013 C015 -->

Comparative studies from Lahore, Kakinada, Fuzhou, and Makkah illustrate how urban InSAR analyses combine radar time series with groundwater, sediment, or land-cover information [@hussain2022; @nadimpalli2025; @zhu2022; @elhag2025]. They also show why local validation matters: sensor geometry, monitoring duration, ground data, and the strength of mechanism evidence vary substantially. Their reported associations support the relevance of the candidate mechanisms, but they cannot substitute for selectivity within this dataset. <!-- Claims: C015 C020 -->

### 4.6 Why tested candidates fail causal selectivity

The groundwater test failed in three mutually reinforcing ways: supported zones had trends opposite to the preregistered direction, controls showed the nominal predicted sign, and forward lags did not outperform falsification lags or survive multiplicity control. This combination matters more than a single non-significant correlation. It says that the available telemetry does not order the four zones as the proposed mechanism predicted. Yet `NO EVIDENCE` remains the correct state because station composites may not sample the stressed aquifer, well construction is unknown, and H001 contains long outages. The test evaluates the retained observation, not groundwater physics in general. <!-- Claims: C008 C018 -->

Shallow texture also fails the predicted ordering. The supported zones are coarser, not finer, than the controls in SoilGrids, and the small sample is entangled with coherence. The direction opposes the declared fine-sediment susceptibility hypothesis, but SoilGrids maps only shallow material and cannot observe a deep compacting unit. Existing built intensity fails for a different reason: all four classification zones are heavily built, so urbanization describes their common setting without discriminating outcomes. Detected recent GHSL change is zero at all four zones, but the later epoch is projected. These findings reject simple proxy-based selectivity; they do not measure deep stratigraphy, pumping stress, or structural load. <!-- Claims: C009 C010 C011 C018 -->

Keeping these failure modes separate avoids a common logical error. Several weak or negative variables do not combine into a stronger causal narrative. Groundwater is a limited completed test, deep susceptibility is not adequately tested, and construction loading is not testable. Their evidence states cannot be averaged. The surviving conclusion is that no tested candidate explains the observed selectivity, not that the supported features lack a physical cause. <!-- Claims: C008 C009 C010 C011 C018 -->

### 4.7 Remaining alternatives are not conclusions

Plausible alternatives remain: deformation in a deeper compressible aquifer system not represented by shallow texture; localized pumping not captured by the available station network; poroelastic or seasonal motion sampled differently by the two tracks; horizontal displacement projected differently into LOS; construction or foundation loading absent from the dated data; and residual atmospheric, unwrapping, or coherence-related effects. Each is consistent with at least one limitation, but consistency is not evidence of occurrence. We list them to define discriminating future observations, not to replace failed tests with speculation. <!-- Claims: C010 C011 C019 C023 -->

The alternatives imply specific evidence needs. Deep borehole logs, screened-interval metadata, colocated piezometry, continuous GNSS, leveling, and documented construction histories would separate several physical hypotheses. Reprocessing with additional viewing geometries or independent algorithms would target measurement explanations. Until such observations exist, ranking these alternatives would be driven more by prior plausibility than by the frozen results. The manuscript therefore leaves the physical mechanism unresolved rather than selecting the most familiar urban explanation. <!-- Claims: C019 C021 C023 -->

### 4.8 Implications for urban InSAR inference

The study supports a workflow in which detection, reproduction, and attribution are treated as separate inferential stages. Detection should be frozen before independent evaluation; the second geometry should have an auditable inventory and network; comparison should occur on a common valid domain and reference convention; and failures should be retained as controls. This structure reduces the opportunity to tune thresholds, pairs, or explanatory variables toward a preferred zone. It also turns non-reproduction into information about the specificity of both the observation and the proposed cause. <!-- Claims: C016 C020 -->

Cross-geometry agreement itself must be reported at the level actually tested. Polygon mean rates, spatial contrasts, time histories, vertical components, and absolute rates are different claims. Likewise, statistical fit, reference offsets, processing sensitivity, temporal non-stationarity, and structural contradiction should remain separate unless a defensible probabilistic model connects them. Publishing H002/H003 and H005 alongside H001/H004 makes the evidential denominator visible. For urban InSAR studies, that transparency is a stronger basis for action than a map in which only confirmatory features and plausible causes survive the writing process. <!-- Claims: C007 C012 C014 C017 C020 -->

This design also clarifies where additional data would be most valuable. A second geometry does not automatically solve attribution, but it triages features into those that warrant costly ground investigation, those requiring measurement diagnosis, and those that should not yet enter causal analysis. Preregistered contrasts then determine whether an explanatory dataset has discriminatory value rather than merely geographic overlap. In this study, that sequence concentrates follow-up on H001/H004 while retaining H002/H003 and H005 as constraints on any future model. The resulting product is not a definitive hazard map; it is an evidence-ranked set of observations with explicit decision boundaries. <!-- Claims: C016 C017 C019 C020 -->

## 5. Limitations

**Local geodetic reference.** No continuous, independent station inside the AOI spans the analysis with sufficient sampling; the nearest adequately sampled GNSS station identified by the project is far outside the study area. The stable-control alignment makes the two relative maps comparable but cannot determine their absolute zero. This affects absolute rates and regional offsets, while leaving within-map zone contrasts invariant. We therefore cannot claim an absolute geodetic velocity or long-wavelength datum accuracy. <!-- Claims: C012 C021 -->

**LOS projection.** Ascending and descending observations have different three-dimensional sensitivity, with weak north-south resolution and no retained valid component decomposition. This affects the physical direction and magnitude assigned to H001/H004 and complicates non-reproduction at H002/H003. We therefore cannot claim vertical displacement, volumetric compaction, or horizontal stability from the LOS results alone. <!-- Claims: C014 C021 -->

**Partial descending coverage.** Orbit 136 covers approximately 70% of the AOI and misses a western strip, although it includes the five frozen polygons. This limits map-wide reproduction and means untested ascending terrain cannot be classified by the descending experiment. We therefore cannot generalize the hotspot-level result to the full 22.6 km2 operating mask or the entire ascending field. <!-- Claims: C005 C022 -->

**Temporal mismatch.** The tracks have different acquisition dates, two long descending gaps, no exactly shared dates, and different retained cumulative behavior. These differences affect event-scale and seasonal comparisons even when full-period mean rates are similar. We therefore cannot claim matched transients, identical displacement histories, or persistence beyond the four-year record. <!-- Claims: C007 C012 -->

**Coherence ambiguity.** Relative LOS velocity varies monotonically with temporal coherence across multiple processing states, and the physical origin of that association is unresolved. Coherence-band matching reduces but cannot remove all dependence on scattering properties or inversion behavior. This affects spatial detection, proxy contrasts, and interpretation of the supported zones. We therefore cannot claim that measurement artefact is absent, only that it is not supported as the sole explanation for H001/H004. <!-- Claims: C012 C023 -->

**Aquifer-depth specificity.** Groundwater wells lack consistent screened-interval, aquifer, construction, and pumping metadata; the H001 composite is sparse and interrupted. The test therefore may not observe hydraulic conditions in the material responsible for motion. This affects the power and physical specificity of the groundwater result. We can report `NO EVIDENCE` for the preregistered test but cannot claim that groundwater influence or aquifer compaction is ruled out. <!-- Claims: C008 C010 -->

**Construction chronology.** Available land-cover and built-surface products measure mapped urban fabric, not structure height, foundation type, load, construction date, tunneling, excavation, or dewatering. This affects any attempt to distinguish static urban setting from active construction forcing. We therefore classify major infrastructure and construction loading as `NOT TESTABLE` and cannot attribute a zone to buildings or infrastructure. <!-- Claims: C011 -->

**H005 contradiction.** No external measurement resolves which geometry, temporal segment, or physical component accounts for H005's opposite-sign rates. This affects the completeness of the five-zone interpretation and blocks its use in mechanism analysis. We therefore cannot assign H005 to the supported or control class, explain its sign, or use it to strengthen any causal narrative. <!-- Claims: C004 C017 -->

## 6. Conclusions

Independent ascending and descending Sentinel-1 observations separated five frozen Delhi-NCR zones into three evidential outcomes. H001 and H004 were supported at the spatial and mean-rate level; H002 and H003 were not reproduced despite adequate descending quality; and H005 remained an unresolved cross-geometry contradiction. The H001/H004 result is restricted to relative LOS spatial structure and observation-period mean rates. It does not establish an absolute rate, vertical motion, matching time histories, or a physical cause.

The preregistered groundwater, shallow-texture, existing-built-intensity, and detected built-expansion tests supplied no evidence for the supported-versus-control selectivity. Deep geological and aquifer-system susceptibility was not adequately tested, while construction loading was not testable. These states are not interchangeable with disproof. Accordingly, the physical mechanism remains unresolved.

The negative controls are central to that conclusion. They show that an ascending anomaly of comparable magnitude and adequate local quality need not survive an independent geometry, and that a regional explanatory variable must account for differential outcomes rather than merely coexist with urban deformation. Retaining H002/H003 and the H005 contradiction therefore changes the scientific claim from detection plus plausible attribution to selective reproduction with explicit inference limits. That separation is the principal contribution of the study.

## Author contributions (CRediT)

**PROPOSED; AWAITING CONFIRMATION BY ALL AUTHORS.**

**Vishal Kumar Chaubey:** Conceptualization, Methodology, Investigation, Data curation, Formal analysis, Visualization, Writing – original draft.

**Harishankar Gangwar:** Supervision, Methodology, Validation, Resources, Writing – review & editing.

**Suresh Kannujiya:** Supervision, Validation, Methodology, Writing – review & editing.

## Funding

**PROPOSED; USE ONLY IF NO SPECIFIC FUNDING WAS RECEIVED.** This research received no specific grant from any funding agency in the public, commercial, or not-for-profit sectors.

## Acknowledgements

The authors gratefully acknowledge Mr. Vivek Chaubey for his continued support during the course of this research.

## Declaration of competing interest

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

## Ethics statement

Ethical approval was not required for this study, as the research did not involve human participants, animals, or personally identifiable information.

## Data and code availability

The datasets generated and/or analysed during the current study are available from the corresponding author upon reasonable request. Publicly available remote-sensing datasets can be obtained from their respective providers. The processing, verification, and manuscript-building code is available in the public project repository; source data and derived products are identified in Supplement S13. No dedicated dataset repository DOI is currently available.

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

**PROPOSED; AWAITING REVIEW AND APPROVAL BY ALL AUTHORS.** During the preparation of this manuscript, the authors used OpenAI Codex for literature organization, manuscript drafting and language refinement, consistency and evidence auditing, and assistance with manuscript and figure organization. Before submission, the authors will review and verify the scientific interpretation, analyses, results, conclusions, and final content, and will take full responsibility for the published work.
