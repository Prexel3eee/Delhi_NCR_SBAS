# Supplementary material

This supplement records the operational implementation behind the evidence-bound main article. Paths are relative to the repository root. The frozen ascending and descending products are not modified by manuscript generation.

## S1. Study area and reference frame

The scientific AOI is stored at `geometry/aoi.geojson`, projected to EPSG:32643, and covers 1,962.4 km2. The analysis mask excludes water and uses the exact AOI rasterization recorded in `qc/sci/aoi_mask_provenance.json`; no hand-edited mask was introduced during writing. Ascending products use a 2,407 x 2,939 approximately 40 m grid and descending products a 2,412 x 2,853 grid before alignment.

The authoritative ascending product is relative to MintPy's auto-selected pixel `(y=1384, x=1451)`, not the intended scientific reference `(1378,1426)`. The separation is 1,028.4 m and the measured zero-level offset is 0.1362 mm yr-1. This is recorded in `provenance/errata/INC-007.json`. Spatial gradients and polygon-to-background contrasts are invariant to the constant offset. Cross-geometry comparisons were separately aligned to a stable common control as described in S6; this does not create an absolute datum.

## S2. Ascending network

The ascending stack uses relative orbit 27, IW2, VV, and burst IDs `027_056011_IW2` through `027_056014_IW2`. Candidate dates and pairs were intersected by acquisition and pair identity across all four bursts. The accepted 119 acquisitions span 2021-10-06 to 2025-09-27. Pair thresholds were maximum temporal baseline 36 days and maximum absolute perpendicular baseline 250 m. The resulting 336-edge graph has one connected component, no isolated nodes, no bridges, no articulation points, and minimum degree three. Baseline and graph records are `qc/network/baseline_table.csv`, `qc/network/network_edges.csv`, and `qc/network/network_summary.json`.

Every accepted pair was processed; no interferogram was removed after viewing the velocity field. HyP3 remote state, local products, and the 336-row manifest were reconciled before inversion. Retrieval and content audits are retained in `qc/production/`, with hash-pinned inputs in `freeze/mintpy_input_v1/` and the authoritative output in `freeze/product_v1/`.

## S3. Descending network

The independent stack uses relative orbit 136, IW1, VV, and burst IDs `136_290874_IW1` through `136_290877_IW1`. The inventory window was 2021-10-01 to 2025-10-01. Ninety-one common accepted acquisitions span 2021-10-02 to 2025-09-23; one otherwise present date, 2024-04-13, was dropped as unconnectable. The standard 36-day and 250 m rules generated the network core. Two record gaps of 108 and 48 days required the minimal flagged longer-baseline additions used in the final 219-pair graph. The graph has one component, no bridges, minimum degree two, and one articulation date, 2022-11-26. Full records are in `qc/descending/network_audit.json`, `qc/descending/network_edges.csv`, and `qc/descending/descending_qc.json`.

The construction was fail-closed: a date was accepted only if all four bursts were present, a pair only if the identity key occurred in every burst, positional zipping was forbidden, no ascending artefact was read, and no hotspot geometry was used for pair selection. The descending footprint does not cover the AOI's western strip, so all comparisons use S6's common domain.

## S4. Processing and correction branches

Both geometries used HyP3 `INSAR_ISCE_MULTI_BURST`, 10 x 2 looks, water masking, and approximately 40 m output spacing. MintPy 1.6.4 inversion used `weightFunc = var`, `minNormVelocity = yes`, and `keepMinSpanTree = no`; the last setting prevents the software default from silently reducing the accepted network. Valid inversion support is `velocityStd > 0`, not array finiteness, because MintPy may represent non-inverted pixels with finite zero fills.

Ascending branch configurations are `config/mintpy_baseline_raw.txt`, `config/mintpy_era5.txt`, `config/mintpy_dem_residual.txt`, and `config/mintpy_bridge_pc.txt`. RAW-336 retained all 336 pairs with unwrap correction, tropospheric correction, DEM-residual correction, and deramping off. ERA5 and ERA5-plus-DEM branches improved only one of four targeted diagnostics; ascending unwrap correction worsened residual fit. The frozen authoritative branch therefore remained RAW-336.

