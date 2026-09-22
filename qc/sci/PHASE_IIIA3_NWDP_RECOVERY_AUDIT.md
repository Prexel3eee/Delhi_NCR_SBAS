# Phase III-A3 — National Water Data Portal Recovery Audit

Generated 2026-09-22 18:21 UTC.

**Scope.** Determine whether NWDP telemetry can support a hotspot-level groundwater temporal test. **No correlation between groundwater and InSAR was performed.** The audit stops at the station and coverage stage.

## 1. Files acquired — live official NWDP downloads

The portal is a **CKAN** instance, so it exposes a full API (`/api/3/action/package_search`, `package_show`, `datastore_search`). Both target resources were retrieved directly. **These are live official downloads, not archival copies** — unlike the CGWB seasonal files.

| Key | Producer | Resource | MB | HTTP | SHA-256 |
|---|---|---|---:|---|---|
| `delhi_sw_gw` | Delhi SW GW | Ground Water Level Delhi_SW_GW Delhi (2021 - 2 | 21.06 | 200 | `46080222a2164bffdf8f…` |
| `cgwb_delhi` | CGWB | Ground Water Level CGWB Delhi (2021 - 2025) Te | 33.94 | 200 | `30ecd97e19a3380489ed…` |

Portal metadata last modified: `2026-09-22T00:32:14.179407`. Frozen as `freeze/nwdp_telemetry_v1`, `freeze_id 731040b8ebdf56e20832de2ef32c4b5056372a409c8039e298ee69179de2b4b5`.

## 2. Actual sampling interval — from timestamps, not the title

The dataset *page* is titled "Telemetry - Hourly" while the resource is labelled "Telemetry Six Hourly". The timestamps decide:

| Quantity | Value |
|---|---:|
| median interval | **6.0 h** |
| mode interval | **6 h** |
| minimum | 0.017 h |
| maximum | 29015.0 h |

**The resource label is correct and the page title is not: the data are six-hourly.**

## 3. Schema audit

| Field | Present |
|---|---|
| station identifier | **name only** — no explicit CGWB/NWDP station code |
| station name | yes |
| latitude / longitude | **yes**, decimal degrees to 8 dp |
| timestamp | **yes**, `Data Acquisition Time`, DD-MM-YYYY HH:MM |
| groundwater level | **yes**, metres |
| unit | metres |
| administrative hierarchy | **yes** — State/District/Tehsil/Block/Village LGD codes |
| producer | yes (`Agency`) |
| well depth / aquifer metadata | **no** |

Coordinates are present **in the observation table itself**, so no separate station metadata join was required.

## 4. Telemetry station registry

| Producer | Stations | Median observations | Median interval |
|---|---:|---:|---:|
| cgwb_delhi | 91 | 2748 | 6.00 h |
| delhi_sw_gw | 96 | 1909 | 6.00 h |
| **total** | **187** | | |

Stations were **not** merged on proximity; the registry is keyed on `(producer, station_name)`.

## 5. Distance gate — the decisive test

| Hotspot | Nearest | ≤ 1 km | ≤ 2 km | 2–5 km | 5–10 km | 10–20 km |
|---|---:|---:|---:|---:|---:|---:|
| **H001** | 2.06 km | 0 | 0 | 2 | 14 | 55 |
| **H004** | 1.97 km | 0 | 2 | 2 | 15 | 57 |
| **H002** | 0.97 km | 1 | 1 | 6 | 31 | 58 |
| **H003** | 0.81 km | 1 | 2 | 7 | 34 | 59 |

### Does NWDP provide a station within 5 km of H001? **YES** — 2 stations.

| Station | Producer | d H001 | d H004 | n | Coverage | Zeros | Constant | Max gap | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| New Delhi Mungeshpur Mungeshpur | delhi_sw_gw | 2.06 | 1.97 | 3852 | 85.1% | 0.0% | 1.4% | 1890 h | **USABLE** |
| New Delhi Salahpur Salahpur | delhi_sw_gw | 2.08 | 1.98 | 3497 | 84.7% | 0.0% | 22.0% | 1878 h | **USABLE** |

**Both stations within 5 km of H001 are clean** (0 % zeros, low constant fraction) — they are *not* among the flagged stations. This improves on the seasonal dataset's 5.92 km. The seasonal figure remains valid *for the seasonal dataset* and was not assumed to describe the telemetry network.

## 6. Temporal completeness (2021-10-01 .. 2025-10-01)

| Station | Producer | Obs in period | Coverage | Months | Median | Max gap |
|---|---|---:|---:|---:|---:|---:|
| New Delhi DSIIDC DSIIDC | delhi_sw_gw | 3191 | 87.1% | 30 | 6.00 h | 1890 h |
| Holambi Kalan-1 | delhi_sw_gw | 2357 | 69.1% | 23 | 6.00 h | 5046 h |
| New Delhi Mungeshpur Mungeshpu | delhi_sw_gw | 3849 | 85.1% | 38 | 6.00 h | 1890 h |
| New Delhi Salahpur Salahpur | delhi_sw_gw | 3497 | 84.7% | 34 | 6.00 h | 1878 h |
| Bawana DJB WTP_1 | cgwb_delhi | 2254 | 80.4% | 24 | 6.00 h | 912 h |
| Naya Bans | delhi_sw_gw | 1870 | 74.5% | 18 | 6.00 h | 3198 h |
| New Delhi Khera Khurd Khera Kh | delhi_sw_gw | 3090 | 87.9% | 29 | 6.00 h | 1896 h |
| Sannoth Lake | delhi_sw_gw | 1616 | 73.2% | 16 | 6.00 h | 1926 h |
| Delhi South West DWARKA Dwarka | cgwb_delhi | 3731 | 97.7% | 33 | 6.00 h | 141 h |
| Delhi North NARELA Bankner Pz | cgwb_delhi | 3220 | 94.3% | 29 | 6.00 h | 180 h |

Coverage is **85–98 %** at the near stations. The principal caveat is **outages**: the Delhi SW GW near stations carry gaps of ~1800–1900 h (≈ 78 days), while the best CGWB stations (DWARKA 3.66 km from H004; KAPESHERA 4.72 km) reach 97.7–99.2 % coverage with maximum gaps of only **30–141 h**. A station is therefore available that is both close **and** gap-poor for H004; for H001 the choice is close-but-gappy (2.06 km, 85 %) or slightly farther and dense (DWARKA 5.82 km, 97.7 %).

## 7. Cross-producer duplication

* Delhi SW GW stations: **96**; CGWB stations: **91**
* shared station **names**: **0**
* shared rounded **coordinates**: **0**

**The two networks are independent — no duplicated feed was found.** However, no authoritative station code exists in either file, so identity could only be tested by name and coordinate, and a genuine duplicate that renamed a station would not be detected. Duplicates are therefore *not observed* rather than *excluded by design*.

## 8. Quality flags (flagged, not repaired)

| Flag | Stations |
|---|---:|
| any negative level | 72 |
| > 50 % exact zeros | **67** |
| > 90 % consecutive-constant | **67** |
| a > 10 m step | 55 |
| duplicate timestamps | 0 |
| **total stations** | **187** |

**67 of 187 stations (36 %) are effectively unusable** — they report mostly exact zeros and are almost entirely constant. These are concentrated in the **Delhi SW GW** feed (e.g. *Chawla Village 1*, *Tajpur Khurd*, *Chhawla Village-2/3*, all 100 % zeros), and they sit at 8–9 km from the hotspots, so they do not block the primary analysis — but they mean the network is smaller in practice than its 187-station headline count.

No smoothing, repair, gap-filling or unit conversion was applied. Nothing was removed.

## 9. Candidate station design (identified before any InSAR comparison)

| Role | Stations |
|---|---|
| PRIMARY — nearest H001 | *New Delhi Mungeshpur* (2.06 km), *New Delhi Salahpur* (2.08 km) |
| PRIMARY — nearest H004 | same two (1.97 / 1.98 km), plus *Delhi South West DWARKA Dwarka Sec* (3.66 km, 97.7 %) |
| NEGATIVE CONTROL — H002 | station at 0.97 km |
| NEGATIVE CONTROL — H003 | station at 0.81 km |
| BACKGROUND | CGWB stations at 5–10 km with ≥ 94 % coverage and no quality flag |

These were selected on **distance and measured quality only**. No groundwater time series was inspected against InSAR, and no station was chosen because its series resembled the deformation pattern.

## 10. Reclassified groundwater gate

```text
GROUNDWATER TEMPORAL TEST:
    PARTIALLY SUPPORTED
```

This is option **B**, and the correction to the earlier verdict is real: the previous `ACCESS-BLOCKED / INADEQUATE` conclusion was drawn from India-WRIS, WIMS and the CGWB portal, and **NWDP was not among the routes tested**. With NWDP included, six-hourly station data with coordinates do exist inside 5 km of H001.

**Why B rather than A.** The data genuinely support the test, but four caveats are material and must enter the analysis protocol:

1. **Outages.** The nearest H001 stations have ~78-day gaps and 85 % coverage; the gap-poor alternative is 5.8 km away.
2. **Network quality.** 67 of 187 stations are effectively dead, so the usable network is substantially smaller than its headline size.
3. **No station code and no aquifer/well-depth metadata**, so identity rests on name + coordinates, and no screen for well construction or aquifer is possible.
4. **The telemetry network is not the seasonal network** — different stations, different producers, no overlap. The two cannot be cross-validated station-by-station.

**Why not C.** Twelve-plus usable six-hourly stations lie within 10 km of H001/H004, including two within 2.1 km of H001 and one at 3.66 km from H004 with 97.7 % coverage and a 141-hour maximum gap. That is sufficient for a hotspot-level temporal test at sub-daily native resolution.

## 11. Next step — protocol before analysis

Per protocol the groundwater temporal-analysis protocol must be **frozen before any hotspot correlation is inspected**, specifying at minimum: which stations, which outage handling, which de-trending, which predefined lag windows, and how the coherence-confoundning control is applied. **No correlation has been run and none is run until that protocol exists.**
