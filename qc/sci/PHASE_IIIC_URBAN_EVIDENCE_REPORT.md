# Phase III-C — Urbanisation / Built-Environment Evidence Test

Generated 2026-09-22 18:46 UTC.

**Result: NO EVIDENCE overall.** Urbanisation describes the *shared setting* of all four hotspots but does **not** explain why H001/H004 reproduce and H002/H003 do not. There was **zero** built-up expansion at any of the four zones over the only interval that overlaps the study period, and the construction test could not be run at all.

No loading-induced deformation is claimed, and `PROVEN` / `CAUSE` / `CAUSED BY` are not used.

## A. Dataset inventory

| Dataset | Source | Native res. | Period | Tests |
|---|---|---|---|---|
| GHSL GHS-BUILT-S E2020 (built-up surface) | JRC GHSL R2023A | 3 arc-sec (~93 m) | epoch 2020 | U1 (2020) and U2 (2020->2025 change) |
| GHSL GHS-BUILT-S E2025 (built-up surface) | JRC GHSL R2023A | 3 arc-sec (~93 m) | epoch 2025 | U1 (2020) and U2 (2020->2025 change) |
| ESA WorldCover 2020 (land cover, 10 m) | ESA / AWS Open Data | 0.3 arc-sec (~9 m) | year 2020 | U1 cross-check |
| ESA WorldCover 2021 (land cover, 10 m) | ESA / AWS Open Data | 0.3 arc-sec (~9 m) | year 2021 | U1 cross-check |
| Major infrastructure / construction footprints | no authoritative machine-readable source obtained | — | — | **NOT OBTAINED** |

## B. Resolution and temporal compatibility

* **GHSL GHS-BUILT-S** — 3 arc-second (~93 m). Epochs 2020 and 2025.
* **ESA WorldCover** — 10 m. Years 2020 and 2021, both **before** the study interval.

**A caveat that materially weakens U2.** In GHSL R2023A the epochs from 2025 onward are **projections, not observations** (the observed series ends at 2020). The 2020→2025 difference is therefore not a measurement of realised urban change, and any U2 result must be read with that in mind.

All area statistics were computed by rasterising each polygon **onto the source grid**; no coarse product was resampled onto the 40 m InSAR grid to manufacture false precision.

## C. U1 — existing built intensity

| Hotspot | Role | GHSL E2020 (m²/cell) | WorldCover 2021 built % | core | buffered |
|---|---|---:|---:|---:|---:|
| **H001** | supported | 2896.0 | 70.57 | 3664.0 | 1662.0 |
| **H002** | negative control | 2563.0 | 73.69 | n/a | 1370.0 |
| **H003** | negative control | 2094.5 | 69.99 | n/a | 505.0 |
| **H004** | supported | 3143.0 | 79.02 | 3763.0 | 1302.0 |
| **H005** | excluded | 1554.0 | 52.38 | n/a | 297.5 |
| _background_ | AOI minus hotspots | 225.0 | 33.74 | | |

**Every hotspot is heavily built: 70–79 % on WorldCover against a 33.7 % AOI background.** That is a genuine and strong shared characteristic — and it is exactly why it fails as an explanation. The protocol states the rule directly: if all four hotspots are similarly urbanised, urbanisation may describe their setting but does not explain geodetic selectivity.

The two datasets also **disagree about H001**. On WorldCover, H001 (70.6 %) sits *below* H002 (73.7 %); on GHSL it sits *above*. A difference that flips sign between two independent products is not a robust discriminator.

## D. U2 — recent built-up expansion

| Hotspot | Role | GHSL change 2020→2025 | % change |
|---|---|---:|---:|
| **H001** | supported | 0.00 | 0.00 |
| **H002** | negative control | 0.00 | 0.00 |
| **H003** | negative control | 0.00 | 0.00 |
| **H004** | supported | 0.00 | 0.00 |
| **H005** | excluded | 14.00 | 0.90 |

**Zero change at all four hotspots.** H005 is the only zone with any increase (+14.0 m²/cell, 0.9 %), and H005 is excluded from hypothesis testing. Combined with the projection caveat above, U2 is a clean null: there is no evidence that the supported zones experienced more land conversion during the study period than the controls — because none of them experienced any measurable conversion in this product.

## E. U3 — major infrastructure / construction

**NOT TESTABLE.** No authoritative machine-readable construction dataset with documented geometry and dates was obtained. Per protocol, proximity alone is not causal evidence, and manually curating projects near H001/H004 while not applying the same search around the controls is forbidden. Recorded as **NOT TESTABLE**, not as a negative finding — the distinction matters, since an untested hypothesis and a refuted one are not the same thing.

## F–G. Positive zones and negative controls