Descending D0 used `config/mintpy_descending_baseline.txt`. D2 changed only the unwrap treatment to bridging plus phase closure and improved seven of seven prespecified reliability diagnostics. D2, located at `mintpy/descending_d2_unwrap_work/` and frozen as `descending_v2_candidate`, is the comparison branch. This geometry-specific choice does not alter the ascending freeze.

## S5. Hotspot definition and freeze

Phase-I connected components were detected in RAW-336 where absolute relative LOS velocity was at least 10 mm yr-1, temporal coherence at least 0.80, and connected area at least 0.4 km2. Eight-neighbour connectivity was used. The implementation is `scripts/32_hotspots.py`; statistics are `qc/sci/phase1/hotspots.csv` and `hotspots.json`, and corrected polygons are `qc/sci/phase1/hotspots_corrected.geojson`. The original GeoJSON is retained only as an incident artefact (INC-008).

Sensitivity was recorded over rate thresholds 5, 7.5, 10, 15, 20, and 25 mm yr-1 and alternate coherence cutoffs in `qc/sci/phase1/hotspot_threshold_sensitivity.csv`. The primary five zones were not reselected. Their 22.6 km2 combined area is the operating extent under this rule. The 6.66 km2 supported-zone area is computed only as frozen H001 plus H004 polygon area and is guarded against recurrence of INC-009.

## S6. Common-domain alignment and comparison

The common mask is ascending valid coverage AND descending valid coverage AND the scientific AOI, with no common coherence threshold. Its authoritative record is `qc/sci/phase2/common_domain.json` and its raster mask `qc/sci/phase2/common_domain_mask.npz`. The domain contains 854,004 pixels, spans 1,366.406 km2, and represents 69.63% of the AOI. It contains all H001, H004, and H005 pixels and all but one pixel each from H002 and H003.

Each native product retains its own reference. For direct comparison, both were re-referenced to the median of the same 3,692 stable-control pixels, defined by common validity, high coherence, and absolute velocity within 3 mm yr-1. The offsets were +0.3546 mm yr-1 ascending and -0.0992 mm yr-1 descending. Comparisons include common-domain field correlation, polygon means, component overlap, centroid separation, magnitude ratio, matched-coherence-band contrast, and split-period behavior. Native-record and common-period summaries remain distinct, and acquisition dates were never interpolated to force identity.

## S7. Groundwater protocol

The protocol identifier is `groundwater_protocol_v1`; it was frozen before correlations were computed. Source and screening records are `qc/sci/phase3/nwdp_telemetry_station_registry.csv`, `groundwater_station_registry_final.csv`, `groundwater_station_qc.csv`, and `dwlr_audit.json`. From 187 candidate NWDP telemetry stations, 111 passed quality screening. Every eligible station within 5 km of a tested polygon was included. Six-hourly values were converted to daily medians only when at least two valid observations were present; missing days were not interpolated. Station-median anomalies were composited by date, with positive anomaly denoting deeper water.

The prespecified forward lag grid was 0, +30, +60, and +90 days. Negative lags -30, -60, and -90 days were falsification tests in which LOS response would precede the proposed forcing. Spearman association was evaluated with 5,000 circular block permutations using 90-day blocks. Benjamini-Hochberg FDR q = 0.05 was applied across the 16 forward-lag zone tests. H005 was never included. Results are in `qc/sci/phase3/groundwater_lag_results.csv` and `groundwater_control_comparison.csv`.

## S8. Geology and urban evidence

SoilGrids 2.0 clay and sand fractions at 0-5 cm and 100-200 cm were sampled by windowed access on the native 250 m grid. Zone and AOI-minus-zones polygons were rasterized on that source grid; no SoilGrids layer was resampled to the InSAR grid. Outputs are `qc/sci/phase3/geology_hotspot_summary.csv` and the dataset registry. These are shallow texture variables only. Formation, age, deep lithology, aquifer boundaries, and compacting interval were unavailable, which fixes deep susceptibility at `NOT ADEQUATELY TESTED`.

