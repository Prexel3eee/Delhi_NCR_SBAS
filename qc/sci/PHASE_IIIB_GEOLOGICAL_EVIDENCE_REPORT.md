# Phase III-B — Geological / Geomorphological Susceptibility Test

Generated 2026-09-22 18:38 UTC.

**Result: NO EVIDENCE — and the observable difference runs *opposite* to the susceptibility hypothesis.** The supported zones sit on **coarser** material (more sand, less clay) than both the controls and the background, where the hypothesis predicts finer, more compressible sediment. The difference is additionally **confounded with measurement quality**.

No geological causation is declared. `PROVEN`, `CAUSE` and `CAUSED BY` are not used.

## 1. Datasets obtained — and the one that matters most was not

| Source | Property | Scale | Status |
|---|---|---|---|
| ISRIC SoilGrids v2.0 | clay, sand, silt at 0–5 cm and 100–200 cm | 250 m | **OBTAINED** (6 layers, windowed remote read) |
| GSI **Bhukosh** | surface geology / lithology | — | **NOT OBTAINED** — unreachable (curl 000) |
| NRSC / Bhuvan | geomorphology | — | **NOT OBTAINED** — no downloadable layer located |

**The authoritative Indian lithological source is unavailable.** SoilGrids is a *soil-property* product, not a geological map: it carries no formation, age or lithostratigraphic information. Every statement below is therefore about **soil texture as a substrate surrogate**, and none is about lithology. Full provenance in `GEOLOGY_DATASET_REGISTRY.csv`.

**A second, harder limitation.** SoilGrids samples only the **top 2 m**. The compressible aquifer-system unit relevant to compaction lies far deeper — typically tens to hundreds of metres. The product therefore does not sample the interval the hypothesis is actually about. This alone prevents a decisive test.

## 2. Scale compatibility

SoilGrids pixel = **250 m**. The largest hotspot (H002, 12.83 km²) spans ~205 pixels; the smallest (H005, 0.84 km²) spans ~13. Hotspot-level summaries are defensible; **within-hotspot gradients are not**, because a small hotspot is comparable to the product's own reported accuracy. No sub-hotspot gradient claim is made anywhere below.

## 3. Substrate summaries

| Hotspot | Role | clay 0–5 cm (%) | silt 0–5 cm | sand 0–5 cm | clay 100–200 cm | clay (core) | clay (buffered) |
|---|---|---:|---:|---:|---:|---:|---:|
| **H001** | supported | 17.40 | 31.65 | 50.85 | 18.60 | 17.30 | 18.65 |
| **H002** | negative control | 23.00 | 34.10 | 43.55 | 23.50 | n/a | 23.30 |
| **H003** | negative control | 24.10 | 33.80 | 43.20 | 23.80 | n/a | 23.90 |
| **H004** | supported | 19.70 | 31.80 | 48.70 | 19.40 | n/a | 19.65 |
| **H005** | excluded | 24.20 | 35.40 | 40.40 | 25.80 | n/a | 24.10 |
| _background_ | AOI minus all hotspots | 22.76 | 33.32 | 43.92 | 24.64 | | |

Boundary uncertainty was tested by shrinking the polygon to its core and buffering it outward. The ordering is unchanged in every case — the result is not a boundary artefact.

## 4. Specificity test — the direction is wrong

| Property | Supported (H001/H004) | Control (H002/H003) | Background | Supported − Control | Separation / background 5–95 range |
|---|---:|---:|---:|---:|---:|
| clay_0-5cm | 18.55 | 23.55 | 22.80 | **-5.00** | 0.649 |
| silt_0-5cm | 31.73 | 33.95 | 33.70 | **-2.23** | 0.337 |
| sand_0-5cm | 49.78 | 43.38 | 43.60 | **+6.40** | 0.577 |
| clay_100-200cm | 19.00 | 23.65 | 24.90 | **-4.65** | 0.567 |

The supported zones carry **−5.0 percentage points less clay** and **+6.4 points more sand** than the controls, and sit closer to the background in silt. The susceptibility hypothesis predicts the deforming zones should sit on *finer, more compressible* material. **They sit on coarser material instead.**

