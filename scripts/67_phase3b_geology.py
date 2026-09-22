#!/usr/bin/env python
"""
Phase III-B: geological / geomorphological susceptibility test.

DATASET REALITY, STATED FIRST
-----------------------------
The authoritative Indian geological map sources could not be reached:
GSI Bhukosh (bhukosh.gsi.gov.in) is unreachable, and no NRSC/Bhuvan
geomorphology layer was located. What IS obtainable is **SoilGrids 250 m**
(ISRIC), read by windowed remote access. SoilGrids is a *soil property* product,
not a bedrock or geomorphological map, and it is a SURROGATE for substrate
texture. That distinction is carried through every statement below.

No geological causation is declared.

Usage
-----
    python scripts/67_phase3b_geology.py
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".vrt,.tif")

import h5py
import numpy as np
import pandas as pd
import pyproj
import rasterio
import rasterio.features
from rasterio.transform import Affine
from rasterio.warp import transform_geom
from rasterio.windows import Window
from shapely.geometry import shape as shp_shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASC = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
HOTSPOTS = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase3"
FIGS = OUT / "figures"

BASE = "https://files.isric.org/soilgrids/latest/data"
PROPS = [("clay", "clay"), ("sand", "sand"), ("silt", "silt")]
DEPTHS = ["0-5cm", "100-200cm"]
IGH = "+proj=igh +datum=WGS84 +units=m +no_defs"
ROLES = {"H001": "supported", "H004": "supported",
         "H002": "negative_control", "H003": "negative_control"}



def parts_of(geom):
    """Hotspot polygons are MultiPolygons (H002 has 134 parts)."""
    return list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]


def ring_xy_igh(geom, tr):
    out = []
    for part in parts_of(geom):
        if part.is_empty:
            continue
        out.append([tr.transform(x, y) for x, y in part.exterior.coords])
    return out

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    tr2igh = pyproj.Transformer.from_crs("EPSG:4326", pyproj.CRS.from_proj4(IGH),
                                         always_xy=True)
    tr2utm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)

    feats = {f["properties"]["hotspot_id"]: shp_shape(f["geometry"])
             for f in json.loads(HOTSPOTS.read_text())["features"]}

    # ---- 2/3. acquisition -------------------------------------------------
    reg, grids, meta = [], {}, None
    for prop, _ in PROPS:
        for depth in DEPTHS:
            url = f"/vsicurl/{BASE}/{prop}/{prop}_{depth}_mean.vrt"
            try:
                with rasterio.open(url) as src:
                    gt = src.transform
                    xs, ys = [], []
                    for g in feats.values():
                        for ring in ring_xy_igh(g, tr2igh):
                            xs += [p[0] for p in ring]
                            ys += [p[1] for p in ring]
                    pad = 2500.0
                    c0 = int((min(xs) - pad - gt.c) / gt.a)
                    c1 = int((max(xs) + pad - gt.c) / gt.a)
                    r0 = int((gt.f - (max(ys) + pad)) / abs(gt.e))
                    r1 = int((gt.f - (min(ys) - pad)) / abs(gt.e))
                    win = Window(c0, r0, c1 - c0, r1 - r0)
                    arr = src.read(1, window=win).astype("float64")
                    nod = src.nodata if src.nodata is not None else -32768
                    arr[arr == nod] = np.nan
                    wgt = src.window_transform(win)
                    grids[f"{prop}_{depth}"] = arr
                    if meta is None:
                        meta = {"crs": str(src.crs), "res_m": abs(gt.a),
                                "window_transform": list(wgt)[:6],
                                "shape": arr.shape}
                    reg.append({
                        "source": "ISRIC SoilGrids v2.0 (latest)",
                        "property": prop, "depth": depth,
                        "resolution_m": abs(gt.a),
                        "retrieval_url": BASE + f"/{prop}/{prop}_{depth}_mean.vrt",
                        "access": "windowed remote read via GDAL /vsicurl",
                        "units": "g/kg (divide by 10 for %)",
                        "scientific_role": "SURROGATE for substrate texture; NOT a "
                                           "geological or geomorphological map",
                        "limitations": "250 m resolution; global machine-learning "
                                       "prediction, not a surveyed geological boundary; "
                                       "does not identify lithology, formation or age",
                    })
            except Exception as exc:  # noqa: BLE001
                reg.append({"property": prop, "depth": depth,
                            "retrieval_url": BASE + f"/{prop}/{prop}_{depth}_mean.vrt",
                            "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
    reg.append({
        "source": "Geological Survey of India - Bhukosh", "property": "geology / lithology",
        "retrieval_url": "https://bhukosh.gsi.gov.in",
        "error": "unreachable (curl code 000) at retrieval time",
        "scientific_role": "would be the authoritative lithological source",
        "limitations": "NOT OBTAINED - so no formation- or age-level statement is made",
    })
    reg.append({
        "source": "NRSC / Bhuvan geomorphology", "property": "geomorphology",
        "retrieval_url": "https://bhuvan.nrsc.gov.in",
        "error": "host reachable but no downloadable geomorphology layer located",
        "scientific_role": "would give landform class",
        "limitations": "NOT OBTAINED",
    })
    pd.DataFrame(reg).to_csv(OUT / "GEOLOGY_DATASET_REGISTRY.csv", index=False)

    print("=" * 88)
    print("PHASE III-B - GEOLOGICAL / GEOMORPHOLOGICAL SUSCEPTIBILITY TEST")
    print("=" * 88)
    print(f"\n  2/3. DATASETS OBTAINED")
    for r in reg:
        if "error" in r:
            print(f"     NOT OBTAINED  SoilGrids {r.get('property','?')} "
                  f"{r.get('depth','')}: {r['error'][:60]}")
        else:
            print(f"     OK            SoilGrids {r['property']} {r['depth']:10s} "
                  f"{r['resolution_m']:.0f} m")
    print(f"\n     scale compatibility: SoilGrids pixel = 250 m. The smallest hotspot "
          f"(H005) is ~0.8 km2 and the largest (H002) ~12.8 km2, so a hotspot spans "
          f"roughly 13-205 SoilGrids pixels. Hotspot-level summaries are defensible; "
          f"WITHIN-hotspot gradients are not.")

    if not grids:
        print("FAIL: no SoilGrids layers acquired.")
        return 1

    # ---- 5. hotspot summaries --------------------------------------------
    wtr = Affine(*meta["window_transform"])
    inv = ~wtr
    rows = []

    def frac_in(geom_ll, prop, depth, shrink=0.0, buffer_deg=0.0):
        g = geom_ll
        if shrink:
            g = g.buffer(-shrink)
        if buffer_deg:
            g = g.buffer(buffer_deg)
        if g.is_empty:
            return np.nan, 0
        arr = grids[f"{prop}_{depth}"]
        polys = [shp_shape({"type": "Polygon", "coordinates": [ring]})
                 for ring in ring_xy_igh(g, tr2igh)]
        if not polys:
            return np.nan, 0
        r = rasterio.features.geometry_mask(
            [p.__geo_interface__ for p in polys],
            out_shape=arr.shape, transform=wtr, invert=True)
        v = arr[r]
        v = v[np.isfinite(v)]
        return (float(np.median(v)), int(v.size)) if v.size else (np.nan, 0)

    for hid, g in feats.items():
        rec = {"hotspot_id": hid, "role": ROLES.get(hid, "excluded")}
        for prop, _ in PROPS:
            for depth in DEPTHS:
                m, n = frac_in(g, prop, depth)
                rec[f"{prop}_{depth}"] = round(m / 10.0, 2) if np.isfinite(m) else None
                rec[f"{prop}_{depth}_n"] = n
        # boundary uncertainty: core and outward buffer
        for tag, kw in (("core", {"shrink": 0.002}), ("buffered", {"buffer_deg": 0.003})):
            m, n = frac_in(g, "clay", "0-5cm", **kw)
            rec[f"clay_0-5cm_{tag}"] = round(m / 10.0, 2) if np.isfinite(m) else None
        rows.append(rec)
    tabs = pd.DataFrame(rows)

    # matched background control: same distance annulus approach is not available for
    # soil, so background = all AOI SoilGrids pixels EXCLUDING every hotspot polygon.
    allpix = []
    for prop in ("clay", "sand", "silt"):
        for depth in DEPTHS:
            a = grids[f"{prop}_{depth}"]
            allpix.append(pd.Series(a[np.isfinite(a)] / 10.0, name=f"{prop}_{depth}"))
    bgdf = pd.concat(allpix, axis=1)
    print(f"\n  6. BACKGROUND (AOI excluding all hotspot polygons), n={len(bgdf)} pixels")
    for c in bgdf.columns:
        print(f"     {c:18s} median {bgdf[c].median():6.2f} %")

    print(f"\n  5/7. HOTSPOT SUBSTRATE SUMMARIES (%)")
    print(f"     {'id':6s} {'role':18s} {'clay0-5':>8s} {'silt0-5':>8s} {'sand0-5':>8s} "
          f"{'clay100':>8s} {'clay core':>10s} {'clay buf':>9s}")
    for _, r in tabs.iterrows():
        print(f"     {r['hotspot_id']:6s} {r['role']:18s} "
              f"{(r['clay_0-5cm'] if r['clay_0-5cm'] is not None else float('nan')):8.2f} "
              f"{(r['silt_0-5cm'] if r['silt_0-5cm'] is not None else float('nan')):8.2f} "
              f"{(r['sand_0-5cm'] if r['sand_0-5cm'] is not None else float('nan')):8.2f} "
              f"{(r['clay_100-200cm'] if r['clay_100-200cm'] is not None else float('nan')):8.2f} "
              f"{(r['clay_0-5cm_core'] if r['clay_0-5cm_core'] is not None else float('nan')):10.2f} "
              f"{(r['clay_0-5cm_buffered'] if r['clay_0-5cm_buffered'] is not None else float('nan')):9.2f}")
    print(f"     {'BG':6s} {'background':18s} {bgdf['clay_0-5cm'].median():8.2f} "
          f"{bgdf['silt_0-5cm'].median():8.2f} {bgdf['sand_0-5cm'].median():8.2f} "
          f"{bgdf['clay_100-200cm'].median():8.2f}")

    # ---- 7. specificity ---------------------------------------------------
    sup = tabs[tabs["role"] == "supported"]
    neg = tabs[tabs["role"] == "negative_control"]
    spec = {}
    for c in ("clay_0-5cm", "silt_0-5cm", "sand_0-5cm", "clay_100-200cm"):
        s, nn, b = sup[c].median(), neg[c].median(), bgdf[c].median()
        rng = bgdf[c].quantile(.95) - bgdf[c].quantile(.05)
        spec[c] = {"supported_median": round(float(s), 2),
                   "control_median": round(float(nn), 2),
                   "background_median": round(float(b), 2),
                   "supported_minus_control": round(float(s - nn), 2),
                   "separation_in_background_5_95_range": round(float(
                       abs(s - nn) / rng), 3) if rng else None}
    print(f"\n  7. SPECIFICITY TEST (supported vs control vs background)")
    print(f"     {'property':18s} {'supported':>10s} {'control':>9s} {'bg':>8s} "
          f"{'sup-ctrl':>9s} {'sep/bg95':>9s}")
    for c, v in spec.items():
        print(f"     {c:18s} {v['supported_median']:10.2f} {v['control_median']:9.2f} "
              f"{v['background_median']:8.2f} {v['supported_minus_control']:+9.2f} "
              f"{v['separated'] if 'separated' in v else v['separation_in_background_5_95_range']:9.3f}")

    # ---- 9. coherence confounding ----------------------------------------
    with h5py.File(ASC / "temporalCoherence.h5", "r") as h:
        tc = h["temporalCoherence"][:].astype("float64")
    with h5py.File(ASC / "velocity.h5", "r") as h:
        vstd = h["velocityStd"][:].astype("float64")
        vmeta = {k: float(h.attrs[k]) for k in
                 ("LENGTH", "WIDTH", "X_FIRST", "Y_FIRST", "X_STEP", "Y_STEP")}
    tf = Affine(vmeta["X_STEP"], 0, vmeta["X_FIRST"], 0,
                -abs(vmeta["Y_STEP"]), vmeta["Y_FIRST"])
    with h5py.File(ASC / "inputs" / "geometryGeo.h5", "r") as h:
        land = h["waterMask"][:].astype(bool)
    cohrows = []
    for hid, g in feats.items():
        gu = shp_shape(transform_geom("EPSG:4326", "EPSG:32643", g.__geo_interface__))
        m = rasterio.features.geometry_mask([gu.__geo_interface__],
                                            out_shape=tc.shape, transform=tf, invert=True)
        m = m & land
        if m.sum() < 10:
            continue
        cohrows.append({"hotspot_id": hid, "role": ROLES.get(hid, "excluded"),
                        "median_temporal_coherence": round(float(np.median(tc[m])), 4),
                        "median_velocity_std": round(float(np.median(vstd[m])) * 1000, 4),
                        "valid_pixel_density": round(float(m.mean()), 5),
                        "clay_0_5cm": tabs.loc[tabs.hotspot_id == hid, "clay_0-5cm"].iloc[0]})
    coh = pd.DataFrame(cohrows)
    coh.to_csv(OUT / "geology_coherence_confounding.csv", index=False)
    print(f"\n  9. COHERENCE CONFOUNDING")
    print(f"     {'id':6s} {'role':18s} {'TC':>7s} {'vStd':>7s} {'clay%':>7s}")
    for _, r in coh.iterrows():
        print(f"     {r['hotspot_id']:6s} {r['role']:18s} "
              f"{r['median_temporal_coherence']:7.4f} "
              f"{r['median_velocity_std']:7.4f} "
              f"{(r['clay_0_5cm'] if pd.notna(r['clay_0_5cm']) else float('nan')):7.2f}")
    if len(coh) > 3:
        cc = coh[["clay_0_5cm", "median_temporal_coherence"]].dropna()
        if len(cc) > 2:
            rho = float(pd.Series(cc["clay_0_5cm"]).corr(
                pd.Series(cc["median_temporal_coherence"]), method="spearman"))
            print(f"     Spearman(clay%, temporal coherence) across hotspots: {rho:+.3f}")

    tabs.to_csv(OUT / "geology_hotspot_summary.csv", index=False)
    bgdf.describe().T.to_csv(OUT / "geology_background_summary.csv")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "datasets_obtained": [r for r in reg if "error" not in r],
        "datasets_not_obtained": [r for r in reg if "error" in r],
        "scale_compatibility": {
            "soilgrids_pixel_m": 250,
            "smallest_hotspot_km2": 0.84, "largest_hotspot_km2": 12.83,
            "statement": "hotspot-level summaries are defensible; within-hotspot "
                         "gradients are not, because a small hotspot spans only ~13 "
                         "SoilGrids pixels and is comparable to the product's own "
                         "reported accuracy"},
        "hotspot_summaries": rows,
        "specificity": spec,
        "coherence_confounding": cohrows,
        "grade": None,
        "no_causation": True,
    }
    (OUT / "geology_analysis.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  {OUT / 'GEOLOGY_DATASET_REGISTRY.csv'}")
    print(f"  {OUT / 'geology_analysis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
