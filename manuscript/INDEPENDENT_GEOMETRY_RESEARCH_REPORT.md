# Independent-geometry validation of Sentinel-1 line-of-sight deformation zones in Delhi-NCR

**Technical research report | 23 September 2026**

Vishal Kumar Chaubey, Harishankar Gangwar, and Suresh Kannujiya

Indian Institute of Remote Sensing (IIRS), Indian Space Research Organisation (ISRO), Dehradun, Uttarakhand, India

Correspondence: Vishal Kumar Chaubey, vishal.chaubey17@outlook.com

## Abstract

**Objective:** To determine which deformation zones identified in an ascending Sentinel-1 small-baseline time series are reproduced by an independently constructed descending observation over Delhi National Capital Region (NCR). **Methods:** Five ascending-defined zones were frozen before analysis of a separate descending orbit. The ascending and descending stacks contained 119 acquisitions/336 interferograms and 91 acquisitions/219 interferograms, respectively. Relative line-of-sight (LOS) velocities were compared within a common valid domain after a declared stable-control alignment. **Results:** H001 and H004 showed concordant spatial features and observation-period rates (ascending/descending: −30.95/−36.02 and −14.31/−12.46 mm yr⁻¹). H002 and H003 were not reproduced despite adequate descending quality. H005 reversed sign (−14.21/+61.39 mm yr⁻¹) and remained unresolved. The two supported zones comprise 6.66 km² when their original polygon areas are summed. Global field agreement was moderate (*r* = 0.363), and the detailed H001 displacement history did not reproduce. **Conclusion:** Independent viewing geometry supports two localized relative-LOS features at the spatial and mean-rate level, not the entire ascending field, vertical motion, matching time histories, or a physical cause. This is an independent measurement-design test, not external peer review or ground-truth validation.

**Keywords:** Delhi-NCR; InSAR; Sentinel-1; SBAS; line-of-sight velocity; cross-geometry validation; reproducibility

## 1. Introduction

A spatially coherent velocity anomaly in one interferometric synthetic-aperture radar (InSAR) viewing geometry does not by itself establish a persistent physical displacement. Viewing direction, reference convention, temporal sampling, and processing residuals can affect a relative LOS estimate [1–3]. A second observation assembled without reusing the first stack provides a stronger test of whether a preidentified feature is repeatable. It still cannot, on its own, determine three-dimensional displacement or cause.

This report addresses one narrow question: which of five Delhi-NCR zones frozen from an ascending Sentinel-1 product survive a separately processed descending geometry? It reports positive, negative, and contradictory outcomes together so that the evidential denominator remains visible. The [full submission manuscript](SUBMISSION_MANUSCRIPT.md) gives the broader study, literature context, mechanism tests, figures, and uncertainty accounting.

## 2. Materials and methods

### 2.1 Observation design and frozen zones

The scientific area of interest covers 1,962.4 km². Observations span October 2021 to September 2025. The ascending product uses relative orbit 27, subswath IW2, with 119 acquisitions and 336 interferograms. Its authoritative RAW-336 branch defined connected zones using three fixed criteria: absolute relative LOS rate ≥10 mm yr⁻¹, temporal coherence ≥0.80, and area ≥0.4 km². Five zones (H001–H005), totaling 22.58 km² under this criterion, were frozen before descending interpretation. This total is a threshold-dependent ascending operating extent, not an independently validated footprint.

The descending experiment uses relative orbit 136, subswath IW1, with 91 acquisitions and 219 interferograms. Its acquisitions, pair network, inversion mask, and native reference were assembled without reusing ascending counterparts or selecting pairs because they intersected a frozen zone. A descending bridging-plus-phase-closure correction branch (D2) was retained after improving all seven prespecified internal reliability diagnostics. The preliminary raw descending result is therefore not the product evaluated below.

### 2.2 Cross-geometry comparison

The valid overlap contains 854,004 pixels, or 1,366.406 km² (69.63% of the area of interest), and includes essentially all five polygons. No common coherence threshold was imposed on the two stacks' different coherence distributions. Each product retained its independent native reference; comparison values were subsequently aligned to a common stable-control zero level. Zone rates, sign, spatial detection, quality, and retained temporal diagnostics were then evaluated without changing the original polygons. The acquisition dates were not interpolated to manufacture matching observations.

The outcome labels are deliberately limited. **Supported** means reproduction of spatial pattern and observation-period mean relative-LOS rate; **not reproduced** means no adequate descending counterpart at the required magnitude despite usable local data; **unresolved contradiction** means the geometries yield opposing observations that this study cannot adjudicate. A supported rate does not imply a reproduced displacement history.

## 3. Results

### 3.1 Zone-level outcomes

**Table 1.** Frozen ascending zones evaluated in the independent descending geometry. Rates are relative LOS velocities in mm yr⁻¹; areas are the original ascending polygon areas.

| Zone | Ascending rate | Descending rate | Area (km²) | Cross-geometry outcome |
|---|---:|---:|---:|---|
| H001 | −30.95 | −36.02 | 5.59 | Supported spatially and in mean rate |
| H004 | −14.31 | −12.46 | 1.07 | Supported spatially and in mean rate |
| H002 | −13.59 | −1.15 | 12.83 | Not reproduced |
| H003 | −12.87 | −0.75 | 2.25 | Not reproduced |
| H005 | −14.21 | +61.39 | 0.84 | Unresolved sign-and-magnitude contradiction |

