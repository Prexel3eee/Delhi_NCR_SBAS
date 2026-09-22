# Comparison with Garg et al. (2022), Scientific Reports 12:651

**Question.** Do the frozen Phase-I zones H001-H005 correspond to the deformation features reported by Garg et al. (2022)?

---

## 1. Provenance constraint (read this first)

**Garg et al. publish no coordinates.** This was verified directly against the open-access record, not assumed:

| Checked | Coordinate content |
|---|---|
| Full text (PMC8758763) | none |
| Supplementary Information (.docx, 5.8 MB) | none |
| Figure captions | none |
| Occurrences of `latitude` / `longitude` / `UTM` / `WGS` | 0 |

The nine named locations exist **only as annotated labels on figures**. The paper identifies them by place name, by map annotation (R1-R6 in Fig. 2b; rectangles d/e/f in Fig. 1c) and by relative distance anchors ("<800 m from IGI Airport", "1.5 km from the runway").

Coordinates used below were therefore **digitised from the published figures**, which carry printed graticules. They are *proxy* positions for the named localities, not coordinates the authors reported.

### Calibration validation

| Test | Result |
|---|---|
| IGI Airport reference square | digitises to 77.084 E, 28.554 N - inside the real airport boundary |
| Kapashera, digitised independently from Fig. 2b and Fig. 1c | agrees to **0.83 km** |
| Faridabad rectangle centre | 77.316 E, 28.412 N vs a true city centre near 77.31 E, 28.41 N |

**Positional uncertainty: ±1.5 km.** Distances below should be read with that floor.

---

## 2. Our frozen zones

| Zone | Centroid lon | Centroid lat | Area km² | Median LOS mm/yr |
|---|---:|---:|---:|---:|
| **H001** | 77.08146 | 28.52099 | 5.5904 | -30.95 |
| **H002** | 77.07367 | 28.81504 | 12.8256 | -13.59 |
| **H003** | 77.08122 | 28.80314 | 2.2544 | -12.87 |
| **H004** | 77.05560 | 28.53308 | 1.0720 | -14.31 |
| **H005** | 77.17372 | 28.82471 | 0.8352 | -14.21 |

---

## 3. Digitised literature features

| Feature | Lon | Lat | Reported sign | Source |
|---|---:|---:|---|---|
| Kapashera | 77.0850 | 28.5099 | subsidence | Fig 1c rect (d) |
| Kapashera (Fig 2b mass) | 77.0812 | 28.5167 | subsidence | Fig 2b dark-red mass |
| Mahipalpur (R1) | 77.1196 | 28.5403 | subsidence | Fig 2b |
| Bijwasan Harijan Basti (R2) | 77.0551 | 28.5336 | subsidence | Fig 2b |
| Sector 22A Gurgaon (R3) | 77.0760 | 28.5122 | subsidence | Fig 2b |
| Sanjay Gram (R4) | 77.0384 | 28.4764 | subsidence | Fig 2b |
| Chack Sadhu (R5) | 77.0857 | 28.4719 | subsidence | Fig 2b |
| Nathupur (R6) | 77.0977 | 28.4918 | subsidence | Fig 2b |
| Dwarka | 77.0687 | 28.6175 | UPLIFT (after phase 1) | Fig 1c rect (f) |
| Faridabad | 77.3163 | 28.4123 | subsidence | Fig 1c rect (e) |

---

## 4. Distance results

Distance is measured **to the nearest point of the hotspot polygon**, not only to its centroid, because the zones are extended and multipart.

| Zone | Nearest literature feature | Polygon distance (km) | Centroid distance (km) | Inside zone? | Sign agrees | Classification |
|---|---|---:|---:|---|---|---|
| **H001** | Kapashera | 0.000 | 1.274 | **yes** | yes | STRONG HISTORICAL SPATIAL CORROBORATION |
| **H002** | Dwarka | 17.858 | 21.848 | no | no | NO CLEAR CORRESPONDENCE |
| **H003** | Dwarka | 19.284 | 20.564 | no | no | NO CLEAR CORRESPONDENCE |
| **H004** | Bijwasan Harijan Basti (R2) | 0.000 | 0.075 | **yes** | yes | STRONG HISTORICAL SPATIAL CORROBORATION |
| **H005** | Dwarka | 24.324 | 25.101 | no | no | NO CLEAR CORRESPONDENCE |

### Literature features falling inside a frozen zone

| Zone | Literature feature | Centroid distance (km) |
|---|---|---:|
| H001 | Kapashera (Fig 2b mass) | 0.475 |
| H001 | Sector 22A Gurgaon (R3) | 1.109 |
| H001 | Kapashera | 1.274 |
| H004 | Bijwasan Harijan Basti (R2) | 0.075 |

