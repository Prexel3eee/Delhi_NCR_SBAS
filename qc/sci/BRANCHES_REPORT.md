# Atmospheric and DEM-Residual Branch Report

Generated: 2026-09-22T09:02:27.508273+00:00

**No deformation product is declared.** Deramping is disabled in every branch.

## Frozen decisions

- freeze_id `137a1926488329355965c05becc192b4440625aa7ceed074045b00dbcda1a762`
- reference **yx [1378, 1426]** (lon 77.095, lat 28.6426)
- network **336 pairs**, curation: none - all pairs retained
- unwrap-error correction: **disabled**
- deramp: **disabled in the principal branch**

## ERA5 coverage gate

- acquisition dates expected: **119**
- ERA5 GRIB files present: **119** (0 missing, 0 undersized)
- delay dates match the accepted-acquisition manifest: **True**
- AOI finite fraction (minimum across all dates): **1.0**
- complete coverage: **True**

The gate is AOI-restricted. PyAPS leaves NaN outside the ERA5 interpolation
domain, so the *global* finite fraction is only 0.6358 - gating on that would reject a branch
that is in fact fully corrected where it matters (0 NaN inside the AOI).

## Correction to the first RAW-vs-ERA5 comparison

The first comparison reported a **15.49 mm/yr RMS** velocity difference. That
was wrong. It used MintPy's `velocityERA5.h5`, which is **not** the
ERA5-corrected velocity:

| file | FILE_PATH provenance | agreement with a direct fit to `timeseries_ERA5.h5` |
|---|---|---|
| `era5_work/velocity.h5` | `timeseries_ERA5.h5` | **0.0008 mm/yr** (correct) |
| `era5_work/velocityERA5.h5` | `inputs/ERA5.h5` (the delay file) | 3.72 mm/yr (not the corrected velocity) |

Products are now resolved by reading `FILE_PATH` metadata rather than by
guessing filename patterns. The corrected difference is **0.52 mm/yr RMS**.

The same class of mistake had already bitten this project once (assuming a
filename pattern made the DEM branch look identical to ERA5), which is why the
resolution is now provenance-based in both scripts.

## Branch comparison (AOI-restricted)

| branch | final timeseries | velocity median (m/yr) | coherence | residual RMS (rad) |
|---|---|---|---|---|
| RAW | `timeseries.h5` | -0.0042 | 0.7488 | 4.593 |
| ERA5 | `timeseries_ERA5.h5` | -0.0041 | 0.7470 | 4.67 |
| ERA5+DEM | `timeseries_ERA5_demErr.h5` | -0.0042 | 0.7470 | 4.6709 |

## Pairwise effects

| comparison | velocity median (mm/yr) | RMS (mm/yr) | max abs (mm/yr) | residual improved / worsened |
|---|---|---|---|---|
| ERA5 minus RAW | +0.01 | 0.52 | 5.08 | 140 / 196 |
| ERA5+DEM minus RAW | -0.05 | 1.04 | 5.03 | 131 / 205 |
| ERA5+DEM minus ERA5 | -0.10 | 0.78 | 3.47 | 142 / 194 |

## Interpretation

- **ERA5 changes the velocity field only slightly** (0.52 mm/yr RMS, max 5.1),
  and slightly **degrades** the fit: residual RMS rises from 4.593 to 4.670 rad,
  with 140 of 336 pairs improved and 196 worsened.
- **Pixel-wise DEM-residual correction adds a further 0.78 mm/yr RMS** change
  relative to ERA5 and a further 1.04 mm/yr relative to RAW; the fit again does
  not improve (4.670 -> 4.671 rad, 142 improved / 194 worsened).
- Neither correction is therefore shown to be beneficial for this stack. On an
  uncorrected baseline the per-interferogram residuals are dominated by
  unmodelled atmosphere and orbit ramps, so residual RMS is a blunt test - but it
  is the test the brief specifies, and it does not favour enabling either.
- ERA5 delays are physically sensible (AOI-median slant delay -3.44 to -2.95 m,
  median date-to-date step 42 mm, max 254 mm), so the corrections are real
  rather than numerical artefacts.

## Status

- Deramping **not** applied; it remains a sensitivity experiment only, because
  broad subsidence gradients may be genuine signal.
- **No final deformation product is declared.**
- Raw LOS velocity remains unreferenced to any external stability datum, and the
  reference choice carries a ~4.8 mm/yr systematic (see the RAW-336 report).

