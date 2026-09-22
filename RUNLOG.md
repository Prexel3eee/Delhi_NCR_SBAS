# RUNLOG — Delhi-NCR Multi-Burst SBAS

Factual record of execution. Newest phase last. All times UTC.

Environment for every run below:

```text
python       3.12.14   (conda env: delhi-hyp3)
asf_search   14.0.0
hyp3_sdk     7.7.8
networkx     3.7
pandas       3.0.6
shapely      2.1.2
matplotlib   3.11.2
mintpy       NOT INSTALLED
```

---

## 2026-09-21 — Phase A: repository + verified inputs

**Action.** Reconciled the handoff bundle against `BUNDLE_MANIFEST.json`; scaffolded the
project tree; copied the frozen AOI into `geometry/`.

**Result.** Both AOI files hash-match the handoff manifest (`aoi.geojson`
`ddeeae475f696a98…`, `aoi.wkt` `8f7e295729116a3b…`). Independent re-audit of the two
historic reconnaissance CSVs reproduced every documented statistic exactly:

```text
any_overlap : 341 pairs / 120 nodes, 1 component, 0 bridges, 0 articulation points
              degree min/mean/median/max 3 / 5.6833 / 6 / 6
              temporal baseline 114x12d, 115x24d, 112x36d
              |B_perp| median 67 m, p95 181 m, max 239 m, 0 negative
50pct       : 278 pairs /  99 nodes, ends 2025-01-18 (excludes 2025 tail)
```

**Decision.** The brief is internally consistent with its provenance data; proceed.

**Note.** `asf_search` 14.0.0 API drift: `DATASET.S1_BURSTS` is now
`DATASET.SLC_BURST`. No credentials needed for metadata search — all queries so far
are anonymous and public.

---

## 2026-09-21 — Phase B: geographic reference burst selection

**Action.** Enumerated every ascending path-27 / VV / IW burst intersecting the AOI on
the representative date 2025-09-27, evaluated all contiguous along-track runs, and
selected the smallest run that fully contains the AOI.

**Result — the hand-entered K=3 collection is INVALID.**

```text
5 bursts intersect the AOI:
  027_056010_IW2   aoi_cov 0.0002
  027_056011_IW2   aoi_cov 0.2780
  027_056012_IW2   aoi_cov 0.4652
  027_056013_IW2   aoi_cov 0.3604
  027_056014_IW2   aoi_cov 0.0170

K=3 (056011,056012,056013) -> AOI fully contained: FALSE
     uncovered 0.3690 % at 76.8856-76.9547 E, 28.8524-28.8726 N
K=4 (056011..056014)       -> AOI fully contained: TRUE, coverage 1.000000
     union / AOI area ratio 3.583
```

All 10 hard HyP3 multi-burst checks PASS for the K=4 collection (count 1–15,
gap-free contiguous relative burst IDs 56011–56014, single path 27, single direction,
single polarization VV, single sub-swath IW2, acquisition spread 8.0 s vs 120 s limit,
no antimeridian crossing, AOI contained, no lateral jog).

**Decision.** Freeze K=4. The AOI is **not** shrunk to preserve K=3.

**Files.** `manifests/geographic_reference_bursts.csv`,
`geometry/selected_bursts.geojson`, `geometry/coverage_report.json`.

---

## 2026-09-21 — Phase C: burst stack discovery (acquisition × burst matrix)

**Action.** Full-period VV inventory for each of the 4 frozen bursts, then the
acquisition × burst completeness matrix with fail-closed handling.

**Three data-source defects were found and fixed before trusting any result:**

1. **`asf_search.search()` raises `ASFSearchError` with an empty message** for certain
   date windows even when data exists. Reproduced for `fullBurstID=027_056011_IW2`,
   2025-05-18: >20 consecutive failures across every supported query form, while
   2025-05-06 / 2025-05-30 / 2025-09-27 all succeeded.

2. **CMR's `POLARIZATION` attribute filter silently drops a granule.** With
   `string,POLARIZATION,VV` added, CMR reports `CMR-Hits=120` but serves only **119**
   granules and page 2 is empty — the 2025-05-18 VV granule is counted yet omitted.
   Fixed by removing the attribute filter and filtering in Python.

3. **`ASFProduct.stack()` never raises on incomplete results.** It returns
   `searchComplete=False` with a truncated stack (observed: 29 products for a 1-year
   window). Naive use silently drops acquisitions.

   Replacement strategy: CMR UMM-JSON is the authoritative, windowed, self-validating
   source. Because every acquisition is dual-pol (`GROUP_ID` mode `DV`), each window is
   required to contain **one VV and one VH granule per acquisition timestamp**; a window
   violating that parity is halved and retried recursively. This is what detects the
   missing granule.

