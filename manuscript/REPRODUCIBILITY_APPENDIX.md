# Reproducibility Appendix

All results derive from frozen inputs. Final evidence freeze `freeze/final_evidence_v1`, `freeze_id db329cf47f4bef92a020056e608decbf95644463f8148570478128d2861c9e88`.

## Upstream freezes

| Freeze | ID |
|---|---|
| v1 | `cf2bdbfd4fa722dd0df9608afba13bf7` |
| mintpy_input_v1 | `0cbe4c4f38b8a20f38b2cb71d135ec80` |
| product_v1 | `2a1304e3521f1e176fba7e05814ae1e7` |
| phase1_observations | `122781a4a81bd49eb4781c7682cff7b3` |
| descending_network_v1 | `8f9eee9a6bdead7a6c8a80e45a32c8df` |
| descending_raw_v1 | `acdb209f443732f4f7c5f7f3f624fd63` |
| phase2a_results | `09017dc3895f4c66ad68004934a634bf` |
| phase2b_closeout_v1 | `16d36635a06d30182e0e5c8485c3f156` |
| descending_v2_candidate | `ba99df90a6f15b3aaaf90fe3042511dd` |
| cgwb_seasonal_v1 | `db0636879f7566f9681be3b704f1ecef` |
| nwdp_telemetry_v1 | `731040b8ebdf56e20832de2ef32c4b50` |
| groundwater_protocol_v1 | `152fa51ca8b656d1bfab8b0e02660b48` |

## Incidents that could have changed a scientific conclusion

Engineering detail is archived in `RUNLOG.md` and `provenance/errata/`. Only incidents with scientific consequence appear here.

| ID | Incident | Consequence |
|---|---|---|
| INC-001 | `find_jobs(name=...)` is an exact match; a prefix query returns nothing | duplicate pilot jobs; retrieval now uses exact-name reconciliation only |
| INC-002 | transient ASF DNS outage killed retrieval at 47/336 | retrieval made resumable with backoff and batched listing |
| INC-004 | `np.bool8` removed in NumPy 2 broke the dask cluster | parallel inversion would not start |
| INC-005 | first RAW-vs-ERA5 comparison read the wrong file | spurious 15.49 mm/yr; corrected to 0.52 mm/yr RMS |
| INC-006 | GNSS co-location "disagreement" was a window artefact | verdict survived, but for a more honest reason: coverage, not measurement quality |
| INC-007 | `product_v1` referenced to a different pixel than the frozen decision | constant 0.136 mm/yr; spatial gradients unaffected. Documented as an append-only erratum |
| INC-008 | Phase-I hotspot polygons were single-pixel fragments | **every polygon-based containment test in Phase II was vacuous** until corrected; the conclusion held once re-tested |

## Verification

```text
python scripts/69_phase4_synthesis.py --verify
python scripts/65_phase3a4_protocol.py --verify
python scripts/verify_freeze.py
python scripts/verify_mintpy_input_v1.py
python scripts/verify_product_v1.py
python scripts/verify_phase1_observations.py
```

All exit 0 against the frozen state.
