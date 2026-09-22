# Phase I Observations — frozen

`freeze_version` **phase1_observations_v1**
`freeze_id` **122781a4a81bd49eb4781c7682cff7b378c97e593fe7d7ed1dd7994b387bede7**

Source: `product_v1` / RAW-336. Velocities are relative to the
**AUTHORITATIVE PRODUCT REFERENCE** (y=1384, x=1451) — see
`provenance/errata/INC-007.json`.

**These are observations, not mechanisms.** No causal statement appears here.

## Deformation zones

| Zone | Area km² | Median LOS mm/yr | Coherence | Cumulative LOS mm | Grade | Persistence |
|---|---:|---:|---:|---:|---|---|
| H001 | 5.59 | -30.95 | 0.925 | -120.7 | A | 14/14 |
| H002 | 12.83 | -13.59 | 0.863 | -48.0 | B | 11/14 |
| H003 | 2.25 | -12.87 | 0.860 | -46.8 | B | 10/14 |
| H004 | 1.07 | -14.31 | 0.963 | -59.6 | B | 10/14 |
| H005 | 0.84 | -14.21 | 0.865 | -44.5 | C | 8/14 |

## Mapped area

**robustly supported mapped deformation area under the selected quality criterion: 22.6 km²**

Criterion: |LOS velocity| ≥ 10 mm/yr, temporal coherence ≥ 0.80, area ≥ 0.4 km²,
8-connectivity.

> This is **NOT the true deformation extent.** Deformation magnitude and temporal
> coherence are strongly associated in this stack, so a coherence-based criterion
> systematically excludes part of the signal. The true extent is **UNRESOLVED**.

## Observational findings

* All five principal zones have **negative LOS velocity** in the frozen sign
  convention (movement away from the satellite along the line of sight). This is
  **not** a subsidence claim.
* H001 approximate median velocity **-30.9 mm/yr**.
* Supported local extremes reach substantially larger negative values
  (magnitude up to **87.4 mm/yr**).
* Major hotspot cumulative LOS displacement approximately
  **-121 to -45 mm**.
* **Rates are non-stationary.** Split-half differences reach
  **10.4–20.2 mm/yr**.
* Northern (H002, H003, H005) and southern
  (H001, H004) groups show **distinct temporal
  behaviour**.
* Reference-choice zero-level range: **4.78 mm/yr**.
* Relative contrast uncertainty (**1.47 mm/yr**)
  is materially smaller than absolute zero-level uncertainty
  (**5.00 mm/yr**).
* The coherence–velocity association is **UNRESOLVED** and is the highest-priority
  question for Phase II.

## Not established

* no mechanism
* no vertical rate
* no absolute rate
* no validated total extent
* no volume or storage change

## Source artefact hashes

| File | sha256 |
|---|---|
| `qc/sci/phase1/hotspots.csv` | `0239009916889a7c2dd71f43f08751188cc9b3c819da49e6a811fc652c3d9a84` |
| `qc/sci/phase1/hotspots.json` | `094da39282987a01dbafb2dc8501f5b7ebe5285749364b7434874a5845414cf0` |
| `qc/sci/phase1/hotspot_persistence.json` | `38a6dee1c667e7cff9e439d59d9339f45bf627f1faa0b20a8a6c14491523e6dd` |
| `qc/sci/phase1/hotspot_persistence.csv` | `575f1ffb906b45a63f21147716b27dc033fe4ef444466bbfccc0748b9f94932d` |
| `qc/sci/phase1/hotspot_timeseries.json` | `f4a579a628e7836e5d1c0660b2579309ad5e285f48b1f385dd94841cf0815c40` |
| `qc/sci/phase1/hotspot_timeseries_summary.csv` | `7217832860129d913d4017c1db5f5a63a3a0c78cbe871570da0450a217d4eda6` |
| `qc/sci/phase1/hotspot_uncertainty.csv` | `4ab8d07152d3e11c1565cb1c4dd0601dbfbb3b840c612cab15bdbbf1a5f73e36` |
| `qc/sci/phase1/uncertainty_budget.json` | `30cb8ba3ae1609cb644de3d3fad9e8f00edd5d5356f9b2b9d3e7e0e3e3249884` |
| `qc/sci/phase1/oscillation_diagnostics.json` | `e03c842fbd35d5609b50d62e4f85ed15cf80487bdbde560adc0154beba438aa4` |
| `qc/sci/phase1/coherence_stratification.csv` | `7c97cd2a5ed2fd120e09737faa3b337ef7d865ca27f22105b83c75f184c3bac8` |
| `qc/sci/phase1/deformation_map_summary.json` | `074fe2f9636e201c9210ab24e01bb2a520cee2062268dae9e6e85b051c08111c` |
| `qc/sci/phase1/evidence_grades.json` | `112135e68e7e158890433ef99b3f000284962f377a3b5a2de91551836f7058fe` |
| `qc/sci/PHASE1_REPORT.md` | `086460400378efa07d9b7a3ec5152d5cf82ae9982b021dbe9dfe91186df99f15` |
