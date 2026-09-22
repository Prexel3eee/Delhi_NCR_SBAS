#!/usr/bin/env python
"""
Phase III-C: urbanisation / built-environment evidence test.

Tests three SEPARATE hypotheses:
  U1  existing built intensity
  U2  recent built-up expansion
  U3  major infrastructure / construction

No loading-induced deformation is claimed. No causal language is used.

Usage
-----
    python scripts/68_phase3c_urban.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
from rasterio.transform import Affine
from rasterio.warp import transform_geom
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
URB = PROJECT_ROOT / "data" / "external" / "urban"
ASC = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase3"
FIGS = OUT / "figures"

ROLES = {"H001": "supported", "H004": "supported",
         "H002": "negative_control", "H003": "negative_control",
         "H005": "excluded"}


def parts_of(g):
    return list(g.geoms) if g.geom_type == "MultiPolygon" else [g]


def sample_hotspot(src, geom, shrink=0.0, buffer_deg=0.0, class_of_interest=None):
    """Fraction of the hotspot covered, or median built surface, respecting the
    SOURCE grid - the polygon is rasterised onto the native source grid, never
    resampled onto the InSAR grid."""
    g = geom
    if shrink:
        g = g.buffer(-shrink)
    if buffer_deg:
        g = g.buffer(buffer_deg)
    if g.is_empty:
        return None, 0
    gu = shp_shape(transform_geom("EPSG:4326", src.crs.to_string(),
                                 g.__geo_interface__))
    polys = [p.__geo_interface__ for p in parts_of(gu) if not p.is_empty]
    if not polys:
        return None, 0
    m = rasterio.features.geometry_mask(polys, out_shape=(src.height, src.width),
                                        transform=src.transform, invert=True)
    if m.sum() == 0:
        return None, 0
    a = src.read(1, masked=False)[m].astype("float64")
    nod = src.nodata
    if nod is not None:
        a = a[a != nod]
    if a.size == 0:
        return None, 0
    if class_of_interest is not None:
        return float((a == class_of_interest).mean()), int(a.size)
    return float(np.median(a)), int(a.size)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    feats = {f["properties"]["hotspot_id"]: shp_shape(f["geometry"])
             for f in json.loads(HOTSPOTS.read_text())["features"]}

    # R7_C26 is the tile covering the AOI (bounds 70-80 E, 19.1-29.1 N). R6_C25 was
    # the wrong tile and returned zeros because it is mostly ocean.
    ghsl = {e: URB / f"ghsl_{e}_AOI.tif" for e in (2020, 2025)}
    wc = {y: URB / f"ESA_WorldCover_10m_{y}_{'v100' if y == 2020 else 'v200'}"
                 f"_N27E075_Map.tif" for y in (2020, 2021)}

    print("=" * 88)
    print("PHASE III-C - URBANISATION / BUILT-ENVIRONMENT EVIDENCE TEST")
    print("=" * 88)

    # ---- A/B. dataset inventory ------------------------------------------
    inv = []
    for e, p in ghsl.items():
        if p.exists():
            with rasterio.open(p) as s:
                inv.append({"dataset": f"GHSL GHS-BUILT-S E{e} (built-up surface)",
                            "source": "JRC GHSL R2023A", "epoch": e,
                            "native_resolution": f"{abs(s.transform.a)*3600:.0f} arc-sec "
                                                 f"(~{abs(s.transform.a)*111320:.0f} m)",
                            "crs": str(s.crs), "units": "m2 of built surface per cell",
                            "acquisition_period": f"epoch {e}",
                            "tests": "U1 (2020) and U2 (2020->2025 change)"})
    for y, p in wc.items():
        if p.exists():
            with rasterio.open(p) as s:
                inv.append({"dataset": f"ESA WorldCover {y} (land cover, 10 m)",
                            "source": "ESA / AWS Open Data", "epoch": y,
                            "native_resolution": f"{abs(s.transform.a)*3600:.1f} arc-sec "
                                                 f"(~{abs(s.transform.a)*111320:.0f} m)",
                            "crs": str(s.crs), "units": "categorical; class 50 = built-up",
                            "acquisition_period": f"year {y}",
                            "tests": "U1 cross-check"})
    inv.append({"dataset": "Major infrastructure / construction footprints",
                "source": "no authoritative machine-readable source obtained",
                "tests": "U3", "status": "NOT OBTAINED",
                "reason": "no official construction-project dataset with documented "
                          "geometry and dates was located; per protocol, proximity alone "
                          "would not be causal evidence and manually curated projects "
                          "near H001/H004 are forbidden"})
    pd.DataFrame(inv).to_csv(OUT / "URBAN_DATASET_REGISTRY.csv", index=False)

    print(f"\n  A. DATASET INVENTORY")
    for d in inv:
        if d.get("status") == "NOT OBTAINED":
            print(f"     NOT OBTAINED  {d['dataset']}")
        else:
            print(f"     OK  {d['dataset']:44s} {d['native_resolution']:22s} "
                  f"{d['acquisition_period']}")
    print(f"\n  B. TEMPORAL COMPATIBILITY")
    print(f"     InSAR study interval : 2021-10 .. 2025-10")
    print(f"     GHSL E2020 / E2025   : spans the study interval -> can support U2")
    print(f"     WorldCover 2020/2021 : both BEFORE the study interval -> supports U1 "
          f"and a pre-period change check, NOT change during the study period")
    print(f"     -> U2 uses GHSL E2020->E2025, the only interval that overlaps the study")

    # ---- C. U1 existing built intensity ----------------------------------
    rows = []
    for hid, g in feats.items():
        r = {"hotspot_id": hid, "role": ROLES[hid]}
        for e, p in ghsl.items():
            if not p.exists():
                continue
            with rasterio.open(p) as s:
                m, n = sample_hotspot(s, g)
                r[f"ghsl_{e}"] = round(m, 1) if m is not None else None
                r[f"ghsl_{e}_n"] = n
                for tag, kw in (("core", {"shrink": 0.002}),
                                ("buf", {"buffer_deg": 0.003})):
                    mm, _ = sample_hotspot(s, g, **kw)
                    r[f"ghsl_{e}_{tag}"] = round(mm, 1) if mm is not None else None
        for y, p in wc.items():
            if p.exists():
                with rasterio.open(p) as s:
                    f, n = sample_hotspot(s, g, class_of_interest=50)
                r[f"wc_builtfrac_{y}"] = round(100 * f, 2) if f is not None else None
        rows.append(r)
    tabs = pd.DataFrame(rows)

    # background: whole GHSL tile minus all hotspots
    # Background must be AOI minus hotspots, NOT the whole 10x10 degree tile:
    # the tile is mostly non-urban, so a whole-tile median is meaningless.
    aoi = shp_shape(json.loads((PROJECT_ROOT / "geometry" / "aoi.geojson")
                               .read_text())["features"][0]["geometry"])
    bgrow = {}
    for e, p in ghsl.items():
        if not p.exists():
            continue
        with rasterio.open(p) as s:
            au = shp_shape(transform_geom("EPSG:4326", s.crs.to_string(),
                                          aoi.__geo_interface__))
            m = rasterio.features.geometry_mask([au.__geo_interface__],
                                                out_shape=(s.height, s.width),
                                                transform=s.transform, invert=True)
            for g in feats.values():
                gu = shp_shape(transform_geom("EPSG:4326", s.crs.to_string(),
                                              g.__geo_interface__))
                m &= ~rasterio.features.geometry_mask(
                    [gu.__geo_interface__], out_shape=(s.height, s.width),
                    transform=s.transform, invert=True)
            a = s.read(1).astype("float64")[m]
            if s.nodata is not None:
                a = a[a != s.nodata]
            bgrow[f"ghsl_{e}"] = float(np.median(a)) if a.size else None
    for y, p in wc.items():
        if not p.exists():
            continue
        with rasterio.open(p) as s:
            au = shp_shape(transform_geom("EPSG:4326", s.crs.to_string(),
                                          aoi.__geo_interface__))
            m = rasterio.features.geometry_mask([au.__geo_interface__],
                                                out_shape=(s.height, s.width),
                                                transform=s.transform, invert=True)
            for g in feats.values():
                gu = shp_shape(transform_geom("EPSG:4326", s.crs.to_string(),
                                              g.__geo_interface__))
                m &= ~rasterio.features.geometry_mask(
                    [gu.__geo_interface__], out_shape=(s.height, s.width),
                    transform=s.transform, invert=True)
            a = s.read(1)[m]
            bgrow[f"wc_builtfrac_{y}"] = float(100 * (a == 50).mean()) if a.size else None

    print(f"\n  C. U1 - EXISTING BUILT INTENSITY")
    print(f"     {'id':6s} {'role':18s} {'GHSL2020':>9s} {'GHSL2025':>9s} "
          f"{'WC built%':>10s} {'core':>8s} {'buf':>8s}")
    for _, r in tabs.iterrows():
        print(f"     {r['hotspot_id']:6s} {r['role']:18s} "
              f"{(r['ghsl_2020'] if pd.notna(r['ghsl_2020']) else float('nan')):9.1f} "
              f"{(r['ghsl_2025'] if pd.notna(r['ghsl_2025']) else float('nan')):9.1f} "
              f"{(r['wc_builtfrac_2021'] if pd.notna(r.get('wc_builtfrac_2021')) else float('nan')):10.2f} "
              f"{(r['ghsl_2020_core'] if pd.notna(r['ghsl_2020_core']) else float('nan')):8.1f} "
              f"{(r['ghsl_2020_buf'] if pd.notna(r['ghsl_2020_buf']) else float('nan')):8.1f}")
    print(f"     {'BG':6s} {'background':18s} {bgrow.get('ghsl_2020', float('nan')):9.1f} "
          f"{bgrow.get('ghsl_2025', float('nan')):9.1f} "
          f"{bgrow.get('wc_builtfrac_2021', float('nan')):10.2f}")

    # ---- D. U2 recent built-up expansion ---------------------------------
    if "ghsl_2020" in tabs and "ghsl_2025" in tabs:
        tabs["ghsl_change"] = tabs["ghsl_2025"] - tabs["ghsl_2020"]
        tabs["ghsl_change_pct"] = 100 * tabs["ghsl_change"] / tabs["ghsl_2020"].replace(0, np.nan)
    print(f"\n  D. U2 - RECENT BUILT-UP EXPANSION (GHSL 2020 -> 2025, spans the study)")
    print(f"     {'id':6s} {'role':18s} {'abs change':>11s} {'% change':>9s}")
    for _, r in tabs.iterrows():
        c = r.get("ghsl_change"); pc = r.get("ghsl_change_pct")
        print(f"     {r['hotspot_id']:6s} {r['role']:18s} "
              f"{(c if pd.notna(c) else float('nan')):11.2f} "
              f"{(pc if pd.notna(pc) else float('nan')):9.2f}")

    # ---- E. U3 -----------------------------------------------------------
    print(f"\n  E. U3 - MAJOR INFRASTRUCTURE / CONSTRUCTION")
    print(f"     NOT TESTABLE - no authoritative machine-readable construction dataset "
          f"with documented geometry and dates was obtained. Per protocol, proximity "
          f"alone is not causal evidence and manually curating projects near H001/H004 "
          f"is forbidden. Recorded as NOT TESTABLE, not as negative.")

    # ---- G/H. controls + coherence confounding ---------------------------
    with h5py.File(ASC / "temporalCoherence.h5", "r") as h:
        tc = h["temporalCoherence"][:].astype("float64")
    with h5py.File(ASC / "velocity.h5", "r") as h:
        vstd = h["velocityStd"][:].astype("float64")
        vm = {k: float(h.attrs[k]) for k in
              ("X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP")}
    tf = Affine(vm["X_STEP"], 0, vm["X_FIRST"], 0, -abs(vm["Y_STEP"]), vm["Y_FIRST"])
    with h5py.File(ASC / "inputs" / "geometryGeo.h5", "r") as h:
        land = h["waterMask"][:].astype(bool)
    coh = []
    for hid, g in feats.items():
        gu = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", g.__geo_interface__))
        m = rasterio.features.geometry_mask([gu.__geo_interface__],
                                            out_shape=tc.shape, transform=tf, invert=True)
        m = m & land
        if m.sum() < 10:
            continue
        wcf = tabs.loc[tabs.hotspot_id == hid, "wc_builtfrac_2021"]
        coh.append({"hotspot_id": hid, "role": ROLES[hid],
                    "median_temporal_coherence": round(float(np.median(tc[m])), 4),
                    "median_velocity_std_mm_per_yr": round(
                        float(np.median(vstd[m])) * 1000, 4),
                    "valid_pixel_fraction": round(float(m.mean()), 5),
                    "built_fraction_pct": float(wcf.iloc[0]) if len(wcf) else None,
                    "ghsl_2020": (float(tabs.loc[tabs.hotspot_id == hid,
                                                 "ghsl_2020"].iloc[0])
                                  if "ghsl_2020" in tabs
                                  and pd.notna(tabs.loc[tabs.hotspot_id == hid,
                                                        "ghsl_2020"].iloc[0])
                                  else None)})
    cdf = pd.DataFrame(coh)
    cdf.to_csv(OUT / "urban_coherence_confounding.csv", index=False)
    print(f"\n  H. COHERENCE CONFOUNDING")
    print(f"     {'id':6s} {'role':18s} {'TC':>7s} {'built%':>8s} {'vStd':>7s}")
    for _, r in cdf.iterrows():
        print(f"     {r['hotspot_id']:6s} {r['role']:18s} "
              f"{r['median_temporal_coherence']:7.4f} "
              f"{(r['built_fraction_pct'] if pd.notna(r['built_fraction_pct']) else float('nan')):8.2f} "
              f"{r['median_velocity_std_mm_per_yr']:7.4f}")
    cc = cdf[["built_fraction_pct", "median_temporal_coherence"]].dropna()
    rho = float(pd.Series(cc["built_fraction_pct"]).corr(
        pd.Series(cc["median_temporal_coherence"]), method="spearman")) if len(cc) > 2 else None
    print(f"     Spearman(built%, temporal coherence) across hotspots: "
          f"{rho:+.3f}" if rho is not None else "     n too small")

    # ---- specificity ------------------------------------------------------
    sup = tabs[tabs["role"] == "supported"]
    neg = tabs[tabs["role"] == "negative_control"]
    spec = {}
    for c in ("ghsl_2020", "ghsl_2025", "wc_builtfrac_2021", "ghsl_change"):
        if c not in tabs:
            continue
        s, nn = sup[c].median(), neg[c].median()
        b = bgrow.get(c) if c in bgrow else None
        spec[c] = {"supported_median": round(float(s), 2) if pd.notna(s) else None,
                   "control_median": round(float(nn), 2) if pd.notna(nn) else None,
                   "background_median": round(float(b), 2) if b is not None else None,
                   "supported_minus_control": round(float(s - nn), 2)
                       if pd.notna(s) and pd.notna(nn) else None}
    print(f"\n  G. SPECIFICITY (supported vs control)")
    for c, v in spec.items():
        print(f"     {c:20s} supported {v['supported_median']}  control "
              f"{v['control_median']}  diff {v['supported_minus_control']}")

    tabs.to_csv(OUT / "urban_hotspot_summary.csv", index=False)

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_inventory": inv,
        "studied_interval": ["2021-10", "2025-10"],
        "hotspot_summaries": rows,
        "specificity": spec,
        "coherence_confounding": {"per_hotspot": coh,
                                  "spearman_builtfrac_vs_coherence": rho},
        "background": bgrow,
        "U3_status": "NOT TESTABLE - no authoritative construction dataset obtained",
        "no_loading_calculation": True,
        "no_causal_language": True,
    }
    (OUT / "urban_analysis.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'URBAN_DATASET_REGISTRY.csv'}")
    print(f"  {OUT / 'urban_analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
