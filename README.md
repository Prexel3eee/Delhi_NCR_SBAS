# Delhi-NCR SBAS-InSAR

**Cross-geometry Sentinel-1 SBAS-InSAR of Delhi-NCR, with preregistered hypothesis testing and a frozen, auditable evidence chain.**

Ascending (relative orbit 27, IW2) and independently constructed descending (orbit 136, IW1) Sentinel-1 stacks were processed with ASF HyP3 `INSAR_ISCE_MULTI_BURST` and inverted with MintPy. Five localized relative line-of-sight deformation zones were detected. Two were independently reproduced across both geometries; two were not; one remained contradictory.

> **Status: scientific investigation closed. Publication package complete.**
> Journal-neutral manuscript ready for journal selection. No target journal chosen.

---

## Headline result

> **The spatial/mean-rate deformation observations at H001 and H004 are independently reproducible; their detailed temporal histories and physical mechanism are not.**

| Zone | Ascending (mm/yr) | Descending (mm/yr) | Classification |
|---|---:|---:|---|
| **H001** | −30.95 | −36.02 | independently supported |
| **H004** | −14.31 | −12.46 | independently supported |
| **H002** | −13.59 | −1.15 | ascending feature not reproduced |
| **H003** | −12.87 | −0.75 | ascending feature not reproduced |
| **H005** | −14.21 | +61.39 | unresolved cross-geometry contradiction |

Rates are mean **relative LOS** over each zone's common-domain pixels. They are not vertical displacement rates.

**Negative controls are a principal result, not a footnote.** H002 and H003 carry ascending magnitudes comparable to H004 with adequate descending quality (temporal coherence 0.900 / 0.886), yet do not reproduce. Any explanation acting across the affected terrain — regional groundwater decline, a shared soil unit, urbanisation of the corridor — predicts all four zones similarly and therefore **fails on selectivity**.

### What the hypothesis tests found

| Hypothesis | Evidence state |
|---|---|
| Groundwater temporal forcing | **NO EVIDENCE** |
| Shallow soil-texture susceptibility | **NO EVIDENCE** (direction opposite to prediction) |
| Deep geological / aquifer-system susceptibility | **NOT ADEQUATELY TESTED** |
| Existing built intensity | **NO EVIDENCE** |
| Recent built-up expansion | **NO EVIDENCE** |
| Major infrastructure / construction | **NOT TESTABLE** |
| Measurement artefact as sole explanation | **NOT SUPPORTED** for H001/H004, but measurement limitations remain |

These three categories are **distinct and are never collapsed**, and none is equivalent to "ruled out":

- **NO EVIDENCE** — a suitable test was conducted and did not support the hypothesis
- **NOT ADEQUATELY TESTED** — available evidence does not observe the relevant physical domain
- **NOT TESTABLE** — the necessary dataset was unavailable

---

## Scientific discipline

This repository is built around one constraint: **no interpretive claim may outrun the frozen evidence**.

- The ascending product (`product_v1`, branch RAW-336) was frozen **before** interpretation.
- The descending stack was constructed independently — **no shared burst, pair, mask or acquisition list** — and no pair was selected because it intersected a hotspot.
- Groundwater lags, thresholds and significance procedures were **preregistered** in `freeze/groundwater_protocol_v1` **before any correlation existed**.
- All 336 ascending pairs were retained, including the weak 36-day and monsoon pairs. No pair was dropped to improve a result.
- Every headline number is traceable to a hash-pinned frozen artefact, and this is enforced by automated audits.

### Corrections tested and **not** adopted

Recorded as results, not omissions:

| Correction | Outcome |
|---|---|
| ERA5 atmospheric | tested, **not beneficial** (0.52 mm/yr RMS); left disabled in the principal branch |
| ERA5 + DEM residual | tested, **not beneficial** (1.04 mm/yr RMS); left disabled |
| Spatial deramping | left disabled; sensitivity experiment only |
| Unwrap correction (ascending) | rejected — did not improve the product |
| Unwrap correction (descending) | **required** — improved 7 of 7 internal metrics |

The asymmetry is itself informative: the two products have different failure modes.

### Terminology the codebase enforces