Urban comparison used ESA WorldCover 2021 built class on its 10 m grid and JRC GHSL GHS-BUILT-S E2020 and E2025 near 93 m on their source grids. Outputs are `qc/sci/phase3/urban_hotspot_summary.csv` and `urban_analysis.json`. The E2025 GHSL layer is projected rather than an observation. No dataset supplied structure height, foundation, load, exact construction date, tunneling, excavation, or dewatering; construction loading is therefore `NOT TESTABLE`.

## S9. Uncertainty and evidence states

The frozen uncertainty registry is `qc/sci/phase4/uncertainty_table.json`. It separates formal fit uncertainty, reference-systematic uncertainty, correction-branch sensitivity, cross-geometry structure, temporal non-stationarity, and data-domain limitations. These terms are not summed. Their units, statistical meanings, and dependence structures differ, and no generative model converts them into a justified combined interval.

Evidence states are fixed in `qc/sci/phase4/final_evidence_matrix.csv`. `NO EVIDENCE` means a suitable prespecified test did not support its prediction. `NOT ADEQUATELY TESTED` means the available measurement did not observe the relevant physical domain. `NOT TESTABLE` means no suitable retained dataset was available. The longer measurement-artefact state records that matched-band contrasts oppose artefact as the sole explanation for H001/H004 while measurement limitations remain.

## S10. Supplementary tables

### Table S1. Frozen hotspot outcomes

| Zone | Ascending rate (mm/yr) | Descending rate (mm/yr) | Area (km2) | Status |
|---|---:|---:|---:|---|
| H001 | -30.95 | -36.02 | 5.59 | INDEPENDENTLY_SUPPORTED |
| H004 | -14.31 | -12.46 | 1.07 | INDEPENDENTLY_SUPPORTED |
| H002 | -13.59 | -1.15 | 12.83 | NOT_REPRODUCED |
| H003 | -12.87 | -0.75 | 2.25 | NOT_REPRODUCED |
| H005 | -14.21 | +61.39 | 0.84 | UNRESOLVED_CONTRADICTION |

The table reports polygon means over the retained common-domain definition. Detailed classifications, coherence values, rate ratios, time-history states, and final interpretations are in `qc/sci/phase4/final_hotspot_table.csv`.

### Table S2. Reproducibility registry

| Component | Authoritative record | Protection |
|---|---|---|
| Ascending input network | `freeze/mintpy_input_v1/FREEZE.json` | hash verification |
| Ascending output | `freeze/product_v1/FREEZE.json` | hash verification; append-only errata |
| Descending network | `qc/descending/network_audit.json` | identity intersection and graph gates |
| Common comparison domain | `qc/sci/phase2/common_domain.json` | fixed mask and stable-control definition |
| Groundwater test | `config/groundwater_protocol_v1.json` | fixed lag/permutation/FDR rules |
| Final classifications | `qc/sci/phase4/final_hotspot_table.csv` | numerical audit against manuscript |
| Evidence states | `qc/sci/phase4/final_evidence_matrix.csv` | verbatim-state audit |

## S11. Scientific incidents

The incidents are retained because they changed the reliability of the workflow, even when final scientific classifications did not change.

### INC-001

- **Problem:** HyP3 `find_jobs(name=...)` performs an exact-name match; a prefix-based idempotency guard therefore found nothing.
- **Consequence:** Seven duplicate pilot jobs were submitted, consuming 35 avoidable credits; the same defect could have duplicated production.
- **Detection:** The credit delta and remote exact-name count disagreed with the intended seven-job set.
- **Correction:** Remote jobs are listed by type and reconciled locally against exact manifest names; all duplicate pilot products were retained transparently.
- **Regression protection:** `tests/test_pilot_idempotency.py` prevents prefix queries and verifies no repeat submission.

### INC-002

