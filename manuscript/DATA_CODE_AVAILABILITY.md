# Data and Code Availability

## Code

All processing, validation, hypothesis-testing and synthesis scripts are in
`scripts/` (70 scripts, numbered by phase). Tests are in `tests/`.

## Processed products

| Product | Location | Freeze |
|---|---|---|
| Ascending authoritative relative LOS solution | `mintpy/baseline_raw_work/` | `product_v1` |
| Ascending published rasters | `products/product_v1/` | derived from `product_v1` |
| Descending raw solution | `mintpy/descending_work/` | `descending_raw_v1` |
| Descending unwrap-corrected candidate | `mintpy/descending_d2_unwrap_work/` | `descending_v2_candidate` |

## External datasets

| Dataset | Source | Access |
|---|---|---|
| Sentinel-1 SLC bursts | ASF / HyP3 | public, credentialed |
| ERA5 | Copernicus CDS | public, credentialed |
| CGWB seasonal groundwater | CGWB via Internet Archive | public; **archived copy of the official URL**, live host was down |
| NWDP six-hourly groundwater telemetry | nwdp.nwic.gov.in | public |
| SoilGrids v2.0 | ISRIC | public |
| GHSL GHS-BUILT-S | JRC | public |
| ESA WorldCover | ESA / AWS Open Data | public |

## Reproducibility notes

* Every freeze is hash-pinned and verified by a companion script.
* Large products are hashed in place rather than duplicated.
* The ascending product was frozen before any interpretation; hypothesis
  protocols were frozen before their correlations existed.

## Limitations on reuse

The published velocity fields are **relative LOS** quantities, not absolute
velocities and not vertical displacement. Users requiring absolute rates must
supply an independent reference; the reference-selection systematic is
4.78 mm/yr.
