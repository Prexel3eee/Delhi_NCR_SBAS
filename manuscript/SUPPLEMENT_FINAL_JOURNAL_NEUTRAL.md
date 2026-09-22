# Supplementary Material

## Part A — Methods

## S1. Study area and reference frame

AOI 1,962.4 km², EPSG:32643, 1.85 % water. All products on a common 40 m grid, 2,407 × 2,939 (ascending) and 2,412 × 2,853 (descending).

## S2. Burst selection and network design

K = 4 contiguous bursts per track, selected by the smallest collection fully containing the AOI (ascending) or containing every hotspot polygon (descending, which cannot cover the AOI's western strip). Networks were built by **identity intersection** across bursts — never a positional zip — with graph audits for connectivity, bridges, articulation points and minimum degree.

Ascending: 336 pairs, max 36 d. Descending: 219 pairs; the record carries two gaps longer than 36 d (108 d and 48 d), so the minimum set of extra pairs needed to connect the epochs and eliminate every bridge was added, each flagged. Result: 1 component, 0 bridges, 1 articulation point.

## S3. Processing

HyP3 `INSAR_ISCE_MULTI_BURST`, 10×2 looks, water mask applied. MintPy 1.6.4 with `weightFunc = var`, `minNormVelocity = yes`, `keepMinSpanTree = no` (MintPy defaults it to yes and would silently drop pairs).

## S4. Correction testing

ERA5 and ERA5+DEM were tested against RAW on four diagnostics better matched to atmospheric error than residual RMS; neither improved the product. Unwrap correction was rejected for ascending. For descending it was **required**: it improved 7 of 7 internal metrics. The difference is itself informative — the two products have different failure modes.

## S5. Quality tiers and validity

Validity is `velocityStd > 0`, **not** `isfinite(velocity)`: MintPy fills the non-inverted region with zeros, so a finiteness test overstates coverage. Descending covers 69.7 % of the AOI.

## S6. Groundwater protocol

Frozen before any correlation (`groundwater_protocol_v1`). Daily medians requiring ≥ 2 valid six-hourly observations; no interpolation. Sign convention: positive anomaly = deeper than the station median. Lags fixed at 0/+30/+60/+90 d with −30/−60/−90 d as falsification. Significance by **circular block permutation with 90-day blocks, 5,000 iterations** — never IID p-values — with Benjamini–Hochberg FDR q = 0.05 across the 16 hotspot-composite tests.

## S7. Geological and urban datasets

SoilGrids read by windowed remote access on its native grid; all polygons rasterised onto the **source** grid, never resampled onto the InSAR grid. Urban statistics likewise computed on native GHSL and WorldCover grids.

## S8. Uncertainty policy

Measurement, reference-systematic, processing-sensitivity and non-stationarity terms are reported **separately and never summed**. They are different kinds of quantity; no valid probabilistic model justifies combining them.


---

## Part B — Reproducibility appendix

Only incidents that could have altered a scientific conclusion are retained. Each is given as problem, potential scientific consequence, detection, correction, and regression protection. Routine implementation failures are excluded.

### INC-005

**Problem.** the first RAW-versus-ERA5 comparison read the uncorrected velocity dataset instead of the corrected one (MintPy FILE_PATH resolves to inputs/ERA5.h5, not velocityERA5.h5)

**Potential scientific consequence.** produced a spurious 15.49 mm/yr difference and would have caused ERA5 to be accepted as beneficial

**Detection.** the reported difference was implausibly large against the known atmospheric magnitude; the file path was audited

**Correction.** corrected comparison gives 0.52 mm/yr RMS; ERA5 and ERA5+DEM were both then judged non-beneficial and left disabled

**Regression protection.** tests/test_correction_validation.py pins the corrected values and the disabled-branch configuration

### INC-006

**Problem.** GNSS co-location appeared to show a ~27 mm/yr disagreement with the InSAR rate

**Potential scientific consequence.** would have implied the InSAR product was substantially biased and undermined the reference choice

**Detection.** the two station series had different end epochs (2023-12 and 2026-09), so the comparison window was not shared

**Correction.** on 745 shared epochs the two agree to 0.767 mm/yr. The conclusion survived but for the correct reason: station coverage, not measurement quality

**Regression protection.** epoch-overlap is required before any station comparison

### INC-007

**Problem.** the frozen ascending configuration did not set reference.yx, so MintPy auto-selected (1384,1451) rather than the intended (1378,1426)

**Potential scientific consequence.** a constant offset of +0.1362 mm/yr in the absolute zero level of the published product

**Detection.** references were audited against the frozen scientific decision record; the two pixels are 1028.4 m apart

**Correction.** documented as an append-only erratum. Branch RMS moved 0.521 to 0.549; no verdict changed. Spatial gradients are invariant to the choice

**Regression protection.** config/mintpy_baseline_raw.txt now sets reference.yx explicitly

### INC-008

**Problem.** the Phase-I hotspot geojson contained single-pixel fragments because scripts/32_hotspots.py broke after the first polygon returned by rasterio.features.shapes

**Potential scientific consequence.** EVERY polygon-based containment and overlap test in Phase II was vacuous - the descending burst-selection containment check and the gate-2 check both passed trivially

**Detection.** a downstream containment test returned implausible per-pixel counts, prompting an audit of the polygon source

**Correction.** qc/sci/phase1/hotspots_corrected.geojson; the frozen CSV was reproduced exactly, and the containment conclusion HOLDS once re-tested on correct geometry

**Regression protection.** scripts/51_fix_hotspot_polygons.py reproduces the corrected geometry and verifies polygon area against pixel area

### INC-009

**Problem.** the independently supported mapped area was published as 3.17 km2 in Phase III-A, Phase IV and the Phase V manuscript

**Potential scientific consequence.** a published area that disagreed with the frozen zone geometry by a factor of 2.1

**Detection.** Phase V-B numerical consistency gate traced the value to no script, table or intermediate artefact

**Correction.** corrected to 6.66 km2 (H001 + H004 from the frozen zone areas), matching the authoritative Phase II-C reconciliation. No conclusion changes; the corrected value is larger

**Regression protection.** scripts/75_phase5b_audit.py asserts that the supported area equals the sum of the frozen zone areas and that every area-like value traces to a frozen source

### INC-002

**Problem.** a transient ASF DNS outage terminated product retrieval at 47 of 336 interferograms

**Potential scientific consequence.** the ascending stack would have been silently incomplete

**Detection.** retrieval count did not reconcile against the frozen network manifest

**Correction.** retrieval made resumable with backoff and single-call batched job listing; all 336 recovered

**Regression protection.** tests/test_production_retrieval.py asserts full reconciliation before any downstream step

### INC-001

**Problem.** ASF find_jobs(name=...) performs an exact match, not a prefix match, so a prefix query returned nothing

**Potential scientific consequence.** seven duplicate pilot jobs were submitted, and an unchecked prefix query could silently mis-report job state during a large submission

**Detection.** credit delta (70) did not match the expected count for the intended job set

**Correction.** all job reconciliation now uses exact-name matching against a local manifest

**Regression protection.** tests/test_asf_client_regressions.py asserts that prefix queries are never issued

### Verification

```text
python scripts/75_phase5b_audit.py
python scripts/74_phase5b_provenance.py --verify
python scripts/70_phase5_manuscript.py --verify
python scripts/verify_freeze.py
python scripts/verify_mintpy_input_v1.py
python scripts/verify_product_v1.py
python scripts/verify_phase1_observations.py
```

All exit 0 against the frozen state.

---

## Part C — Figure captions



Each caption is self-contained: geometry/branch, units, quality mask, sample definition, uncertainty meaning, exclusions and limitations are stated where relevant. No caption contains a causal interpretation.

## F1 — Study design and independent acquisition geometry

**Study design and independent acquisition geometry.** (A) Frozen coverage geometry for the Delhi-NCR study area (1,962.4 km², EPSG:32643). Blue denotes the four ascending burst footprints (relative orbit 27, IW2); orange denotes the four descending footprints (relative orbit 136, IW1); black is the AOI boundary. The red hatched area is the 28.0 % of the AOI not covered by the descending track — a western strip containing no classification zone. White circles mark the five zones (H001–H005), which are small relative to the AOI. (B) Stack composition. The two stacks share no burst, interferogram, mask or acquisition list; no pair was selected because it intersected a zone. *Limitation:* descending coverage is partial, so the descending geometry cannot validate the entire ascending field.

*Source data:* `geometry/aoi.geojson`, `geometry/selected_bursts.geojson`, `geometry/descending/selected_bursts.geojson`, `geometry/descending/coverage_report.json`, `qc/sci/phase1/hotspots_corrected.geojson`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig1`

## F2 — Ascending relative LOS velocity

**Ascending relative LOS velocity field (authoritative product, RAW-336).** (A) Mean relative line-of-sight velocity, all 336 interferograms retained, no pair excluded. Units are mm yr⁻¹. Warm colours indicate motion toward the satellite; blue indicates motion away. (B) Distribution of the same field on a log count scale; dashed line is the median. *Quality mask:* water-masked; non-inverted pixels excluded (validity defined by velocityStd > 0, not by finiteness, because MintPy fills the non-inverted region with zeros). *Uncertainty:* values are **relative** LOS rates, not vertical displacement. The reference pixel carries a **4.78 mm yr⁻¹ systematic** that offsets the absolute zero level; spatial gradients are invariant to it. Formal measurement uncertainty is 0.87 mm yr⁻¹; these terms are not combined.

*Source data:* `products/product_v1/los_velocity_mm_per_yr.tif`

*Rendered by:* `scripts/73_phase5b_restyle.py::fig2`

## F3 — Cross-geometry classification of the five zones

**Cross-geometry classification of the five zones.** Grouped mean relative LOS rates by zone and viewing geometry: ascending (solid blue) and descending (hatched orange). Units are mm yr⁻¹. The strip beneath the axis encodes the frozen cross-geometry status. *Sample definition:* mean rate over each zone's common-domain pixels (854,246 px). *Branches:* ascending = RAW-336; descending = unwrap-corrected candidate. *Limitation:* ascending and descending are separate LOS geometries and are never converted to vertical displacement here. H001/H004 are independently supported at the spatial and mean-rate level; H002/H003 are not reproduced; H005 is a cross-geometry contradiction.

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