- **Problem:** A transient ASF DNS outage terminated the initial retrieval at 47 of 336 products.
- **Consequence:** A non-resumable workflow could have left an incomplete ascending corpus.
- **Detection:** Retrieved-product counts failed reconciliation against the frozen 336-pair manifest.
- **Correction:** Connection and listing gained capped backoff, typed network failure, resumable downloads, and a single batched job listing; all 336 products were recovered.
- **Regression protection:** `tests/test_production_retrieval.py` requires complete remote-ledger-local reconciliation.

### INC-005

- **Problem:** The first RAW-versus-ERA5 comparison read the wrong velocity dataset because the MintPy file pointer did not resolve to the corrected velocity product.
- **Consequence:** It produced a spurious 15.49 mm yr-1 difference and would have favored an unsupported correction branch.
- **Detection:** The magnitude was inconsistent with the atmospheric product and triggered a file-path audit.
- **Correction:** The corrected comparison is 0.52 mm yr-1 RMS; ERA5 and ERA5-plus-DEM remained non-beneficial and disabled in RAW-336.
- **Regression protection:** `tests/test_correction_validation.py` pins both corrected values and branch settings.

### INC-006

- **Problem:** A GNSS co-location comparison used unequal time windows and appeared to disagree by approximately 27 mm yr-1.
- **Consequence:** The artefactual difference could have been interpreted as a large InSAR bias.
- **Detection:** Station end epochs were audited and found to differ substantially.
- **Correction:** Comparison on 745 shared epochs reduced the station difference to 0.767 mm yr-1; GNSS remained unsuitable because of coverage, not measurement disagreement.
- **Regression protection:** `tests/test_correction_validation.py` requires maximal shared-window comparison and header-resolved vertical components.

### INC-007

- **Problem:** RAW-336 allowed MintPy to auto-select `(1384,1451)` rather than using the intended `(1378,1426)` reference.
- **Consequence:** The relative zero differs by 0.1362 mm yr-1; spatial contrasts and all zone geometry remain unchanged.
- **Detection:** The only pixel identically zero on all 119 dates was located and checked against the decision record.
- **Correction:** The discrepancy is an append-only erratum; all manuscript values are labeled relative and cross-geometry comparisons use the shared stable-control alignment.
- **Regression protection:** `provenance/errata/INC-007.json` pins coordinates, hashes, measured offset, and reporting requirements; future revisions must set every branch reference explicitly.

### INC-008

- **Problem:** `hotspots.geojson` stored single-pixel fragments and detection-order IDs because polygon extraction stopped after its first returned shape.
- **Consequence:** Earlier polygon containment and overlap checks were vacuous, although the frozen CSV statistics were unaffected.
- **Detection:** Implausible polygon pixel counts prompted an audit against the zone raster and CSV areas.
- **Correction:** `qc/sci/phase1/hotspots_corrected.geojson` reproduces every frozen zone area; all descending containment checks were rerun and every zone remained covered.
- **Regression protection:** `scripts/51_fix_hotspot_polygons.py` verifies polygon-versus-pixel area and identifier mapping.

### INC-009

- **Problem:** Three reports repeated 3.17 km2 as the independently supported area without a derivation.
- **Consequence:** The published summary disagreed with the frozen H001 plus H004 geometry by a factor of approximately 2.1.
- **Detection:** The Phase-V numerical consistency gate traced every area-like value and found no source for 3.17.
- **Correction:** The value is 6.66 km2, derived from 5.5904 plus 1.0720 km2 and rounded; no classification or mechanism conclusion changes.
- **Regression protection:** `scripts/75_phase5b_audit.py` asserts equality to the frozen zone-area sum and fails untraceable area values.

## S12. Figure captions

# Figure Captions

Each caption is self-contained: geometry/branch, units, quality mask, sample definition, uncertainty meaning, exclusions and limitations are stated where relevant. No caption contains a causal interpretation.

## F1 — Study design and independent acquisition geometry