**Result.**

```text
027_056011_IW2   119 records / 119 dates   (2025-05-18 unresolvable)
027_056012_IW2   120 records / 120 dates   asf_search cross-check agree=True
027_056013_IW2   120 records / 120 dates   asf_search cross-check agree=True
027_056014_IW2   120 records / 120 dates   asf_search cross-check agree=True

union of dates                       120
complete 4-burst acquisitions        119
incomplete acquisitions                1
platform                             SENTINEL-1A only (homogeneous, no S1C/S1D)
accepted-series gaps                 115x12d, 3x24d
metadata validation                  PASS (path / direction / polarization / sub-swath / burst IDs)
```

### Documented unresolved item: `027_056011_IW2` on 2025-05-18

This is recorded as **evidence, not data**. No record was fabricated.

```text
Observed once, directly from a CMR granules.umm_json query:
    S1_056011_IW2_20250518T125536_VV_6366-BURST

Not reproducible afterwards:
    - 15 consecutive single-day CMR retries  -> VV never served again
    - 5 alternate query forms (fullBurstID, relativeBurstID+orbit,
      absoluteBurstID, geo_search, ASFProduct.stack) -> all failed
    - CMR always reports CMR-Hits=2 for any window containing the
      acquisition, but serves only the VH granule
    - a windowed split narrowed to 2025-05-17T16:30 -> 2025-05-20T12:00
      and still returned VV=0, VH=1

Independent corroboration that the acquisition is real:
    - parent SLC S1A_IW_SLC__1SDV_20250518T125513_20250518T125543_059249_075A3B_6366
      appears in the full-scene reconnaissance network (all 120 dates)
    - live ASF SLC search for 2025-05-18 / path 27 / ascending returns S1A SLC scenes
    - "1SDV" confirms dual-polarization (VV+VH) was acquired
    - neighbouring 12-day dates 2025-05-06 and 2025-05-30 both return the burst
```

**Decision.** EXCLUDE the acquisition, fail-closed, per the brief's homogeneity rule:
an acquisition missing even one required burst is not silently substituted with a
smaller burst set. Accepted stack is therefore **119 acquisitions**, not 120.
Re-check CMR before production; if the VV granule is served, re-run Phases C–D to
recover a 120-acquisition network.

**Also fixed.** Absolute orbit is not a CMR burst attribute; it is decoded from
`GROUP_ID` (e.g. `S1A_IWDV_0086_0092_059249_027` → absolute orbit 59249, platform S1A).
`absoluteBurstID` is *not* time-stable (127260595 on 2025-05-18 vs 131395356 on
2025-09-27) and is *not* sub-swath-unique, so it is never used as an identity key.

**Files.** `manifests/burst_inventory_2021_2025.csv`,
`manifests/acquisition_burst_matrix.csv`, `manifests/accepted_acquisitions.csv`,
`manifests/excluded_acquisitions.csv`, `manifests/acquisition_gaps.csv`,
`manifests/burst_completeness_matrix.csv`, `manifests/burst_search_log.csv`,
`qc/inventory/inventory_provenance.json`.

---

## 2026-09-21 — Phase D: burst-level SBAS network + audit

**Action.** Per-burst perpendicular baselines against one fixed reference acquisition
(2021-10-06), identity-joined pair construction, then graph audit.

### Third silent-failure defect found and fixed

`asf_search.baseline.stack.check_reference` does:

```python
if reference sceneName not in stack: reference = stack[0]
```

When the fixed reference granule is absent from a search window it is **silently
replaced**, and every temporal/perpendicular baseline in that window is then measured
from the wrong date. Because the period is covered by disjoint 180-day windows and the
reference lies only in the first, *every later window was re-based*. Since this project
derives a pair's |B_perp| as the difference of two per-date values, a per-window offset
corrupts every pair spanning two windows.

Evidence before the fix — `027_056011_IW2` showed physically implausible values:

```text
2025-06-11  temporalBaseline=0   (reference is 2021-10-06 -> expected -1438)
per-burst |B_perp| divergence per date: max 198 m, 7 dates > 20 m
spurious exact 0.0 baselines on 2025-04-24 / 05-06 / 05-30 / 06-11
```

Fix: inject the fixed reference product into every window before baseline computation,
and independently validate that each product's `temporalBaseline` equals the true day
offset from the reference date (dropping `noStateVectors` scenes, which have no
computed perpendicular baseline). After the fix:

