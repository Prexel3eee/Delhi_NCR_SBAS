# Delhi-NCR SBAS-InSAR — HyP3 Multi-Burst + MintPy

Sentinel-1 ascending SBAS-InSAR workflow for the Delhi-NCR AOI, using ASF HyP3
`INSAR_ISCE_MULTI_BURST` for interferogram generation and MintPy for time-series
inversion.

**Current state: v1 frozen (119 acquisitions / 336 pairs). No HyP3 job has been submitted.**

| Phase | Description | Status |
|---|---|---|
| B | Geographic reference burst selection | ✅ frozen, K=4, AOI 100 % covered |
| C | Historical burst stack + acquisition×burst matrix | ✅ 119 homogeneous acquisitions |
| D | Burst-level SBAS network + audit | ✅ 336 pairs, all acceptance criteria pass |
| — | **v1 production freeze** | ✅ `freeze_id cf2bdbfd…`, 21 artefacts, read-only |
| — | Regression tests + MintPy/QC environment | ✅ 20 tests pass, `delhi-mintpy` ready |
| E | Credit estimate + pilot selection | ✅ 1680 credits @ 10x2; pilot 35 credits |
| F | Pilot submission | ⛔ **blocked on Earthdata credentials** |
| G | Production submission | ⬜ blocked on pilot QC + explicit approval |
| H | MintPy ingestion / inversion | ⬜ env ready, awaiting products |

See `RUNLOG.md` for the full evidence trail and `state/project_state.json` for
machine-readable status.

## Frozen baseline (v1)

```text
freeze_id    cf2bdbfd4fa722dd0df9608afba13bf7cd9361a0897dea14ea70e724c8b1924d
snapshot     freeze/v1/   (21 artefacts, 11 critical, read-only)
               119 accepted acquisitions / 336 pairs / K=4
               2025-05-18 excluded fail-closed — NOT to be recovered for v1

verify       python scripts/verify_freeze.py
```

`verify_freeze.py` checks the snapshot hashes *and* that the live `manifests/` still
match the frozen baseline. It exits non-zero on drift, which is the realistic accident:
re-running `03`/`04` silently changes the network a paid submission would use. The same
guarantee is wired into the test-suite, so an accidental re-run fails CI.

## Frozen scientific inputs

```text
AOI          geometry/aoi.geojson   (hash-verified against the handoff manifest)
Period       2021-10-01 -> 2025-10-01  (usable: 2021-10-06 -> 2025-09-27)
Orbit        ASCENDING, relative orbit 27, VV, IW
Bursts       027_056011_IW2, 027_056012_IW2, 027_056013_IW2, 027_056014_IW2  (K=4)
Platform     Sentinel-1A only (homogeneous)
Network      temporal <= 36 d, |B_perp| <= 250 m
```

## Key results

```text
Acquisitions accepted        119   (1 excluded: 2025-05-18, CMR serving anomaly)
Interferograms               336
Connected components         1
Bridges / articulation pts   0 / 0
Degree min/mean/median/max   3 / 5.6471 / 6 / 6
|B_perp| median / p95 / max  70 m / 186 m / 248 m

Production credits @ 10x2    1680  (21.00 % of the 8000/month Basic allocation)
Production credits @ 20x4     336
Production credits @ 5x1     5040
Pilot                        7 jobs / 35 credits
```

Two findings are worth highlighting:

* The originally hand-entered **K=3 burst set does not cover the AOI** (0.369 %
  uncovered at the north-west corner). The minimum valid collection is **K=4**. The AOI
  was not shrunk to preserve K=3.
* Because K=4 crosses the 10x2 credit tier boundary, cost per job rises from 1 to
  **5 credits** (5×). At 20x4, K=4 still costs 1 credit.

## Environment

Two conda environments, deliberately separated so MintPy's GDAL pins cannot perturb the
search/submission stack:

```bash
conda activate delhi-hyp3     # python 3.12, asf_search 14.0.0, hyp3_sdk 7.7.8  (phases B-F)
conda activate delhi-mintpy   # python 3.11, mintpy 1.6.4, gdal 3.12.3         (phases G-H)
```

Pinned in `env/` (`*.yml` plus `*-requirements-lock.txt`).

No NASA Earthdata credentials are needed for Phases B–E. All metadata access is
anonymous. Credentials are required only for pilot/production submission and download,
and must be supplied interactively or via a protected `.netrc` kept out of version
control. **No secret material is stored in this repository.**

## Tests

```bash
python -m pytest tests/          # 20 tests, offline, no credentials required
```

* `tests/test_asf_client_regressions.py` — pins the three ASF/CMR silent-failure modes
  (see below) so a refactor cannot quietly remove the guards.
* `tests/test_freeze_v1_invariants.py` — pins the v1 decision (119/336/K=4, 2025-05-18
  not recovered, no unfrozen burst in any pair, production not submitted) and fails if
  critical artefacts drift from the freeze.

Both suites pass in either environment (the regression tests are pure-Python and mock all
I/O).

## Pipeline

Run in order. Each script is idempotent and re-runnable.

```bash
python scripts/01_verify_bursts.py            # seed-burst sanity check
python scripts/02_select_reference_bursts.py  # Phase B -> geometry/ + burst manifest
python scripts/03_inventory_bursts.py         # Phase C -> acquisition x burst matrix
python scripts/04_build_sbas_network.py       # Phase D -> sbas_pairs.csv + network audit
python scripts/05_estimate_hyp3_cost.py       # Phase E -> cost + pilot (no submission)
```

`scripts/asf_client.py` is the shared ASF/CMR access layer. It exists because the
metadata APIs have three silent-failure modes that would corrupt an SBAS network; each
is guarded and documented in the module docstring:

1. `asf_search.search()` intermittently raises `ASFSearchError` (empty CMR message) for
   valid windows.
2. CMR's `POLARIZATION` attribute filter reports more hits than it serves, silently
   omitting a granule.
3. `ASFProduct.stack()` returns truncated stacks with `searchComplete=False`, and
   `check_reference` silently substitutes a different baseline reference when the fixed
   reference is absent from the search window.

## Layout

```text
config/       project + frozen pilot configuration
geometry/     AOI, selected burst footprints, coverage report
manifests/    frozen burst list, acquisition matrix, accepted/excluded, pairs, pilot
qc/inventory/ inventory provenance incl. the documented CMR anomaly
qc/network/   network audit, baselines, baseline-time and degree plots
qc/cost_estimate.json
state/        project_state.json
scripts/      the pipeline
data/         (empty) hyp3_zips / hyp3_extracted / mintpy
```

## Next step

1. Provide Earthdata credentials.
2. Approve the 7-job pilot (35 credits).
3. Submit pilot, download products, run pilot QC (AOI coverage, coherence, unwrapped
   phase, connected components, water-mask comparison).
4. Estimate on-disk size from real pilot products, then seek approval for the
   1680-credit production run at 10x2 / 40 m.

## Known open items

* **`027_056011_IW2` on 2025-05-18** — CMR reports the granule in its hit count but does
  not serve it (the VV granule was observed once and never reproducibly again). The
  acquisition is excluded fail-closed, giving 119 rather than 120 acquisitions.
  Re-check CMR before production. Evidence in `qc/inventory/inventory_provenance.json`
  and `RUNLOG.md`.
* Re-check the live HyP3 credit table immediately before any large submission.
* LOS velocity must not be reported as vertical subsidence without explicit geometric
  justification.