**Study design and independent acquisition geometry.** (A) Frozen coverage geometry for the Delhi-NCR study area (1,962.4 km², EPSG:32643). Blue denotes the four ascending burst footprints (relative orbit 27, IW2); orange denotes the four descending footprints (relative orbit 136, IW1); black is the AOI boundary. The red hatched area is the 28.0 % of the AOI not covered by the descending track — a western strip containing no classification zone. White circles mark the five zones (H001–H005), which are small relative to the AOI; north arrow and 20 km scale refer to the EPSG:32643 projection. (B) Stack composition. The two stacks share no burst, interferogram, mask or acquisition list; no pair was selected because it intersected a zone. *Limitation:* descending coverage is partial, so the descending geometry cannot validate the entire ascending field.

*Source data:* `geometry/aoi.geojson`, `geometry/selected_bursts.geojson`, `geometry/descending/selected_bursts.geojson`, `geometry/descending/coverage_report.json`, `qc/sci/phase1/hotspots_corrected.geojson`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig1`

## F2 — Ascending relative LOS velocity

**Ascending relative LOS velocity field (authoritative product, RAW-336).** (A) Mean relative line-of-sight velocity, all 336 interferograms retained, no pair excluded. Units are mm yr⁻¹. Warm colours indicate motion toward the satellite; blue indicates motion away; the map display is saturated at ±20 mm yr⁻¹ while the underlying values are retained. (B) Distribution of the same field on a log count scale; dashed line is the median. *Quality mask:* water-masked; non-inverted pixels excluded (validity defined by velocityStd > 0, not by finiteness, because MintPy fills the non-inverted region with zeros). *Uncertainty:* values are **relative** LOS rates, not vertical displacement. The reference pixel carries a **4.78 mm yr⁻¹ systematic** that offsets the absolute zero level; spatial gradients are invariant to it. Formal measurement uncertainty is 0.87 mm yr⁻¹; these terms are not combined.

*Source data:* `products/product_v1/los_velocity_mm_per_yr.tif`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig2`

## F3 — Cross-geometry classification of the five zones

**Cross-geometry classification of the five zones.** Grouped mean relative LOS rates by zone and viewing geometry: ascending (solid blue) and descending (hatched orange). Units are mm yr⁻¹. The strip beneath the axis encodes the frozen cross-geometry status. *Sample definition:* mean rate over each zone's pixels within the 854,004-pixel final common valid domain. *Branches:* ascending = RAW-336; descending = unwrap-corrected candidate. *Limitation:* ascending and descending are separate LOS geometries and are never converted to vertical displacement here. H001/H004 are independently supported at the spatial and mean-rate level; H002/H003 are not reproduced; H005 is a cross-geometry contradiction.

*Source data:* `qc/sci/phase4/final_hotspot_table.csv`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig3`

## F4 — Cross-track agreement and the selectivity of reproduction

**Cross-track agreement and the selectivity of reproduction.** (A) Cross-track agreement between ascending and unwrap-corrected descending velocity, for the raw descending branch (D0) and the unwrap-corrected branch (D2). **These are retained aggregate agreement statistics over 854,321 shared-domain pixels — not a pixel-level scatter.** Paired per-pixel values were not retained in the frozen evidence set, so no scatter is shown and none has been synthesised. (B) Fraction of each ascending zone's area overlapped by a descending-detected component. *Quality mask:* common valid domain of both stacks. *Limitation:* agreement is moderate and spatially heterogeneous, not global; a plane-detrended coefficient is given because a long-wavelength offset remains between geometries.

*Source data:* `qc/sci/phase2b/revalidation_v2.json`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig4`

## F5 — Zones independently supported by the descending geometry

**Zones independently supported by the descending geometry (H001 and H004).** (A) Mean relative LOS rate by geometry; bars as in F3. (B) Ratio of descending to ascending magnitude; dashed line is exact agreement. *Units:* mm yr⁻¹ (A), dimensionless ratio (B). *What is reproduced:* the spatial pattern, the mean rate and the amplitude ratio. *What is NOT reproduced:* the detailed displacement histories — see F8. *Area statement:* 6.66 km² is the area of Phase-I zones independently supported at the zone level by the descending geometry. It is not a validated extent, is not extrapolated beyond these zones, and is not a vertical displacement rate.

