# Independent-geometry validation report

**Delhi-NCR Sentinel-1 SBAS study | 23 September 2026**

## Scope and decision

This report assesses whether five zones defined in the ascending Sentinel-1 analysis survive a separately assembled descending observation. **Two zones (H001 and H004) are supported at the spatial-pattern and observation-period mean-rate level; two (H002 and H003) are not reproduced; one (H005) remains contradictory.** This is an independent *measurement-geometry* check, not independent external peer review, ground-survey validation, or proof of a physical mechanism.

## Independence and comparison design

The ascending stack contains 119 acquisitions and 336 interferograms; the descending stack contains 91 acquisitions and 219 interferograms. The descending orbit, bursts, acquisition list, interferogram network, inversion mask, and native reference were assembled independently of the ascending product. The five ascending zones were frozen before descending classification. Comparisons use the common valid domain (854,004 pixels; 1,366.406 km²; 69.63% of the scientific area of interest), with both relative LOS products aligned to the same stable-control zero level. All five polygons have essentially complete common-domain coverage. The descending product reported here is the final D2 correction branch, not the superseded early Phase II-A product.

## Zone-level findings

Rates are mean relative line-of-sight (LOS) velocities in mm yr⁻¹. Polygon areas are the original frozen ascending-zone areas, not a continuously validated footprint.

| Zone | Ascending | Descending | Area (km²) | Decision |
|---|---:|---:|---:|---|
| H001 | −30.95 | −36.02 | 5.59 | Independently supported spatially and in mean rate |
| H004 | −14.31 | −12.46 | 1.07 | Independently supported spatially and in mean rate |
| H002 | −13.59 | −1.15 | 12.83 | Not reproduced despite adequate descending quality |
| H003 | −12.87 | −0.75 | 2.25 | Not reproduced despite adequate descending quality |
| H005 | −14.21 | +61.39 | 0.84 | Unresolved opposite-sign and magnitude contradiction |

The H001 and H004 polygon areas sum to **6.66 km²** after rounding (5.5904 + 1.0720 = 6.6624 km²). This is 29.5% of the 22.58 km² ascending criterion-derived operating extent, **not** a claim that every pixel in those polygons was independently validated. The older 3.17 km² figure in the archived Phase IV synthesis was incorrect and was superseded by [erratum INC-009](../provenance/errata/INC-009.json).

## Strength of agreement and limits

The corrected cross-geometry field correlation is moderate (Pearson *r* = 0.3626); it does not validate the full regional field. Mean-rate agreement must not be conflated with time-history agreement: H001's retained cumulative summaries disagree (ascending −120.7 mm; descending +1.1 mm), and its cross-series correlation is *r* = 0.007. The geometries have different acquisition dates and descending temporal gaps. The result is restricted to relative LOS spatial structure and mean rates within the overlap domain. It establishes neither absolute or vertical displacement nor subsidence mechanism. No colocated, sufficiently sampled continuous GNSS or leveling series provides external ground truth for these zones.

## Mechanism evidence

The preregistered tests yielded **no evidence** that observed groundwater-level variability, shallow soil texture, existing built intensity, or detected recent built-up expansion explains why H001/H004 reproduced while H002/H003 did not. Deep geological or aquifer-system susceptibility was **not adequately tested**; major construction loading was **not testable** with the obtained records. “No evidence” for these particular tests is not evidence that groundwater, geology, or construction cannot contribute. H005 was excluded from causal testing because its geometry contradiction remains unresolved.

## What remains before stronger validation

An external reviewer or independent analyst has not yet issued a report. Stronger physical validation requires suitable local GNSS or leveling, depth-specific well and geological records, construction chronology, and/or additional independent viewing geometries or processing. Those data would test absolute motion, displacement components, time histories, and cause; the present independent-geometry result does not.

## Audit trail

The frozen classifications, rates, and evidence states are in [`final_hotspot_table.csv`](../qc/sci/phase4/final_hotspot_table.csv) and [`final_evidence_matrix.csv`](../qc/sci/phase4/final_evidence_matrix.csv). The comparison domain and acquisition spans are in [`common_domain.json`](../qc/sci/phase2/common_domain.json); corrected D2 agreement diagnostics are in [`revalidation_v2.json`](../qc/sci/phase2b/revalidation_v2.json). [The submission manuscript](SUBMISSION_MANUSCRIPT.md) supplies the full methods, uncertainty accounting, literature context, and limitations.