- **relative LOS deformation ≠ vertical displacement.** No decomposition is published. The Phase II-A component estimates were withdrawn as invalid.
- **independently supported spatial/mean-rate feature ≠ independently validated time history.** H001's ascending cumulative displacement is −120.7 mm against +1.1 mm descending.
- **`22.6 km²`** = "robustly supported mapped deformation area under the selected ascending quality criterion" — an operating figure, **not** a validated extent.
- **`6.66 km²`** = area of Phase-I zones independently supported at the hotspot level by the descending geometry (H001 + H004), not extrapolated.
- Uncertainty is reported as **separate terms and never summed**: formal 0.87 mm/yr; reference systematic 4.78 mm/yr (absolute offset only); processing sensitivity 0.52–1.04 mm/yr; temporal non-stationarity **10.4–20.2 mm/yr**, which dominates every statistical interval.

---

## Repository layout

```text
scripts/       83 scripts, numbered by phase (01 -> 76) + pubstyle.py
tests/         74 passing tests, offline, no credentials required
config/        MintPy branch configurations + frozen scientific decisions
geometry/      AOI, burst footprints, coverage report
manifests/     frozen burst list, acquisition matrix, pairs
freeze/        14 hash-pinned read-only freezes (see below)
provenance/    append-only errata (INC-007 .. INC-009 full documents)
qc/
  inventory/   inventory provenance, incl. the CMR serving anomaly
  network/     SBAS network audit, baselines, degree plots
  sci/         15 scientific phase reports + phase1/2/3/4 artefacts
manuscript/    journal-neutral manuscript, supplement, figures, audits
products/      published rasters derived from product_v1
state/         project_state.json - machine-readable status
data/          NOT TRACKED - see Data availability
```

### The pipeline, in phases

| Scripts | Phase | What it does |
|---|---|---|
| `01`–`05` | B–E | burst selection, inventory, SBAS network, cost estimate |
| `06`–`30` | F–H | pilot, production submission, retrieval, MintPy prep, inversion |
| `31`–`38` | I | Phase-I characterization: deformation map, hotspots, time series, uncertainty |
| `39`–`50` | II-A | independent descending track, cross-validation, decomposition (withdrawn) |
| `51`–`57` | II-B | descending reliability diagnostics, unwrap/conncomp, ERA5 |
| `58`–`59` | II-C | hotspot-level cross-geometry reconciliation |
| `60`–`69` | III–IV | causal-evidence testing, final synthesis |
| `70`–`76` | V–V-B | manuscript, publication figures, provenance, audits |

---

## Environment

Two conda environments, deliberately separated so MintPy's GDAL pins cannot perturb the search/submission stack.

```bash
conda env create -f env/delhi-hyp3.yml      # py3.12, asf_search 14.0.0, hyp3_sdk 7.7.8
conda env create -f env/delhi-mintpy.yml    # py3.11, mintpy 1.6.4, gdal 3.12.3
```

Pinned versions are in `env/*-requirements-lock.txt`.

> **Note:** `conda activate` may fail in some shells. The scripts work fine with a direct interpreter path, e.g. `/path/to/envs/delhi-mintpy/bin/python`. Scripts that shell out to `prep_hyp3.py` need the env's `bin/` on `PATH`.

### Credentials

**None are stored in this repository.** Data *acquisition* (not analysis) requires:

- **NASA Earthdata** login for ASF HyP3 submission/download — supply via `~/.netrc`, mode 600
- **Copernicus CDS** key for ERA5 — supply via `~/.cdsapirc`, mode 600

All metadata access for burst selection is anonymous. Credentials are required only for submitting jobs, downloading products, and fetching ERA5.

---

## Reproducing

```bash
# 1. verify the frozen baseline (exits non-zero on any drift)
python scripts/verify_freeze.py
python scripts/verify_mintpy_input_v1.py
python scripts/verify_product_v1.py
python scripts/verify_phase1_observations.py

# 2. run the test suite (offline, no credentials)
python -m pytest tests/ -o addopts=""

# 3. rebuild the publication package from frozen artefacts
python scripts/70_phase5_manuscript.py --build     # manuscript
python scripts/72_phase5b_figures.py               # F9-F11
python scripts/73_phase5b_restyle.py               # F1-F8, F12
python scripts/74_phase5b_provenance.py --build    # figure provenance
python scripts/75_phase5b_audit.py                 # numerical/terminology/claim audits
python scripts/76_phase5b_finalize.py              # journal-neutral exports
python scripts/70_phase5_manuscript.py --freeze    # seal the freeze LAST

# 4. verify the sealed package
python scripts/74_phase5b_provenance.py --verify
```

