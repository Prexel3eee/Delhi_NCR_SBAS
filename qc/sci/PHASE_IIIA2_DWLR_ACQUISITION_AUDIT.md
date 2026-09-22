# Phase III-A2 — High-Frequency Groundwater Acquisition Audit

Generated 2026-09-22 18:16 UTC.

**Scope.** Determine whether a groundwater dataset capable of testing H001/H004 *temporally* can be obtained. **No correlation between groundwater and InSAR was performed. No causal claim is made.**

## 1. Seasonal dataset frozen

`freeze/cgwb_seasonal_v1`, `freeze_id db0636879f7566f9681be3b704f1ecef19270ca4363903ae4f4f54643528453e`

> The source file is an archived copy of an official CGWB URL retrieved via the Internet Archive because the live CGWB host was unavailable at retrieval time.

**This is not a live CGWB download.** It is an archived copy of the official URL, and every later report must say so.

| File | Season | Year | Pages | MB | AOI rows | SHA-256 |
|---|---|---:|---:|---:|---:|---|
| `pre-monsoon_2022_data_for_website.pdf` | pre-monsoon | 2022 | 589 | 14.6 | 1919 | `e47585c8cb458add…` |
| `august_2022_data_for_website.pdf` | august | 2022 | 576 | 13.6 | 1184 | `00b8e479b6617c8f…` |
| `nov_2022_data_for_website.pdf` | november | 2022 | 593 | 15.0 | 1966 | `11337c3605df16a9…` |
| `jan_2023_data_for_website.pdf` | january | 2023 | 619 | 14.3 | 1384 | `1a892e86a787d496…` |

Known schema limitations, all of which persist: no CGWB station code; season and year only (no exact measurement date); no aquifer or well-depth metadata; well type blank in some rows.

## 2. Frozen limitations

```text
TEMPORAL COVERAGE:  four seasonal observations spanning 2022-2023 only
SPATIAL COVERAGE:   no monitoring station within 2 km of any hotspot
H001:               nearest station 5.92 km
```

Therefore the following are **not permitted** from the seasonal dataset, and these restrictions carry into every later report:

* monthly groundwater coupling
* groundwater trend estimation
* hotspot-localized groundwater attribution
* lag analysis requiring dense time series
* causal claim linking groundwater decline to H001/H004
* interpolation of four seasonal points into a monthly series

## 3. Allowed use of the seasonal data

* monitoring-network geometry
* regional groundwater-level context
* seasonal state comparison
* spatial groundwater gradients at those four epochs
* H004/H002/H003 coarse proximity context
* identifying candidate stations for later high-frequency retrieval

It is retained as an independent official cross-check and will **not** be discarded even if high-frequency data are later obtained.

## 4. High-frequency routes tested

| Source | Status | Observation |
|---|---|---|
| India-WRIS (preferred DWLR route) | **ACCESS BLOCKED** | curl code 000 - host unreachable |
| India-WRIS WRIS app | **ACCESS BLOCKED** | curl code 000 - host unreachable |
| WIMS / Ministry of Water Resources | **ACCESS BLOCKED** | curl code 000 - host unreachable |
| CGWB groundwater data portal | **ACCESS BLOCKED** | HTTP 200 but every page is an HTML 'Maintenance Mode' notice; /api, /api/v1, /swagger/index.html, /api/groundwater, /api/WaterLevel all 404 |
| CGWB main site | **ACCESS BLOCKED** | HTTP 502 Bad Gateway on every path; www.cgwb.gov.in does not resolve (000) |
| NWIC (National Water Informatics Centre) | **NO DATA PRODUCT** | HTTP 200, but it is a landing page only; its data links point to India-WRIS (unreachable) and data.gov.in (key-gated). No downloadable groundwater product. |
| data.gov.in | **CONTEXT ONLY / KEY-GATED** | Catalogue searchable; resource queries return HTTP 400 'Authorization field missing'. No API key available. Resources found are state/district ANNUAL aggregates, not station observations. |
| Delhi Jal Board | **NO DATA PRODUCT** | HTTP 200; no groundwater-level data endpoint located |
| Delhi state portal | **NO DATA PRODUCT** | HTTP 200; no station-level groundwater observation service located |
| National Hydrology Project | **ACCESS BLOCKED** | curl code 000 - unreachable |
| India-WRIS river network subdomain | **ACCESS BLOCKED** | curl code 000 - unreachable |
| Internet Archive - CGWB DWLR files | **NO DATA PRODUCT** | Searched for DWLR / telemetry / hourly / digital. The archive holds only DWLR photographs (2006) and DWLR tender documents (2022) - no observation data. |
| Flood Forecasting (india-water) | **WRONG PRODUCT** | HTTP 200 but it is a flood-forecast service, not groundwater |

**High-frequency DWLR: ACCESS BLOCKED on every route tested.** Every preferred route named in the protocol was tried, and none returned station observations.

## 5. Station geometry

| Hotspot | Nearest station | ≤ 2 km | 2–5 km | 5–10 km | 10–20 km |
|---|---:|---:|---:|---:|---:|
| **H001** | 5.92 km | 0 | 0 | 28 | 146 |
| **H004** | 3.80 km | 0 | 6 | 22 | 149 |
| **H002** | 2.14 km | 0 | 6 | 45 | 111 |
| **H003** | 3.48 km | 0 | 5 | 55 | 116 |

