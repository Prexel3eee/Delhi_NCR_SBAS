#!/usr/bin/env python
"""
Shared publication style for the Phase V figure set.

Design constraints
------------------
* Legible in grayscale        -> redundant encoding by luminance AND hatch
* Legible at column width     -> base font 7 pt, single column 3.35 in
* Legible in PDF              -> vector output, fonts embedded as Type 42
* Colour-vision deficient     -> Okabe-Ito palette, never hue alone

This module contains no science. It is presentation only.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIGS = PROJECT_ROOT / "qc" / "sci" / "phase4" / "figures"

# ---------------------------------------------------------------- geometry
SINGLE_COL = 3.35          # in, typical single-column width
ONE_HALF_COL = 5.20
DOUBLE_COL = 7.10          # in, typical double-column width

# ---------------------------------------------------------------- palette
# Okabe-Ito, the standard colour-vision-deficiency safe qualitative set.
OI_BLUE = "#0072B2"
OI_ORANGE = "#E69F00"
OI_GREEN = "#009E73"
OI_VERMILLION = "#D55E00"
OI_PURPLE = "#CC79A7"
OI_SKY = "#56B4E9"
OI_YELLOW = "#F0E442"
OI_BLACK = "#000000"
OI_GREY = "#7F7F7F"

#: Two-geometry encoding: hue + luminance + texture.
GEOM = {
    "ascending":  {"color": OI_BLUE,   "hatch": None,  "label": "ascending"},
    "descending": {"color": OI_ORANGE, "hatch": "///", "label": "descending"},
}

#: Cross-geometry status encoding.
STATUS = {
    "supported":      {"color": OI_GREEN,      "hatch": None,   "label": "independently supported"},
    "not_reproduced": {"color": OI_VERMILLION, "hatch": "///",  "label": "not reproduced"},
    "contradiction":  {"color": OI_PURPLE,     "hatch": "...",  "label": "cross-geometry contradiction"},
    "excluded":       {"color": OI_GREY,       "hatch": "xxx",  "label": "excluded"},
}

#: Hotspot -> status. Frozen classifications; presentation only.
HOTSPOT_STATUS = {
    "H001": "supported",
    "H004": "supported",
    "H002": "not_reproduced",
    "H003": "not_reproduced",
    "H005": "contradiction",
}

#: Reference/background encoding: never a data colour.
REF_COLOR = "#444444"
REF_LW = 0.8

MAIN_ORDER = ["H001", "H004", "H002", "H003", "H005"]


def style_of(hotspot: str) -> dict:
    return STATUS[HOTSPOT_STATUS[hotspot]]


def bar_kwargs(hotspot: str, **over):
    s = style_of(hotspot)
    k = {"color": s["color"], "hatch": s["hatch"],
         "edgecolor": "black", "linewidth": 0.4}
    k.update(over)
    return k


def status_legend(handles_only: bool = False):
    return [Patch(facecolor=v["color"], hatch=v["hatch"], edgecolor="black",
                  linewidth=0.4, label=v["label"])
            for k, v in STATUS.items() if k != "excluded"]


def geom_legend():
    return [Patch(facecolor=v["color"], hatch=v["hatch"], edgecolor="black",
                  linewidth=0.4, label=v["label"]) for v in GEOM.values()]


# ---------------------------------------------------------------- rcParams
def apply_style() -> None:
    mpl.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
        "font.size": 7.0,
        "axes.titlesize": 7.5,
        "axes.labelsize": 7.0,
        "axes.linewidth": 0.6,
        "axes.edgecolor": "black",
        "axes.labelpad": 2.0,
        "axes.titlepad": 4.0,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": "#D9D9D9",
        "grid.linewidth": 0.4,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.2,
        "ytick.major.size": 2.2,
        "legend.fontsize": 6.0,
        "legend.frameon": False,
        "legend.handlelength": 1.5,
        "legend.handleheight": 0.9,
        "legend.labelspacing": 0.35,
        "legend.borderpad": 0.3,
        "legend.columnspacing": 0.9,
        "lines.linewidth": 1.0,
        "lines.markersize": 3.0,
        "patch.linewidth": 0.4,
        "hatch.linewidth": 0.4,
        "errorbar.capsize": 1.6,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })


# ---------------------------------------------------------------- helpers
def panel_label(ax, letter: str, dx: float = -0.16, dy: float = 1.04):
    """Bold panel letter, outside the axes, consistent across all figures."""
    ax.text(dx, dy, letter, transform=ax.transAxes, fontsize=8.0,
            fontweight="bold", va="bottom", ha="left")


def note(fig, text: str, y: float = -0.02):
    """Single consistent footnote slot beneath a figure."""
    fig.text(0.5, y, text, ha="center", va="top", fontsize=5.8,
             color="#333333", linespacing=1.4)


def suptitle(fig, text: str, y: float = 1.0):
    fig.suptitle(text, y=y, fontsize=8.0, fontweight="bold")


def clean_rate_axis(ax, ylabel: str = "mean LOS rate (mm yr$^{-1}$)"):
    ax.set_ylabel(ylabel)
    ax.axhline(0, color="black", lw=0.6, zorder=1)


def save(fig, stem: str, also_pdf: bool = True) -> list:
    """Write PNG (600 dpi) and vector PDF. Returns written paths."""
    FIGS.mkdir(parents=True, exist_ok=True)
    out = []
    png = FIGS / f"{stem}.png"
    fig.savefig(png)
    out.append(png)
    if also_pdf:
        pdf = FIGS / f"{stem}.pdf"
        fig.savefig(pdf)
        out.append(pdf)
    plt.close(fig)
    return out
