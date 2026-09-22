#!/usr/bin/env python
"""
Phase V-B: publication re-render of F1-F8 and F12 on the shared style.

Styling only. Every plotted value is read from the frozen evidence set; no
statistic is recomputed and no unretained sample is synthesised.

F1  study design (real frozen coverage geometry, not a schematic)
F2  ascending relative LOS velocity
F3  hotspot cross-geometry classification
F4  cross-track agreement (aggregate retained statistics only)
F5  H001 + H004 independently supported
F6  H002 + H003 negative controls (H001 excluded for plotting scale)
F7  H005 unresolved contradiction
F8  cumulative totals and the rate-versus-history caveat
F12 competing-hypothesis evidence matrix

Usage
-----
    python scripts/73_phase5b_restyle.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pubstyle as ps  # noqa: E402

P4 = ps.PROJECT_ROOT / "qc" / "sci" / "phase4"
P2B = ps.PROJECT_ROOT / "qc" / "sci" / "phase2b"
P2C = ps.PROJECT_ROOT / "qc" / "sci" / "phase2c"
GEO = ps.PROJECT_ROOT / "geometry"

ASC = ps.GEOM["ascending"]
DESC = ps.GEOM["descending"]


# ======================================================================
def _grouped(ax, ht, ids, width=0.36, ylab="mean LOS rate (mm yr$^{-1}$)"):
    sub = ht[ht.hotspot.isin(ids)].set_index("hotspot").loc[ids]
    x = np.arange(len(ids))
    a_ = sub.ascending_rate_mm_per_yr.values
    d_ = sub.descending_rate_mm_per_yr.values
    ax.bar(x - width / 2, a_, width, facecolor=ASC["color"],
           edgecolor="black", lw=0.4, label=ASC["label"])
    ax.bar(x + width / 2, d_, width, facecolor=DESC["color"],
           edgecolor="black", lw=0.4, hatch=DESC["hatch"], label=DESC["label"])
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(ids)
    ax.set_ylabel(ylab)
    span = max(abs(np.concatenate([a_, d_])).max(), 1.0)
    for i, (va, vd) in enumerate(zip(a_, d_)):
        for off, v in ((-width / 2, va), (width / 2, vd)):
            up = v >= 0
            ax.text(i + off, v + (span * 0.04 if up else -span * 0.04),
                    f"{v:+.1f}", ha="center",
                    va="bottom" if up else "top", fontsize=5.6)
    ax.set_ylim(-span * 1.28, span * 1.28)
    return sub


# ======================================================================
def fig1():
    """Real frozen coverage geometry. No schematic content."""
    import geopandas as gpd

    aoi = gpd.read_file(GEO / "aoi.geojson").to_crs(32643)
    ba = gpd.read_file(GEO / "selected_bursts.geojson").to_crs(32643)
    bd = gpd.read_file(GEO / "descending" / "selected_bursts.geojson").to_crs(32643)
    hs = gpd.read_file(ps.PROJECT_ROOT / "qc" / "sci" / "phase1"
                       / "hotspots_corrected.geojson").to_crs(32643)

    # the uncovered strip: AOI minus the descending burst union
    uncovered = gpd.GeoDataFrame(
        geometry=[aoi.geometry.union_all().difference(bd.geometry.union_all())],
        crs=32643)

    fig = plt.figure(figsize=(ps.DOUBLE_COL, 3.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1], wspace=0.33)
    ax = fig.add_subplot(gs[0, 0])

    aoi.plot(ax=ax, facecolor="#F5F5F5", edgecolor="none", zorder=0)
    ba.plot(ax=ax, facecolor=ASC["color"], edgecolor="none", alpha=0.22,
            zorder=1)
    bd.plot(ax=ax, facecolor=DESC["color"], edgecolor="none", alpha=0.28,
            zorder=2)
    uncovered.plot(ax=ax, facecolor="none", edgecolor="#B00020", lw=0.0,
                   hatch="xxx", zorder=3)
    aoi.boundary.plot(ax=ax, edgecolor="black", lw=0.7, zorder=4)

    # hotspots are genuinely small; mark with a ring plus a leader label.
    # Offsets are hand-spread because H001/H004 and H002/H003 are close pairs.
    LABEL_OFF = {
        "H001": (5200, 2600, "left"),
        "H004": (-5200, -3000, "right"),
        "H002": (-6800, 3400, "right"),
        "H003": (6200, 3400, "left"),
        "H005": (5600, -2600, "left"),
    }
    for _, r in hs.iterrows():
        c = r.geometry.representative_point()
        ax.plot(c.x, c.y, marker="o", ms=2.6, mfc="white", mec="black",
                mew=0.5, zorder=6)
    for hid, (dx, dy, ha) in LABEL_OFF.items():
        r = hs[hs.hotspot_id == hid].iloc[0]
        c = r.geometry.representative_point()
        ax.annotate(hid, (c.x, c.y), xytext=(c.x + dx, c.y + dy),
                    fontsize=5.8, ha=ha, va="center", zorder=7,
                    arrowprops=dict(arrowstyle="-", lw=0.4, color="#666666",
                                    shrinkA=0.0, shrinkB=1.5))

    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_aspect("equal")
    ps.panel_label(ax, "A", dx=-0.02, dy=1.01)
    ax.set_title("Acquisition coverage and classification zones", fontsize=7.2)

    ax = fig.add_subplot(gs[0, 1])
    ax.axis("off")
    ps.panel_label(ax, "B", dx=-0.04, dy=1.01)
    ax.set_title("Independent stacks, no shared acquisition", fontsize=7.2)
    rows = [("Orbit / subswath", "27 / IW2", "136 / IW1"),
            ("Acquisitions", "119", "91"),
            ("Interferograms", "336", "219"),
            ("AOI covered", "100 %", "72.0 %"),
            ("Zones covered", "5 / 5", "5 / 5"),
            ("Shared bursts", "none", "none"),
            ("Shared pairs", "none", "none")]
    tb = ax.table(cellText=[list(r[1:]) for r in rows],
                  rowLabels=[r[0] for r in rows],
                  colLabels=["ascending", "descending"], loc="center",
                  cellLoc="center", bbox=[0.0, 0.10, 1.0, 0.82])
    tb.auto_set_font_size(False)
    tb.set_fontsize(6.0)
    for (r, c), cell in tb.get_celld().items():
        cell.set_linewidth(0.4)
        if r == 0:
            cell.set_facecolor("#EDEDED")
            cell.set_text_props(weight="bold")

    fig.legend(handles=[
        plt.Rectangle((0, 0), 1, 1, fc=ASC["color"], alpha=0.35, ec="none",
                      label="ascending bursts"),
        plt.Rectangle((0, 0), 1, 1, fc=DESC["color"], alpha=0.40, ec="none",
                      label="descending bursts"),
        plt.Rectangle((0, 0), 1, 1, fc="none", ec="#B00020", hatch="xxx",
                      label="AOI not covered by descending (28.0 %)"),
    ] + ps.status_legend(), loc="lower center", bbox_to_anchor=(0.5, -0.055),
        ncol=3, fontsize=5.6, handletextpad=0.5, columnspacing=1.2)

    ps.note(fig,
            "Frozen geometry only. Descending covers 72.0 % of the AOI because four contiguous bursts "
            "cannot span the full study area at this track;\n"
            "the uncovered western strip contains no classification zone. The descending stack was "
            "constructed independently — no burst, pair, mask\nor acquisition list is shared, and no pair "
            "was selected because it intersected a zone.",
            y=-0.135)
    return ps.save(fig, "F01_study_design")


# ======================================================================
def fig2():
    p = ps.PROJECT_ROOT / "products" / "product_v1" / "los_velocity_mm_per_yr.tif"
    with rasterio.open(p) as s:
        v = s.read(1).astype(float)
        v[s.read_masks(1) == 0] = np.nan

    fig, axes = plt.subplots(1, 2, figsize=(ps.DOUBLE_COL, 2.9),
                             gridspec_kw={"width_ratios": [1.3, 1]})
    ax = axes[0]
    im = ax.imshow(v, cmap="RdYlBu_r", vmin=-20, vmax=20)
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.043, pad=0.02)
    cb.set_label("relative LOS velocity (mm yr$^{-1}$)", fontsize=6.2)
    cb.ax.tick_params(labelsize=5.8)
    cb.outline.set_linewidth(0.4)
    ps.panel_label(ax, "A", dx=-0.02, dy=1.01)
    ax.set_title("Ascending relative LOS velocity", fontsize=7.5)
    ax.text(0.02, 0.02, "blue = moving away from satellite",
            transform=ax.transAxes, fontsize=5.6, color="white",
            bbox=dict(fc="black", alpha=0.5, ec="none", pad=1.4))

    ax = axes[1]
    fin = v[np.isfinite(v)]
    ax.hist(fin, bins=200, range=(-90, 40), color="#9E9E9E", lw=0)
    ax.set_yscale("log")
    med = float(np.median(fin))
    ax.axvline(med, color="black", lw=0.8, ls="--")
    ax.annotate(f"median {med:+.2f}", xy=(med, 2e4), xytext=(-6, 0),
                textcoords="offset points", ha="right", fontsize=5.8)
    ax.set_xlabel("relative LOS velocity (mm yr$^{-1}$)")
    ax.set_ylabel("pixel count (log scale)")
    ax.set_xlim(-90, 40)
    ps.panel_label(ax, "B", dx=-0.16, dy=1.01)
    ax.set_title("Strongly asymmetric distribution", fontsize=7.5)

    ps.note(fig,
            "Authoritative ascending product (RAW-336, 336 interferograms retained, no pair excluded). "
            "Values are RELATIVE LOS rates, not vertical\ndisplacement. The reference pixel carries a "
            "4.78 mm yr$^{-1}$ systematic that offsets the absolute zero level; spatial gradients are "
            "invariant to it.", y=-0.02)
    return ps.save(fig, "F02_ascending_velocity")


# ======================================================================
def fig3(ht):
    fig, ax = plt.subplots(figsize=(ps.ONE_HALF_COL, 2.9))
    ids = ps.MAIN_ORDER
    _grouped(ax, ht, ids)
    ax.set_ylim(-46, 76)
    ax.legend(handles=ps.geom_legend(), loc="lower left", fontsize=5.8)
    # status strip drawn OUTSIDE the axes so the rate axis stays tight
    for i, h in enumerate(ids):
        s = ps.style_of(h)
        ax.add_patch(plt.Rectangle((i - 0.42, -0.185), 0.84, 0.045,
                                   transform=ax.get_xaxis_transform(),
                                   facecolor=s["color"], edgecolor="black",
                                   lw=0.4, hatch=s["hatch"], clip_on=False,
                                   zorder=6))
    ax.text(-0.185, -0.162, "status", transform=ax.transAxes, fontsize=5.4,
            ha="right", va="center", color="#333333")
    ax.set_title("F3  Cross-geometry classification of the five zones",
                 fontsize=7.5)
    ps.note(fig,
            "Status strip: independently supported (H001, H004), not reproduced (H002, H003), "
            "cross-geometry contradiction (H005).\n"
            "Rates are mean relative LOS over each zone's common-domain pixels; ascending and "
            "descending are separate geometries and are\nnot converted to vertical displacement.",
            y=-0.10)
    return ps.save(fig, "F03_hotspot_classification")


# ======================================================================
def fig4():
    rv = json.loads((P2B / "revalidation_v2.json").read_text())
    d0, d2 = rv["agreement_v1_phase2a"], rv["agreement_v2"]

    fig, axes = plt.subplots(1, 2, figsize=(ps.DOUBLE_COL, 2.7),
                             gridspec_kw={"width_ratios": [1, 1.15]})
    ax = axes[0]
    mets = [("Pearson", "pearson"), ("Spearman", "spearman"),
            ("Plane\ndetrended", "plane_detrended")]
    x = np.arange(len(mets))
    v0 = [d0[k] for _, k in mets]
    v2 = [d2[k] for _, k in mets]
    ax.bar(x - 0.19, v0, 0.38, facecolor="#BFBFBF", edgecolor="black",
           lw=0.4, label="D0  raw descending")
    ax.bar(x + 0.19, v2, 0.38, facecolor="#4D4D4D", edgecolor="black",
           lw=0.4, hatch="///", label="D2  unwrap-corrected")
    for i, (a_, b_) in enumerate(zip(v0, v2)):
        ax.text(i - 0.19, a_ + 0.014, f"{a_:.3f}", ha="center", fontsize=5.6)
        ax.text(i + 0.19, b_ + 0.014, f"{b_:.3f}", ha="center", fontsize=5.6)
    ax.set_xticks(x)
    ax.set_xticklabels([m for m, _ in mets])
    ax.set_ylabel("cross-track agreement")
    ax.set_ylim(0, 0.46)
    ax.legend(loc="upper left", fontsize=5.6)
    ps.panel_label(ax, "A", dx=-0.18, dy=1.01)
    ax.set_title("Unwrap correction improves every metric", fontsize=7.0)

    ax = axes[1]
    hs = [h["hotspot_id"] for h in rv["hotspots"]]
    ov = [h["overlap_fraction"] for h in rv["hotspots"]]
    bars = ax.bar(hs, ov, 0.6, color=[ps.style_of(h)["color"] for h in hs],
                  edgecolor="black", lw=0.4)
    for b, h in zip(bars, hs):
        b.set_hatch(ps.style_of(h)["hatch"])
    ax.axhline(0.5, color=ps.REF_COLOR, lw=ps.REF_LW, ls="--")
    for i, v in enumerate(ov):
        ax.text(i, v + 0.03, f"{v:.2f}", ha="center", fontsize=5.6)
    ax.set_ylabel("descending-detected fraction\nof ascending zone area")
    ax.set_ylim(0, 1.18)
    ax.legend(handles=ps.status_legend(), loc="upper center", fontsize=5.4,
              ncol=3, columnspacing=0.8, handletextpad=0.4)
    ps.panel_label(ax, "B", dx=-0.16, dy=1.01)
    ax.set_title("Reproduction is spatial and sharply selective", fontsize=7.0)

    ps.note(fig,
            "Panel A values are RETAINED AGGREGATE agreement statistics over 854,321 shared-domain pixels; "
            "paired per-pixel values were not retained,\nso no pixel-level scatter is shown and none is "
            "synthesised. Panel B is the fraction of each ascending zone overlapped by a\n"
            "descending-detected component. Agreement is moderate and spatially heterogeneous, not global.",
            y=-0.02)
    return ps.save(fig, "F04_cross_geometry_agreement")


# ======================================================================
def fig5(ht):
    fig, axes = plt.subplots(1, 2, figsize=(ps.DOUBLE_COL, 2.8),
                             gridspec_kw={"width_ratios": [1.35, 1]})
    _grouped(axes[0], ht, ["H001", "H004"])
    axes[0].legend(handles=ps.geom_legend(), loc="lower left", fontsize=5.8)
    ps.panel_label(axes[0], "A", dx=-0.14, dy=1.01)
    axes[0].set_title("H001 + H004 — independently supported", fontsize=7.0)

    ax = axes[1]
    d = ht[ht.hotspot.isin(["H001", "H004"])].set_index("hotspot")
    ratio = (d.descending_rate_mm_per_yr / d.ascending_rate_mm_per_yr).abs()
    bars = ax.bar(["H001", "H004"], ratio.values, 0.5,
                  color=[ps.style_of(h)["color"] for h in ["H001", "H004"]],
                  edgecolor="black", lw=0.4)
    ax.axhline(1.0, color="black", lw=0.8, ls="--")
    ax.text(1.45, 1.03, "exact agreement", fontsize=5.6, ha="right")
    for i, v in enumerate(ratio.values):
        ax.text(i, v + 0.03, f"{v:.2f}×", ha="center", fontsize=6.2)
    ax.set_ylim(0, 1.45)
    ax.set_ylabel("descending / ascending magnitude")
    ps.panel_label(ax, "B", dx=-0.20, dy=1.01)
    ax.set_title("Amplitude agreement", fontsize=7.0)

    ps.note(fig,
            "Spatial and mean-rate characteristics are reproduced; the detailed displacement "
            "histories are NOT (see F8).\n"
            "6.66 km$^2$ is the area of Phase-I zones independently supported at the zone level by the "
            "descending geometry (H001 + H004).\n"
            "It is not a validated extent, is not extrapolated beyond these zones, and is not a "
            "vertical displacement rate.", y=-0.02)
    return ps.save(fig, "F05_supported_features")


# ======================================================================
def fig6(ht):
    """H001 is excluded for plotting scale only — stated on the figure."""
    ids = ["H004", "H002", "H003"]
    fig, ax = plt.subplots(figsize=(ps.ONE_HALF_COL, 3.0))
    _grouped(ax, ht, ids)
    ax.set_ylim(-25.0, 26.0)
    ax.axvspan(0.5, 2.5, facecolor="#F2F2F2", edgecolor="none", zorder=0)

    ax.text(0, 17.5, "reproduced", ha="center", va="center", fontsize=7.0,
            color=ps.STATUS["supported"]["color"], weight="bold")
    ax.text(1.5, 17.5, "not reproduced", ha="center", va="center", fontsize=7.0,
            color=ps.STATUS["not_reproduced"]["color"], weight="bold")

    mb = {"H004": -12.13, "H002": -11.60, "H003": -10.93}
    for i, h in enumerate(ids):
        ax.text(i, -20.5, f"matched-band contrast\n{mb[h]:.2f}", ha="center",
                va="center", fontsize=5.6, color="#333333")

    ax.legend(handles=ps.geom_legend(), loc="upper center",
              bbox_to_anchor=(0.5, -0.14), ncol=2, fontsize=5.8)
    ax.set_title("F6  H002 + H003 — negative controls", fontsize=7.5)
    ps.note(fig,
            "H001 is omitted from this panel for plotting scale only: at −30.9 / −36.0 mm yr$^{-1}$ it "
            "would compress the comparison shown here.\nIt is reported in F5 and is not selectively "
            "excluded. The descending geometry shows adequate quality at H002/H003 (temporal\n"
            "coherence 0.900 / 0.886) yet no matching component. Any explanation acting across the "
            "affected terrain predicts all three similarly,\nand therefore fails on selectivity.",
            y=-0.26)
    return ps.save(fig, "F06_negative_controls")


# ======================================================================
def fig7(ht):
    r = ht.set_index("hotspot").loc["H005"]
    fig, ax = plt.subplots(figsize=(ps.SINGLE_COL, 2.9))
    ax.bar([0, 1], [r.ascending_rate_mm_per_yr, r.descending_rate_mm_per_yr],
           0.55, facecolor=[ASC["color"], DESC["color"]], edgecolor="black",
           lw=0.4)
    ax.patches[1].set_hatch(DESC["hatch"])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["ascending", "descending"])
    ax.set_ylabel("mean LOS rate (mm yr$^{-1}$)")
    for i, v in enumerate([r.ascending_rate_mm_per_yr,
                           r.descending_rate_mm_per_yr]):
        ax.text(i, v + (3 if v >= 0 else -3), f"{v:+.2f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=6.2)
    ax.set_ylim(-30, 78)
    ax.annotate("the two geometries\nactively disagree", xy=(0.5, 12),
                xytext=(0.5, 40), ha="center", fontsize=6.0,
                color=ps.STATUS["contradiction"]["color"],
                arrowprops=dict(arrowstyle="->", lw=0.7,
                                color=ps.STATUS["contradiction"]["color"]))
    ax.set_title("F7  H005 — unresolved cross-geometry contradiction",
                 fontsize=7.5)
    ps.note(fig,
            "This is not a reproduction failure: the geometries disagree in sign and magnitude. "
            "H005 is retained in the main text as an\nunresolved result. No explanation for the "
            "contradiction is offered here, and none is claimed.", y=0.0)
    return ps.save(fig, "F07_H005_contradiction")


# ======================================================================
def fig8():
    temp = json.loads((P2C / "hotspot_reconciliation.json").read_text())["temporal"]

    fig, axes = plt.subplots(1, 2, figsize=(ps.DOUBLE_COL, 2.8),
                             gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axes[0]
    order = [h for h in ps.MAIN_ORDER if h in temp]
    x = np.arange(len(order))
    a_ = [temp[h]["ascending_total_mm"] for h in order]
    d_ = [temp[h]["descending_total_mm"] for h in order]
    ax.bar(x - 0.19, a_, 0.38, facecolor=ASC["color"], edgecolor="black",
           lw=0.4, label=ASC["label"])
    ax.bar(x + 0.19, d_, 0.38, facecolor=DESC["color"], edgecolor="black",
           lw=0.4, hatch=DESC["hatch"], label=DESC["label"])
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(order)
    ax.set_ylabel("total cumulative LOS (mm)")
    ax.legend(loc="lower left", fontsize=5.8)
    for i, (va, vd) in enumerate(zip(a_, d_)):
        for off, v in ((-0.19, va), (0.19, vd)):
            up = v >= 0
            ax.text(i + off, v + (6 if up else -6), f"{v:+.0f}", ha="center",
                    va="bottom" if up else "top", fontsize=5.4)
    ax.set_ylim(-235, 60)
    ps.panel_label(ax, "A", dx=-0.12, dy=1.01)
    ax.set_title("Cumulative totals differ by geometry", fontsize=7.0)

    ax = axes[1]
    ax.axis("off")
    ps.panel_label(ax, "B", dx=-0.02, dy=1.01)
    ax.set_title("Scope of independent reproduction", fontsize=7.0)
    rows = [("Spatial pattern", "reproduced", True),
            ("Mean rate", "reproduced", True),
            ("Amplitude ratio", "reproduced", True),
            ("Cumulative history", "NOT reproduced", False)]
    for i, (lab, val, ok) in enumerate(rows):
        yy = 0.76 - i * 0.185
        ax.text(0.02, yy, lab, fontsize=7.0, transform=ax.transAxes,
                va="center")
        ax.text(0.58, yy, val, fontsize=7.0, transform=ax.transAxes,
                va="center", weight="bold",
                color=ps.STATUS["supported" if ok else "not_reproduced"]["color"])
    h1 = temp.get("H001", {})
    ax.text(0.02, 0.05,
            f"H001 detrended cross-geometry\ncorrelation r = "
            f"{h1.get('pearson_detrended', float('nan')):.3f}\n"
            f"ascending {h1.get('ascending_total_mm', float('nan')):+.1f} mm vs "
            f"descending {h1.get('descending_total_mm', float('nan')):+.1f} mm",
            fontsize=5.8, transform=ax.transAxes, linespacing=1.4)

    ps.note(fig,
            "Retained cumulative endpoint totals are shown; per-epoch series were not retained and are "
            "NOT reconstructed. Independent reproduction\nextends to the spatial and mean-rate "
            "characteristics only — the ascending and descending H001 cumulative series differ "
            "substantially.", y=-0.02)
    return ps.save(fig, "F08_rate_vs_history")


# ======================================================================
def fig12():
    """Evidence matrix.

    The state is encoded as a swatch rather than by hatching the whole cell,
    so that no hatch ever overprints the text.
    """
    em = pd.read_csv(P4 / "final_evidence_matrix.csv")
    ENC = {
        "NO EVIDENCE": ("#8C8C8C", None),
        "NOT ADEQUATELY TESTED": ("#D9D9D9", "///"),
        "NOT TESTABLE": ("#FFFFFF", "..."),
    }
    fig, ax = plt.subplots(figsize=(ps.DOUBLE_COL, 2.6))
    ax.axis("off")
    ax.grid(False)
    n = len(em)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, n + 0.5)

    ax.text(0.012, n + 0.24, "competing hypothesis", fontsize=6.4,
            weight="bold", va="center")
    ax.text(0.598, n + 0.24, "evidence state", fontsize=6.4, weight="bold",
            va="center")
    ax.plot([0, 1], [n + 0.06, n + 0.06], color="black", lw=0.6)

    for i, r in em.iterrows():
        y = n - i - 0.5
        state = r.evidence_state
        fc, ht = ENC.get(state, ("#EFEFEF", "xxx"))
        ax.add_patch(plt.Rectangle((0, y - 0.42), 1.0, 0.84,
                                   facecolor="white", edgecolor="black",
                                   lw=0.4))
        ax.plot([0.59, 0.59], [y - 0.42, y + 0.42], color="black", lw=0.4)
        # swatch encodes the category without touching the text
        ax.add_patch(plt.Rectangle((0.605, y - 0.20), 0.030, 0.40,
                                   facecolor=fc, edgecolor="black", lw=0.4,
                                   hatch=ht))
        ax.text(0.012, y, r.hypothesis, fontsize=6.2, va="center")
        if len(state) > 34:
            a_, _, b_ = state.partition(", ")
            ax.text(0.655, y + 0.17, a_ + ",", fontsize=5.8, va="center")
            ax.text(0.655, y - 0.17, b_, fontsize=5.8, va="center")
        else:
            ax.text(0.655, y, state, fontsize=6.0, va="center")

    ax.text(0.0, -0.42,
            "NO EVIDENCE = a suitable test was conducted and did not support the hypothesis   ·   "
            "NOT ADEQUATELY TESTED = available evidence does not observe the relevant physical domain   ·   "
            "NOT TESTABLE = the necessary dataset was unavailable.\nThese three categories are distinct and "
            "are never collapsed, and none of them is equivalent to \"ruled out\".",
            fontsize=5.6, va="top", color="#333333", linespacing=1.5)
    ax.set_title("F12  Competing-hypothesis evidence matrix (frozen)", fontsize=7.5,
                 y=1.02)
    return ps.save(fig, "F12_evidence_matrix")


def main() -> int:
    ps.apply_style()
    ht = pd.read_csv(P4 / "final_hotspot_table.csv")
    written = []
    for fn in (fig1, fig2, lambda: fig3(ht), fig4, lambda: fig5(ht),
               lambda: fig6(ht), lambda: fig7(ht), fig8, fig12):
        written += fn()
    print("=" * 88)
    print("PHASE V-B - PUBLICATION RE-RENDER F1-F8, F12")
    print("=" * 88)
    for p in written:
        print(f"     {p.relative_to(ps.PROJECT_ROOT)}  "
              f"({p.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
