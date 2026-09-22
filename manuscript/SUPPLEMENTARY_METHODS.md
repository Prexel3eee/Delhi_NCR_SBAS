# Supplementary Methods

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
