#!/usr/bin/env python
"""
Phase V: definitive main figure set (F1-F8).

Publication rendering only. Every panel is drawn from the frozen evidence set;
no quantity is recomputed, no dataset added.

F1  study design / acquisition geometry
F2  ascending authoritative relative LOS velocity
F3  (already rendered) hotspot classification
F4  ascending vs descending agreement, D0 and D2
F5  H001 + H004 independent support
F6  H002 + H003 negative controls
F7  H005 cross-geometry contradiction
F8  rate-versus-history caveat

Usage
-----
    python scripts/71_phase5_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.patches import Patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
P4 = PROJECT_ROOT / "qc" / "sci" / "phase4"
P2C = PROJECT_ROOT / "qc" / "sci" / "phase2c"
FIGS = P4 / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 200, "font.size": 8,
    "axes.titlesize": 9, "axes.labelsize": 8, "axes.grid": True,
    "grid.alpha": 0.25, "axes.axisbelow": True, "savefig.bbox": "tight",
})

C_SUP = "#1b7837"   # independently supported
C_NEG = "#b2182b"   # not reproduced
C_CON = "#7b3294"   # contradiction
C_BG = "#d9d9d9"


def hotspot_colors(h):
    return {"H001": C_SUP, "H004": C_SUP, "H002": C_NEG,
            "H003": C_NEG, "H005": C_CON}.get(h, C_BG)


def load_velocity():
    p = PROJECT_ROOT / "products" / "product_v1" / "los_velocity_mm_per_yr.tif"
    with rasterio.open(p) as s:
        v = s.read(1).astype(float)
        v[s.read_masks(1) == 0] = np.nan
    return v


def load_quality():
    p = PROJECT_ROOT / "products" / "product_v1" / "quality_mask.tif"
    if not p.exists():
        return None
    with rasterio.open(p) as s:
        return s.read(1)


# --------------------------------------------------------------------------
def fig1():
    rep = json.loads((PROJECT_ROOT / "geometry" / "descending"
                      / "coverage_report.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))

    ax = axes[0]
    ax.set_title("F1  Acquisition geometry and asymmetric coverage")
    ax.set_xlabel("Easting (km, EPSG:32643)")
    ax.set_ylabel("Northing (km)")
    ax.set_aspect("equal")
    ax.grid(False)
    # schematic: AOI box, ascending full coverage, descending strip
    ax.add_patch(plt.Rectangle((0, 0), 100, 100, fc="#f0f0f0",
                               ec="k", lw=0.8, zorder=1))
    ax.text(50, 96, "AOI 1,962.4 km$^2$", ha="center", va="top", fontsize=7)
    ax.add_patch(plt.Rectangle((0, 0), 100, 100, fc="#4393c3", alpha=0.18,
                               ec="none", zorder=2))
    ax.text(50, 50, "ascending  orbit 27 / IW2\n4 bursts  •  full AOI",
            ha="center", va="center", fontsize=7.5, color="#2166ac", zorder=4)
    # descending covers all hotspots but misses the west
    ax.add_patch(plt.Rectangle((22, 0), 78, 100, fc="#d6604d", alpha=0.22,
                               ec="#b2182b", lw=0.9, ls="--", zorder=3))
    ax.text(61, 22, "descending  orbit 136 / IW1\n4 bursts  •  72.0 % of AOI",
            ha="center", va="center", fontsize=7.5, color="#b2182b", zorder=5)
    ax.annotate("western strip not covered", xy=(11, 62), xytext=(3, 78),
                fontsize=7, color="#b2182b",
                arrowprops=dict(arrowstyle="->", color="#b2182b", lw=0.9))
    for h, (x, y) in {"H001": (48, 58), "H004": (66, 40), "H002": (36, 74),
                      "H003": (74, 66), "H005": (56, 30)}.items():
        ax.plot(x, y, "o", ms=6, mfc=hotspot_colors(h), mec="k", mew=0.6,
                zorder=6)
        ax.text(x + 2.2, y + 1.2, h, fontsize=6.8, zorder=6)
    ax.set_xlim(-4, 104)
    ax.set_ylim(-4, 104)
    ax.set_xticks([])
    ax.set_yticks([])

    ax = axes[1]
    ax.set_title("Independent coverage, no shared acquisition")
    ax.axis("off")
    rows = [
        ("", "Ascending", "Descending"),
        ("Orbit / subswath", "27 / IW2", "136 / IW1"),
        ("Acquisitions", "119", "91"),
        ("Interferograms", "336", "219"),
        ("AOI covered", "100 %", "72.0 %"),
        ("Hotspots covered", "5 / 5", "5 / 5"),
        ("Shared bursts", "—", "none"),
        ("Shared pairs", "—", "none"),
    ]
    tb = ax.table(cellText=[r[1:] for r in rows[1:]],
                  rowLabels=[r[0] for r in rows[1:]],
                  colLabels=rows[0][1:], loc="center", cellLoc="center")
    tb.auto_set_font_size(False)
    tb.set_fontsize(7.5)
    tb.scale(1, 1.55)
    for (r, c), cell in tb.get_celld().items():
        cell.set_linewidth(0.4)
        if r == 0:
            cell.set_facecolor("#e8e8e8")
            cell.set_text_props(weight="bold")
    ax.text(0.5, 0.055,
            "the descending stack was built independently:\n"
            "no pair was selected because it intersected a hotspot",
            ha="center", va="bottom", fontsize=7, style="italic",
            transform=ax.transAxes)
    fig.savefig(FIGS / "F01_study_design.png")
    plt.close(fig)


# --------------------------------------------------------------------------
def fig2():
    v = load_velocity()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.0),
                             gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axes[0]
    ax.set_title("F2  Ascending relative LOS velocity (authoritative, RAW-336)")
    im = ax.imshow(v, cmap="RdYlBu_r", vmin=-20, vmax=20)
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    cb = fig.colorbar(im, ax=ax, fraction=0.042, pad=0.02)
    cb.set_label("relative LOS velocity (mm/yr)", fontsize=7)
    ax.text(0.02, 0.02, "blue = moving away from satellite (negative LOS)",
            transform=ax.transAxes, fontsize=6.5, color="w",
            bbox=dict(fc="k", alpha=0.45, ec="none", pad=1.6))

    ax = axes[1]
    ax.set_title("Distribution is strongly asymmetric")
    fin = v[np.isfinite(v)]
    ax.hist(fin, bins=220, range=(-90, 40), color="#4393c3", lw=0)
    ax.set_yscale("log")
    ax.axvline(np.median(fin), color="k", lw=1.0, ls="--")
    ax.annotate(f"median {np.median(fin):+.2f} mm/yr",
                xy=(np.median(fin), ax.get_ylim()[1] * 0.35),
                xytext=(-6, 0), textcoords="offset points",
                ha="right", fontsize=7)
    ax.axvspan(-90, -10, color="#b2182b", alpha=0.10, lw=0)
    ax.text(-50, ax.get_ylim()[1] * 0.02,
            "deformation carried by a\nminority of the AOI",
            ha="center", fontsize=6.8, color="#b2182b")
    ax.set_xlabel("relative LOS velocity (mm/yr)")
    ax.set_ylabel("pixel count (log)")
    ax.set_xlim(-90, 40)
    fig.savefig(FIGS / "F02_ascending_velocity.png")
    plt.close(fig)


# --------------------------------------------------------------------------
def fig4():
    """Real aggregates only.

    Per-pixel paired values were not retained in the frozen evidence set, so
    no scatter is drawn. Fabricating a distribution from reported moments
    would misrepresent the data.
    """
    rv = json.loads((PROJECT_ROOT / "qc" / "sci" / "phase2b"
                     / "revalidation_v2.json").read_text())
    d0 = rv["agreement_v1_phase2a"]
    d2 = rv["agreement_v2"]
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.6),
                             gridspec_kw={"width_ratios": [1, 1.1]})

    ax = axes[0]
    ax.set_title("Unwrap correction improves every agreement metric",
                 fontsize=8.5)
    mets = [("Pearson", "pearson"), ("Spearman", "spearman"),
            ("Plane-detrended", "plane_detrended")]
    x = np.arange(len(mets))
    v0 = [d0[k] for _, k in mets]
    v2 = [d2[k] for _, k in mets]
    ax.bar(x - 0.19, v0, 0.38, color="#b2182b", label="D0  raw descending")
    ax.bar(x + 0.19, v2, 0.38, color="#1b7837", label="D2  unwrap-corrected")
    for i, (a_, b_) in enumerate(zip(v0, v2)):
        ax.text(i - 0.19, a_ + 0.012, f"{a_:.3f}", ha="center", fontsize=6.5,
                color="#b2182b")
        ax.text(i + 0.19, b_ + 0.012, f"{b_:.3f}", ha="center", fontsize=6.5,
                color="#1b7837")
    ax.set_xticks(x)
    ax.set_xticklabels([m for m, _ in mets])
    ax.set_ylabel("cross-track agreement")
    ax.set_ylim(0, 0.46)
    ax.legend(fontsize=6.5, loc="upper left")
    ax.text(0.5, -0.30,
            "n = 854,321 shared pixels; agreement remains moderate",
            transform=ax.transAxes, ha="center", fontsize=6.8, style="italic")

    ax = axes[1]
    ax.set_title("Reproduction is spatial, and sharply selective", fontsize=8.5)
    hs, ov = [], []
    for h in rv["hotspots"]:
        hs.append(h["hotspot_id"])
        ov.append(h["overlap_fraction"])
    cols = [hotspot_colors(h) for h in hs]
    ax.bar(hs, ov, color=cols, width=0.58)
    ax.axhline(0.5, color="k", lw=0.8, ls="--")
    ax.text(4.45, 0.52, "half of hotspot area", fontsize=6.3, ha="right")
    for i, v in enumerate(ov):
        ax.text(i, v + 0.025, f"{v:.2f}", ha="center", fontsize=7)
    ax.set_ylabel("descending-detected fraction\nof ascending hotspot area")
    ax.set_ylim(0, 1.15)
    ax.legend(handles=[Patch(fc=C_SUP, label="reproduced"),
                       Patch(fc=C_NEG, label="not reproduced"),
                       Patch(fc=C_CON, label="contradiction")],
              fontsize=6.3, loc="upper center", ncol=3, framealpha=0.9,
              bbox_to_anchor=(0.5, 1.0))

    fig.suptitle("F4  Unwrapping, not viewing geometry, limited cross-track "
                 "agreement", y=1.03, fontsize=9)
    fig.savefig(FIGS / "F04_cross_geometry_agreement.png")
    plt.close(fig)


# --------------------------------------------------------------------------
def _grouped(ax, ht, ids, width=0.36):
    """Vertical grouped bars: ascending vs descending mean LOS rate."""
    sub = ht[ht.hotspot.isin(ids)].set_index("hotspot").loc[ids]
    x = np.arange(len(ids))
    a_ = sub.ascending_rate_mm_per_yr.values
    d_ = sub.descending_rate_mm_per_yr.values
    ax.bar(x - width / 2, a_, width, color="#4393c3", label="ascending")
    ax.bar(x + width / 2, d_, width, color="#d6604d", label="descending")
    ax.axhline(0, color="k", lw=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(ids)
    ax.set_ylabel("mean LOS rate (mm/yr)")
    span = max(abs(np.concatenate([a_, d_])).max(), 1.0)
    for i, (va, vd) in enumerate(zip(a_, d_)):
        for off, v, c in ((-width / 2, va, "#2166ac"),
                          (width / 2, vd, "#b2182b")):
            up = v >= 0
            ax.text(i + off, v + (span * 0.035 if up else -span * 0.035),
                    f"{v:+.1f}", ha="center",
                    va="bottom" if up else "top", fontsize=6.4, color=c)
    ax.set_ylim(-span * 1.30, span * 1.30)
    return sub, a_, d_


def fig5(ht):
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.6),
                             gridspec_kw={"width_ratios": [1.3, 1]})
    _grouped(axes[0], ht, ["H001", "H004"])
    axes[0].set_title("F5  H001 + H004 — independently supported",
                      fontsize=8.5)
    axes[0].legend(fontsize=6.5, loc="lower left")

    ax = axes[1]
    d = ht[ht.hotspot.isin(["H001", "H004"])].set_index("hotspot")
    ratio = (d.descending_rate_mm_per_yr / d.ascending_rate_mm_per_yr).abs()
    ax.bar(["H001", "H004"], ratio.values, color=C_SUP, width=0.5)
    ax.axhline(1.0, color="k", lw=1.0, ls="--")
    ax.text(1.45, 1.03, "exact agreement", fontsize=6.5, ha="right")
    for i, v in enumerate(ratio.values):
        ax.text(i, v + 0.03, f"{v:.2f}×", ha="center", fontsize=7.5)
    ax.set_ylim(0, 1.45)
    ax.set_ylabel("descending / ascending magnitude")
    ax.set_title("Amplitude agreement", fontsize=8.5)
    fig.text(0.5, -0.08,
             "spatial and mean-rate characteristics reproduced\n"
             "3.17 km$^2$ = area of Phase-I deformation zones independently "
             "supported at the hotspot level by the descending geometry\n"
             "this is not a validated extent and is not extrapolated",
             ha="center", fontsize=6.8, style="italic")
    fig.savefig(FIGS / "F05_supported_features.png")
    plt.close(fig)


def fig6(ht):
    """The matched comparison.

    H001 is excluded deliberately: at -31/-36 mm/yr it would dominate the
    y-range and crush the H004-vs-H002/H003 contrast that carries the
    argument. H001 belongs to F5.
    """
    ids = ["H004", "H002", "H003"]
    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    _grouped(ax, ht, ids)
    ax.set_ylim(-25.0, 25.0)
    ax.axvspan(0.5, 2.5, color=C_NEG, alpha=0.07, lw=0)

    ax.text(0, 17.5, "reproduced\n(ascending ∧ descending)",
            ha="center", va="center", fontsize=7.2, color=C_SUP,
            weight="bold")
    ax.text(1.5, 17.5, "not reproduced\n(ascending only)",
            ha="center", va="center", fontsize=7.2, color=C_NEG,
            weight="bold")

    # matched-band ascending contrast is the preregistered comparison
    mb = {"H004": -12.13, "H002": -11.60, "H003": -10.93}
    for i, h in enumerate(ids):
        ax.text(i, -20.0, f"matched-band contrast\n{mb[h]:.2f} mm/yr",
                ha="center", va="center", fontsize=6.3, color="#444444")

    ax.set_title("F6  H002 + H003 — negative controls\n"
                 "comparable ascending signal, adequate descending quality",
                 fontsize=8.5)
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=2, frameon=False)
    fig.text(0.5, -0.20,
             "the controls match H004's ascending magnitude and carry adequate "
             "descending quality (TC 0.90 / 0.89)\n"
             "yet show no descending counterpart — any explanation acting "
             "across the affected terrain predicts all three\n"
             "similarly, and therefore fails on selectivity",
             ha="center", fontsize=6.8, style="italic")
    fig.savefig(FIGS / "F06_negative_controls.png")
    plt.close(fig)


def fig7(ht):
    r = ht.set_index("hotspot").loc["H005"]
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ax.bar([0, 1], [r.ascending_rate_mm_per_yr, r.descending_rate_mm_per_yr],
           color=["#4393c3", "#d6604d"], width=0.5)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["ascending", "descending"])
    ax.set_ylabel("mean LOS rate (mm/yr)")
    ax.set_title("F7  H005 — unresolved cross-geometry contradiction", fontsize=8.5)
    for i, v in enumerate([r.ascending_rate_mm_per_yr,
                           r.descending_rate_mm_per_yr]):
        ax.text(i, v + (3 if v >= 0 else -3), f"{v:+.2f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=8)
    ax.annotate("not a reproduction failure:\nthe two geometries actively disagree",
                xy=(0.5, 10), xytext=(0.5, 34), ha="center", fontsize=7,
                color=C_CON,
                arrowprops=dict(arrowstyle="->", color=C_CON, lw=0.9))
    ax.set_ylim(-30, 75)
    fig.savefig(FIGS / "F07_H005_contradiction.png")
    plt.close(fig)


def fig8():
    """Real frozen temporal values only.

    Per-epoch cumulative series were not retained, so endpoint totals and
    detrended correlation are shown instead of a reconstructed curve.
    """
    p = P2C / "hotspot_reconciliation.json"
    if not p.exists():
        return
    temp = json.loads(p.read_text())["temporal"]

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6),
                             gridspec_kw={"width_ratios": [1.15, 1]})

    ax = axes[0]
    ax.set_title("F8  Cumulative displacement totals by geometry",
                 fontsize=8.5)
    order = ["H001", "H004", "H002", "H003", "H005"]
    order = [h for h in order if h in temp]
    x = np.arange(len(order))
    a_ = [temp[h]["ascending_total_mm"] for h in order]
    d_ = [temp[h]["descending_total_mm"] for h in order]
    ax.bar(x - 0.19, a_, 0.38, color="#4393c3", label="ascending")
    ax.bar(x + 0.19, d_, 0.38, color="#d6604d", label="descending")
    ax.axhline(0, color="k", lw=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(order)
    ax.set_ylabel("total cumulative LOS displacement (mm)")
    ax.legend(fontsize=6.5, loc="lower left")
    for i, (va, vd) in enumerate(zip(a_, d_)):
        ax.text(i - 0.19, va + (4 if va >= 0 else -4), f"{va:+.0f}",
                ha="center", va="bottom" if va >= 0 else "top", fontsize=6.3)
        ax.text(i + 0.19, vd + (4 if vd >= 0 else -4), f"{vd:+.0f}",
                ha="center", va="bottom" if vd >= 0 else "top", fontsize=6.3)
    ax.axvspan(-0.5, 1.5, color=C_SUP, alpha=0.08, lw=0)
    ax.text(0.5, ax.get_ylim()[0] * 0.80, "supported features",
            ha="center", fontsize=6.5, color=C_SUP)

    ax = axes[1]
    ax.set_title("Where independent reproduction applies", fontsize=8.5)
    rows = [("Spatial pattern", "reproduced", C_SUP),
            ("Mean rate", "reproduced", C_SUP),
            ("Amplitude ratio", "reproduced", C_SUP),
            ("Cumulative history", "NOT reproduced", C_NEG)]
    for i, (lab, val, col) in enumerate(rows):
        yy = 0.78 - i * 0.185
        ax.text(0.02, yy, lab, fontsize=8.5, transform=ax.transAxes,
                va="center")
        ax.text(0.60, yy, val, fontsize=8.5, color=col, weight="bold",
                transform=ax.transAxes, va="center")
    h1 = temp.get("H001", {})
    ax.text(0.02, 0.045,
            f"H001 detrended cross-geometry correlation "
            f"r = {h1.get('pearson_detrended', float('nan')):.3f}\n"
            f"ascending {h1.get('ascending_total_mm', float('nan')):+.1f} mm  "
            f"vs descending {h1.get('descending_total_mm', float('nan')):+.1f} mm",
            fontsize=6.8, style="italic", transform=ax.transAxes)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)

    fig.text(0.5, -0.05,
             "the ascending and descending H001 cumulative series differ "
             "substantially — independent reproduction does not extend to "
             "the detailed displacement history",
             ha="center", fontsize=6.8, style="italic")
    fig.savefig(FIGS / "F08_rate_vs_history.png")
    plt.close(fig)


def main() -> int:
    ht = pd.read_csv(P4 / "final_hotspot_table.csv")
    fig1()
    fig2()
    fig4()
    fig5(ht)
    fig6(ht)
    fig7(ht)
    fig8()
    print("=" * 88)
    print("PHASE V - DEFINITIVE FIGURE SET")
    print("=" * 88)
    for p in sorted(FIGS.glob("F0*.png")) + sorted(FIGS.glob("F1*.png")):
        print(f"     {p.relative_to(PROJECT_ROOT)}  ({p.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