*Source data:* `qc/sci/phase4/final_hotspot_table.csv`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig5`

## F6 — H002 and H003 - negative controls

**H002 and H003 — negative controls.** Mean relative LOS rate by geometry for the two ascending zones that were not reproduced, alongside the one reproduced zone of comparable magnitude. Units are mm yr⁻¹. "Matched-band contrast" is the ascending contrast computed in a common temporal-coherence band. **H001 is omitted from this panel for plotting scale only:** at −30.9 / −36.0 mm yr⁻¹ it would compress the comparison shown here. It is reported in F5 and is not selectively excluded. *Quality:* the descending geometry is adequate at both controls (temporal coherence 0.900 and 0.886), so their absence is not a quality artefact. Any explanation acting across the affected terrain predicts all three zones similarly, and therefore fails on selectivity.

*Source data:* `qc/sci/phase4/final_hotspot_table.csv`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig6`

## F7 — H005 - unresolved cross-geometry contradiction

**H005 — unresolved cross-geometry contradiction.** Mean relative LOS rate by geometry. Units are mm yr⁻¹. *Sample definition:* common-domain pixels within the H005 polygon. The two geometries disagree in both sign and magnitude, so this is not a reproduction failure but an active contradiction. H005 is retained in the main text as an unresolved result. No explanation for the contradiction is offered, and none is claimed.

*Source data:* `qc/sci/phase4/final_hotspot_table.csv`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig7`

## F8 — Cumulative totals and the scope of independent reproduction

**Cumulative totals and the scope of independent reproduction.** (A) Retained total cumulative LOS displacement over the full stack by geometry; units are mm. **Per-epoch cumulative series were not retained in the frozen evidence set and are NOT reconstructed.** (B) Which characteristics are and are not independently reproduced. *Key limitation:* independent reproduction extends to the **spatial and mean-rate** characteristics only. The ascending and descending H001 cumulative series differ substantially (ascending −120.7 mm against descending +1.1 mm; detrended cross-geometry correlation r = 0.007). The descending series carries large opposing jumps.

*Source data:* `qc/sci/phase2c/hotspot_reconciliation.json`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig8`

## F9 — Groundwater temporal forcing - lag and falsification diagnostic

**Groundwater temporal forcing — lag and falsification diagnostic.** (A) Spearman ρ between the groundwater depth anomaly and the LOS series as a function of the lag applied to groundwater, per zone. Negative lags (grey field) are **falsification tests**, in which deformation leads groundwater; positive lags test the causal direction. (B) Mean |ρ| for forward against falsification lags. *Sample definition:* NWDP six-hourly depth-to-water telemetry, station-anomaly composited to daily medians; zones are H001, H004, H002 and H003 only — H005 has no groundwater composite and is absent. *Sign convention:* the protocol predicts a **negative** association (deeper groundwater → more negative LOS). *Significance:* circular block permutation, 90-day blocks; 0 of 16 forward-lag tests survive Benjamini–Hochberg FDR q = 0.05 (all permutation p ≥ 0.49). *Limitation:* this is **not** a refutation of groundwater as a mechanism. Aquifer metadata, well depths and screened intervals are unavailable, the H001 network has ~78-day outages and only two stations, and LOS is not vertical displacement.

*Source data:* `qc/sci/phase3/groundwater_lag_results.csv`, `qc/sci/phase3/groundwater_control_comparison.csv`

*Rendered by:* `scripts/72_phase5b_figures.py::fig9`

## F10 — Shallow substrate texture

**Shallow substrate texture — direction opposite to prediction.** Clay at 0–5 cm (A) and 100–200 cm (B), and sand at 0–5 cm (C), by zone. Units are % by mass. Dashed line is the AOI-minus-zones background. *Dataset:* SoilGrids v2.0 (ISRIC), 250 m, sampled on its native grid and never resampled to the 40 m InSAR grid. *Critical limitation:* this is a **shallow soil-texture surrogate**, not a geological map. It samples the upper ~2 m only and does not observe the compaction interval; lithology, formation and age are not identified. Deep geological / aquifer-system susceptibility is therefore **NOT ADEQUATELY TESTED**, not exonerated. H005 is shown for completeness and is not part of the supported/control contrast. The supported zones carry −5.0 percentage points less clay and +6.4 points more sand than the controls, opposite to the fine-sediment direction the hypothesis predicts.

