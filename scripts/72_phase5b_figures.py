#!/usr/bin/env python
"""
Phase V-B: publication re-render of F9, F10, F11.

Styling only. Every plotted value is read from an existing frozen
machine-readable table. No statistic is recomputed, no derived quantity is
created, no frozen result is regenerated.

F9   groundwater lag / falsification diagnostic
F10  shallow soil-texture comparison
F11  urban-intensity comparison

Usage
-----
    python scripts/72_phase5b_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pubstyle as ps  # noqa: E402

P3 = ps.PROJECT_ROOT / "qc" / "sci" / "phase3"

ASC = ps.GEOM["ascending"]
DESC = ps.GEOM["descending"]

# role -> grayscale-safe pair for lag diagnostics (deliberately NOT the
# hotspot-status colours, which encode something different)
LAGROLE = {
    "forward":      {"color": "#BFBFBF", "hatch": None,  "label": "forward lag (causal direction)"},
    "falsification": {"color": "#4D4D4D", "hatch": "///", "label": "falsification lag (reverse direction)"},
}


# ======================================================================
def fig9():
    """Groundwater lag / falsification diagnostic.

    Source: qc/sci/phase3/groundwater_lag_results.csv
            qc/sci/phase3/groundwater_control_comparison.csv
    """
    lag = pd.read_csv(P3 / "groundwater_lag_results.csv")
    ctl = pd.read_csv(P3 / "groundwater_control_comparison.csv")
    hs = ["H001", "H004", "H002", "H003"]          # H005 has no GW test
    markers = {"H001": "o", "H004": "s", "H002": "^", "H003": "D"}
    styles = {"H001": "-", "H004": "-", "H002": "--", "H003": "--"}

    fig, axes = plt.subplots(1, 2, figsize=(ps.DOUBLE_COL, 2.75),
                             gridspec_kw={"width_ratios": [1.35, 1]})

    # ---- A: lag curve ------------------------------------------------
    ax = axes[0]
    lo, hi = -105, 105
    ax.axvspan(lo, 0, facecolor="#F2F2F2", edgecolor="none", zorder=0)
    ax.axvline(0, color="black", lw=0.6, zorder=1)
    ax.axhline(0, color="black", lw=0.6, zorder=1)

    for hid in hs:
        d = lag[lag.hotspot == hid].sort_values("lag_days")
        s = ps.style_of(hid)
        ax.plot(d.lag_days, d.spearman, styles[hid], marker=markers[hid],
                color=s["color"], mec="black", mew=0.4, ms=3.4, lw=0.9,
                label=f"{hid}  ({'supported' if hid in ('H001','H004') else 'control'})",
                zorder=3)

    ax.set_xlim(lo, hi)
    ax.set_ylim(-0.52, 0.36)
    ax.set_xticks([-90, -60, -30, 0, 30, 60, 90])
    ax.set_xlabel("lag applied to groundwater (days)")
    ax.set_ylabel("Spearman ρ  (GW depth anomaly vs LOS)")
    ps.panel_label(ax, "A", dx=-0.13)
    ax.set_title("Lag correlations", fontsize=7.5)
    ax.text(-52, 0.30, "falsification\ndirection", ha="center", fontsize=6.0,
            color="#333333", linespacing=1.3)
    ax.text(52, 0.30, "causal\ndirection", ha="center", fontsize=6.0,
            color="#333333", linespacing=1.3)
    ax.annotate("prediction-consistent sign", xy=(88, -0.40), ha="right",
                fontsize=5.8, color="#333333")
    ax.annotate("", xy=(92, -0.46), xytext=(92, -0.30),
                arrowprops=dict(arrowstyle="->", lw=0.6, color="#333333"))
    ax.legend(loc="lower left", fontsize=5.6, ncol=2, columnspacing=0.7,
              handletextpad=0.5)

    # ---- B: forward vs falsification magnitude -----------------------
    ax = axes[1]
    x = np.arange(len(hs))
    w = 0.36
    fwd = [abs(ctl.loc[ctl.hotspot == h, "mean_positive_rho"].iloc[0]) for h in hs]
    fal = [abs(ctl.loc[ctl.hotspot == h, "mean_negative_rho"].iloc[0]) for h in hs]
    ax.bar(x - w / 2, fwd, w, facecolor=LAGROLE["forward"]["color"],
           edgecolor="black", lw=0.4, label=LAGROLE["forward"]["label"])
    ax.bar(x + w / 2, fal, w, facecolor=LAGROLE["falsification"]["color"],
           edgecolor="black", lw=0.4, hatch=LAGROLE["falsification"]["hatch"],
           label=LAGROLE["falsification"]["label"])
    ax.set_xticks(x)
    ax.set_xticklabels(hs)
    ax.set_ylabel("|mean Spearman ρ|")
    ax.set_ylim(0, 0.44)
    ps.panel_label(ax, "B", dx=-0.15)
    ax.set_title("Falsification ≥ forward at all four", fontsize=7.5)
    ax.legend(loc="upper right", fontsize=5.6)

    ps.note(fig,
            "Source: frozen groundwater lag tables (NWDP six-hourly depth-to-water telemetry, "
            "station-anomaly composited).\n"
            "Protocol expectation is a NEGATIVE association (deeper groundwater → more negative LOS). "
            "Forward lags test the causal direction;\n"
            "reverse lags are falsification tests. 0 of 16 forward-lag tests survive Benjamini–Hochberg "
            "FDR q = 0.05 (all permutation p ≥ 0.49).\n"
            "H005 has no groundwater composite and is absent. This is not a refutation of groundwater "
            "as a mechanism: aquifer metadata, well depths and\n"
            "screened intervals are unavailable, and LOS is not vertical displacement.",
            y=-0.04)
    return ps.save(fig, "F09_groundwater_falsification")


# ======================================================================
def fig10():
    """Shallow soil texture.

    Source: qc/sci/phase3/geology_hotspot_summary.csv
    Background values are the frozen report-level AOI-minus-hotspots means
    recorded in PHASE_IIIB_GEOLOGICAL_EVIDENCE_REPORT.md.
    """
    g = pd.read_csv(P3 / "geology_hotspot_summary.csv")
    bg = {"clay_0-5cm": 22.76, "clay_100-200cm": 24.64, "sand_0-5cm": 43.92}
    order = ["H001", "H004", "H002", "H003", "H005"]

    panels = [("clay_0-5cm", "A", "Clay 0–5 cm", "% by mass"),
              ("clay_100-200cm", "B", "Clay 100–200 cm", "% by mass"),
              ("sand_0-5cm", "C", "Sand 0–5 cm", "% by mass")]

    fig, axes = plt.subplots(1, 3, figsize=(ps.DOUBLE_COL, 2.6))
    for ax, (col, letter, title, ylab) in zip(axes, panels):
        vals = [g.loc[g.hotspot_id == h, col].iloc[0] for h in order]
        cols = [ps.style_of(h)["color"] for h in order]
        hat = [ps.style_of(h)["hatch"] for h in order]
        bars = ax.bar(order, vals, 0.62, color=cols, edgecolor="black", lw=0.4)
        for b, h in zip(bars, hat):
            b.set_hatch(h)
        ax.axhline(bg[col], color=ps.REF_COLOR, lw=ps.REF_LW, ls="--", zorder=3)
        ax.set_ylabel(ylab)
        ax.set_title(f"{title}\nbackground {bg[col]:.1f}%", fontsize=6.8)
        ps.panel_label(ax, letter, dx=-0.20)
        ax.set_ylim(0, max(vals + [bg[col]]) * 1.22)
        for i, v in enumerate(vals):
            ax.text(i, v + 0.4, f"{v:.1f}", ha="center", fontsize=5.6)

    fig.legend(handles=ps.status_legend(), loc="upper center",
               bbox_to_anchor=(0.5, 1.045), ncol=3, fontsize=5.8,
               handletextpad=0.4, columnspacing=1.4)
    ps.suptitle(fig, "Shallow substrate texture — supported zones are COARSER, "
                     "opposite to the predicted fine-sediment direction", y=1.14)
    ps.note(fig,
            "Source: SoilGrids v2.0 (ISRIC), 250 m, sampled on the native grid — a shallow "
            "soil-texture SURROGATE, not a geological map.\n"
            "It samples the upper ~2 m only and does not observe the compaction interval; "
            "lithology, formation and age are not identified.\n"
            "Supported zones carry −5.0 pp less clay and +6.4 pp more sand than controls. "
            "H005 is shown for completeness and is not part of the\n"
            "supported/control contrast. Deep geological / aquifer-system susceptibility is "
            "NOT ADEQUATELY TESTED, not exonerated.",
            y=-0.06)
    return ps.save(fig, "F10_soil_texture")


# ======================================================================
def fig11():
    """Urban built intensity.

    Source: qc/sci/phase3/urban_hotspot_summary.csv
    Background values from PHASE_IIIC_URBAN_EVIDENCE_REPORT.md.
    """
    u = pd.read_csv(P3 / "urban_hotspot_summary.csv")
    order = ["H001", "H004", "H002", "H003", "H005"]

    fig, axes = plt.subplots(1, 2, figsize=(ps.DOUBLE_COL, 2.7),
                             gridspec_kw={"width_ratios": [1, 1]})

    # ---- A: WorldCover built fraction -------------------------------
    ax = axes[0]
    vals = [u.loc[u.hotspot_id == h, "wc_builtfrac_2021"].iloc[0] for h in order]
    bars = ax.bar(order, vals, 0.62,
                  color=[ps.style_of(h)["color"] for h in order],
                  edgecolor="black", lw=0.4)
    for b, h in zip(bars, order):
        b.set_hatch(ps.style_of(h)["hatch"])
    ax.axhline(33.74, color=ps.REF_COLOR, lw=ps.REF_LW, ls="--", zorder=3)
    ax.set_ylabel("built fraction (%)")
    ax.set_ylim(0, 100)
    ax.set_title("ESA WorldCover 2021\nbackground 33.7%", fontsize=6.8)
    ps.panel_label(ax, "A", dx=-0.18)
    for i, v in enumerate(vals):
        ax.text(i, v + 1.6, f"{v:.1f}", ha="center", fontsize=5.6)

    # ---- B: GHSL built surface --------------------------------------
    ax = axes[1]
    gv = [u.loc[u.hotspot_id == h, "ghsl_2020"].iloc[0] for h in order]
    bars = ax.bar(order, gv, 0.62,
                  color=[ps.style_of(h)["color"] for h in order],
                  edgecolor="black", lw=0.4)
    for b, h in zip(bars, order):
        b.set_hatch(ps.style_of(h)["hatch"])
    ax.axhline(225.0, color=ps.REF_COLOR, lw=ps.REF_LW, ls="--", zorder=3)
    ax.set_ylabel("built surface (m$^2$ cell$^{-1}$)")
    ax.set_ylim(0, 4600)
    ax.set_title("GHSL GHS-BUILT-S E2020\nbackground 225 m$^2$", fontsize=6.8)
    ps.panel_label(ax, "B", dx=-0.18)
    for i, v in enumerate(gv):
        ax.text(i, v + 70, f"{v:.0f}", ha="center", fontsize=5.6)
    # the flip is between H001 and H002, not H004
    ax.annotate("", xy=(0, 3560), xytext=(1, 3560),
                arrowprops=dict(arrowstyle="<->", lw=0.6, color="#333333"))
    ax.text(0.5, 3720, "H001/H002 ranking flips vs panel A", ha="center",
            fontsize=5.6, color="#333333")

    fig.legend(handles=ps.status_legend(), loc="upper center",
               bbox_to_anchor=(0.5, 1.045), ncol=3, fontsize=5.8,
               handletextpad=0.4, columnspacing=1.4)
    ps.suptitle(fig, "All four classification zones are heavily built — a shared "
                     "setting that cannot explain selectivity", y=1.14)
    ps.note(fig,
            "Source: ESA WorldCover 2021 (10 m) and JRC GHSL GHS-BUILT-S E2020 (~93 m); "
            "polygons rasterised on each SOURCE grid, never resampled to 40 m.\n"
            "H001 and H002 rank differently between the two products — a discriminator that "
            "flips sign between independent datasets is not robust.\n"
            "GHSL 2020→2025 built-up change is exactly zero at H001–H004. Post-2020 GHSL epochs "
            "are projections, not observations, so this is an\n"
            "absence of detected change rather than a measured absence. Built fraction "
            "describes the common setting; it does not separate the supported\n"
            "zones from the controls. No loading is estimated here.",
            y=-0.06)
    return ps.save(fig, "F11_urban_intensity")


def main() -> int:
    ps.apply_style()
    written = []
    for fn in (fig9, fig10, fig11):
        written += fn()
    print("=" * 88)
    print("PHASE V-B - PUBLICATION RE-RENDER F9-F11")
    print("=" * 88)
    for p in written:
        print(f"     {p.relative_to(ps.PROJECT_ROOT)}  "
              f"({p.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
