# Publication-grade visualization — `product_v1`

**Status:** complete.
**Source:** `products/product_v1/` (frozen `product_v1`, `2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37`)

```text
SCIENTIFIC VALUES MODIFIED = NO
SOURCE PRODUCT MODIFIED    = NO
VISUALIZATION ONLY         = YES
```

---

## 1. Approach

The rasters were treated as read-only scientific data under a cartographic
design layer. Nothing was smoothed, interpolated, resampled, reclassified,
histogram-equalised or normalised per panel; `imshow` runs with
`interpolation="nearest"`. Display ranges are *view* parameters only — they
change what is visible, never what is stored — and every one is recorded in
`VISUALIZATION_SCALE_REPORT.json` with its selection rule.

Design decisions were driven by data semantics rather than by palette
preference:

| Semantic | Encoding chosen | Why |
|---|---|---|
| signed (velocity, displacement) | diverging, symmetric about zero | sign is physical; zero must be locatable |
| magnitude (coherence, uncertainty, residual) | sequential, monotonic lightness | ordering is the message; must survive greyscale |
| ordered categorical (quality tier) | discrete ordinal ramp + neutral grey | classes are ordinal, not numeric |
| terrain (elevation) | hypsometric sequential | context only; must stay subordinate |

Palettes come from **cmcrameri** (Crameri et al.) and **cmocean** (Thyng et
al.) — perceptually uniform and colour-vision-deficiency-aware. `jet`/rainbow
was rejected: it is non-uniform in perceptual space and fabricates apparent
structure at its luminance steps.

Family consistency is enforced through `config/visualization_v1.yaml` (one
typography scale, one layout, one AOI/reference/scale-bar treatment, one
export policy) rather than per-figure styling.

---

## 2. Palette rationale per raster

| Raster | Palette | Type | Rationale |
|---|---|---|---|
| `los_velocity_mm_per_yr` | `vik` | diverging | light neutral centre makes zero identifiable; symmetric ends keep both signs equally legible |
| `los_displacement_mm` | `vik` | diverging | same physical quantity family as velocity, so the same ramp; consistent reading across the family |
| `temporal_coherence` | `batlow` | sequential | monotonic lightness; reliability reads as "how much colour" |
| `los_velocity_uncertainty_mm_per_yr` | `amp` | sequential | deliberately a different sequential family from coherence so uncertainty is never confused with reliability |
| `los_residue_rad` | `dense` | sequential | third sequential family; positive-only magnitude |
| `elevation_m` | `topo` | hypsometric | terrain-aware; river plain to Aravalli ridge reads naturally |
| `quality_mask` | discrete Blues + grey | ordered categorical | 4 ordinal classes; grey reserved for excluded |

Hotspot outlines use a white under-stroke plus a thin dark stroke rather than a
single colour, because the polygons sit on both dark (low-velocity) and light
(near-zero) data and a single stroke disappears against one or the other.

---

## 3. Display ranges

Full detail, including measured percentiles and the selection rule, is in
`VISUALIZATION_SCALE_REPORT.json`.

| Raster | Displayed | Actual range | Rule |
|---|---|---|---|
| velocity | −20 … +20 mm/yr | −87.39 … +25.86 | symmetric at ⌈p99.5\|v\|⌉; clips 0.63 % |
| displacement | −80 … +80 mm | −350.9 … +88.21 | symmetric at ⌈p99.5\|d\|⌉; clips 0.52 % |
| coherence | 0.80 … 1.00 | 0.800 … 1.000 | full range *of this product* (pre-masked at 0.80) |
| uncertainty | 0 … 1.80 mm/yr | 0 … 2.241 | contains p99.5 = 1.61 with headroom |
| residual | 0 … 0.25 rad | 0 … 0.3054 | contains p99 = 0.210 with headroom |
| elevation | 146 … 254 m | 146 … 254 | full valid range; context layer |
| quality tier | classes 1–4 + excluded | 1,203,788 px | categorical; no numeric range |

A second velocity variant at the **full range ±90 mm/yr** is provided
(`F01b`) so nothing is hidden by the robust scale.

---

## 4. Outputs

| Item | Path |
|---|---|
| Quicklooks (7 PNG, 150 dpi) | `products/product_v1/quicklooks/` |
| Publication figures (18 PNG @ 600 dpi + 18 PDF) | `products/product_v1/figures/` |
| Overview multi-panel | `products/product_v1/figures/F08_product_v1_overview.{png,pdf}` |
| Scale report | `products/product_v1/figures/VISUALIZATION_SCALE_REPORT.json` |
| Captions | `products/product_v1/figures/CAPTIONS.md` |
| Output hashes | `products/product_v1/figures/OUTPUT_HASHES.json` |
| Config | `config/visualization_v1.yaml` |
| Generator | `scripts/visualize_product_v1.py` |

**Main figures:** `F01` relative LOS velocity · `F02` cumulative LOS
displacement · `F03` temporal coherence · `F04` velocity uncertainty · `F05`
quality tiers · `F06` elevation context · `F07` residual phase · `F08`
overview.

**Variants:** `_hotspots` suffix on every main figure (zone outlines overlaid,
never baked into the base raster) · `F01b` full-range velocity · `S01`
extended coherence · `S02` velocity with quality-tier annotation.

---

## 5. Rasters whose distribution or semantics make conventional visualization misleading

These are the cases a reviewer should know about. All are handled in the
figures and captions, but the underlying hazard remains.

