# Correction Validation and v1 Product Freeze

Generated 2026-09-22 09:34 UTC.

**Principal candidate: `RAW-336`** — promoted: none. Corrections tested: ERA5 atmospheric delay, and ERA5 followed by pixel-wise DEM-residual estimation. Spatial deramping remains disabled in the principal branch.

## 1. Why residual RMS alone was not enough

On an uncorrected baseline the per-interferogram residuals are dominated by unmodelled atmosphere and orbit ramps, so raw residual RMS is a blunt discriminator: a correction can worsen it while still removing a real error. Four diagnostics better matched to the signature of atmospheric and DEM-residual error were used instead.

## 2. Targeted diagnostics

| Diagnostic | RAW | ERA5 | ERA5+DEM | Prefer |
|---|---:|---:|---:|---|
| A. Velocity high-pass energy (mm/yr) |  **2.967** |      2.986 |      3.001 | lower |
| B. Stable-area velocity median (mm/yr) |     -0.010 |     +0.165 |     +0.414 | closer to 0 |
| B. Stable-area robust scatter (mm/yr) |      1.794 |      1.865 |      2.123 | lower |
| C. \|Spearman(residual, elevation)\| |     0.1497 | **0.0332** |     0.0847 | lower |
| D. Per-pixel residual scatter (rad) | **9.0987** |     9.1703 |     9.1964 | lower |

The stable-area mask is defined from the RAW branch (temporal coherence >= 0.9, |velocity| <= 3.0 mm/yr, n = 256758 pixels) so it is identical across branches.

### Interpretation

* **ERA5 does what an atmospheric correction should.** The elevation-correlated residual falls from 0.1497 to 0.0332 — a 78% reduction, and the only diagnostic any correction wins. The error ERA5 targets is genuinely present in the RAW solution.
* **But it does not improve the product.** Removing it leaves the velocity field marginally rougher (2.967 -> 2.9864 mm/yr), the stable-area scatter slightly larger (1.7945 -> 1.8649 mm/yr), and the stable-area median displaced from -0.0101 to 0.1649 mm/yr — i.e. it introduces a small non-zero offset in areas that should read zero. The atmospheric component is real but not what limits this product.
* **The DEM-residual step is counterproductive.** It raises the elevation-correlated residual back to 0.0847 (worse than ERA5 alone) and is the worst branch on the other three diagnostics, including the largest stable-area offset (0.4143 mm/yr) and the largest scatter (2.1233 mm/yr).

The diagnostics favour smoother solutions, so a correction that removed real signal would also score well. The independent velocity-agreement check guards against that: neither correction is a large-magnitude change (ERA5-RAW RMS 0.521 mm/yr; ERA5+DEM-RAW RMS 1.036 mm/yr), so no branch is silently deleting a large deformation signal.

## 3. GNSS / CORS assessment

Outcome: **GNSS CANNOT DISCRIMINATE**.

* no station within 30 km has >= 30 daily solutions inside the study period (best: 14).
* in-AOI records either end before 2021-10-06 or hold only episodic daily solutions.
* co-located receivers disagree by up to 0.77 mm/yr (median 0.77), implying an achievable vertical-rate accuracy of only 0.54 mm/yr against a 1.04 mm/yr branch difference.
* the nearest station with dense in-period sampling is 210 km away, so its rate convolves the real spatial gradient of the Indo-Gangetic/Himalayan vertical field with any correction benefit.
* a point rate at that distance is not comparable to an AOI-mean InSAR rate.

The co-location test is the internally controlled one — it needs no external truth. The only qualifying pair, `LCK3`/`LCK4` (0.01 km apart, 745 shared epochs), agrees to -0.767 mm/yr once both are evaluated over the **same** time window. GNSS measurement quality is therefore not the limitation; station geometry is. Note that comparing each station's full record instead produces a spurious ~27 mm/yr difference, because the two records end in 2023-12 and 2026-09 respectively.

An earlier pass reported "GNSS REFERENCE AVAILABLE" from a stations-passing-a-threshold count. That is superseded: passing a solutions/span threshold is not the same as being able to discriminate a sub-mm/yr branch difference.

## 4. Frozen v1 product

`RAW-336` is frozen as the authoritative v1 deformation solution.

* Reference point: 28.6426, 77.095 (EPSG:32643), MintPy pixel `1378,1426`, inside the AOI.
* All 336 interferograms retained; no pair excluded.
* ERA5 atmospheric correction: tested, not beneficial — not applied.
* ERA5 + pixel-wise DEM-residual correction: tested, not beneficial — not applied.
* Network-based unwrap correction (bridge + phase closure): tested, degrades fit — disabled.
* Spatial deramping: disabled in the principal branch (broad subsidence gradients may be genuine signal); sensitivity experiment only.

The reference-point choice carries a documented systematic of 4.78 mm/yr (sd 1.72) among candidates selected without using velocity; relative spatial gradients are unaffected. See `qc/sci/reference_sensitivity.json`.

### Per-branch summary

| Branch | Velocity median (m/yr) | Temporal coherence | Residual RMS (rad) |
|---|---:|---:|---:|
| RAW | -0.004151 | 0.748842 | 4.593 |
| ERA5 | -0.004091 | 0.747026 | 4.67 |
| ERA5+DEM | -0.004172 | 0.747026 | 4.6709 |

## 5. Scope and open items

This is a v1 deformation solution, not a calibrated geodetic product. It is not corrected for tropospheric delay in the frozen branch, and its absolute reference carries the stated 4.78 mm/yr systematic. Validation against an independent in-AOI geodetic reference was not possible with the available GNSS data.