```text
027_056011_IW2  119 baseline rows, 0 rejected, 0 reference substitutions
027_056012_IW2  120 baseline rows, 0 rejected
027_056013_IW2  120 baseline rows, 0 rejected
027_056014_IW2  120 baseline rows, 0 rejected
per-burst |B_perp| divergence: median 4 m, max 6 m, 0 dates > 20 m
reference date row: exactly 0.0 for all four bursts
```

### Network result

```text
thresholds                    temporal <= 36 d, |B_perp| <= 250 m
candidate pairs per burst     336 (all four bursts, before intersection)
union of pair keys            336
intersection (valid for all)  336        dropped for missing burst: 0
pairs emitted                 336
rejected at payload validation  0

nodes                         119
edges                         336
connected components          1
isolated nodes                0
bridges                       0
articulation points           0
degree min/mean/median/max    3 / 5.6471 / 6 / 6
degree distribution           {3: 2, 4: 4, 5: 28, 6: 85}
acquisition gaps              115x12d, 3x24d (max 24 d)
pair temporal baseline        113x12d, 113x24d, 110x36d
pair |B_perp| (m)             min 1.0 / median 70.0 / p95 186.2 / max 248.0
```

All 6 preferred acceptance criteria PASS (1 component, no isolated nodes, no bridges,
no articulation points, min degree ≥ 3, no unexplained long gap).

**Cross-validation against the historic reconnaissance.** Excluding the 6 pairs that
involve the excluded 2025-05-18 acquisition leaves 335 reconnaissance pairs; the burst
network holds 336. The sets differ by exactly one pair:

```text
in burst network only : 2022-09-07 -> 2022-09-19
in reconnaissance only: (none)
```

That pair passes the burst-level |B_perp| gate while the full-scene gate excluded it.
This is expected: burst and full-scene baselines use different reference geometry, and
the brief requires the burst network to be recomputed rather than inherited.

**Decision.** Freeze the network at **336 pairs / 119 acquisitions**.

**Files.** `manifests/sbas_pairs.csv`, `qc/network/network_summary.json`,
`qc/network/network_edges.csv`, `qc/network/network_degree.csv`,
`qc/network/baseline_table.csv`, `qc/network/baseline_time_plot.png`,
`qc/network/degree_histogram.png`.

---

## 2026-09-21 — Phase E: credit estimate and pilot selection (no submission)

**Action.** Exact credit computation from the official HyP3 burst-InSAR table, verified
against <https://hyp3-docs.asf.alaska.edu/using/credits/> on the day of the run, plus
pilot selection. **Nothing was submitted.**

```text
K = 4, N = 336

looks   pixel   credits/job   total   % of 8000/month
20x4    80 m              1     336           4.20 %
10x2    40 m              5    1680          21.00 %   <- primary pilot config
5x1     20 m             15    5040          63.00 %
```

**Cost consequence of K=4.** At 10x2 looks the tier boundary is K=1–3 → 1 credit;
K=4 moves it to 5 credits/job, a **5× increase** over a K≤3 collection. At 20x4 the
K=1–4 tier keeps 1 credit/job. Recorded explicitly rather than absorbed silently.

**Decision.** Retain **10x2 / 40 m** as the primary pilot configuration (brief §14).
20x4 is not adopted merely to save credits; it would require the pilot to demonstrate
that 80 m pixels are adequate for the intended urban deformation analysis.

**Pilot (7 jobs, 35 credits = 0.438 % of monthly allocation).**

```text
1. 2025-02-11 -> 2025-02-23   12 d   |B_perp|   2 m   lowest |B_perp| 12-day
2. 2021-12-05 -> 2021-12-29   24 d   |B_perp|  64 m   median |B_perp| 24-day
3. 2025-03-31 -> 2025-05-06   36 d   |B_perp| 170 m   p90 |B_perp| 36-day stress test
4. 2025-06-23 -> 2025-07-05   12 d   |B_perp|   6 m   monsoon (Jun-Sep)
5. 2025-03-07 -> 2025-03-19   12 d   |B_perp|   2 m   dry season (Nov-Mar)
6. 2025-05-30 -> 2025-07-05   36 d   |B_perp|   1 m   late-period 2025 tail
7. 2025-02-11 -> 2025-02-23   12 d   |B_perp|   2 m   water-mask control (mask OFF)
```

Pair 7 repeats pair 1 with `apply_water_mask=False` so the pilot can compare unwrapping
and connected components near the Yamuna (brief §15).

**Files.** `qc/cost_estimate.json`, `manifests/pilot_pairs.csv`, `config/pilot.yaml`.