| Comparison | Supported (H001/H004) | Control (H002/H003) | Difference |
|---|---:|---:|---:|
| ghsl_2020 | 3019.5 | 2328.75 | **+690.75** |
| ghsl_2025 | 3019.5 | 2328.75 | **+690.75** |
| wc_builtfrac_2021 | 74.79 | 71.84 | **+2.95** |
| ghsl_change | 0.0 | 0.0 | **+0.0** |

The separations are small in absolute terms (+2.95 percentage points on WorldCover built fraction, i.e. all four zones are in the same heavily built class), and the GHSL difference is partly driven by H003 being the least built of the four. Neither is a discriminating contrast.

## H. Coherence confounding

| Hotspot | Role | temporal coherence | built % | velocity uncertainty |
|---|---|---:|---:|---:|
| H001 | supported | 0.9255 | 70.57 | 0.9594 |
| H002 | negative control | 0.8634 | 73.69 | 1.2768 |
| H003 | negative control | 0.8604 | 69.99 | 1.2506 |
| H004 | supported | 0.9630 | 79.02 | 0.7268 |
| H005 | excluded | 0.8653 | 52.38 | 1.4038 |

**Spearman(built %, temporal coherence) = +0.500.** Higher built fraction accompanies *higher* coherence here — the opposite sign to the clay case in Phase III-B, but confounding all the same: the supported zones are again the higher-coherence ones, so built fraction and measurement quality covary and neither can be credited from these four values.

## I. Core / boundary sensitivity

Core-shrink and outward-buffer variants were computed for GHSL. The core values exceed the full-polygon values at H001 (3664 vs 2896) and H004 (3763 vs 3143), so built intensity is higher at the centres — but the same is true for the controls where computable, so the ordering is not changed and no claim depends on the boundary choice.

## J. Evidence grades

```text
U1  EXISTING BUILT INTENSITY ........ NO EVIDENCE
U2  RECENT BUILT-UP EXPANSION ....... NO EVIDENCE
U3  MAJOR INFRASTRUCTURE ............ NOT TESTABLE

OVERALL URBAN / BUILT-ENVIRONMENT ... NO EVIDENCE
```

## K. Strongest supporting evidence

The four hotspots are **strongly and consistently built** (70–79 %) against a 33.7 % AOI background, and the built intensity is higher in the hotspot cores than in their buffers. That establishes a real shared setting.

## L. Strongest counter-evidence

1. **Shared, not selective.** All four zones are in the same heavily built class, so built intensity cannot separate the zones that reproduce from those that do not.
2. **The datasets disagree on H001** — the ranking flips between WorldCover and GHSL.
3. **Zero measured built-up change** at all four zones over the study interval.
4. **The GHSL 2025 epoch is a projection, not an observation.**
5. **Confounded with coherence** (ρ = +0.500).

## M. Untestable components

* **U3 major infrastructure / construction** — no authoritative dated dataset.
* **Temporal association** (protocol §12): no dataset with sufficient temporal resolution was obtained, so urbanisation **cannot** be tested against the H001/H004 non-stationarity, the split-half rate changes, or any seasonal behaviour. That is recorded as **NOT TESTABLE**. No temporal history was fabricated from static spatial products.
* **Night-time lights** were not acquired, so no secondary built-intensity proxy is available.
* **Building height, footprint, construction type and foundation** were not obtained, so **no loading calculation** was attempted — the protocol forbids estimating structural load from footprints or built-up fraction.

## N. Conclusions permitted

* The supported deformation zones sit in **densely built terrain**, as do the two non-reproduced controls. Built environment is a **shared setting**, not a discriminator.
* Built-up **expansion** during the study period is **not** supported as an explanation: no measurable conversion occurred at any of the four zones in the available product.
* No built-environment variable distinguishes H001/H004 from H002/H003 at a level that survives the dataset disagreement and the coherence confounding.

## O. Conclusions not permitted

* **No loading-induced deformation claim.** No building mass, height, foundation or construction-timing data exist here, so `BUILT-ENVIRONMENT ASSOCIATION` is the strongest permitted framing — and even that is not supported.
* **No construction or urbanisation causation.**
* **No temporal claim** — the non-stationarity remains unexplained by any urban dataset obtained.
* **No combination with the weak groundwater and geology results into a composite causal story.** Per protocol §17, weak variables are not summed into a stronger narrative.

## Figures

* `qc/sci/phase3/figures/UC01_built_intensity.png`
* `qc/sci/phase3/figures/UC02_coherence_confounding.png`

No causal arrows. Machine-readable source data in `qc/sci/phase3/`.

## Stopping point

Stopped after the evidence grades, as instructed. No final causal narrative has been written. The urban/built-environment hypothesis is graded NO EVIDENCE, with U3 recorded as NOT TESTABLE rather than negative.