Note also that all five zones lie on the same broad Indo-Gangetic alluvial plain at 164–179 m elevation. Regionally the substrate is uniform; the differences above are second-order texture contrasts within one depositional setting.

## 5. Coherence confounding — and it is severe

| Hotspot | Role | median temporal coherence | median velocityStd (mm/yr) | clay 0–5 cm (%) |
|---|---|---:|---:|---:|
| H001 | supported | 0.9255 | 0.9594 | 17.40 |
| H002 | negative control | 0.8634 | 1.2768 | 23.00 |
| H003 | negative control | 0.8604 | 1.2506 | 24.10 |
| H004 | supported | 0.9630 | 0.7268 | 19.70 |
| H005 | excluded | 0.8653 | 1.4038 | 24.20 |

**Spearman(clay %, temporal coherence) = −0.600 across the hotspots.** The supported zones are simultaneously the *coarser* and the *higher-coherence* ones. Substrate texture and measurement quality are therefore entangled here, and the protocol explicitly forbids interpreting an apparent geological association without accounting for that. With only four hotspot values, no reliable adjustment is possible.

## 6. Specificity, source resolution and the tests that could not be run

The protocol requires that a geological explanation gain support only if H001/H004 share a susceptible characteristic that H002/H003 lack, localised enough to explain the selectivity. Here:

* the zones **do** differ from the controls — but in the **opposite** direction to susceptibility;
* the difference is **confounded** with coherence (ρ = −0.600);
* the source is a **soil surrogate, not a geological map**, at 250 m;
* the sampled interval is the **top 2 m**, not the compaction unit;
* **no second independent geological dataset** was obtainable, so cross-dataset consistency cannot be assessed.

## 7. Evidence grade

```text
GEO EVIDENCE:  NO EVIDENCE
```

| Criterion | Assessment |
|---|---|
| spatial correspondence | a difference exists, but **opposite** in sign to the hypothesis |
| specificity to H001/H004 | present yet inverted, and confounded with coherence |
| negative controls | the controls behave like the background, not like the positives — the opposite of the required pattern |
| source-map resolution | 250 m soil surrogate; **cannot** support lithological or formation claims |
| consistency across independent datasets | **not assessable** — only one dataset obtained |
| coherence confounding | **severe** (ρ = −0.600) |
| physical plausibility | the observed direction contradicts the compressible-sediment expectation |

## 8. Strongest supporting and strongest counter evidence

**Strongest supporting:** only that the supported zones are *distinguishable* from the controls in substrate texture at all (≈5–6 percentage points, ≈0.6 of the background 5–95 range). That is a real, boundary-robust separation.

**Strongest counter-evidence:** (1) the separation's **direction is opposite** to the susceptibility hypothesis; (2) it is **confounded** with coherence at ρ = −0.600; (3) the source cannot see the compaction interval; (4) the authoritative geological map was unobtainable, so the test could not be run as specified.

## 9. Separation from the groundwater result

Per protocol §12 these stay separate. The groundwater test returned NO EVIDENCE; this phase returns NO EVIDENCE for a different and partly opposing reason. Even had susceptibility been supported, *"deformation occurs preferentially over compressible sediment"* would **not** imply *"groundwater withdrawal caused compaction"*. Mechanism and susceptibility are not merged anywhere in this report.

## 10. Unresolved limitations

1. **GSI Bhukosh unreachable** — no lithology, formation or age information.
2. **No geomorphology layer** located from NRSC/Bhuvan.
3. **SoilGrids samples only the top 2 m**, not the compaction unit.
4. **No soil-profile validation** at the hotspots.
5. **Coherence confounding** cannot be adjusted with only four hotspot values.
6. **Single dataset** — no independent geological cross-check possible.
7. **Structural features** were not tested; no independently mapped fault or lineament dataset was obtained, and none is claimed.

## 11. Figures

* `qc/sci/phase3/figures/GB01_substrate.png`
* `qc/sci/phase3/figures/GB02_specificity.png`
* `qc/sci/phase3/figures/GB03_coherence_confounding.png`

No causal arrows are drawn. Every figure has machine-readable source data in `qc/sci/phase3/`.

## 12. Stopping point

Stopped before urbanisation analysis, as instructed. No causal narrative has been written and none is implied.