---

## 2026-09-21 — v1 accepted and frozen; tests and MintPy environment prepared

**Owner decision.** Accept the 119-acquisition / 336-pair network as **v1**. Stop all
attempts to recover the 2025-05-18 acquisition. Production remains blocked pending pilot
QC and explicit approval.

### Immutable freeze v1

Snapshot of 21 artefacts (11 critical) into `freeze/v1/`, each hashed, the snapshot marked
read-only, and a single digest derived over the decision-defining content:

```text
freeze_id  cf2bdbfd4fa722dd0df9608afba13bf7cd9361a0897dea14ea70e724c8b1924d
critical   AOI, selected bursts, accepted/excluded acquisitions, matrix,
           sbas_pairs, pilot_pairs, pilot.yaml, network_summary
provenance burst inventory, coverage report, search log, inventory provenance,
           net edges/degree, baseline table, cost estimate
```

`scripts/verify_freeze.py` checks two independent things and exits non-zero on either:

1. **snapshot integrity** — every frozen file still hashes to its recorded value and the
   recomputed `freeze_id` matches;
2. **working-tree agreement** — the live `manifests/`, `qc/` and `config/` files still
   match the frozen baseline. This is the realistic accident: re-running script `03`/`04`
   silently changes the network that a paid submission would be based on.

Verified: exit 0, `freeze_id cf2bdbfd4fa722dd... intact`.

### Regression tests for the three failure modes

`tests/test_asf_client_regressions.py` (13 tests, offline, no network):

```text
mode 1  asf_search raising on valid windows
        - day-level failure is recorded, never silently dropped
        - good sub-windows survive a failing neighbour
        - a failing asf_search cannot alter or block the authoritative CMR result
mode 2  CMR POLARIZATION filter silently omitting granules
        - the request must never carry a POLARIZATION attribute filter  <- the exact bug
        - VV/VH parity check detects a missing granule and a skewed timestamp
        - inventory splits a wide window and recovers the dropped granule
        - an unresolvable window is recorded as UNRESOLVED and never fabricated
        - burst_inventory fails closed when no granule is available
mode 3  stack() truncation and silent reference substitution
        - the fixed reference IS injected into every window
        - a re-based product is detected via temporalBaseline and rejected
        - noStateVectors scenes are rejected (no perpendicular baseline)
        - a correctly referenced window is NOT rejected (guard is not over-eager)
```

`tests/test_freeze_v1_invariants.py` (7 tests) pins the v1 decision so an accidental
re-run of `03`/`04` fails CI rather than being discovered after credits are spent:
`freeze_id` self-consistency, frozen snapshots untouched, critical artefacts undrifted,
119/336/K=4, 2025-05-18 not recovered and absent from all pairs, no unfrozen burst in any
pair, production not submitted.

```text
delhi-hyp3  : 20 passed in 0.28 s
delhi-mintpy: 20 passed in 37.74 s
```

### MintPy / QC environment

