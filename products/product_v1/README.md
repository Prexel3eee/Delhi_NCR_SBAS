# products/product_v1

Georeferenced rasters published from the frozen `product_v1` deformation solution
(RAW-336). These are **derived, regenerable** artefacts — the authoritative
inputs are the hash-pinned HDF5 products recorded in
`freeze/product_v1/FREEZE.json`. The `*.tif` files are not tracked by git
(see `.gitignore`); regenerate them with:

```bash
python scripts/31_deformation_map.py
```

## Files

| File | Units | Description |
|---|---|---|
| `los_velocity_mm_per_yr.tif` | mm/yr | LOS velocity, relative to the processing reference |
| `los_velocity_uncertainty_mm_per_yr.tif` | mm/yr | Formal 1-sigma from the inversion (not the full error budget) |
| `los_displacement_mm.tif` | mm | Cumulative LOS displacement, 2021-10-06 → 2025-09-27 |
| `temporal_coherence.tif` | 1 | MintPy temporal coherence |
| `los_residue_rad.tif` | rad | Median residual phase |
| `elevation_m.tif` | m | Copernicus DEM, context only |
| `quality_mask.tif` | tier code | 1 = coherence ≥ 0.90, 2 = ≥ 0.80, 3 = ≥ 0.70, 4 = permissive, 0 = excluded |

## Conventions

* **LOS, not vertical.** Sentinel-1 measures a projection of the full 3-D
  displacement. No vertical rate is published here.
* **Relative, not absolute.** Every value is relative to the processing reference
  pixel `(row 1384, col 1451)`. Spatial gradients are well determined; the
  absolute offset is uncertain at ~5 mm/yr (dominated by the 4.78 mm/yr
  reference-selection systematic).
* **Deformation rasters are masked to quality tier ≤ 2** (temporal coherence
  ≥ 0.80). `quality_mask.tif` carries the full tiering, including the
  lower-coherence pixels where much of the signal sits — see
  `qc/sci/PHASE1_REPORT.md` section 3.
* NoData is `-9999`.

## Provenance

* Source freeze: `product_v1`, `freeze_id 2a1304e3521f1e176fba7e05814ae1e79ba5332d4be709c16ee17c9aefdedf37`
* Grid: 2407 × 2939 @ 40 m, EPSG:32643
* Verify the source is untouched: `python scripts/verify_product_v1.py`

**INC-007:** the frozen decision names reference pixel `(1378, 1426)`, but the
product is actually referenced to `(1384, 1451)` because the RAW config never set
`mintpy.reference.yx`. The difference is a constant `+0.1362 mm/yr` on every
pixel, so all spatial gradients and hotspot contrasts are unaffected. See
`qc/sci/PHASE1_REPORT.md` section 0.1.
