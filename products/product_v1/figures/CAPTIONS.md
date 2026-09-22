# Figure captions — product_v1 visualization

Draft captions. Each distinguishes LOS from vertical, relative from absolute, formal from full uncertainty, and quality masking from deformation magnitude. No causal interpretation is offered.

Source freeze: `product_v1`, `2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37`.

## F01_relative_LOS_velocity

**Relative LOS velocity (mm/yr), frozen RAW-336 solution.** Sentinel-1 ascending relative orbit 27, IW2, 1991-2025. Values are mean relative line-of-sight velocity referenced to the actual processing reference pixel (row 1384, col 1451; 705780 E, 3169940 N). **These are LOS velocities, not vertical displacement rates**; no vertical conversion is applied or implied. The diverging scale is centred on zero so the sign of LOS motion is unambiguous. Display range ±20 mm/yr, chosen as the symmetric 99.5th percentile of |v| (21.9 mm/yr); 0.63 % of valid pixels exceed this and saturate. A full-range variant at ±90 mm/yr is available. Grey is NoData / excluded — it is not a deformation value. Published under the tier ≤ 2 quality convention (temporal coherence ≥ 0.80); the grey area therefore also contains lower-coherence pixels where signal may exist.

## F02_cumulative_LOS_displacement

**Cumulative relative LOS displacement (mm), 2021-10-06 to 2025-09-27.** Signed, zero-centred display. Relative to the processing reference pixel, not an absolute geodetic displacement. Display range ±80 mm (symmetric 99.5th percentile of |d| = 82.4 mm); an isolated extreme of −350.9 mm exists in the raster and saturates. Grey is NoData / excluded.

## F03_temporal_coherence

**MintPy temporal coherence** over the inverted network. Displayed on 0.80–1.00 because this published raster is pre-masked at the tier-2 boundary; a 0–1 scale would compress every retained value into its top fifth. This is the full range *of this product*, not a stretch to observed extremes. The dashed line marks coherence 0.90 (the tier-1 boundary). Coherence is a reliability measure, **not** a deformation magnitude, and low coherence does not imply the absence of signal — see the extended-field supplementary panel.

## F04_velocity_uncertainty

**Formal LOS velocity uncertainty (1σ, mm/yr)** from the MintPy inversion. This is the formal statistical fit uncertainty only. It **excludes** the reference-selection systematic (4.78 mm/yr), processing-branch sensitivity (0.52–1.04 mm/yr) and any absolute geodetic calibration error; the full error budget is substantially larger and is not representable as a single value. Sequential scale, 0–1.80 mm/yr.

## F05_quality_tiers

**Retained quality tier**, an ordered categorical product. Tier 1 ≥ 0.90 temporal coherence (highest support); tier 2 ≥ 0.80; tier 3 ≥ 0.70; tier 4 permissive / caution. Grey is tier 0 (excluded). A continuous colourbar is deliberately not used because the classes are ordinal, not numeric. Tiers 1 and 2 together (541,511 px, 7.7 % of the grid) are the mask under which the deformation rasters are published; tiers 3 and 4 are retained but excluded from them.

## F06_elevation_context

**Elevation (Copernicus DEM), context layer only.** This is not a deformation product and carries no deformation information. It is included to place the deformation zones in topographic context. Display range is the full valid range (146–254 m); no hillshade exaggeration is applied.

## F07_residual_phase

**Median residual phase (rad)** from the MintPy inversion. Measured distribution is strictly non-negative (min 0.0000, max 0.3054, 0 % below zero), so this is a magnitude, **not** a signed or cyclic quantity. A sequential encoding is therefore used; a cyclic palette would be misleading despite the radian units.

## F08_product_v1_overview

**product_v1 overview.** (a) relative LOS velocity; (b) temporal coherence; (c) formal LOS velocity uncertainty (1σ); (d) retained quality tier. Panels share the same extent and AOI outline. Each panel carries its own scale and is **not** normalised against the others. Velocity and uncertainty are different quantities and their colour ramps are not comparable to one another. Velocity is LOS-relative, not vertical.

## S01_temporal_coherence_extended

**Temporal coherence, extended field (supplementary).** Read from the frozen `temporalCoherence.h5` rather than the published masked raster, so that tiers 3 and 4 (0.70–0.80) are visible. The main product is masked at 0.80, and this panel exists so that the masked map is not misread as showing that lower-coherence regions contain no signal. Dashed lines mark the 0.70, 0.80 and 0.90 tier boundaries.

## S02_velocity_with_quality_tiers

**Relative LOS velocity with quality-tier overlay (supplementary).** The velocity field is shown with tier-boundary contours so that the relationship between measurement reliability and apparent deformation magnitude is visible. Phase I found a reproducible coherence–velocity association; it is shown here as an observational relationship and **no physical origin is inferred**. Velocity is LOS-relative, not vertical.

## Common note

All panels: EPSG:32643, 40 m pixels, NoData −9999 rendered as neutral grey. No smoothing, interpolation, resampling or reclassification was applied to any scientific raster. Grey indicates NoData or exclusion and **never** a scientific value, and is distinct from a zero value in the diverging ramps.

**Water masking.** HyP3 processing applied a water mask, so open water never enters the inversion and appears as excluded (grey). In the tier and coherence panels the Yamuna channel and several reservoirs therefore appear as thin linear or patchy grey / near-zero features threading through the data. These are genuine exclusions, not data gaps or processing artefacts. Against the dark low-coherence background they can read as bright lines by simultaneous contrast.

**Reference pixel.** Every deformation panel marks the actual processing reference at row 1384, col 1451 (705780 E, 3169940 N; 77.10523 E, 28.64023 N) with a star. This is *not* the originally intended reference (row 1378, col 1426), which the product does not use - see INC-007.