Created a dedicated conda environment (the analysis stack is kept separate from the
search/submission stack so MintPy's GDAL pins cannot perturb `asf_search`):

```text
delhi-mintpy   python 3.11.16   mintpy 1.6.4 (>= 1.6.3 required)   gdal 3.12.3
               rasterio 1.4.4   geopandas 1.1.4   h5py 3.16.0
               scipy 1.17.1     shapely 2.1.2     pytest 9.1.1
```

Confirmed present: `smallbaselineApp.py`, `load_data.py`, **`prep_hyp3.py`** (the
HyP3-product prep tool required for Phase H), `modify_network.py`, `reference_point.py`,
`timeseries2velocity.py`. Environment pinned to `env/delhi-mintpy.yml` and
`env/delhi-mintpy-requirements-lock.txt`; the search/submission stack pinned to
`env/delhi-hyp3.yml` and `env/delhi-hyp3-requirements-lock.txt`.

---

## 2026-09-21 — Phase F: pilot submitted (10x2)

**Authentication.** `~/.netrc` created with mode `600` for Earthdata user
`vishu_sar_1709`. `~/.netrc` is listed in `.gitignore`; no secret is stored in the
repository. Owner intends to rotate these credentials later.

```text
account status     APPROVED
credits before     8000
authenticated      OK (my_info)
```

**Submitted.** Script `scripts/07_submit_pilot.py`, `INSAR_ISCE_MULTI_BURST`, `looks=10x2`,
4 reference + 4 secondary bursts per job, both payloads pre-validated by
`prepare_insar_isce_multi_burst_job` (no credentials needed) before any spend.

```text
1. 2025-02-11 -> 2025-02-23   12 d   |B_perp|   2 m   lowest |B_perp| 12-day
2. 2021-12-05 -> 2021-12-29   24 d   |B_perp|  64 m   median |B_perp| 24-day
3. 2025-03-31 -> 2025-05-06   36 d   |B_perp| 170 m   p90 |B_perp| 36-day stress test
4. 2025-06-23 -> 2025-07-05   12 d   |B_perp|   6 m   monsoon (Jun-Sep)
5. 2025-03-07 -> 2025-03-19   12 d   |B_perp|   2 m   dry season (Nov-Mar)
6. 2025-05-30 -> 2025-07-05   36 d   |B_perp|   1 m   late-period 2025 tail
7. 2025-02-11 -> 2025-02-23   12 d   |B_perp|   2 m   water-mask control (mask OFF)
```

All 14 jobs reached `RUNNING`. Production was **not** touched.

### INC-001 — idempotency guard was wrong; 7 duplicate jobs, 35 wasted credits

The first submission of 7 jobs was correct. I then re-ran `--submit --yes`
specifically to *verify* idempotency — and it submitted 7 more.

```text
root cause
    hyp3_sdk HyP3.find_jobs(name=...) performs an EXACT name match.
    The guard passed the project prefix 'delhi_ncr_sbas_a27_v1_pilot',
    which matches nothing, so the "already submitted?" check always
    answered "no" and every run resubmitted all 7 pairs.

measured evidence
    find_jobs(name='delhi_ncr_sbas_a27_v1_pilot')                    -> 0 matches
    find_jobs(name='delhi_ncr_sbas_a27_v1_pilot_20250211_20250223')  -> 2 matches

impact
    14 pilot jobs instead of 7; 70 credits instead of 35 (8000 -> 7930).
    The duplicates are identical pairs, so there is no scientific impact -
    only wasted credits and clutter. The SDK exposes no job cancel/delete
    call, so the duplicates cannot be withdrawn. At production scale
    (336 jobs) the same bug would have wasted 1680 credits.

fix
    List multi-burst jobs via find_jobs(job_type=...) and match EXACT names
    locally; the name= filter is never used.
    tests/test_pilot_idempotency.py (8 tests) pins this, including a guard
    asserting find_existing never passes name= to find_jobs.

verification of the fix
    A third --submit run reported 7 distinct existing names, skipped all 7,
    submitted 0 jobs, and credits stayed at 7930 (14 multi-burst jobs).

ledger
    manifests/hyp3_jobs.csv was reconciled from remote HyP3 truth and
    honestly records all 14 jobs. persist() is now append-only, because
    collapsing rows by job name is exactly what would have hidden this.
```

**Status.** 14 multi-burst jobs `RUNNING`; 7930 credits remain (production at 10x2 needs
1680, so the allocation is still sufficient). HyP3 Basic retains products for 14 days, so
download should follow promptly once the jobs finish.

**New script modes.** `--dry-run` (default, no credentials), `--submit --yes`,
`--status`, `--reconcile`.

---

## 2026-09-22 — Phase F/G: pilot retrieval, QC and acceptance

**Retrieval.** Polled to terminal state and downloaded immediately (HyP3 Basic retains
products for only 14 days). All 14 jobs `SUCCEEDED`; all 14 products downloaded.

```text
zip total        1721.4 MB   (mean 123.0 MB/product, max 124.4 MB)
extracted total  1775.3 MB   (mean 126.8 MB/product, ratio x1.031)
files/product    14 (water mask ON) / 13 (water mask OFF - multi-burst omits it)
layout           data/hyp3_zips/<job_name>__<job_id8>/
                 data/hyp3_extracted/<job_name>__<job_id8>/
```

Both duplicate copies were preserved as instructed; job-id-keyed directories mean
duplicate names cannot collide.

**Ledger reconciliation** (append-only ledger vs remote truth, report-only — the ledger is
never rewritten by reconciliation):

```text
ledger rows 14 | ledger distinct job_ids 14 | remote jobs 14
in ledger not remote 0 | in remote not ledger 0 | duplicate job names 7
credit cost per job (HyP3-reported) {5: 14} | credits charged 70
```

The `credit_cost` field comes from HyP3 itself and independently confirms the K=4 @ 10x2
cost model of **5 credits/job** that was derived from the published credit table.

**QC on the 7 unique scientific configurations.**

```text
CRS EPSG:32643 (UTM 43N) | pixel 40 m  -> confirms looks=10x2
AOI fully inside every product: True for all 7
valid data over the AOI: 1.000 for all 7
median coherence:  0.82, 0.82, 0.79, 0.72 (winter/spring)
                   0.51 (12 d monsoon), 0.42, 0.41 (36 d dry->pre-monsoon)
connected components in AOI: 1-8; largest covers 60-99% of the AOI
```

The two 36-day pairs are the weakest, as expected: fewer components coalesce, largest
component drops to 69% / 60%, and median coherence falls to ~0.41. Those are the stress
cases the pilot was designed to expose.

**Reproducibility (INC-001 turned into evidence).** Every duplicated pair was compared
layer by layer: **all 7 configurations bit-identical** (7/7 layers for masked, 6/6 for the
control). HyP3 multi-burst processing is deterministic, so an accidental duplicate
submission became a genuine determinism test.

**Water-mask ON/OFF around the Yamuna.**

| region | valid unwrapped fraction, mask ON | mask OFF |
|---|---|---|
| water | **0.000** | 0.743 |
| land | 0.605 | 0.605 |

Water fraction of the raster is 0.909% (1.85% inside the AOI, since the Yamuna crosses
it). Masking removes water from phase unwrapping completely and leaves land validity
unchanged, so **`apply_water_mask = True` is recommended for production**.

> **Defect found: water-mask polarity was inverted.** I had assumed `1 = water`. ASF's
> documentation states the opposite for product packages
> (<https://hyp3-docs.asf.alaska.edu/water_masking/>): *"Water pixels are assigned a value
> of 0, and all remaining pixels are assigned a value of 1 ... the pixel values are
> opposite to the reference water mask."* The first QC pass therefore reported a 99.09%
> water fraction for Delhi. Corrected, and now verified two ways: against the docs, and
> self-consistently from the data (the region HyP3 actually excludes from unwrapping is
> exactly the 0.909% `0`-valued region).

**Burst-merge seam check (multi-burst specific).** Per-azimuth-row medians are compared to
a local rolling median and scored with a robust MAD z-score, gated on both the z-score and
an absolute effect size, with a margin excluding rows near the mosaic boundary. Result: no
catastrophic seam. Largest single-row coherence deviation ~0.10 with <=1.7% of rows
flagged. The detector cannot separate a burst seam from a genuine east-west scene feature
(river, road, land-use boundary), so this is supporting evidence, not proof.

**Storage projection** (from measured products, not assumptions):

```text
measured     zip mean 123.0 MB, extracted mean 126.8 MB
336 pairs    zip 41.31 GB, extracted 42.61 GB, MintPy working ~63.9 GB
             GRAND TOTAL 147.83 GB against 551 GB free
pilot actual 1.72 GB zip + 1.78 GB extracted (+656 MB clipped/staged)
```

**MintPy preparation and ingestion test.**

```text
products        6 water-mask=ON configurations (the control lacks the mask layer)
common overlap  EPSG:32643, [647640, 3129000, 765360, 3225440]
target grid     2943 x 2311 px @ 40 m - ONE grid for every layer of every pair
prep_hyp3.py    exit 0, 42 .rsc metadata files
load_data       exit 0 -> inputs/ifgramStack.h5
                6 interferograms over 11 acquisition dates
```

This is a loadability test, not an inversion: the pilot pairs are not a connected time
series (the 2021 pair is isolated from the 2025 pairs), so a full SBAS inversion is
neither expected nor meaningful here. Connectivity is a property of the full 336-pair
stack in Phase H.

> **Defects found and fixed during MintPy preparation.**
> 1. **AOI/CRS mismatch.** The frozen AOI is lon/lat (EPSG:4326) while HyP3 products are
>    UTM 43N. Masking with unreprojected coordinates produced an all-False mask, which
>    silently looked like "zero valid pixels" rather than an error. Both scripts now
>    reproject the AOI.
> 2. **Products are NOT on byte-identical grids.** Different pairs geocode to different
>    extents/origins, so the naive "assert the same transform and read the same window"
>    approach failed. Confirms brief section 42.5. All layers are now read boundlessly
>    onto one shared target grid derived from the common overlap.
> 3. **Renaming broke MintPy's date parsing.** MintPy parses the product name (encoding
>    both acquisition dates) from the filename. Clipped files must therefore keep the
>    original HyP3 stem plus a `_clipped` suffix, and `<product_name>.txt` must sit beside
>    them; otherwise `prep_hyp3` raises "Failed to parse product name from filename".
> 4. **`Job.succeeded` / `Job.failed` are methods, not properties** in `hyp3_sdk`, so
>    `if job.succeeded:` is always truthy (a bound method object). The first downloader
>    tried to download RUNNING jobs and logged spurious failures. All state checks now
>    compare `status_code`. Pinned by `tests/test_pilot_retrieval.py`.
> 5. **Edge-versus-interior validity is not informative for a merged multi-burst mosaic**
>    (the bounding box includes large nodata corners); it is reported for completeness
>    only, and the seam check is the meaningful multi-burst test.
> 6. **Land-relative unwrapped-phase validity.** Gating on the plain AOI fraction
>    penalised the water mask for working correctly (1.85% of AOI pixels are water).
>    The gate now measures AOI land pixels.

**Pilot acceptance: 18/18 gates PASSED.** See `qc/pilot/PILOT_ACCEPTANCE_REPORT.md`.

```text
all 14 jobs succeeded and downloaded        ledger reconciles both ways
credit cost matches the estimate            all 7 configurations QC'd
AOI fully inside every product              geometry consistent (1 CRS, 40 m)
valid data covers the AOI                   coherence usable (median >= 0.30)
unwrapped phase usable over land            connected components sensible
no catastrophic burst-merge seam            duplicate copies reproducible
water mask excludes water                   water mask preserves land
water-mask polarity verified vs ASF docs    MintPy preparation succeeded
MintPy ingestion succeeded                  storage sufficient for production
```

**Production remains BLOCKED.** No production job has been submitted; 7930 credits remain
and production at 10x2 needs 1680.

---

## 2026-09-22 — Phase H: production submitted; retrieval survived an ASF outage

**Production approved by the owner: 1680 credits authorised** for the frozen v1 network
(119 acquisitions / 336 pairs), `INSAR_ISCE_MULTI_BURST`, K=4, `looks=10x2`,
`apply_water_mask=True`. No frozen artefact was modified.

### Pre-flight gates (all required to pass before any spend)

```text
[PASS] verify_freeze.py exit 0
[PASS] test suite: 38 passed
[PASS] 336 payloads validated (K=4, 10x2, water mask, temporal <= 36 d,
       |B_perp| <= 250 m, 1:1 with the frozen pair manifest)
[PASS] all payloads accepted by prepare_insar_isce_multi_burst_job

EXPECTED MISSING JOBS: 336        EXPECTED CREDITS: 1680
```

### Submission — 336/336 in 9 batches of 40 (final batch 16)

Every batch was verified before the next began:

```text
batch 1-8  reconcile remote=ledger, 0 orphans | duplicates clean | delta=200 (expected 200)
batch 9    reconcile remote=336 ledger=336     | duplicates clean | delta=80  (expected 80)

credits 7930 -> 6250 = 1680 consumed, exactly 5 x 336
```

Credit deltas were read from HyP3's own balance, not inferred from the table. Idempotency
used **exact-name local matching only**; `find_jobs(name=<prefix>)` was never called.

### INC-002 — the first retrieval run was killed by a transient ASF outage

Part-way through retrieval, DNS for `hyp3-api.asf.alaska.edu` and
`cumulus.asf.alaska.edu` stopped resolving while `urs.earthdata.nasa.gov` still did. Even
authentication raised, and the run exited with a traceback after 47 of 336 products.

```text
impact         none permanent: the 47 downloaded products and their hashed
               inventory were intact, and retrieval is resumable.
root cause 1   connection and job listing were not retried, so a network blip
               was fatal.
root cause 2   the poll used hyp3.refresh(Batch), which issues one HTTP request
               PER JOB - 336 requests per cycle - maximising exposure to a blip.
fix            connect_hyp3() and fetch_jobs() retry with capped linear backoff
               and raise a typed NetworkUnavailable; the batch is listed in a
               single find_jobs(job_type=...) call; the initial connection WAITS
               for the API (up to --max-outages polls) instead of failing fast;
               transient failures inside the loop rebuild the session.
tests          tests/test_production_retrieval.py (9 offline tests) pins all of
               it, including that find_jobs is never called with name= and that
               the batch is listed in exactly one call.
```

When connectivity returned, **all 336 jobs had reached SUCCEEDED** and the ledger
reconciled with 0 orphans in either direction and no duplicate names.

---

## 2026-09-22 — Phase I: production retrieval complete; MintPy production ingestion verified

**Production retrieval: 336/336 downloaded.** All 336 jobs `SUCCEEDED` (0 failed, 0 expired).

```text
compressed   41.02 GB   (mean 122.09 MB/product)
extracted    42.30 GB   (mean 125.91 MB/product, x1.0313)
total        83.33 GB

product inventory  336 rows, 336 download_ok, 336 unique job ids,
                   all 336 carrying a 64-char ZIP sha256
file inventory     4704 rows (exactly 14 files per product), 336 job ids,
                   2352 hashed (336 x the 7 scientific layers)
layers             all 336 products carry unw_phase, corr, conncomp, dem,
                   lv_theta, lv_phi, water_mask; 0 products missing any
reconciliation     336 expected job names = 336 ledger names, 0 missing, 0 unexpected
                   every frozen pair has exactly one product
duplicate names    none
credits            1680 consumed / 1680 authorised
freeze             verify_freeze.py exit 0
```

`qc/production/PRODUCTION_REPORT.md` records the corpus as **CLEAN**.

### MintPy production preparation

All 336 products (x7 layers = 2352 rasters) clipped onto **one shared target grid**,
`prep_hyp3` metadata written, and MintPy ingestion run.

```text
common overlap   EPSG:32643, [647720, 3129040, 765280, 3225320], 117.6 x 96.3 km
target grid      2939 x 2407 px @ 40 m - one grid for every layer of every pair
AOI              fully inside the common overlap
prep_hyp3        exit 0, 2352 .rsc files
load_data        exit 0 -> production_work/inputs/ifgramStack.h5
                 unwrapPhase (336, 2407, 2939), bperp (336,)
```

**Network reconciliation — MintPy load vs the frozen 336-pair manifest (brief section 24
Stage 2):**

```text
MintPy pairs 336 | manifest pairs 336 | IDENTICAL PAIR SETS: True
MintPy dates 119 | accepted acquisitions 119 | IDENTICAL DATE SETS: True
2025-05-18 absent from the network (v1 policy)
bperp 336 entries, all finite, range -247.8 to 235.3 m (gate <= 250 m)
```

> **Format trap worth recording.** MintPy stores dates as `YYYYMMDD` while the manifests
> use `YYYY-MM-DD`, so a naive set comparison reports 336 pairs in each and **zero**
> overlap — which reads like a catastrophic mismatch but is purely a formatting
> difference. Normalising the format shows the networks are exactly identical. Without
> this check the Stage 2 gate would have been misread as a failure.

### INC-003 — production preparation died on an inventory schema mismatch

The first production preparation run failed before clipping a single raster:

```text
KeyError: Index(['apply_water_mask'], dtype='str')
```

`13_download_production.py` writes a different inventory schema from
`08_download_pilot.py`: the pilot recorded `apply_water_mask`, production did not, and
`select_products()` deduplicated on that column unconditionally.

```text
fix    script 13 now records the column; select_products() derives it from the
       HyP3 job name (the control carries a _nomask suffix) when absent, so a
       schema drift between the pilot and production inventories cannot break
       the pipeline again; the existing 336-row inventory was backfilled.
tests  tests/test_mintpy_prep_selection.py (5 tests)
```

**Also fixed:** the retrieval outage hardening was regression-guarded in
`tests/test_production_retrieval.py` (9 tests), and `importorskip` guards mean each
environment collects what it can import.

```text
delhi-hyp3   47 passed, 1 skipped
delhi-mintpy 43 passed, 1 skipped
```

---

## Current status

```text
Phase B  burst geometry frozen                 COMPLETE (K=4, AOI 100 % covered)
Phase C  historical stack verified             COMPLETE (119 homogeneous acquisitions)
Phase D  SBAS network audited                  COMPLETE (336 pairs, all criteria pass)
Phase E  cost estimated, pilot defined         COMPLETE (1680 credits at 10x2)
         v1 frozen, tests + MintPy env ready   COMPLETE (freeze_id cf2bdbfd...)
Phase F  pilot submitted + retrieved           COMPLETE (14/14 SUCCEEDED)
Phase G  pilot QC and acceptance               COMPLETE (18/18 gates PASSED)
Phase H  production submitted + retrieved      COMPLETE (336/336 SUCCEEDED, 1680 credits)
         production completion report          COMPLETE (corpus CLEAN)
Phase I  MintPy production preparation         COMPLETE (336 ifgs / 119 dates loaded)
Phase J  MintPy inversion and interpretation   NOT STARTED (awaiting instruction)
```

**No scientific inversion has been run.** The loaded network is verified to match the
frozen v1 manifest exactly; the next step is the staged inversion (reference-area
selection, network QC, atmospheric/residual corrections, then LOS displacement and
velocity).

Nothing recovered or inserted 2025-05-18, and all 336 interferograms — including the weak
36-day and monsoon pairs — are retained. Quality-based pair removal, if any, belongs in
MintPy QC now that the production data exist.