1. **`quality_mask.tif` is not a mask.** It is a five-class ordinal quality
   product, and its NoData value (0) *is* tier 0 by construction. A
   conventional binary rendering — the obvious default given the filename —
   would discard the entire tier hierarchy and would present tier 0 as
   "missing" rather than "excluded". Rendered here as ordered categorical with
   an explicit legend and no continuous colourbar.

2. **`temporal_coherence.tif` cannot be shown on 0–1.** The published raster is
   pre-masked at the tier-2 boundary, so 0–1 would compress every retained
   value into the top fifth of the ramp and imply that the whole AOI sits at
   high coherence. Displayed at 0.80–1.00, which is the honest full range *of
   this product*. Because that in turn risks implying lower-coherence regions
   contain no signal, `S01` shows the extended field read from the frozen
   `temporalCoherence.h5`, masked to the AOI: **44.9 % of the AOI has
   coherence < 0.70** and 44.2 % is ≥ 0.80.

3. **`los_residue_rad.tif` has radian units but is not cyclic.** The statistic
   is a non-negative median magnitude (measured min 0.0000, max 0.3054, 0 %
   below zero). A cyclic palette — the conventional choice for phase — would
   be actively wrong here because it would imply wraparound that does not
   exist. Sequential encoding used.

4. **`los_displacement_mm.tif` is dominated by one extreme.** Single-pixel
   \|max\| is 350.9 mm against p99.5 of 82.4 mm. Full-range rendering would
   make the entire deformation field visually flat.

5. **`los_velocity_mm_per_yr.tif` likewise.** \|max\| 87.4 mm/yr against p99.5
   of 21.9. Same failure mode; both are provided at full range as variants.

6. **The 7.7 % figure is a mask artefact, not a data-quality signal.** The
   deformation rasters are valid over 7.7 % of the *grid* but **44.2 % of the
   AOI** — the rest of the grid lies outside the study area entirely. A reader
   seeing the sparse-looking map could reasonably misjudge the data coverage.
   Stated explicitly in the captions.

7. **Elevation has a narrow range over a wide AOI.** 146–254 m across ~120 km.
   Small changes in ramp choice visually exaggerate relief, so no hillshade or
   3-D styling is applied; the layer is kept deliberately subordinate to the
   deformation maps.

8. **Water-masked features can read as bright lines.** The Yamuna channel and
   several reservoirs appear as excluded (grey) or near-zero-coherence
   features. Against the dark low-coherence background they read as *bright*
   by simultaneous contrast, which can suggest a data artefact. They are
   genuine exclusions and are noted in the captions.

---

## 6. Expert-review checklist (Section 18)

| Question | Answer |
|---|---|
| Can zero be identified immediately? | yes — diverging ramps are symmetric with a light neutral centre |
| Can positive/negative LOS be distinguished? | yes — and without relying on red/green discrimination |
| Are extreme values dominating the scale? | no — robust ranges clip ≤ 0.63 %; full-range variants provided |
| Are low-quality regions clearly identifiable? | yes — F05 ordered categorical, plus `S01` extended field |
| Does NoData look different from zero? | yes — NoData is neutral grey `#D6D6D6`; ramp centre is near-white |
| Is uncertainty visually distinguishable from deformation? | yes — different quantity, different ramp family, separate figure |
| Does the quality-tier hierarchy read intuitively? | yes — dark = strongest support, light = permissive, grey = excluded |
| Are labels truthful? | yes — "relative LOS", never "vertical" or "subsidence" |
| Would a reader mistake LOS for vertical motion? | mitigated — stated on every deformation caption |
| Would a reader mistake relative for absolute? | mitigated — reference pixel marked and stated |
| Can it be understood when printed / at half-page? | yes — monotonic-lightness ramps, 7 pt base type, ≥ 0.4 pt strokes |

**Defects found and fixed during this review** (presentation only, no
scientific pattern altered):

- `imshow` was initially rendered in pixel-index space against axes limits in
  UTM metres, placing the raster off-screen. Every panel showed only the
  NoData facecolour. Fixed by supplying the projected extent from the raster
  transform.
- Tier-boundary contours degenerated into dense black speckle over a noisy
  field, obscuring the data they were meant to annotate. Moved to dashed marks
  on the colourbar.
- `S01` initially showed `temporalCoherence.h5` across the whole bounding box,
  including area outside the study boundary. Now masked to the AOI.
- Hotspot labels collided for the close pairs H001/H004 and H002/H003, and
  single-stroke outlines vanished against dark data. Fixed with spread leader
  labels and a white halo.
- Internal jargon ("robust scale", "product_v1", "RAW-336") leaked into figure
  titles; replaced with descriptive layer names.

---

## 7. Correspondence to the scientific record

These figures visualize the frozen product. They do **not** re-derive,
re-interpret or extend it.

- Velocity and displacement are **relative LOS** quantities, not vertical
  displacement and not absolute geodetic rates.
- Uncertainty shown is the **formal inversion uncertainty only**; it excludes
  the reference systematic (4.78 mm/yr), branch sensitivity (0.52–1.04 mm/yr)
  and calibration error.
- The reference pixel marked is the **actual** processing reference
  (row 1384, col 1451), not the originally intended (row 1378, col 1426) —
  see INC-007.
- No causal interpretation is attached to any panel. The coherence–velocity
  association visible in `S02` is an observational relationship whose physical
  origin is unresolved.
