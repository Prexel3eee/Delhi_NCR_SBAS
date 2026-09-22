# Phase III-A1 — Groundwater Data Recovery Gate

Generated 2026-09-22 18:10 UTC.

**Scope.** Determine whether official CGWB *static* resources can supply usable site-level groundwater observations without the unavailable India-WRIS / gwdata portal. No InSAR product, hotspot classification, hypothesis grade or prior result was altered. **No correlation analysis was performed.**

## 1. Corrected access status

| Data class | Previous wording | Corrected wording |
|---|---|---|
| High-frequency DWLR (WIMS / India-WRIS) | "unobtainable" | **ACCESS BLOCKED** |
| Seasonal / periodic CGWB compiled data | (not distinguished) | **AVAILABLE — RECOVERED** |

The two classes were previously conflated. They are different products and only the high-frequency one is blocked.

## 2. Files actually obtained

| File | MB | Season | Year | AOI rows |
|---|---:|---|---:|---:|
| `pre-monsoon_2022_data_for_website.pdf` | 14.6 | pre-monsoon | 2022 | 269 |
| `august_2022_data_for_website.pdf` | 13.6 | august | 2022 | 0 |
| `nov_2022_data_for_website.pdf` | 15.0 | november | 2022 | 263 |
| `jan_2023_data_for_website.pdf` | 14.3 | january | 2023 | 167 |

**Official source.** All four are official CGWB files, referenced from the CGWB "Ground Water Level Monitoring" page:

```text
https://cgwb.gov.in/sites/default/files/inline-files/<file>
```

The live host currently returns **HTTP 502 Bad Gateway** (`www.cgwb.gov.in` does not resolve at all), so the files were retrieved through the Internet Archive's copy **of that exact official URL**. The archive URL is recorded per file in `groundwater_source_inventory.csv`. This is provenance discovery against the official file, not a third-party mirror, and no third-party-edited copy was used.

## 3. Schema audit

| Field | Present |
|---|---|
| station / site name | **yes** |
| latitude | **yes** (decimal degrees, 5–7 dp) |
| longitude | **yes** |
| district | **yes** |
| well type | **yes** (Dug Well / Bore Well; blank in some rows) |
| depth to water level | **yes**, in **mbgl** |
| season + year | **yes** |
| CGWB station code | **no** |
| exact measurement date | **no** — season and year only |
| aquifer / well depth metadata | **no** |

The data are **station-level with reproducible coordinates**, not aggregated. That is the decisive schema question and it resolves positively.

## 4. Station registry

| Property | Value |
|---|---:|
| unique stations within the AOI (+0.25°) | **612** |
| stations with ≥2 of the 4 seasons | 87 |
| stations with all 4 seasons | 0 |

States represented: Delhi, Haryana, Uttar Pradesh. The registry was built **before** any relationship to H001–H004 was examined.

## 5. Distance to the hotspots

| Band | Stations | H001 | H004 | H002 | H003 |
|---|---:|---:|---:|---:|---:|
| ≤ 2 km | **0** | 0 | 0 | 0 | 0 |
| 2–5 km | 15 | 0 | 6 | 6 | 5 |
| 5–10 km | 76 | 28 | 28 | 51 | 60 |
| 10–20 km | 229 | 174 | 177 | 162 | 176 |

**No CGWB station lies within 2 km of any hotspot**, and only 15 lie within 5 km. H001 — the strongest and largest zone — has **no station inside 5 km**. Any hotspot-level groundwater test would rest on stations 5–20 km away, where the groundwater field cannot be assumed uniform.

## 6. Temporal sampling

* CGWB design frequency: **4 observations per year** (January, pre-monsoon, August, November). This is the native resolution and is preserved.
* Obtained: **4 of 4 seasonal slots, but only for 2022 and 2023** — one full annual cycle (pre-monsoon 2022 → August 2022 → November 2022 → January 2023).
* **No interpolation to monthly values was performed, and none will be.** Four seasonal observations are four observations; calling them a monthly series would manufacture resolution that does not exist.

## 7. 2021–2025 completeness

| Requirement | Status |
|---|---|
| study period | 2021-10-01 .. 2025-09-30 |
| seasonal files for 2021 | **not obtainable** |
| 2022 | **obtained** (3 of 4 seasons) |
| 2023 | **obtained** (January only) |
| 2024 | **not obtainable** |
| 2025 | **not obtainable** |
| coverage complete | **NO** |

The archive holds the 2022 and early-2023 seasonal files; later volumes are not present in it and the live CGWB host is down. A 2024 volume (`volume_24_jan_to_mar_2024_web.pdf`) exists in the archive but is a bulletin, not the station-level seasonal table, and was not used.

## 8. Final classification

```text
GROUNDWATER:
    PARTIALLY TESTABLE — SEASONAL SITE DATA ONLY
```

This is option **B**. It is not option C, because genuine station-level data with coordinates and measurements were recovered; and it is not option A, because the recovered data support only seasonal, single-cycle, decametre-distance analysis, not monthly or hotspot-localised analysis.

### What this does and does not permit

**Permitted at this resolution:**
* spatial comparison of groundwater depth between the 5–10 km and 10–20 km bands around the supported zones and around the negative controls;
* a one-cycle seasonal amplitude comparison (pre-monsoon → monsoon → post-monsoon → winter) between those bands;
* a check of whether any spatial contrast in groundwater depth distinguishes H001/H004 from H002/H003 — which is the constraint Phase III-A identified as central.

**Not permitted:**
* any monthly or high-frequency temporal coupling claim;
* any statement about groundwater *trend* over the study period — one annual cycle cannot yield a trend;
* any hotspot-localised claim, since no station is within 2 km and H001 has none within 5 km;
* treating the four seasonal observations as a continuous time series.

*The groundwater hypothesis is therefore no longer UNTESTABLE, but it is not yet well-testable either. The binding limits are now the 5–20 km station distance and the single available annual cycle.*

## 9. What was not done

No geology, urban-loading, land-cover or GRACE analysis was begun. No causal narrative was written. H005 was not used for anything.
