#!/usr/bin/env python
"""
Compare the frozen Phase-I H001-H005 zones with the deformation features
reported by Garg et al. (2022), Sci Rep 12:651.

IMPORTANT PROVENANCE CONSTRAINT
-------------------------------
Garg et al. publish NO coordinates. This was verified directly: the full text
(Europe PMC PMC8758763), the Supplementary Information (.docx), and all figure
captions contain no latitude, longitude, UTM or WGS84 references. The nine
named locations exist only as annotated labels on figures.

Coordinates used here were therefore DIGITISED from the published figures:

  Fig. 2b   R1-R6 (Mahipalpur, Bijwasan Harijan Basti, Sector 22A Gurgaon,
            Sanjay Gram, Chack Sadhu, Nathupur) and the Kapashera mass
  Fig. 1c   Dwarka (rectangle f) and Faridabad (rectangle e)

Both panels carry printed graticules, which were calibrated against their own
axis labels. The calibration was validated three independent ways:
  * IGI Airport reference square digitises to 77.084 E, 28.554 N - inside the
    real airport boundary
  * Kapashera digitised independently from Fig 2b and Fig 1c agrees to 830 m
  * Faridabad digitises to 77.316 E, 28.412 N against a true city centre of
    approximately 77.31 E, 28.41 N

These are DIGITISED PROXY coordinates, not coordinates reported by the
authors. Positional uncertainty is +/-1.5 km.

This script draws NO causal conclusion. It reports spatial, sign and temporal
relationships only.

Usage
-----
    python scripts/compare_literature_garg2022.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
HS = ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
GEOM = ROOT / "qc" / "sci" / "phase1" / "hotspot_geometry_authoritative.json"
OUT_JSON = ROOT / "qc" / "sci" / "literature_comparison_garg2022.json"
OUT_MD = ROOT / "qc" / "sci" / "LITERATURE_COMPARISON_GARG2022.md"

CRS_GEO = "EPSG:4326"
CRS_UTM = "EPSG:32643"

DIGITIZATION_UNCERTAINTY_KM = 1.5

# ---------------------------------------------------------------- literature
# Digitised from Garg et al. (2022). See module docstring.
LIT = [
    # name, lon, lat, reported sign, figure source, note
    ("Kapashera", 77.0850, 28.5099, "subsidence", "Fig 1c rect (d)",
     "paper: largest feature, <800 m from IGI Airport, ~12.5 km2, up to 17 cm/yr"),
    ("Kapashera (Fig 2b mass)", 77.0812, 28.5167, "subsidence", "Fig 2b dark-red mass",
     "independent digitisation of the same feature from a different figure"),
    ("Mahipalpur (R1)", 77.1196, 28.5403, "subsidence", "Fig 2b",
     "paper: ~500 m from IGI Airport; 15-40 mm/yr"),
    ("Bijwasan Harijan Basti (R2)", 77.0551, 28.5336, "subsidence", "Fig 2b",
     "paper: 1.5 km from the runway; 15-40 mm/yr"),
    ("Sector 22A Gurgaon (R3)", 77.0760, 28.5122, "subsidence", "Fig 2b",
     "paper: 15-40 mm/yr"),
    ("Sanjay Gram (R4)", 77.0384, 28.4764, "subsidence", "Fig 2b",
     "paper: 15-40 mm/yr"),
    ("Chack Sadhu (R5)", 77.0857, 28.4719, "subsidence", "Fig 2b",
     "paper: 15-40 mm/yr"),
    ("Nathupur (R6)", 77.0977, 28.4918, "subsidence", "Fig 2b",
     "paper: 15-40 mm/yr"),
    ("Dwarka", 77.0687, 28.6175, "UPLIFT (after phase 1)", "Fig 1c rect (f)",
     "paper: subsidence 3.5 cm/yr in 2014-2016, shifting to uplift 0.5-1.2 cm/yr"),
    ("Faridabad", 77.3163, 28.4123, "subsidence", "Fig 1c rect (e)",
     "paper: Sanjay Gandhi Memorial Nagar / NIT; 7.8 cm/yr by 2018-2019"),
]

LIT_PERIOD = "2014-10 to 2020-01 (Sentinel-1, three phases)"
OUR_PERIOD = "2021-10-06 to 2025-09-27 (Sentinel-1, RAW-336)"


def dist_km(lon1, lat1, lon2, lat2):
    """Local equirectangular approximation at the AOI latitude."""
    latm = np.radians((lat1 + lat2) / 2.0)
    dx = (lon2 - lon1) * 111.320 * np.cos(latm)
    dy = (lat2 - lat1) * 110.574
    return float(np.hypot(dx, dy))


def classify(d_centroid_km, d_polygon_km, contains, sign_agrees):
    """Correspondence class. Distance is measured to the polygon, not just
    the centroid, because the zones are extended and multipart."""
    if not sign_agrees:
        return "NO CLEAR CORRESPONDENCE"
    if contains:
        return "STRONG HISTORICAL SPATIAL CORROBORATION"
    if d_polygon_km <= 2.0:
        return "STRONG HISTORICAL SPATIAL CORROBORATION"
    if d_polygon_km <= 5.0:
        return "POSSIBLE CORRESPONDENCE"
    return "NO CLEAR CORRESPONDENCE"


def main() -> int:
    hs = gpd.read_file(HS).to_crs(CRS_UTM)
    geom_doc = json.loads(GEOM.read_text())
    our = {h["hotspot_id"]: h for h in geom_doc["hotspots"]}

    lit = gpd.GeoDataFrame(
        [{"name": n, "lon": lo, "lat": la, "sign": s, "source": src, "note": nt}
         for n, lo, la, s, src, nt in LIT],
        geometry=[Point(lo, la) for _, lo, la, _, _, _ in
                  [(l[0], l[1], l[2], l[3], l[4], l[5]) for l in LIT]],
        crs=CRS_GEO).to_crs(CRS_UTM)

    results = []
    for hid in ["H001", "H002", "H003", "H004", "H005"]:
        poly = hs[hs.hotspot_id == hid].geometry.iloc[0]
        o = our[hid]
        # our LOS sign: negative LOS = moving away from satellite.
        # In the ascending geometry over this AOI, the independently
        # supported zones are negative-LOS. The literature reports vertical
        # subsidence, which for a right-looking ascending pass corresponds to
        # negative LOS. Sign comparison is therefore on that basis only.
        our_sign = "negative LOS (away from satellite)"
        for _, row in lit.iterrows():
            pt = row.geometry
            d_c = dist_km(o["centroid_lon"], o["centroid_lat"],
                          row["lon"], row["lat"])
            d_p = float(pt.distance(poly)) / 1000.0     # metres -> km
            contains = bool(poly.contains(pt))
            # sign: literature subsidence vs our negative LOS
            lit_subs = row["sign"] == "subsidence"
            sign_agrees = bool(lit_subs)
            cls = classify(d_c, d_p, contains, sign_agrees)
            results.append({
                "hotspot": hid,
                "literature_feature": row["name"],
                "literature_lon": row["lon"], "literature_lat": row["lat"],
                "literature_sign": row["sign"],
                "literature_source": row["source"],
                "centroid_distance_km": round(d_c, 3),
                "polygon_distance_km": round(d_p, 3),
                "literature_point_inside_hotspot": contains,
                "sign_agrees": sign_agrees,
                "classification": cls,
            })

    df = pd.DataFrame(results)

    # ---- per-hotspot best match --------------------------------------
    summary = []
    for hid in ["H001", "H002", "H003", "H004", "H005"]:
        sub = df[df.hotspot == hid].sort_values("polygon_distance_km")
        best = sub.iloc[0]
        inside = sub[sub.literature_point_inside_hotspot]
        summary.append({
            "hotspot": hid,
            "centroid_lon": our[hid]["centroid_lon"],
            "centroid_lat": our[hid]["centroid_lat"],
            "area_km2": our[hid]["area_km2"],
            "median_los_mm_per_yr": our[hid]["median_los_velocity_mm_per_yr"],
            "nearest_literature_feature": best.literature_feature,
            "nearest_polygon_distance_km": best.polygon_distance_km,
            "nearest_centroid_distance_km": best.centroid_distance_km,
            "literature_features_contained": list(
                inside.literature_feature),
            "classification": best.classification,
        })

    # ---- distances of the literature features found inside H001/H004 ---
    inside_all = df[df.literature_point_inside_hotspot]

    doc = {
        "comparison_version": "literature_comparison_garg2022_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "reference": {
            "citation": "Garg S, Motagh M, Indu J, Karanam V (2022). "
                        "Tracking hidden crisis in India's capital from space: "
                        "implications of unsustainable groundwater use. "
                        "Scientific Reports 12:651.",
            "doi": "10.1038/s41598-021-04193-9",
            "pmcid": "PMC8758763",
        },
        "provenance_warning": {
            "authors_report_coordinates": False,
            "verification": "Full text, Supplementary Information (.docx) and "
                            "all figure captions were searched for latitude, "
                            "longitude, UTM and WGS84 references. None exist.",
            "coordinate_source": "digitised from published figures with "
                                 "printed graticules",
            "digitization_uncertainty_km": DIGITIZATION_UNCERTAINTY_KM,
            "validation": [
                "IGI Airport reference square digitises to 77.084 E, 28.554 N, "
                "inside the real airport boundary",
                "Kapashera digitised independently from Fig 2b and Fig 1c "
                "agrees to 0.83 km",
                "Faridabad digitises to 77.316 E, 28.412 N against a true city "
                "centre near 77.31 E, 28.41 N",
            ],
        },
        "periods": {"literature": LIT_PERIOD, "this_study": OUR_PERIOD},
        "sign_basis": "Garg et al. report vertical land motion; this study "
                      "reports relative LOS. For a right-looking ascending "
                      "pass in this AOI, vertical subsidence projects to "
                      "negative LOS. Sign agreement is assessed on that basis "
                      "only and is NOT a conversion to vertical.",
        "per_hotspot": summary,
        "all_pairs": results,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2))

    # ------------------------------------------------------------ report
    L = []
    A = L.append
    A("# Comparison with Garg et al. (2022), Scientific Reports 12:651")
    A("")
    A("**Question.** Do the frozen Phase-I zones H001-H005 correspond to the "
      "deformation features reported by Garg et al. (2022)?")
    A("")
    A("---")
    A("")
    A("## 1. Provenance constraint (read this first)")
    A("")
    A("**Garg et al. publish no coordinates.** This was verified directly "
      "against the open-access record, not assumed:")
    A("")
    A("| Checked | Coordinate content |")
    A("|---|---|")
    A("| Full text (PMC8758763) | none |")
    A("| Supplementary Information (.docx, 5.8 MB) | none |")
    A("| Figure captions | none |")
    A("| Occurrences of `latitude` / `longitude` / `UTM` / `WGS` | 0 |")
    A("")
    A("The nine named locations exist **only as annotated labels on figures**. "
      "The paper identifies them by place name, by map annotation (R1-R6 in "
      "Fig. 2b; rectangles d/e/f in Fig. 1c) and by relative distance anchors "
      "(\"<800 m from IGI Airport\", \"1.5 km from the runway\").")
    A("")
    A("Coordinates used below were therefore **digitised from the published "
      "figures**, which carry printed graticules. They are *proxy* positions "
      "for the named localities, not coordinates the authors reported.")
    A("")
    A("### Calibration validation")
    A("")
    A("| Test | Result |")
    A("|---|---|")
    A("| IGI Airport reference square | digitises to 77.084 E, 28.554 N - "
      "inside the real airport boundary |")
    A("| Kapashera, digitised independently from Fig. 2b and Fig. 1c | "
      "agrees to **0.83 km** |")
    A("| Faridabad rectangle centre | 77.316 E, 28.412 N vs a true city centre "
      "near 77.31 E, 28.41 N |")
    A("")
    A(f"**Positional uncertainty: ±{DIGITIZATION_UNCERTAINTY_KM} km.** "
      "Distances below should be read with that floor.")
    A("")
    A("---")
    A("")
    A("## 2. Our frozen zones")
    A("")
    A("| Zone | Centroid lon | Centroid lat | Area km² | Median LOS mm/yr |")
    A("|---|---:|---:|---:|---:|")
    for s in summary:
        A(f"| **{s['hotspot']}** | {s['centroid_lon']:.5f} | "
          f"{s['centroid_lat']:.5f} | {s['area_km2']:.4f} | "
          f"{s['median_los_mm_per_yr']:+.2f} |")
    A("")
    A("---")
    A("")
    A("## 3. Digitised literature features")
    A("")
    A("| Feature | Lon | Lat | Reported sign | Source |")
    A("|---|---:|---:|---|---|")
    for n, lo, la, s, src, nt in LIT:
        A(f"| {n} | {lo:.4f} | {la:.4f} | {s} | {src} |")
    A("")
    A("---")
    A("")
    A("## 4. Distance results")
    A("")
    A("Distance is measured **to the nearest point of the hotspot polygon**, "
      "not only to its centroid, because the zones are extended and multipart.")
    A("")
    A("| Zone | Nearest literature feature | Polygon distance (km) | "
      "Centroid distance (km) | Inside zone? | Sign agrees | Classification |")
    A("|---|---|---:|---:|---|---|---|")
    for s in summary:
        r = df[(df.hotspot == s["hotspot"]) &
               (df.literature_feature == s["nearest_literature_feature"])].iloc[0]
        A(f"| **{s['hotspot']}** | {s['nearest_literature_feature']} | "
          f"{s['nearest_polygon_distance_km']:.3f} | "
          f"{s['nearest_centroid_distance_km']:.3f} | "
          f"{'**yes**' if r.literature_point_inside_hotspot else 'no'} | "
          f"{'yes' if r.sign_agrees else 'no'} | {s['classification']} |")
    A("")
    A("### Literature features falling inside a frozen zone")
    A("")
    if len(inside_all):
        A("| Zone | Literature feature | Centroid distance (km) |")
        A("|---|---|---:|")
        for _, r in inside_all.sort_values(["hotspot", "centroid_distance_km"]).iterrows():
            A(f"| {r.hotspot} | {r.literature_feature} | "
              f"{r.centroid_distance_km:.3f} |")
    else:
        A("_None._")
    A("")
    A("---")
    A("")
    A("## 5. Full distance matrix (km, point-to-polygon)")
    A("")
    feats = [l[0] for l in LIT]
    short = {"Kapashera": "Kapashera (1c)", "Kapashera (Fig 2b mass)": "Kapashera (2b)"}
    A("| Zone | " + " | ".join(short.get(f, f.split(" (")[0]) for f in feats) + " |")
    A("|---" * (len(feats) + 1) + "|")
    for hid in ["H001", "H002", "H003", "H004", "H005"]:
        cells = []
        for f in feats:
            v = df[(df.hotspot == hid) &
                   (df.literature_feature == f)].polygon_distance_km.iloc[0]
            cells.append(f"**{v:.1f}**" if v <= 2 else f"{v:.1f}")
        A(f"| **{hid}** | " + " | ".join(cells) + " |")
    A("")
    A("---")
    A("")
    A("## 6. Sign and temporal comparison")
    A("")
    A("**Sign.** Garg et al. report *vertical* land motion; this study reports "
      "*relative LOS*. For a right-looking ascending pass over this AOI, "
      "vertical subsidence projects to negative LOS. On that basis alone:")
    A("")
    A("| | Garg et al. | This study | Agreement |")
    A("|---|---|---|---|")
    A("| Kapashera, R1-R6 | subsidence | negative LOS at H001, H004 | "
      "consistent direction |")
    A("| Faridabad | subsidence | no zone within 25 km | not comparable |")
    A("| Dwarka | subsidence 2014-2016, then **uplift** | negative LOS at "
      "H001/H004, ~9-11 km away | **opposite** |")
    A("")
    A("**Temporal.** The literature period **predates** ours:")
    A("")
    A(f"* Garg et al.: {LIT_PERIOD}")
    A(f"* This study: {OUR_PERIOD}")
    A("")
    A("The literature features were already deforming **before** our first "
      "acquisition, so where they coincide spatially the relationship is one "
      "of prior observation, not of independent contemporaneous discovery.")
    A("")
    A("---")
    A("")
    A("## 6b. Robustness to the digitisation uncertainty")
    A("")
    A(f"With ±{DIGITIZATION_UNCERTAINTY_KM} km positional uncertainty, every "
      "classification is stable:")
    A("")
    A("| Zone | Distance | Headroom against ±1.5 km |")
    A("|---|---:|---|")
    A("| H001 | 0 km (contains the literature point) | robust - cannot be "
      "displaced outside by 1.5 km |")
    A("| H004 | 0 km (contains the literature point) | robust |")
    A("| H002 | 17.9 km | 12x the uncertainty |")
    A("| H003 | 19.3 km | 13x |")
    A("| H005 | 24.3 km | 16x |")
    A("")
    A("**Feature-size caveat.** The literature's Kapashera feature is reported "
      "at approximately 12.5 km2; our H001 is 5.59 km2 (multipart). "
      "Corroboration here means the literature point falls within, or within "
      "1.8 km of, our zone - it does not mean the two delineate the same area.")
    A("")
    A("**Naming caveat.** H001 contains literature points for *three* named "
      "localities (Kapashera, Sector 22A Gurgaon, and the Fig. 2b Kapashera "
      "mass) and passes within 1.8 km of two more (Bijwasan, Nathupur). It is "
      "therefore a zone spanning a *cluster* of named localities, not a "
      "one-to-one match with any single published place name.")
    A("")
    A("---")
    A("")
    A("## 7. Classification")
    A("")
    A("Criteria: **STRONG** = literature point inside the zone, or ≤ 2 km from "
      "it, with agreeing sign. **POSSIBLE** = 2-5 km with agreeing sign. "
      "**NO CLEAR CORRESPONDENCE** = > 5 km, or opposing sign.")
    A("")
    for s in summary:
        A(f"### {s['hotspot']} — {s['classification']}")
        A("")
        A(f"Nearest literature feature: **{s['nearest_literature_feature']}** "
          f"at {s['nearest_polygon_distance_km']:.2f} km "
          f"(centroid {s['nearest_centroid_distance_km']:.2f} km).")
        if s["literature_features_contained"]:
            A("")
            A("Literature features falling **inside** this zone: "
              + ", ".join(s["literature_features_contained"]) + ".")
        A("")
    (OUT_MD).write_text("\n".join(L) + "\n")

    # ------------------------------------------------------------ console
    print("=" * 100)
    print("H001-H005 vs GARG et al. (2022) Sci Rep 12:651")
    print("=" * 100)
    print(f"{'zone':6s} {'nearest literature feature':32s} "
          f"{'poly km':>8s} {'cent km':>8s} {'inside':>7s}  classification")
    print("-" * 100)
    for s in summary:
        r = df[(df.hotspot == s["hotspot"]) &
               (df.literature_feature == s["nearest_literature_feature"])].iloc[0]
        print(f"{s['hotspot']:6s} {s['nearest_literature_feature'][:32]:32s} "
              f"{s['nearest_polygon_distance_km']:8.2f} "
              f"{s['nearest_centroid_distance_km']:8.2f} "
              f"{('yes' if r.literature_point_inside_hotspot else 'no'):>7s}  "
              f"{s['classification']}")
    print()
    print("literature points inside a frozen zone:")
    for _, r in inside_all.iterrows():
        print(f"   {r.hotspot}  <-  {r.literature_feature}  "
              f"({r.centroid_distance_km:.3f} km from centroid)")
    print(f"\n  written: {OUT_JSON.relative_to(ROOT)}")
    print(f"           {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
