# Pilot Acceptance Report

Generated: 2026-09-22T00:06:59.541560+00:00

## Verdict: **PILOT ACCEPTED**

18/18 gates passed. Production remains **blocked** pending explicit approval.

## Gates

| # | Gate | Result | Observed | Expected | Source |
|---|---|---|---|---|---|
| 1 | `all_pilot_jobs_reached_terminial_and_succeeded` | PASS | "14/14 downloaded" | 14/14 SUCCEEDED and downloaded | `manifests/product_inventory.csv` |
| 2 | `ledger_reconciles_with_remote_truth` | PASS | "ledger=14 remote=14 only_ledger=0 only_remote=0" | bidirectional coverage, 0 orphans | `qc/pilot/ledger_reconciliation.json` |
| 3 | `credit_cost_matches_the_estimate` | PASS | "{'5': 14} total=70" | 5 credits/job (K=4 @ 10x2), 70 total | `HyP3 job metadata (credit_cost)` |
| 4 | `qc_covered_all_unique_configurations` | PASS | 7 | 7 unique scientific configurations | `qc/pilot/pilot_qc.json` |
| 5 | `aoi_fully_inside_every_product` | PASS | [true, true, true, true, true, true, true] | True for all | `qc/pilot/pilot_qc.json` |
| 6 | `product_geometry_consistent` | PASS | {"crs": ["EPSG:32643"], "pixel_size_m": ["40.0"]} | one CRS, 40 m pixel spacing (10x2) | `qc/pilot/pilot_qc.json` |
| 7 | `valid_data_covers_the_aoi` | PASS | [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] | >= 0.99 of AOI pixels carry valid data | `qc/pilot/pilot_qc.json` |
| 8 | `coherence_usable_across_all_configs` | PASS | {"min": 0.4075, "values": [0.7188, 0.8169, 0.8169, 0.7925, 0.4242, 0.4075, 0.5075]} | median coherence >= 0.30 for every configuration | `qc/pilot/pilot_qc.json` |
| 9 | `unwrapped_phase_usable_over_land` | PASS | [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] | >= 0.99 of AOI *land* pixels unwrapped (water excluded by design) | `qc/pilot/pilot_qc.json` |
| 10 | `connected_components_sensible` | PASS | {"largest_component_fraction_min": 0.600088, "components": [1, 2, 3, 2, 6, 8, 1]} | largest component >= 0.50 of the AOI in every configuration | `qc/pilot/pilot_qc.json` |
| 11 | `no_catastrophic_burst_merge_seam` | PASS | {"max_coherence_residual": 0.1015, "max_flagged_rows": 31} | coherence residual < 0.25 and < 5% of rows flagged | `qc/pilot/pilot_qc.json (seam check)` |
| 12 | `duplicate_copies_are_reproducible` | PASS | "7 configurations compared, all_identical=True" | every layer bit-identical between duplicate submissions | `qc/pilot/reproducibility.json` |
| 13 | `water_mask_excludes_water_from_unwrapping` | PASS | {"water_masked_valid": 0.0, "water_unmasked_valid": 0.743416} | water pixels have 0 valid unwrapped phase when masked, > 0.5 when not | `qc/pilot/water_mask_comparison.json` |
| 14 | `water_mask_does_not_remove_land` | PASS | {"land_masked_valid": 0.604778, "land_unmasked_valid": 0.604778} | land valid fraction unchanged by masking | `qc/pilot/water_mask_comparison.json` |
| 15 | `water_mask_polarity_verified_against_asf_docs` | PASS | "0 = water, 1 = land (HyP3 product convention; opposite of ASF reference tiles)" | 0 = water, 1 = land per https://hyp3-docs.asf.alaska.edu/water_masking/ | `qc/pilot/water_mask_comparison.json` |
| 16 | `mintpy_preparation_succeeded` | PASS | "prep_hyp3 exit=0 rsc=42" | prep_hyp3 exit 0 with .rsc metadata written | `mintpy/pilot_ingestion_report.json` |
| 17 | `mintpy_ingestion_succeeded` | PASS | {"exit": 0, "interferograms": 6, "dates": 11} | load_data exit 0 with 6 interferograms loaded | `mintpy/pilot_ingestion_report.json` |
| 18 | `storage_sufficient_for_production` | PASS | {"projected_grand_total_gb": 147.83, "free_disk_gb": 555} | projected total < 60% of 555 GB free | `qc/pilot/storage_estimate.json` |

## Pilot summary

- Jobs submitted: 14 (7 unique configurations x 2 copies; the duplicate was INC-001)
- Products downloaded: 14/14
- Credits charged (HyP3-reported): 70
- Unique configurations QC'd: 7

## Reproducibility

All duplicate pairs were compared layer-by-layer: **all_identical = True**. HyP3 multi-burst processing is deterministic, so the accidental duplicate submission became a genuine determinism test.

## Water-mask decision

| region | metric | masked | unmasked |
|---|---|---|---|
| water | valid unwrapped fraction | 0.0 | 0.743416 |
| land | valid unwrapped fraction | 0.604778 | 0.604778 |

Masking removes water from unwrapping completely and leaves land unchanged, so **`apply_water_mask = True` is recommended for production**.

## Storage

- Measured: zip mean 123.0 MB, extracted mean 126.8 MB (x1.031)
- Projected for 336 pairs: zip 41.31 GB, extracted 42.61 GB, MintPy working 63.91 GB
- **Grand total 147.83 GB** against 555 GB free

## MintPy ingestion

- `prep_hyp3.py`: exit 0 (42 .rsc files)
- `smallbaselineApp.py --dostep load_data`: exit 0
- Loaded 6 interferograms over 11 acquisition dates

This is a loadability test. The pilot pairs are not a connected time series, so a full SBAS inversion is not attempted at this stage.

## Production recommendation

- looks: **10x2 (40 m)**, `apply_water_mask = True`
- 336 pairs, **1680 credits** (21% of the monthly allocation)
- projected storage **147.83 GB**
- **NOT submitted.** Awaiting explicit owner approval.

## Known limitations

- The seam detector cannot distinguish a burst merge seam from a real east-west scene feature (river, road, land-use boundary); its verdict is supporting evidence, not proof.
- Edge-versus-interior validity is not informative for a merged multi-burst mosaic (the bounding box includes nodata corners); it is reported for completeness only.
- The network in this pilot is deliberately tiny and disconnected; time-series connectivity is a Phase H property of the full {PRODUCTION_PAIRS}-pair stack.
- The 2025-05-18 acquisition remains excluded from v1 (documented CMR serving anomaly).