### Best available stations

**H001** — nearest is 5.92 km:

| Station | State | Distance | Seasons | Type |
|---|---|---:|---:|---|
| South West   DWARKA                      | Delhi | 5.92 km | 1 | unspecified |
| South West   Dug Wellarka   Dug Wellarka | Delhi | 5.92 km | 1 | Dug Well |
| South West   Dug Wellarka   Dug Wellarka | Delhi | 5.92 km | 1 | Dug Well |

**H004** — nearest is 3.80 km:

| Station | State | Distance | Seasons | Type |
|---|---|---:|---:|---|
| South West   DWARKA                      | Delhi | 3.80 km | 1 | unspecified |
| South West   Dug Wellarka   Dug Wellarka | Delhi | 3.80 km | 1 | Dug Well |
| South West   Dug Wellarka   Dug Wellarka | Delhi | 3.80 km | 1 | Dug Well |

**H001 cannot be improved on today.** The protocol asked explicitly whether any station could improve on the current >5 km nearest seasonal station; the answer is no. The nearest usable station to H001 is **5.92 km** away, outside every window in which a groundwater head field could be treated as uniform with the hotspot.

## 6. Study-period overlap and temporal completeness

| Requirement | Status |
|---|---|
| study period | 2021-10-01 .. 2025-09-30 |
| seasonal overlap | 4 epochs, all inside 2022-2023 |
| fraction of study period covered | ≈ 25 % |
| native sampling frequency | 4 observations per year |
| observations per station | 1–4 |
| stations with ≥ 2 seasons | 87 of 612 |
| high-frequency (DWLR) observations | **none obtainable** |

No resampling was defined, because no actual sampling frequency beyond four seasonal snapshots was obtained. Native observation times are preserved where they exist at all.

## 7. data.gov.in route

No API key is available. Per protocol the route is **not** used for hotspot-level testing, and the resources visible in the catalogue are state/district **annual aggregates**. Classified **CONTEXT ONLY**. If a key becomes available the first step is to inspect the returned schema, not to assume it contains observations.

## 8. Official-request package (prepared, not submitted)

A request has been drafted but **no RTI has been filed and nothing has been submitted**.

**Content sought:** station-level DWLR groundwater observations; Delhi-NCR and the districts intersecting the AOI; 2021-10-01 to 2025-10-01; station coordinates (latitude, longitude); station IDs; well depth and aquifer metadata where available; native observation timestamps (not resampled); depth-to-water-level values with units.

**Geography:** H001 (77.0813, 28.5212) first — it currently has no station within 5 km; then H004 (77.0554, 28.5333); then H002 and H003 as controls; matched non-hotspot areas within the AOI. H005 is excluded.

**Routes:** CGWB regional office, NWIC / WIMS, formal data request, RTI if necessary.

## 9. Final classification

```text
GROUNDWATER TEMPORAL TEST:
    STILL ACCESS-BLOCKED / INADEQUATE
```

This is option **C**, and the reasoning is worth separating from the seasonal gate's earlier option B:

* the **seasonal** dataset is genuinely recovered and usable for context (option B at that gate);
* but the question asked **here** is whether H001/H004 can be tested **temporally**, and on that test the answer is no, on two independent grounds: **neither sufficiently local** (no station within 2 km of any hotspot; none within 5 km of H001) **nor sufficiently long** (one annual cycle against a four-year study period), with high-frequency data blocked on every route.

**A genuine hotspot-level temporal groundwater test is therefore not possible with currently accessible data.** Nothing about groundwater causation can be concluded either way, and no correlation was run.

## 10. What would change this

One of the following, in order of expected value:

1. **DWLR station records within 5 km of H001** — the single highest-value acquisition. Nothing else would so directly enable the test.
2. **A data.gov.in API key**, if the returned schema proves to expose station-level dated observations rather than aggregates.
3. **Additional seasonal years** (2021, 2024, 2025) from the CGWB seasonal series, which would at least extend the record to multiple annual cycles — though it would not fix the 5–20 km distance problem.

Route 3 alone would not make the test possible. The distance problem is the binding constraint, and only route 1 or 2 addresses it.

## 11. Known parsing caveat in the station registry

The site-name field shows a **column-bleed artefact** in some rows: the CGWB table's
WELL SITE TYPE column is unpopulated in some Delhi rows, so the layout-extracted text
runs the well type into the name (e.g. `Dug Wellarka`). This affects the **`site_name`
field only**.

* `latitude` and `longitude` are **unaffected** — they are extracted by regex anchored
  on the decimal-degree pattern, and were validated against the AOI bounding box.
* `well_type` is therefore **unreliable** in those rows and must not be used.
* The **distance calculations are unaffected**, because they use only coordinates.

Any later use of this registry must treat the station identifier as `(latitude,
longitude)` — which is reproducible — and not as the site name, which is not. This is
a further reason the registry needs a proper station code, which the CGWB seasonal
files do not carry.