Scripts are idempotent and re-runnable. The freeze step must run last, because the manifest hashes every output.

> `scripts/71_phase5_figures.py` is **superseded** by `72`/`73` and exits 2 rather than silently overwriting the publication figures.

---

## Data availability

**The SAR corpus is not tracked in this repository** (~131 GB of HyP3 products under `data/`, which is gitignored). Cloning this repository gives you the code, the frozen artefacts and the manuscripts — **not** the input scenes. What *is* tracked is everything needed to audit and rebuild the results from the frozen artefacts:

| Product | Location | Freeze |
|---|---|---|
| Ascending authoritative relative LOS solution | `mintpy/baseline_raw_work/` | `product_v1` |
| Published rasters | `products/product_v1/` | derived from `product_v1` |
| Descending raw solution | `mintpy/descending_work/` | `descending_raw_v1` |
| Descending unwrap-corrected candidate | `mintpy/descending_d2_unwrap_work/` | `descending_v2_candidate` |

Large products are **hashed in place** rather than duplicated.

### External datasets

| Dataset | Source | Access |
|---|---|---|
| Sentinel-1 SLC bursts | ASF / HyP3 | public, credentialed |
| ERA5 | Copernicus CDS | public, credentialed |
| CGWB seasonal groundwater | CGWB | public; **archived copy** used, live host was down |
| NWDP six-hourly telemetry | nwdp.nwic.gov.in | public |
| SoilGrids v2.0 | ISRIC | public |
| GHSL GHS-BUILT-S | JRC | public |
| ESA WorldCover | ESA / AWS Open Data | public |
| GNSS vertical velocities | Nevada Geodetic Laboratory | public |

### Corpus accounting

```text
Ascending    119 acquisitions  336 interferograms   1680 HyP3 credits
             (1 excluded: 2025-05-18, CMR serving anomaly)
Descending    92 accepted, 1 unconnectable within |B_perp| <= 250 m
              91 inverted       219 interferograms   1095 credits
Pilot         14 jobs (7 unique + 7 duplicates), 70 credits
```

**Limitations on reuse:** the published velocity fields are **relative LOS** quantities, not absolute velocities and not vertical displacement. Users requiring absolute rates must supply an independent reference; the reference-selection systematic is **4.78 mm/yr**.

---

## Freezes and verification

Fourteen hash-pinned, read-only freezes (directories `0555`, files `0444`). Each has a companion verifier that exits non-zero on drift.

```text
freeze/v1                      network freeze: 119 acquisitions / 336 pairs / K=4
freeze/mintpy_input_v1         ifgramStack.h5, 19.71 GB, sha256 4289c87d...
freeze/product_v1              RAW-336 authoritative v1 deformation solution
freeze/phase1_observations     5 zones, 22.58 km2 mapped area
freeze/descending_network_v1   descending SBAS network
freeze/descending_raw_v1       DESCENDING_RAW_V1
freeze/descending_v2_candidate DESCENDING_PRODUCT_V2_CANDIDATE (unwrap-corrected)
freeze/phase2a_results         Phase II-A cross-validation
freeze/phase2b_closeout_v1     descending reliability closeout
freeze/cgwb_seasonal_v1        archived CGWB seasonal groundwater
freeze/nwdp_telemetry_v1       live official NWDP download
freeze/groundwater_protocol_v1 preregistered before any correlation
freeze/final_evidence_v1       final synthesis
                               db329cf47f4bef92a020056e608decbf95644463f8148570478128d2861c9e88
freeze/publication_v1          publication package, 42 artefacts
                               57d95f6921fc11ce778baff4db8cae1442f40decd026406138fef5147b0219df
```

---

## Incidents and errata

Nine incidents are recorded across the project. Full erratum documents live in `provenance/errata/` (INC-007, INC-008, INC-009, indexed in `index.json`); the machine-readable log is `state/project_state.json` → `incident_log`; the narrative trail is `RUNLOG.md`.

Seven could have altered a scientific conclusion and are retained in the reproducibility appendix (`manuscript/SUPPLEMENT_FINAL_JOURNAL_NEUTRAL.md`), each with **problem, potential scientific consequence, detection, correction, regression protection**. Routine implementation failures were dropped.