---

## 5. Full distance matrix (km, point-to-polygon)

| Zone | Kapashera (1c) | Kapashera (2b) | Mahipalpur | Bijwasan Harijan Basti | Sector 22A Gurgaon | Sanjay Gram | Chack Sadhu | Nathupur | Dwarka | Faridabad |
|---|---|---|---|---|---|---|---|---|---|---|
| **H001** | **0.0** | **0.0** | 2.5 | **1.8** | **0.0** | 4.7 | 3.7 | **1.8** | 8.9 | 24.5 |
| **H002** | 29.9 | 29.1 | 27.1 | 27.1 | 29.6 | 33.5 | 34.1 | 32.0 | 17.9 | 47.8 |
| **H003** | 31.2 | 30.5 | 28.2 | 28.6 | 31.0 | 35.0 | 35.5 | 33.3 | 19.3 | 48.0 |
| **H004** | 3.0 | 2.2 | 5.4 | **0.0** | 2.2 | 6.0 | 6.7 | 5.3 | 8.9 | 27.9 |
| **H005** | 35.2 | 34.6 | 31.3 | 33.5 | 35.2 | 40.0 | 39.3 | 36.9 | 24.3 | 47.1 |

---

## 6. Sign and temporal comparison

**Sign.** Garg et al. report *vertical* land motion; this study reports *relative LOS*. For a right-looking ascending pass over this AOI, vertical subsidence projects to negative LOS. On that basis alone:

| | Garg et al. | This study | Agreement |
|---|---|---|---|
| Kapashera, R1-R6 | subsidence | negative LOS at H001, H004 | consistent direction |
| Faridabad | subsidence | no zone within 25 km | not comparable |
| Dwarka | subsidence 2014-2016, then **uplift** | negative LOS at H001/H004, ~9-11 km away | **opposite** |

**Temporal.** The literature period **predates** ours:

* Garg et al.: 2014-10 to 2020-01 (Sentinel-1, three phases)
* This study: 2021-10-06 to 2025-09-27 (Sentinel-1, RAW-336)

The literature features were already deforming **before** our first acquisition, so where they coincide spatially the relationship is one of prior observation, not of independent contemporaneous discovery.

---

## 6b. Robustness to the digitisation uncertainty

With ±1.5 km positional uncertainty, every classification is stable:

| Zone | Distance | Headroom against ±1.5 km |
|---|---:|---|
| H001 | 0 km (contains the literature point) | robust - cannot be displaced outside by 1.5 km |
| H004 | 0 km (contains the literature point) | robust |
| H002 | 17.9 km | 12x the uncertainty |
| H003 | 19.3 km | 13x |
| H005 | 24.3 km | 16x |

**Feature-size caveat.** The literature's Kapashera feature is reported at approximately 12.5 km2; our H001 is 5.59 km2 (multipart). Corroboration here means the literature point falls within, or within 1.8 km of, our zone - it does not mean the two delineate the same area.

**Naming caveat.** H001 contains literature points for *three* named localities (Kapashera, Sector 22A Gurgaon, and the Fig. 2b Kapashera mass) and passes within 1.8 km of two more (Bijwasan, Nathupur). It is therefore a zone spanning a *cluster* of named localities, not a one-to-one match with any single published place name.

---

## 7. Classification

Criteria: **STRONG** = literature point inside the zone, or ≤ 2 km from it, with agreeing sign. **POSSIBLE** = 2-5 km with agreeing sign. **NO CLEAR CORRESPONDENCE** = > 5 km, or opposing sign.

### H001 — STRONG HISTORICAL SPATIAL CORROBORATION

Nearest literature feature: **Kapashera** at 0.00 km (centroid 1.27 km).

Literature features falling **inside** this zone: Kapashera, Kapashera (Fig 2b mass), Sector 22A Gurgaon (R3).

### H002 — NO CLEAR CORRESPONDENCE

Nearest literature feature: **Dwarka** at 17.86 km (centroid 21.85 km).

### H003 — NO CLEAR CORRESPONDENCE

Nearest literature feature: **Dwarka** at 19.28 km (centroid 20.56 km).

### H004 — STRONG HISTORICAL SPATIAL CORROBORATION

Nearest literature feature: **Bijwasan Harijan Basti (R2)** at 0.00 km (centroid 0.07 km).

Literature features falling **inside** this zone: Bijwasan Harijan Basti (R2).

### H005 — NO CLEAR CORRESPONDENCE

Nearest literature feature: **Dwarka** at 24.32 km (centroid 25.10 km).

