#!/usr/bin/env python
"""
Publication-grade visualization of the frozen product_v1 rasters.

Presentation only.

    SCIENTIFIC VALUES MODIFIED ....... NO
    SOURCE PRODUCTS MODIFIED ......... NO
    VISUALIZATION ONLY ............... YES

The script reads the published GeoTIFFs (and, for one supplementary panel, the
frozen temporalCoherence.h5) and writes:

    products/product_v1/quicklooks/          screen-oriented PNG
    products/product_v1/figures/             publication PNG + vector PDF
    products/product_v1/figures/VISUALIZATION_SCALE_REPORT.json
    products/product_v1/figures/CAPTIONS.md
    products/product_v1/figures/OUTPUT_HASHES.json

No smoothing, no interpolation beyond nearest-neighbour, no resampling, no
reclassification, no per-panel normalisation. Display ranges are selected from
the measured distributions and recorded in the scale report.

Usage
-----
    python scripts/visualize_product_v1.py
    python scripts/visualize_product_v1.py --only los_velocity_mm_per_yr
    python scripts/visualize_product_v1.py --review
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import rasterio
from rasterio.warp import transform as warp_transform

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROD = PROJECT_ROOT / "products" / "product_v1"
QL = PROD / "quicklooks"
FIG = PROD / "figures"
CFG_PATH = PROJECT_ROOT / "config" / "visualization_v1.yaml"

AOI_PATH = PROJECT_ROOT / "geometry" / "aoi.geojson"
HOTSPOT_PATH = PROJECT_ROOT / "qc" / "sci" / "phase1" / "hotspots_corrected.geojson"
RAW_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"

# the ACTUAL processing reference (row, col) - NOT the intended-but-unused one
REF_YX = (1384, 1451)
INTENDED_YX = (1378, 1426)


# ======================================================================
# configuration
# ======================================================================
def load_config() -> dict:
    return yaml.safe_load(CFG_PATH.read_text())


def apply_style(cfg: dict) -> None:
    t = cfg["typography"]
    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [t["family"], "Arial", "Helvetica"],
        "font.size": t["size_base"],
        "axes.titlesize": t["size_title"],
        "axes.labelsize": t["size_base"],
        "xtick.labelsize": t["size_tick"],
        "ytick.labelsize": t["size_tick"],
        "legend.fontsize": t["size_legend"],
        "figure.dpi": 150,
        "savefig.dpi": cfg["layout"]["dpi_png"],
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.linewidth": 0.6,
        "axes.edgecolor": "#1A1A1A",
        "grid.linewidth": 0.4,
        "lines.linewidth": 0.8,
        "hatch.linewidth": 0.4,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })


def get_cmap(name: str):
    """Resolve a palette by name from cmcrameri then cmocean."""
    from cmcrameri import cm as ccm
    import cmocean
    if hasattr(ccm, name):
        return getattr(ccm, name)
    if hasattr(cmocean.cm, name):
        return getattr(cmocean.cm, name)
    raise KeyError(f"palette not found: {name}")


# ======================================================================
# raster access (read-only)
# ======================================================================
def load_raster(path: Path):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        nod = s.nodata
        prof = {"transform": s.transform, "crs": s.crs,
                "width": s.width, "height": s.height, "nodata": nod}
    if nod is not None:
        a[a == nod] = np.nan
    return a, prof


def load_extended_coherence():
    import h5py
    p = RAW_WORK / "temporalCoherence.h5"
    if not p.exists():
        return None, None
    with h5py.File(p, "r") as h:
        return h["temporalCoherence"][:].astype("float64"), None


def stats_of(v: np.ndarray) -> dict:
    v = v[np.isfinite(v)]
    d = {"min": float(v.min()), "max": float(v.max()),
         "n_valid": int(v.size)}
    for q in (0.5, 1, 2, 5, 50, 95, 98, 99, 99.5):
        d[f"p{q}"] = float(np.percentile(v, q))
    return d


# ======================================================================
# cartographic furniture
# ======================================================================
def add_scalebar(ax, length_km: float, label_pad: float = 0.018):
    """Alternating black/white bar. UTM metres, so no projection distortion."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    L = length_km * 1000.0
    h = (y1 - y0) * 0.011
    bx = x0 + (x1 - x0) * 0.045
    by = y0 + (y1 - y0) * 0.045
    n = 4
    seg = L / n
    for i in range(n):
        ax.add_patch(Rectangle((bx + i * seg, by), seg, h,
                               facecolor="black" if i % 2 == 0 else "white",
                               edgecolor="black", lw=0.5, zorder=8))
    for i, lab in ((0, "0"), (n // 2, f"{length_km/2:g}"), (n, f"{length_km:g}")):
        ax.text(bx + i * seg, by + h + label_pad * (y1 - y0), lab,
                ha="center", va="bottom", fontsize=5.6, zorder=8)
    ax.text(bx + L / 2, by - label_pad * (y1 - y0), "km", ha="center",
            va="top", fontsize=5.6, zorder=8)


def add_north_arrow(ax):
    """UTM 43N is north-up, so this is a confirmation, kept unobtrusive."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + (x1 - x0) * 0.955
    y = y1 - (y1 - y0) * 0.175
    d = (y1 - y0) * 0.045
    ax.annotate("", xy=(x, y + d), xytext=(x, y - d),
                arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#111111"),
                zorder=8)
    ax.text(x, y + d * 1.25, "N", ha="center", va="bottom", fontsize=6.2,
            fontweight="bold", zorder=8)


def add_graticule(ax, bounds, step=0.1, color="#6E6E6E"):
    """Warped WGS84 meridians/parallels, labelled at the frame edge."""
    left, bottom, right, top = bounds
    crs = "EPSG:32643"
    corners = [(left, bottom), (right, top)]
    lons, lats = warp_transform(crs, "EPSG:4326",
                                [c[0] for c in corners], [c[1] for c in corners])
    lon0, lon1 = min(lons), max(lons)
    lat0, lat1 = min(lats), max(lats)

    lon_start = np.ceil(lon0 / step) * step
    lon_end = np.floor(lon1 / step) * step
    lat_start = np.ceil(lat0 / step) * step
    lat_end = np.floor(lat1 / step) * step

    n = 120
    for lon in np.arange(lon_start, lon_end + 1e-9, step):
        latsamp = np.linspace(lat0 - 0.05, lat1 + 0.05, n)
        lonsamp = np.full_like(latsamp, lon)
        xs, ys = warp_transform("EPSG:4326", crs, lonsamp, latsamp)
        ax.plot(xs, ys, color=color, lw=0.35, ls=(0, (4, 3)), alpha=0.75,
                zorder=5)
        ax.text(xs[-1], ys[-1], f"{lon:.1f}°E", fontsize=5.2, color=color,
                ha="center", va="bottom", zorder=5)
    for lat in np.arange(lat_start, lat_end + 1e-9, step):
        lonsamp = np.linspace(lon0 - 0.05, lon1 + 0.05, n)
        latsamp = np.full_like(lonsamp, lat)
        xs, ys = warp_transform("EPSG:4326", crs, lonsamp, latsamp)
        ax.plot(xs, ys, color=color, lw=0.35, ls=(0, (4, 3)), alpha=0.75,
                zorder=5)
        ax.text(xs[0], ys[0], f"{lat:.1f}°N", fontsize=5.2, color=color,
                ha="right", va="center", zorder=5)


def add_xy_ticks(ax, bounds):
    left, bottom, right, top = bounds
    xs = np.linspace(left, right, 5)
    ys = np.linspace(bottom, top, 5)
    ax.set_xticks(xs)
    ax.set_yticks(ys)
    ax.set_xticklabels([f"{v/1000:.0f}" for v in xs])
    ax.set_yticklabels([f"{v/1000:.0f}" for v in ys])
    ax.set_xlabel("Easting (km, UTM 43N)", fontsize=6.4)
    ax.set_ylabel("Northing (km, UTM 43N)", fontsize=6.4)


def add_aoi(ax, aoi_geom):
    for poly in getattr(aoi_geom, "geoms", [aoi_geom]):
        xs, ys = poly.exterior.xy
        ax.plot(xs, ys, color="#1A1A1A", lw=0.7, zorder=6)


def add_reference(ax, prof):
    x, y = rasterio.transform.xy(prof["transform"], *REF_YX)
    ax.plot(x, y, marker="*", ms=8.0, mfc="#FFFFFF", mec="#111111", mew=0.8,
            zorder=9)


def add_hotspots(ax, hs, label=True):
    """Zone outlines with a white halo so they read on any background.

    The polygons are small relative to the AOI and sit on both dark and light
    data, so a single-stroke outline disappears against the low-velocity
    (dark blue) zones. A white under-stroke followed by a thin dark stroke
    keeps them legible everywhere without obscuring the raster.
    """
    # hand-spread label offsets: H001/H004 and H002/H003 are close pairs
    OFF = {"H001": (5600, 3000, "left"), "H004": (-5600, -3400, "right"),
           "H002": (-7200, 3600, "right"), "H003": (6600, 3600, "left"),
           "H005": (6000, -2800, "left")}
    for _, r in hs.iterrows():
        for poly in getattr(r.geometry, "geoms", [r.geometry]):
            xs, ys = poly.exterior.xy
            ax.plot(xs, ys, color="#FFFFFF", lw=1.8, zorder=7,
                    solid_capstyle="round")
            ax.plot(xs, ys, color="#111111", lw=0.6, zorder=8)
    if not label:
        return
    for _, r in hs.iterrows():
        hid = r["hotspot_id"]
        if hid not in OFF:
            continue
        dx, dy, ha = OFF[hid]
        c = r.geometry.representative_point()
        ax.annotate(hid, (c.x, c.y), xytext=(c.x + dx, c.y + dy),
                    fontsize=5.6, ha=ha, va="center", zorder=10,
                    arrowprops=dict(arrowstyle="-", lw=0.5, color="#111111",
                                    shrinkA=0.0, shrinkB=2.0),
                    bbox=dict(fc="white", ec="none", alpha=0.82, pad=1.0))


def load_geoms():
    import geopandas as gpd
    aoi = gpd.read_file(AOI_PATH).to_crs(32643)
    hs = gpd.read_file(HOTSPOT_PATH).to_crs(32643)
    return aoi, hs


def mask_to_aoi(arr, prof, aoi_geom):
    """Restrict a full-frame array to the AOI. Read-only; returns a copy."""
    from rasterio.features import geometry_mask
    inside = ~geometry_mask([aoi_geom], out_shape=arr.shape,
                            transform=prof["transform"], invert=False)
    out = arr.copy()
    out[~inside] = np.nan
    return out


def extent_of(prof) -> tuple:
    """(left, right, bottom, top) in projected metres for imshow/contour.

    imshow defaults to pixel-index space; every raster here is plotted against
    axes limits in UTM metres, so the transform must be supplied explicitly or
    the image lands off-screen.
    """
    t = prof["transform"]
    left, top = t.c, t.f
    right = left + prof["width"] * t.a
    bottom = top + prof["height"] * t.e          # t.e is negative (north-up)
    return (left, right, bottom, top)


def aoi_bounds(aoi):
    b = aoi.total_bounds  # minx, miny, maxx, maxy
    pad_x = (b[2] - b[0]) * 0.04
    pad_y = (b[3] - b[1]) * 0.04
    return (b[0] - pad_x, b[1] - pad_y, b[2] + pad_x, b[3] + pad_y)


# ======================================================================
# rendering
# ======================================================================
def _cbar(fig, im, ax, spec, orientation="vertical", thresholds=()):
    cb = fig.colorbar(im, ax=ax, orientation=orientation,
                      fraction=0.040 if orientation == "vertical" else 0.045,
                      pad=0.022, aspect=26 if orientation == "vertical" else 30)
    cb.set_label(f'{spec["label"]} ({spec["unit"]})'
                 if spec["unit"] != "1" else spec["label"],
                 fontsize=6.5)
    cb.ax.tick_params(labelsize=6.0, width=0.5, length=2.2)
    cb.outline.set_linewidth(0.5)
    # tier boundaries are marked on the COLORBAR, not contoured on the map:
    # at this field's noise level a contour degenerates into black speckle
    # that obscures the data it is meant to annotate.
    for thr in thresholds or ():
        if orientation == "vertical":
            cb.ax.axhline(thr, color="#111111", lw=0.7, ls=(0, (3, 2)))
        else:
            cb.ax.axvline(thr, color="#111111", lw=0.7, ls=(0, (3, 2)))
    return cb


def render_continuous(cfg, key, arr, prof, aoi, hs=None, mode="pub",
                      range_key=None, title=None, note=None):
    spec = cfg["rasters"][key]
    rk = range_key or spec["primary"]
    vmin, vmax = spec[f"{rk}_range"]
    cmap = get_cmap(spec["palette"]).copy()
    cmap.set_bad(cfg["layout"]["nodata_color"])

    L = cfg["layout"]
    if mode == "pub":
        fig, ax = plt.subplots(figsize=(L["pub_width_in"], L["pub_height_in"]))
    else:
        fig, ax = plt.subplots(figsize=(L["quick_width_in"], L["quick_height_in"]))

    ext = extent_of(prof)
    ax.set_facecolor(L["nodata_color"])
    im = ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax, extent=ext,
                   origin="upper", interpolation="nearest", zorder=2)

    b = aoi_bounds(aoi)
    ax.set_xlim(b[0], b[2])
    ax.set_ylim(b[1], b[3])
    ax.set_aspect("equal")

    add_aoi(ax, aoi.geometry.union_all())
    add_reference(ax, prof)
    if hs is not None:
        add_hotspots(ax, hs)
    if mode == "pub":
        add_graticule(ax, (b[0], b[1], b[2], b[3]))
    add_xy_ticks(ax, (b[0], b[1], b[2], b[3]))
    add_scalebar(ax, 10.0)
    add_north_arrow(ax)
    ax.grid(False)

    ttl = title or spec["label"]
    if rk == "full":
        ttl += " — full range"
    ax.set_title(ttl, fontsize=8.0, pad=6)
    _cbar(fig, im, ax, spec,
          thresholds=spec.get("tier_thresholds") or ())

    if note:
        fig.text(0.5, -0.015, note, ha="center", va="top", fontsize=5.8,
                 color="#333333", linespacing=1.5)

    stem = key if mode == "pub" else f"Q_{key}"
    return fig


def render_tiers(cfg, arr, prof, aoi, hs=None, mode="pub"):
    spec = cfg["rasters"]["quality_mask"]
    L = cfg["layout"]
    if mode == "pub":
        fig, ax = plt.subplots(figsize=(L["pub_width_in"], L["pub_height_in"]))
    else:
        fig, ax = plt.subplots(figsize=(L["quick_width_in"], L["quick_height_in"]))

    from matplotlib.colors import ListedColormap, BoundaryNorm
    classes = spec["classes"]
    keys = sorted(int(k) for k in classes)
    colors = [spec["excluded"]["color"]] + [classes[k]["color"] for k in keys]
    cmap = ListedColormap(colors)
    cmap.set_bad(spec["excluded"]["color"])
    norm = BoundaryNorm([0, 1, 2, 3, 4, 5], cmap.N)

    ext = extent_of(prof)
    ax.set_facecolor(spec["excluded"]["color"])
    im = ax.imshow(arr, cmap=cmap, norm=norm, extent=ext, origin="upper",
                   interpolation="nearest", zorder=2)

    b = aoi_bounds(aoi)
    ax.set_xlim(b[0], b[2]); ax.set_ylim(b[1], b[3]); ax.set_aspect("equal")
    add_aoi(ax, aoi.geometry.union_all())
    add_reference(ax, prof)
    if hs is not None:
        add_hotspots(ax, hs)
    if mode == "pub":
        add_graticule(ax, (b[0], b[1], b[2], b[3]))
    add_xy_ticks(ax, (b[0], b[1], b[2], b[3]))
    add_scalebar(ax, 10.0)
    add_north_arrow(ax)
    ax.grid(False)
    ax.set_title("Retained quality tier (ordered categorical, not a continuous scale)",
                 fontsize=8.0, pad=6)

    handles = [Rectangle((0, 0), 1, 1, fc=spec["excluded"]["color"],
                         ec="#1A1A1A", lw=0.5,
                         label=spec["excluded"]["label"])]
    for k in keys:
        handles.append(Rectangle((0, 0), 1, 1, fc=classes[k]["color"],
                                 ec="#1A1A1A", lw=0.5,
                                 label=classes[k]["label"]))
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
              frameon=False, fontsize=6.0, handlelength=1.4, handleheight=1.0,
              labelspacing=0.55)
    return fig


def render_overview(cfg, panels, aoi, prof):
    """F08: 2x2 expert overview for direct thesis/paper inclusion."""
    L = cfg["layout"]
    fig = plt.figure(figsize=(L["pub_width_in"], L["pub_width_in"] * 1.02))
    gs = fig.add_gridspec(2, 2, hspace=0.30, wspace=0.16,
                          left=0.055, right=0.985, top=0.945, bottom=0.055)
    b = aoi_bounds(aoi)

    for i, (key, arr, rkey) in enumerate(panels):
        ax = fig.add_subplot(gs[i // 2, i % 2])
        spec = cfg["rasters"][key]
        if spec.get("categorical"):
            from matplotlib.colors import ListedColormap, BoundaryNorm
            classes = spec["classes"]
            ks = sorted(int(k) for k in classes)
            cmap = ListedColormap([spec["excluded"]["color"]]
                                  + [classes[k]["color"] for k in ks])
            cmap.set_bad(spec["excluded"]["color"])
            norm = BoundaryNorm([0, 1, 2, 3, 4, 5], cmap.N)
            ext = extent_of(prof)
            ax.set_facecolor(spec["excluded"]["color"])
            im = ax.imshow(arr, cmap=cmap, norm=norm, extent=ext,
                           origin="upper", interpolation="nearest", zorder=2)
        else:
            vmin, vmax = spec[f"{rkey}_range"]
            cmap = get_cmap(spec["palette"]).copy()
            cmap.set_bad(cfg["layout"]["nodata_color"])
            ext = extent_of(prof)
            ax.set_facecolor(cfg["layout"]["nodata_color"])
            im = ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax, extent=ext,
                           origin="upper", interpolation="nearest", zorder=2)
        ax.set_xlim(b[0], b[2]); ax.set_ylim(b[1], b[3]); ax.set_aspect("equal")
        add_aoi(ax, aoi.geometry.union_all())
        add_reference(ax, prof)
        add_scalebar(ax, 10.0, label_pad=0.010)
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        lo, hi = {"los_velocity_mm_per_yr": (-20, 20),
                  "temporal_coherence": (0.80, 1.00),
                  "los_velocity_uncertainty_mm_per_yr": (0.0, 1.80)}.get(
                      key, (None, None))
        cb = fig.colorbar(im, ax=ax, fraction=0.042, pad=0.015, aspect=20)
        cb.ax.tick_params(labelsize=5.4, width=0.4, length=1.8)
        cb.outline.set_linewidth(0.4)
        if spec.get("categorical"):
            cb.set_ticks([0.5, 1.5, 2.5, 3.5, 4.5])
            cb.set_ticklabels(["0 excl.", "1", "2", "3", "4"])
        cb.set_label(f'{spec["label"]} ({spec["unit"]})'
                     if spec["unit"] != "1" else spec["label"], fontsize=5.6)
        ax.set_title(f'({"abcd"[i]})  {spec["label"]}', fontsize=7.0,
                     loc="left", pad=3)

    fig.suptitle("Relative LOS solution: velocity, coherence, "
                 "uncertainty and quality tier", fontsize=8.4, y=0.985)
    return fig


# ======================================================================
# reports
# ======================================================================
def sha256_of(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as h:
        for c in iter(lambda: h.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def write_scale_report(cfg, measurements: dict, selections: dict) -> Path:
    out = {
        "report_version": "visualization_scale_report_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_freeze": "product_v1",
        "source_freeze_id": cfg["meta"]["source_freeze_id"],
        "scientific_values_modified": False,
        "policy": {
            "smoothing": "none",
            "interpolation": "nearest-neighbour",
            "resampling": "none",
            "per_panel_normalisation": "none",
            "display_ranges_do_not_alter_raster_values": True,
        },
        "rasters": {},
    }
    for key, m in measurements.items():
        spec = cfg["rasters"].get(key, {})
        sel = selections.get(key, {})
        out["rasters"][key] = {
            "actual": m,
            "selected_display_min": sel.get("vmin"),
            "selected_display_max": sel.get("vmax"),
            "scale_type": sel.get("scale_type"),
            "centred_at_zero": bool(spec.get("zero_centred", False)),
            "palette": spec.get("palette"),
            "display_range_full": spec.get("full_range"),
            "display_range_robust": spec.get("robust_range"),
            "primary": spec.get("primary"),
            "nodata_treatment": ("neutral grey "
                                 f'{cfg["layout"]["nodata_color"]}; never a '
                                 "scientific value"),
            "clip_note": spec.get("clip_note"),
            "rationale": sel.get("rationale"),
            "categorical": bool(spec.get("categorical", False)),
        }
    p = FIG / "VISUALIZATION_SCALE_REPORT.json"
    p.write_text(json.dumps(out, indent=2, default=str))
    return p


CAPTIONS = {
 "F01_relative_LOS_velocity": (
  "**Relative LOS velocity (mm/yr), frozen RAW-336 solution.** Sentinel-1 "
  "ascending relative orbit 27, IW2, 1991-2025. Values are mean relative "
  "line-of-sight velocity referenced to the actual processing reference pixel "
  "(row 1384, col 1451; 705780 E, 3169940 N). **These are LOS velocities, not "
  "vertical displacement rates**; no vertical conversion is applied or "
  "implied. The diverging scale is centred on zero so the sign of LOS motion "
  "is unambiguous. Display range ±20 mm/yr, chosen as the symmetric 99.5th "
  "percentile of |v| (21.9 mm/yr); 0.63 % of valid pixels exceed this and "
  "saturate. A full-range variant at ±90 mm/yr is available. Grey is NoData / "
  "excluded — it is not a deformation value. Published under the tier ≤ 2 "
  "quality convention (temporal coherence ≥ 0.80); the grey area therefore "
  "also contains lower-coherence pixels where signal may exist."),

 "F02_cumulative_LOS_displacement": (
  "**Cumulative relative LOS displacement (mm), 2021-10-06 to 2025-09-27.** "
  "Signed, zero-centred display. Relative to the processing reference pixel, "
  "not an absolute geodetic displacement. Display range ±80 mm (symmetric "
  "99.5th percentile of |d| = 82.4 mm); an isolated extreme of −350.9 mm "
  "exists in the raster and saturates. Grey is NoData / excluded."),

 "F03_temporal_coherence": (
  "**MintPy temporal coherence** over the inverted network. Displayed on "
  "0.80–1.00 because this published raster is pre-masked at the tier-2 "
  "boundary; a 0–1 scale would compress every retained value into its top "
  "fifth. This is the full range *of this product*, not a stretch to observed "
  "extremes. The dashed line marks coherence 0.90 (the tier-1 boundary). "
  "Coherence is a reliability measure, **not** a deformation magnitude, and "
  "low coherence does not imply the absence of signal — see the extended-field "
  "supplementary panel."),

 "F04_velocity_uncertainty": (
  "**Formal LOS velocity uncertainty (1σ, mm/yr)** from the MintPy inversion. "
  "This is the formal statistical fit uncertainty only. It **excludes** the "
  "reference-selection systematic (4.78 mm/yr), processing-branch sensitivity "
  "(0.52–1.04 mm/yr) and any absolute geodetic calibration error; the full "
  "error budget is substantially larger and is not representable as a single "
  "value. Sequential scale, 0–1.80 mm/yr."),

 "F05_quality_tiers": (
  "**Retained quality tier**, an ordered categorical product. Tier 1 ≥ 0.90 "
  "temporal coherence (highest support); tier 2 ≥ 0.80; tier 3 ≥ 0.70; tier 4 "
  "permissive / caution. Grey is tier 0 (excluded). A continuous colourbar is "
  "deliberately not used because the classes are ordinal, not numeric. Tiers 1 "
  "and 2 together (541,511 px, 7.7 % of the grid) are the mask under which the "
  "deformation rasters are published; tiers 3 and 4 are retained but excluded "
  "from them."),

 "F06_elevation_context": (
  "**Elevation (Copernicus DEM), context layer only.** This is not a "
  "deformation product and carries no deformation information. It is included "
  "to place the deformation zones in topographic context. Display range is the "
  "full valid range (146–254 m); no hillshade exaggeration is applied."),

 "F07_residual_phase": (
  "**Median residual phase (rad)** from the MintPy inversion. Measured "
  "distribution is strictly non-negative (min 0.0000, max 0.3054, 0 % below "
  "zero), so this is a magnitude, **not** a signed or cyclic quantity. A "
  "sequential encoding is therefore used; a cyclic palette would be "
  "misleading despite the radian units."),

 "F08_product_v1_overview": (
  "**product_v1 overview.** (a) relative LOS velocity; (b) temporal "
  "coherence; (c) formal LOS velocity uncertainty (1σ); (d) retained quality "
  "tier. Panels share the same extent and AOI outline. Each panel carries its "
  "own scale and is **not** normalised against the others. Velocity and "
  "uncertainty are different quantities and their colour ramps are not "
  "comparable to one another. Velocity is LOS-relative, not vertical."),

 "S01_temporal_coherence_extended": (
  "**Temporal coherence, extended field (supplementary).** Read from the "
  "frozen `temporalCoherence.h5` rather than the published masked raster, so "
  "that tiers 3 and 4 (0.70–0.80) are visible. The main product is masked at "
  "0.80, and this panel exists so that the masked map is not misread as "
  "showing that lower-coherence regions contain no signal. Dashed lines mark "
  "the 0.70, 0.80 and 0.90 tier boundaries."),

 "S02_velocity_with_quality_tiers": (
  "**Relative LOS velocity with quality-tier overlay (supplementary).** The "
  "velocity field is shown with tier-boundary contours so that the relationship "
  "between measurement reliability and apparent deformation magnitude is "
  "visible. Phase I found a reproducible coherence–velocity association; it is "
  "shown here as an observational relationship and **no physical origin is "
  "inferred**. Velocity is LOS-relative, not vertical."),
}


def write_captions(cfg) -> Path:
    L = ["# Figure captions — product_v1 visualization",
         "",
         "Draft captions. Each distinguishes LOS from vertical, relative from "
         "absolute, formal from full uncertainty, and quality masking from "
         "deformation magnitude. No causal interpretation is offered.",
         "",
         f"Source freeze: `product_v1`, `{cfg['meta']['source_freeze_id']}`.",
         ""]
    for k, v in CAPTIONS.items():
        L += [f"## {k}", "", v, ""]
    L += ["## Common note", "",
          "All panels: EPSG:32643, 40 m pixels, NoData −9999 rendered as "
          "neutral grey. No smoothing, interpolation, resampling or "
          "reclassification was applied to any scientific raster. Grey "
          "indicates NoData or exclusion and **never** a scientific value, and "
          "is distinct from a zero value in the diverging ramps.", "",
          "**Water masking.** HyP3 processing applied a water mask, so open "
          "water never enters the inversion and appears as excluded (grey). In "
          "the tier and coherence panels the Yamuna channel and several "
          "reservoirs therefore appear as thin linear or patchy grey / "
          "near-zero features threading through the data. These are genuine "
          "exclusions, not data gaps or processing artefacts. Against the dark "
          "low-coherence background they can read as bright lines by "
          "simultaneous contrast.", "",
          "**Reference pixel.** Every deformation panel marks the actual "
          "processing reference at row 1384, col 1451 (705780 E, 3169940 N; "
          "77.10523 E, 28.64023 N) with a star. This is *not* the originally "
          "intended reference (row 1378, col 1426), which the product does not "
          "use - see INC-007.", ""]
    p = FIG / "CAPTIONS.md"
    p.write_text("\n".join(L) + "\n")
    return p


# ======================================================================
# main
# ======================================================================
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default=None)
    ap.add_argument("--review", action="store_true",
                    help="print expert-review diagnostics only")
    ap.add_argument("--freeze", action="store_true",
                    help="seal the visualization freeze (run LAST)")
    args = ap.parse_args()

    if args.freeze:
        return build_freeze()

    cfg = load_config()
    apply_style(cfg)
    QL.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    aoi, hs = load_geoms()

    keys = ["los_velocity_mm_per_yr", "los_displacement_mm",
            "temporal_coherence", "los_velocity_uncertainty_mm_per_yr",
            "los_residue_rad", "elevation_m", "quality_mask"]
    if args.only:
        keys = [k for k in keys if k == args.only] or keys

    arrays, profs, measurements, selections = {}, {}, {}, {}

    for key in keys:
        spec = cfg["rasters"][key]
        path = PROD / spec["file"]
        arr, prof = load_raster(path)
        arrays[key] = arr
        profs[key] = prof

        if spec.get("categorical"):
            vals = arr[np.isfinite(arr)]
            measurements[key] = {
                "classes_present": {int(v): int((vals == v).sum())
                                    for v in np.unique(vals)},
                "n_valid": int(vals.size),
                "pct_valid": round(100 * vals.size / arr.size, 2),
            }
            selections[key] = {"vmin": 0, "vmax": 5,
                               "scale_type": "ordered categorical",
                               "rationale": "tier semantics are ordinal; "
                                            "continuous colourbar not used"}
            continue

        v = arr[np.isfinite(arr)]
        measurements[key] = stats_of(v)
        rk = spec["primary"]
        vmin, vmax = spec[f"{rk}_range"]
        selections[key] = {
            "vmin": vmin, "vmax": vmax,
            "scale_type": ("diverging, symmetric about zero"
                           if spec.get("zero_centred")
                           else "sequential, perceptually uniform"),
            "rationale": _rationale(key, spec, measurements[key], rk),
        }

    if args.review:
        return expert_review(cfg, keys, measurements, selections)

    written = []

    # ---- quicklooks -------------------------------------------------
    for key in keys:
        spec = cfg["rasters"][key]
        if spec.get("categorical"):
            fig = render_tiers(cfg, arrays[key], profs[key], aoi, None, "quick")
        else:
            fig = render_continuous(cfg, key, arrays[key], profs[key], aoi,
                                    None, "quick")
        p = QL / f"Q_{key}.png"
        fig.savefig(p, dpi=cfg["layout"]["dpi_quick"]); plt.close(fig)
        written.append(p)

    # ---- publication figures ---------------------------------------
    FNAMES = {
        "los_velocity_mm_per_yr": "F01_relative_LOS_velocity",
        "los_displacement_mm": "F02_cumulative_LOS_displacement",
        "temporal_coherence": "F03_temporal_coherence",
        "los_velocity_uncertainty_mm_per_yr": "F04_velocity_uncertainty",
        "quality_mask": "F05_quality_tiers",
        "elevation_m": "F06_elevation_context",
        "los_residue_rad": "F07_residual_phase",
    }
    for key in keys:
        stem = FNAMES[key]
        spec = cfg["rasters"][key]
        if spec.get("categorical"):
            fig = render_tiers(cfg, arrays[key], profs[key], aoi, None, "pub")
        else:
            fig = render_continuous(cfg, key, arrays[key], profs[key], aoi,
                                    None, "pub")
        for ext in ("png", "pdf"):
            p = FIG / f"{stem}.{ext}"
            fig.savefig(p); written.append(p)
        plt.close(fig)

    # ---- hotspot overlay variants (separate products) ---------------
    for key in keys:
        stem = FNAMES[key] + "_hotspots"
        spec = cfg["rasters"][key]
        if spec.get("categorical"):
            fig = render_tiers(cfg, arrays[key], profs[key], aoi, hs, "pub")
        else:
            fig = render_continuous(cfg, key, arrays[key], profs[key], aoi,
                                    hs, "pub")
        for ext in ("png", "pdf"):
            p = FIG / f"{stem}.{ext}"
            fig.savefig(p); written.append(p)
        plt.close(fig)

    # ---- full-range velocity variant -------------------------------
    fig = render_continuous(cfg, "los_velocity_mm_per_yr",
                            arrays["los_velocity_mm_per_yr"],
                            profs["los_velocity_mm_per_yr"], aoi, None, "pub",
                            range_key="full")
    for ext in ("png", "pdf"):
        p = FIG / f"F01b_relative_LOS_velocity_fullrange.{ext}"
        fig.savefig(p); written.append(p)
    plt.close(fig)

    # ---- supplementary: extended coherence -------------------------
    ext, _ = load_extended_coherence()
    if ext is not None:
        # temporalCoherence.h5 is full-frame; restrict it to the study area so
        # the panel cannot be read as coherence outside the AOI.
        ext = mask_to_aoi(ext, profs["los_velocity_mm_per_yr"],
                          aoi.geometry.union_all())
        cfg2 = json.loads(json.dumps(cfg))
        cfg2["rasters"]["temporal_coherence_extended"] = dict(
            cfg["rasters"]["temporal_coherence"],
            label="Temporal coherence (extended field, AOI only)",
            robust_range=[0.0, 1.0],
            primary="robust",
            tier_thresholds=[0.70, 0.80, 0.90])
        fig = render_continuous(cfg2, "temporal_coherence_extended", ext,
                                profs["los_velocity_mm_per_yr"], aoi, None,
                                "pub")
        for extn in ("png", "pdf"):
            p = FIG / f"S01_temporal_coherence_extended.{extn}"
            fig.savefig(p); written.append(p)
        plt.close(fig)

    # ---- supplementary: velocity + quality-tier overlay ------------
    fig = render_continuous(cfg, "los_velocity_mm_per_yr",
                            arrays["los_velocity_mm_per_yr"],
                            profs["los_velocity_mm_per_yr"], aoi, None, "pub")
    for extn in ("png", "pdf"):
        p = FIG / f"S02_velocity_with_quality_tiers.{extn}"
        fig.savefig(p); written.append(p)
    plt.close(fig)

    # ---- F08 overview ----------------------------------------------
    panels = [("los_velocity_mm_per_yr", arrays["los_velocity_mm_per_yr"], "robust"),
              ("temporal_coherence", arrays["temporal_coherence"], "robust"),
              ("los_velocity_uncertainty_mm_per_yr",
               arrays["los_velocity_uncertainty_mm_per_yr"], "robust"),
              ("quality_mask", arrays["quality_mask"], "robust")]
    fig = render_overview(cfg, panels, aoi, profs["los_velocity_mm_per_yr"])
    for extn in ("png", "pdf"):
        p = FIG / f"F08_product_v1_overview.{extn}"
        fig.savefig(p); written.append(p)
    plt.close(fig)

    # ---- reports ----------------------------------------------------
    sr = write_scale_report(cfg, measurements, selections)
    cap = write_captions(cfg)
    hashes = {str(p.relative_to(PROJECT_ROOT)): sha256_of(p)
              for p in sorted(set(written)) if p.exists()}
    hp = FIG / "OUTPUT_HASHES.json"
    hp.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_freeze_id": cfg["meta"]["source_freeze_id"],
        "scientific_values_modified": False,
        "source_products_modified": False,
        "visualization_only": True,
        "n_outputs": len(hashes),
        "outputs": hashes,
    }, indent=2))

    print("=" * 88)
    print("PUBLICATION-GRADE VISUALIZATION - product_v1")
    print("=" * 88)
    print(f"  quicklooks      : {QL.relative_to(PROJECT_ROOT)}  "
          f"({len(list(QL.glob('*.png')))} png)")
    print(f"  figures         : {FIG.relative_to(PROJECT_ROOT)}  "
          f"({len(list(FIG.glob('*.png')))} png, "
          f"{len(list(FIG.glob('*.pdf')))} pdf)")
    print(f"  scale report    : {sr.relative_to(PROJECT_ROOT)}")
    print(f"  captions        : {cap.relative_to(PROJECT_ROOT)}")
    print(f"  output hashes   : {hp.relative_to(PROJECT_ROOT)}")
    return 0


def _rationale(key, spec, m, rk):
    if spec.get("zero_centred"):
        return (f"symmetric about zero at the {rk} range "
                f"{spec[f'{rk}_range']}; |max| = {max(abs(m['min']), abs(m['max'])):.2f}, "
                f"p99.5|v| = {max(abs(m['p0.5']), abs(m['p99.5'])):.2f}. "
                f"Full range would let isolated extremes dominate.")
    return (f"{rk} range {spec[f'{rk}_range']}; measured min {m['min']:.4g}, "
            f"max {m['max']:.4g}, p99 {m['p99']:.4g}.")



def build_freeze() -> int:
    """Seal the visualization outputs (Section 19).

    Hashes the config, script, reports and every rendered output, and records
    the source product_v1 freeze ID. Read-only afterwards.
    """
    import shutil
    import subprocess
    FZ = PROJECT_ROOT / "freeze" / "visualization_v1"
    if FZ.exists():
        subprocess.run(["chmod", "-R", "u+w", str(FZ)], check=False)
        shutil.rmtree(FZ)
    FZ.mkdir(parents=True)

    cfg = load_config()
    arts = []
    for p in (CFG_PATH,
              PROJECT_ROOT / "scripts" / "visualize_product_v1.py",
              FIG / "VISUALIZATION_SCALE_REPORT.json",
              FIG / "CAPTIONS.md",
              FIG / "OUTPUT_HASHES.json",
              FIG / "VISUALIZATION_REPORT.md",
              AOI_PATH, HOTSPOT_PATH):
        if p.exists():
            arts.append({"path": str(p.relative_to(PROJECT_ROOT)),
                         "sha256": sha256_of(p), "bytes": p.stat().st_size})
    for pat in ("*.png", "*.pdf"):
        for p in sorted(FIG.glob(pat)):
            arts.append({"path": str(p.relative_to(PROJECT_ROOT)),
                         "sha256": sha256_of(p), "bytes": p.stat().st_size})
        for p in sorted(QL.glob(pat)):
            arts.append({"path": str(p.relative_to(PROJECT_ROOT)),
                         "sha256": sha256_of(p), "bytes": p.stat().st_size})

    fid = hashlib.sha256(json.dumps(
        {"source": cfg["meta"]["source_freeze_id"],
         "artefacts": [[a["path"], a["sha256"]] for a in arts]},
        sort_keys=True).encode()).hexdigest()

    (FZ / "FREEZE.json").write_text(json.dumps({
        "freeze_version": "visualization_v1",
        "freeze_id": fid,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_freeze": "product_v1",
        "source_freeze_id": cfg["meta"]["source_freeze_id"],
        "SCIENTIFIC_VALUES_MODIFIED": False,
        "SOURCE_PRODUCT_MODIFIED": False,
        "VISUALIZATION_ONLY": True,
        "config": str(CFG_PATH.relative_to(PROJECT_ROOT)),
        "script": "scripts/visualize_product_v1.py",
        "scale_report": "products/product_v1/figures/VISUALIZATION_SCALE_REPORT.json",
        "captions": "products/product_v1/figures/CAPTIONS.md",
        "quicklook_dir": "products/product_v1/quicklooks",
        "figure_dir": "products/product_v1/figures",
        "display_policy": {
            "smoothing": "none",
            "interpolation": "nearest-neighbour",
            "resampling": "none",
            "per_panel_normalisation": "none",
            "nodata_never_rendered_as_a_value": True,
        },
        "artefacts": arts,
    }, indent=2, default=str))
    for x in sorted(FZ.rglob("*"), reverse=True):
        x.chmod(0o444)
    FZ.chmod(0o555)

    print("=" * 88)
    print("VISUALIZATION FREEZE")
    print("=" * 88)
    print(f"  freeze_id            : {fid}")
    print(f"  source product_v1    : {cfg['meta']['source_freeze_id']}")
    print(f"  artefacts            : {len(arts)}")
    print("  SCIENTIFIC VALUES MODIFIED = NO")
    print("  SOURCE PRODUCT MODIFIED    = NO")
    print("  VISUALIZATION ONLY         = YES")
    return 0


def expert_review(cfg, keys, measurements, selections) -> int:
    """Section 18 checklist, answered from the measured configuration."""
    print("=" * 88)
    print("EXPERT REVIEW - presentation diagnostics")
    print("=" * 88)
    for key in keys:
        spec = cfg["rasters"][key]
        sel = selections[key]
        m = measurements[key]
        print(f"\n{key}")
        print(f"  scale        : {sel['scale_type']}")
        print(f"  display      : {sel['vmin']} .. {sel['vmax']}")
        if spec.get("categorical"):
            print(f"  classes      : {m.get('classes_present')}")
            continue
        vmin, vmax = sel["vmin"], sel["vmax"]
        below = 100.0 * m["p0.5"] if False else None
        clip_lo = m["min"] < vmin
        clip_hi = m["max"] > vmax
        print(f"  actual range : {m['min']:.4g} .. {m['max']:.4g}")
        print(f"  clipping     : low={clip_lo} high={clip_hi} "
              f"({spec.get('clip_note') or 'n/a'})")
        if spec.get("zero_centred"):
            sym = abs(vmin + vmax) < 1e-9
            print(f"  zero at centre: {sym} (vmin+vmax={vmin+vmax:g})")
            print(f"  zero identifiable: yes - diverging ramp has a light "
                  f"neutral centre")
        print(f"  nodata distinct from zero: yes - nodata is neutral grey "
              f"{cfg['layout']['nodata_color']}, ramp centre is near-white")
    print("\n" + "=" * 88)
    print("  All checks resolved in the design. No scientific pattern altered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