The two most instructive:

- **INC-008** — Phase-I hotspot polygons were single-pixel fragments, making **every polygon-based containment test in Phase II vacuous**. Detected by an implausible downstream count. Corrected geometry reproduced the frozen CSV exactly, and the containment conclusion **holds** once re-tested.
- **INC-009** — the independently supported mapped area was published as 3.17 km² through three phases. The Phase V-B numerical gate found it traced to **no script, table or artefact**. Authoritative value is **6.66 km²**, exactly derivable from the frozen zone areas. Corrected; no conclusion changes.

Also documented: `2025-05-18` (`027_056011_IW2`) is excluded **fail-closed** — CMR reports the granule in its hit count but does not serve it. The acquisition was never fabricated, giving 119 rather than 120.

---

## Tests

```bash
python -m pytest tests/ -o addopts=""      # 74 passed, 1 skipped
```

| File | Covers |
|---|---|
| `test_asf_client_regressions.py` | the three ASF/CMR **silent-failure modes** |
| `test_freeze_v1_invariants.py` | the v1 decision (119/336/K=4, no unfrozen burst in any pair) |
| `test_pilot_idempotency.py` | pilot re-run safety, bit-identical configs |
| `test_pilot_retrieval.py` / `test_production_retrieval.py` | full retrieval reconciliation |
| `test_mintpy_prep_selection.py` | HyP3-schema drift handling |
| `test_correction_validation.py` | corrections tested-not-beneficial |
| `test_phase1_characterization.py` | Phase-I observation invariants |

`scripts/asf_client.py` exists because the metadata APIs have **three silent-failure modes** that would corrupt an SBAS network — each is guarded and documented in the module docstring.

---

## Manuscript and publication package

`manuscript/` holds the complete journal-neutral package:

| File | Contents |
|---|---|
| `MANUSCRIPT_FINAL_JOURNAL_NEUTRAL.md` | abstract, results, hypothesis tests, discussion, limitations, Table 1 |
| `SUPPLEMENT_FINAL_JOURNAL_NEUTRAL.md` | methods S1–S8, condensed incident appendix, all captions |
| `FIGURE_CAPTIONS.md` | 12 self-contained captions |
| `FIGURE_PROVENANCE.json` | per-figure sources, hashes, transformations, output hashes |
| `AUDIT_REPORT.json` | numerical / terminology / claim audits |
| `TITLE_CANDIDATES.md` | 8 candidates, none selected |
| `REFERENCES.md` | **no bibliographic metadata invented**; unverified fields marked explicitly |
| `SUBMISSION_READINESS_REPORT.md` | 11/12 gates PASS |

**Figures** (12 main, PNG 600 dpi + vector PDF, one style system, legible in grayscale and for colour-vision deficiencies via redundant luminance **and** hatch encoding) are in `qc/sci/phase4/figures/`.

Two figures are explicitly restricted against inventing data, and say so on the figure:

- **F4** reports retained *aggregate* agreement statistics. Paired per-pixel values were not retained, so **no scatter is shown and none is synthesised**.
- **F8** reports retained cumulative totals. Per-epoch series were not retained and are **not reconstructed**.

---

## Roadmap

The highest-value additions, in order:

1. **Deep borehole / lithologic logs**, sediment thickness, aquifer architecture — the single largest unobserved domain
2. **Local continuous GNSS or levelling inside the AOI** — the nearest adequately sampled station is 209.9 km away
3. **H005-focused unwrap/phase investigation** — the contradiction is unexplained
4. Better H001/H004 temporal validation — reproduces the rate, not the history
5. Well metadata (aquifer, screened interval, depth) — aquifer identity is currently unknown
6. Documented construction chronology — major infrastructure is currently `NOT TESTABLE`

---

## Citation and license

No `LICENSE` or `CITATION.cff` is present yet. **Add both before publishing** — the author should choose the licence, and the citation should carry the `publication_v1` freeze ID.

If you use these products, note that they are **relative LOS** deformation rates and that the mechanism remains unresolved. Please do not cite them as subsidence rates or attribute them to a specific cause.

## Acknowledgements

Sentinel-1 data are provided by ESA/Copernicus. HyP3 processing is provided by the Alaska Satellite Facility. Groundwater observations are from CGWB and the National Water Data Portal (NWIC), Government of India.