*Source data:* `qc/sci/phase3/geology_hotspot_summary.csv`

*Rendered by:* `scripts/72_phase5b_figures.py::fig10`

## F11 — Built intensity

**Built intensity — a shared setting that does not discriminate.** (A) Built fraction from ESA WorldCover 2021; (B) built surface from JRC GHSL GHS-BUILT-S E2020. Dashed lines are AOI-minus-zones backgrounds. *Sample definition:* polygons rasterised onto each **source** grid (10 m and ~93 m); no coarse product was resampled to 40 m. All four classification zones are heavily built (70–79 %) against a 33.7 % AOI background. That is a genuine shared characteristic and precisely why it fails as an explanation: it **describes the common urban setting but does not separate the supported zones from the controls**. H001 and H002 rank differently between the two products, so the discriminator is not robust. *Limitation:* GHSL 2020→2025 built-up change is exactly zero at H001–H004, but post-2020 GHSL epochs are projections rather than observations, so this is an absence of detected change rather than a measured absence. No loading is estimated: height, footprint, construction type and foundation are unavailable.

*Source data:* `qc/sci/phase3/urban_hotspot_summary.csv`

*Rendered by:* `scripts/72_phase5b_figures.py::fig11`

## F12 — Competing-hypothesis evidence matrix

**Competing-hypothesis evidence matrix (frozen).** Evidence state assigned to each preregistered hypothesis. Swatches encode the category; the three categories are distinct and are never collapsed. **NO EVIDENCE** = a suitable test was conducted and did not support the hypothesis. **NOT ADEQUATELY TESTED** = available evidence does not observe the relevant physical domain. **NOT TESTABLE** = the necessary dataset was unavailable. None of these is equivalent to "ruled out", and no composite score is formed across rows. Grades are reproduced verbatim from the frozen evidence matrix.

*Source data:* `qc/sci/phase4/final_evidence_matrix.csv`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig12`

## S13. Data and code availability

# Data and Code Availability

## Code

All processing, validation, hypothesis-testing and synthesis scripts are in
`scripts/` (70 scripts, numbered by phase). Tests are in `tests/`.

## Processed products

| Product | Location | Freeze |
|---|---|---|
| Ascending authoritative relative LOS solution | `mintpy/baseline_raw_work/` | `product_v1` |
| Ascending published rasters | `products/product_v1/` | derived from `product_v1` |
| Descending raw solution | `mintpy/descending_work/` | `descending_raw_v1` |
| Descending unwrap-corrected candidate | `mintpy/descending_d2_unwrap_work/` | `descending_v2_candidate` |

## External datasets

| Dataset | Source | Access |
|---|---|---|
| Sentinel-1 SLC bursts | ASF / HyP3 | public, credentialed |
| ERA5 | Copernicus CDS | public, credentialed |
| CGWB seasonal groundwater | CGWB via Internet Archive | public; **archived copy of the official URL**, live host was down |
| NWDP six-hourly groundwater telemetry | nwdp.nwic.gov.in | public |
| SoilGrids v2.0 | ISRIC | public |
| GHSL GHS-BUILT-S | JRC | public |
| ESA WorldCover | ESA / AWS Open Data | public |

## Reproducibility notes

* Every freeze is hash-pinned and verified by a companion script.
* Large products are hashed in place rather than duplicated.
* The ascending product was frozen before any interpretation; hypothesis
  protocols were frozen before their correlations existed.

## Limitations on reuse

The published velocity fields are **relative LOS** quantities, not absolute
velocities and not vertical displacement. Users requiring absolute rates must
supply an independent reference; the reference-selection systematic is
4.78 mm/yr.