H001 and H004 had same-sign descending spatial features and comparable rate magnitudes. Their rate-magnitude ratios were 1.16 and 0.87, respectively; their descending median temporal coherences were 0.906 and 0.909. These findings support the features at the spatial and mean-rate level. Their original polygon areas sum to **6.66 km²** (5.5904 + 1.0720 = 6.6624 km² before rounding), or 29.5% of the 22.58 km² ascending operating extent. This is a polygon-area sum, not a claim that every pixel is independently validated. An older 3.17 km² value was corrected in [erratum INC-009](../provenance/errata/INC-009.json).

H002 and H003 had descending rates near zero relative to ascending rates around −13 mm yr⁻¹. Their descending median temporal coherences were 0.900 and 0.886, so simple absence of usable descending observations does not explain the non-reproduction. That result does **not** prove physical stationarity or identify an artefact: different LOS sensitivity, temporal behavior, or residual processing structure remain possible. H005 showed a much larger, opposite-sign descending rate. Its median descending temporal coherence was 0.851, and the contradiction was retained rather than assigning either geometry priority.

### 3.2 Regional and temporal agreement

After descending D2 correction, field-wide ascending–descending Pearson correlation was *r* = 0.3626, compared with 0.1752 for the preliminary descending branch. Agreement remained moderate and spatially heterogeneous; it cannot be interpreted as validation of the full ascending velocity map. Descending coverage also omits part of the area of interest.

The detailed histories provide a separate limitation. For H001, retained cumulative displacement summaries were −120.7 mm ascending and +1.1 mm descending, with detrended cross-series correlation *r* = 0.007. H004 likewise lacked a reproduced detailed history. Consequently, the positive classifications concern observation-period spatial structure and mean rates only; they do not support matching time-series evolution.

## 4. Discussion

The contrast between H001/H004 and H002/H003 is the central validation result. Features of similar ascending-rate order and adequate local quality did not all survive the independent viewing geometry. Retaining the two non-reproduced zones as negative controls prevents a regional explanation from being accepted solely because it overlaps an ascending anomaly. H005 further shows that a second geometry may expose a substantive contradiction rather than provide a binary confirmation.

The preregistered mechanism analyses supplied **no evidence** that observed groundwater-level variability, shallow soil texture, existing built intensity, or detected recent built-up expansion explains the supported-versus-control contrast. Deep geological or aquifer-system susceptibility was **not adequately tested**, and major construction loading was **not testable** using the obtained records. These evidence states must not be read as disproof of groundwater, geology, or construction effects. H005 was excluded from causal testing because its observation remained contradictory.

Three limitations set the interpretation boundary. First, both products are relative LOS measurements; common-control alignment does not yield an absolute geodetic datum or a reliable vertical/east decomposition. Second, temporal mismatch and descending gaps constrain detailed time-history comparisons. Third, no sufficiently sampled colocated GNSS or leveling series supplies external ground truth. Additional local geodesy, depth-specific hydrogeological data, dated construction records, and independent processing or viewing geometries would be needed to test physical displacement and attribution more strongly.

## 5. Conclusion

Independent descending Sentinel-1 processing reproduced two of five frozen Delhi-NCR ascending zones at the spatial and mean-rate level. Two zones were not reproduced despite adequate descending quality, and one produced an unresolved opposite-sign contradiction. The supported 6.66 km² is the sum of two original polygons, not a continuous validated footprint. The study does not establish vertical subsidence, matching displacement histories, or a causal mechanism. External independent review and ground-truth validation remain outstanding.

## Data and reproducibility record

The frozen zone classifications and rates are in [`final_hotspot_table.csv`](../qc/sci/phase4/final_hotspot_table.csv); mechanism evidence states are in [`final_evidence_matrix.csv`](../qc/sci/phase4/final_evidence_matrix.csv). Acquisition spans, overlap, and reference alignment are documented in [`common_domain.json`](../qc/sci/phase2/common_domain.json); corrected descending diagnostics are in [`revalidation_v2.json`](../qc/sci/phase2b/revalidation_v2.json). This report is a focused synthesis of those records and does not supersede the full methods and limitations in the [submission manuscript](SUBMISSION_MANUSCRIPT.md).

## References

1. Ferretti A, Prati C, Rocca F. Permanent scatterers in SAR interferometry. *IEEE Transactions on Geoscience and Remote Sensing*. 2001;39(1):8–20. [doi:10.1109/36.898661](https://doi.org/10.1109/36.898661).
2. Berardino P, Fornaro G, Lanari R, Sansosti E. A new algorithm for surface deformation monitoring based on small baseline differential SAR interferograms. *IEEE Transactions on Geoscience and Remote Sensing*. 2002;40(11):2375–2383. [doi:10.1109/TGRS.2002.803792](https://doi.org/10.1109/TGRS.2002.803792).
3. Crosetto M, Monserrat O, Cuevas-González M, Devanthéry N, Crippa B. Persistent Scatterer Interferometry: A review. *ISPRS Journal of Photogrammetry and Remote Sensing*. 2016;115:78–89. [doi:10.1016/j.isprsjprs.2015.10.011](https://doi.org/10.1016/j.isprsjprs.2015.10.011).
