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

## Current status

```text
Phase B  burst geometry frozen                 COMPLETE (K=4, AOI 100 % covered)
Phase C  historical stack verified             COMPLETE (119 homogeneous acquisitions)
Phase D  SBAS network audited                  COMPLETE (336 pairs, all criteria pass)
Phase E  cost estimated, pilot defined         COMPLETE (1680 credits at 10x2; pilot 35)
         v1 frozen, tests + MintPy env ready   COMPLETE (freeze_id cf2bdbfd…)
Phase F  pilot submitted                       COMPLETE (14 jobs RUNNING; 70 credits)
Phase G  production submission                 BLOCKED (pilot QC + explicit approval)
Phase H  MintPy ingestion / inversion          NOT STARTED (env ready, no products yet)
```

**Next actions**

1. Wait for the pilot jobs to finish, then download and extract products (14-day retention).
2. Run pilot QC (AOI coverage, coherence, unwrapped phase, connected components,
   water-mask on/off comparison at the Yamuna).
3. Estimate on-disk size from real pilot products.
4. Seek explicit approval for the 1680-credit production run at 10x2.
5. Rotate the Earthdata credentials at leisure.


