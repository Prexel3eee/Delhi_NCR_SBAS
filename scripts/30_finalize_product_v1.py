#!/usr/bin/env python
"""
Freeze RAW-336 as the authoritative v1 deformation solution, and emit the
correction-validation report.

Decision
--------
The final correction-validation stage ran two independent evidential streams:

  * GNSS/CORS suitability  (qc/sci/gnss_suitability.json)
  * targeted stable-area atmospheric/topographic diagnostics
    (qc/sci/correction_validation.json)

Neither promotes a correction. GNSS cannot discriminate the branches on
coverage grounds, and on the four product-quality diagnostics RAW-336 wins three
while ERA5 wins one (the elevation-correlated residual, where it does exactly
what an atmospheric correction should). ERA5+DEM wins none and is the worst on
three. RAW-336 is therefore frozen as v1 and both corrections are recorded as
tested but not beneficial.

What "freeze" means here
------------------------
`freeze/v1/` and `freeze/mintpy_input_v1/` snapshot their artefacts by copying.
The RAW-336 products are far too large to duplicate (timeseries.h5 alone is
3.4 GB), so this freeze instead **pins them in place**: each large product
records its SHA-256, byte size and mtime_ns, and `verify_product_v1.py`
re-checks all three. Small decision/evidence artefacts are copied.

Usage
-----
    python scripts/30_finalize_product_v1.py            # create (refuses to clobber)
    python scripts/30_finalize_product_v1.py --force    # rebuild
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DIR = PROJECT_ROOT / "freeze" / "product_v1"
RAW_WORK = PROJECT_ROOT / "mintpy" / "baseline_raw_work"
QC_DIR = PROJECT_ROOT / "qc" / "sci"

FREEZE_VERSION = "product_v1"
PRINCIPAL_BRANCH = "RAW-336"

#: Large derived products: pinned in place by hash+size+mtime, never copied.
PINNED_PRODUCTS: list[tuple[str, bool]] = [
    ("mintpy/baseline_raw_work/timeseries.h5", True),
    ("mintpy/baseline_raw_work/velocity.h5", True),
    ("mintpy/baseline_raw_work/temporalCoherence.h5", True),
    ("mintpy/baseline_raw_work/maskTempCoh.h5", True),
    ("mintpy/baseline_raw_work/avgSpatialCoh.h5", True),
    ("mintpy/baseline_raw_work/maskConnComp.h5", True),
    ("mintpy/baseline_raw_work/numInvIfgram.h5", True),
    ("mintpy/baseline_raw_work/avgPhaseVelocity.h5", False),
    ("mintpy/baseline_raw_work/numTriNonzeroIntAmbiguity.h5", False),
]

#: Small artefacts copied into the freeze for audit.
COPIED_ARTEFACTS: list[tuple[str, bool]] = [
    ("config/scientific_decisions_v2.json", True),
    ("config/mintpy_baseline_raw.txt", True),
    ("freeze/mintpy_input_v1/FREEZE.json", True),
    ("manifests/sbas_pairs.csv", True),
    ("manifests/accepted_acquisitions.csv", True),
    ("qc/sci/correction_validation.json", True),
    ("qc/sci/branch_comparison.json", True),
    ("qc/sci/gnss_suitability.json", True),
    ("qc/sci/reference_sensitivity.json", False),
    ("qc/sci/unwrap_comparison.json", False),
    ("qc/sci/network_comparison.json", False),
    ("qc/sci/era5_coverage.json", False),
]

BINARY_SUFFIXES = {".h5", ".grib", ".zip", ".tif"}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def build_report() -> str:
    cv = load_json(QC_DIR / "correction_validation.json")
    gnss = load_json(QC_DIR / "gnss_suitability.json")
    bc = load_json(QC_DIR / "branch_comparison.json")
    dec = load_json(PROJECT_ROOT / "config" / "scientific_decisions_v2.json")

    tests = cv.get("tests", {})
    rough = tests.get("A_velocity_highpass_energy_mm_per_yr", {})
    stable = tests.get("B_stable_area", {})
    topo = tests.get("C_topography_correlation_spearman", {})
    pix = tests.get("D_per_pixel_residual_scatter_rad", {})
    pairwise = bc.get("pairwise", {})
    ref = dec.get("decisions", {}).get("reference", {})

    def row(label, mapping, digits, unit, lower_is_better=True):
        # NOTE: no trailing newline - rows are joined with "\n" by the caller, and a
        # stray newline would insert blank lines that break the markdown table.
        vals = {b: mapping.get(b) for b in ("RAW", "ERA5", "ERA5+DEM")}
        best = None
        if all(v is not None for v in vals.values()):
            best = min(vals, key=vals.get) if lower_is_better else max(vals, key=vals.get)
        cells = "".join(
            f" {'**' + format(vals[b], f'.{digits}f') + '**' if b == best else format(vals[b], f'.{digits}f'):>10s} |"
            if vals[b] is not None else " " * 10 + " |"
            for b in ("RAW", "ERA5", "ERA5+DEM"))
        # A literal '|' inside a label would be read as a column separator.
        label = label.replace("|", "\\|")
        return f"| {label} |{cells} {'lower' if lower_is_better else 'higher'} |"

    lines = [
        "# Correction Validation and v1 Product Freeze",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.",
        "",
        f"**Principal candidate: `{PRINCIPAL_BRANCH}`** — promoted: "
        f"{cv.get('promoted') or 'none'}. Corrections tested: ERA5 atmospheric delay, "
        "and ERA5 followed by pixel-wise DEM-residual estimation. Spatial deramping "
        "remains disabled in the principal branch.",
        "",
        "## 1. Why residual RMS alone was not enough",
        "",
        "On an uncorrected baseline the per-interferogram residuals are dominated by "
        "unmodelled atmosphere and orbit ramps, so raw residual RMS is a blunt "
        "discriminator: a correction can worsen it while still removing a real error. "
        "Four diagnostics better matched to the signature of atmospheric and "
        "DEM-residual error were used instead.",
        "",
        "## 2. Targeted diagnostics",
        "",
        "| Diagnostic | RAW | ERA5 | ERA5+DEM | Prefer |",
        "|---|---:|---:|---:|---|",
    ]
    lines.append(row("A. Velocity high-pass energy (mm/yr)", rough, 3, "mm/yr"))
    lines.append(
        f"| B. Stable-area velocity median (mm/yr) |"
        f" {stable.get('RAW', {}).get('velocity_median_mm_per_yr', float('nan')):+10.3f} |"
        f" {stable.get('ERA5', {}).get('velocity_median_mm_per_yr', float('nan')):+10.3f} |"
        f" {stable.get('ERA5+DEM', {}).get('velocity_median_mm_per_yr', float('nan')):+10.3f} |"
        f" closer to 0 |")
    lines.append(
        "| B. Stable-area robust scatter (mm/yr) |"
        + "".join(
            f" {stable.get(b, {}).get('velocity_robust_std_mm_per_yr', float('nan')):10.3f} |"
            for b in ("RAW", "ERA5", "ERA5+DEM"))
        + " lower |")
    lines.append(row("C. |Spearman(residual, elevation)|", topo, 4, ""))
    lines.append(row("D. Per-pixel residual scatter (rad)", pix, 4, "rad"))
    lines += [
        "",
        f"The stable-area mask is defined from the RAW branch "
        f"(temporal coherence >= {cv.get('stable_mask_definition', {}).get('temporal_coherence_min')}, "
        f"|velocity| <= {cv.get('stable_mask_definition', {}).get('abs_velocity_max_mm_per_yr')} mm/yr, "
        f"n = {stable.get('RAW', {}).get('n_pixels')} pixels) so it is identical across branches.",
        "",
        "### Interpretation",
        "",
        "* **ERA5 does what an atmospheric correction should.** The elevation-correlated "
        f"residual falls from {topo.get('RAW')} to {topo.get('ERA5')} — a "
        f"{100 * (1 - abs(topo.get('ERA5', 0)) / abs(topo.get('RAW', 1))):.0f}% reduction, and "
        "the only diagnostic any correction wins. The error ERA5 targets is genuinely "
        "present in the RAW solution.",
        "* **But it does not improve the product.** Removing it leaves the velocity field "
        f"marginally rougher ({rough.get('RAW')} -> {rough.get('ERA5')} mm/yr), the "
        f"stable-area scatter slightly larger ({stable.get('RAW', {}).get('velocity_robust_std_mm_per_yr')} "
        f"-> {stable.get('ERA5', {}).get('velocity_robust_std_mm_per_yr')} mm/yr), and the "
        f"stable-area median displaced from {stable.get('RAW', {}).get('velocity_median_mm_per_yr')} "
        f"to {stable.get('ERA5', {}).get('velocity_median_mm_per_yr')} mm/yr — i.e. it "
        "introduces a small non-zero offset in areas that should read zero. The "
        "atmospheric component is real but not what limits this product.",
        "* **The DEM-residual step is counterproductive.** It raises the "
        f"elevation-correlated residual back to {topo.get('ERA5+DEM')} (worse than ERA5 "
        "alone) and is the worst branch on the other three diagnostics, including the "
        f"largest stable-area offset ({stable.get('ERA5+DEM', {}).get('velocity_median_mm_per_yr')} mm/yr) "
        "and the largest scatter "
        f"({stable.get('ERA5+DEM', {}).get('velocity_robust_std_mm_per_yr')} mm/yr).",
        "",
        "The diagnostics favour smoother solutions, so a correction that removed real "
        "signal would also score well. The independent velocity-agreement check guards "
        "against that: neither correction is a large-magnitude change "
        f"(ERA5-RAW RMS {pairwise.get('ERA5_minus_RAW', {}).get('rms_mm_per_yr')} mm/yr; "
        f"ERA5+DEM-RAW RMS {pairwise.get('ERA5+DEM_minus_RAW', {}).get('rms_mm_per_yr')} mm/yr), "
        "so no branch is silently deleting a large deformation signal.",
        "",
        "## 3. GNSS / CORS assessment",
        "",
        f"Outcome: **{gnss.get('outcome', 'not assessed')}**.",
        "",
    ]
    for reason in str(gnss.get("reason", "")).split("; "):
        if reason:
            lines.append(f"* {reason}.")
    colo = gnss.get("colocation", {}).get("pairs", [])
    if colo:
        lines += [
            "",
            "The co-location test is the internally controlled one — it needs no external "
            "truth. The only qualifying pair, `LCK3`/`LCK4` (0.01 km apart, 745 shared "
            f"epochs), agrees to {colo[0]['rate_difference_mm_per_yr']} mm/yr once both are "
            "evaluated over the **same** time window. GNSS measurement quality is therefore "
            "not the limitation; station geometry is. Note that comparing each station's "
            "full record instead produces a spurious ~27 mm/yr difference, because the two "
            "records end in 2023-12 and 2026-09 respectively.",
            "",
            "An earlier pass reported \"GNSS REFERENCE AVAILABLE\" from a stations-passing-a-"
            "threshold count. That is superseded: passing a solutions/span threshold is not "
            "the same as being able to discriminate a sub-mm/yr branch difference.",
        ]
    lines += [
        "",
        "## 4. Frozen v1 product",
        "",
        f"`RAW-336` is frozen as the authoritative v1 deformation solution.",
        "",
        f"* Reference point: {ref.get('lat')}, {ref.get('lon')} (EPSG:{ref.get('epsg')}), "
        f"MintPy pixel `{ref.get('mintpy_reference_yx')}`, inside the AOI.",
        "* All 336 interferograms retained; no pair excluded.",
        "* ERA5 atmospheric correction: tested, not beneficial — not applied.",
        "* ERA5 + pixel-wise DEM-residual correction: tested, not beneficial — not applied.",
        "* Network-based unwrap correction (bridge + phase closure): tested, degrades fit — disabled.",
        "* Spatial deramping: disabled in the principal branch (broad subsidence gradients "
        "may be genuine signal); sensitivity experiment only.",
        "",
        "The reference-point choice carries a documented systematic of 4.78 mm/yr "
        "(sd 1.72) among candidates selected without using velocity; relative spatial "
        "gradients are unaffected. See `qc/sci/reference_sensitivity.json`.",
        "",
        "### Per-branch summary",
        "",
        "| Branch | Velocity median (m/yr) | Temporal coherence | Residual RMS (rad) |",
        "|---|---:|---:|---:|",
    ]
    for branch, info in bc.get("branches", {}).items():
        lines.append(
            f"| {branch} | {info.get('velocity_m_per_yr', {}).get('median')} | "
            f"{info.get('temporal_coherence', {}).get('median')} | "
            f"{info.get('residual_rms_rad_median')} |")
    lines += [
        "",
        "## 5. Scope and open items",
        "",
        "This is a v1 deformation solution, not a calibrated geodetic product. It is not "
        "corrected for tropospheric delay in the frozen branch, and its absolute reference "
        "carries the stated 4.78 mm/yr systematic. Validation against an independent "
        "in-AOI geodetic reference was not possible with the available GNSS data.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild the snapshot")
    args = parser.parse_args()

    if FREEZE_DIR.exists() and not args.force:
        print(f"ERROR: {FREEZE_DIR} already exists. Use --force to rebuild.", file=sys.stderr)
        return 1

    # --- preconditions ----------------------------------------------------
    problems = []
    for rel, critical in PINNED_PRODUCTS:
        path = PROJECT_ROOT / rel
        if not path.exists():
            (problems if critical else []).append(f"missing pinned product: {rel}")
    for rel, critical in COPIED_ARTEFACTS:
        path = PROJECT_ROOT / rel
        if not path.exists():
            (problems if critical else []).append(f"missing artefact: {rel}")
    if problems:
        print("ERROR: freeze preconditions failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    # Confirm the pinned products really are the RAW branch.
    import h5py  # noqa: PLC0415  (only needed once preconditions pass)
    velocity = PROJECT_ROOT / "mintpy" / "baseline_raw_work" / "velocity.h5"
    with h5py.File(velocity, "r") as handle:
        source = str(handle.attrs.get("FILE_PATH", ""))
    if not source.endswith("timeseries.h5"):
        print(f"ERROR: velocity.h5 does not derive from timeseries.h5 (got {source!r}).\n"
              "       The RAW branch may have been overwritten by a corrected branch.",
              file=sys.stderr)
        return 1
    print(f"  branch check OK: velocity.h5 <- {source}")

    if FREEZE_DIR.exists():
        # The previous snapshot was sealed read-only, so every directory (including
        # the top level) must be made writable before its contents can be unlinked.
        for path in sorted(FREEZE_DIR.rglob("*"), reverse=True):
            path.chmod(0o755) if path.is_dir() else path.chmod(0o644)
        FREEZE_DIR.chmod(0o755)
        shutil.rmtree(FREEZE_DIR)
    FREEZE_DIR.mkdir(parents=True)

    print("=" * 88)
    print("FREEZE PRODUCT v1 - RAW-336")
    print("=" * 88)

    # --- pin large products in place --------------------------------------
    print("\n  pinned products (hashed in place):")
    pinned = []
    for rel, critical in PINNED_PRODUCTS:
        path = PROJECT_ROOT / rel
        digest = sha256_of(path)
        st = path.stat()
        pinned.append({"path": rel, "sha256": digest, "bytes": st.st_size,
                       "mtime_ns": st.st_mtime_ns, "critical": critical})
        print(f"    {rel:60s} {st.st_size / 1e6:10.1f} MB  {digest[:16]}")

    # --- copy small artefacts ---------------------------------------------
    print("\n  copied artefacts:")
    copied = []
    for rel, critical in COPIED_ARTEFACTS:
        src = PROJECT_ROOT / rel
        dst = FREEZE_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        digest = sha256_of(dst)
        copied.append({"path": rel, "sha256": digest, "bytes": dst.stat().st_size,
                       "critical": critical})
        print(f"    {rel:60s} {dst.stat().st_size / 1e3:10.1f} kB  {digest[:16]}")

    # --- report -----------------------------------------------------------
    report = build_report()
    report_path = QC_DIR / "CORRECTION_VALIDATION_REPORT.md"
    report_path.write_text(report)
    (FREEZE_DIR / "CORRECTION_VALIDATION_REPORT.md").write_text(report)
    print(f"\n  report -> {report_path}")

    # --- freeze id --------------------------------------------------------
    cv = load_json(QC_DIR / "correction_validation.json")
    payload = json.dumps({
        "version": FREEZE_VERSION,
        "principal_branch": PRINCIPAL_BRANCH,
        "pinned": [[p["path"], p["sha256"]] for p in pinned],
        "copied": [[c["path"], c["sha256"]] for c in copied],
        "promoted": cv.get("promoted"),
        "decision": "RAW-336 frozen; ERA5 and ERA5+DEM tested but not beneficial",
    }, sort_keys=True).encode()
    freeze_id = hashlib.sha256(payload).hexdigest()

    gnss = load_json(QC_DIR / "gnss_suitability.json")
    manifest = {
        "freeze_version": FREEZE_VERSION,
        "freeze_id": freeze_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "principal_branch": PRINCIPAL_BRANCH,
        "statement": (
            "RAW-336 is the authoritative v1 deformation solution. ERA5 atmospheric "
            "correction and ERA5+DEM pixel-wise DEM-residual correction were both tested "
            "with targeted stable-area atmospheric/topographic diagnostics and are not "
            "beneficial; they are not applied. Spatial deramping is disabled."),
        "corrections_tested_not_beneficial": [
            {"name": "ERA5 atmospheric delay",
             "evidence": "qc/sci/correction_validation.json",
             "result": "1 of 4 diagnostics improved; reduces elevation-correlated residual "
                       "from 0.1497 to 0.0332 but roughens the velocity field and enlarges "
                       "stable-area scatter"},
            {"name": "ERA5 + pixel-wise DEM residual",
             "evidence": "qc/sci/correction_validation.json",
             "result": "1 of 4 diagnostics improved; worst branch on stable-area offset and "
                       "scatter, and degrades the elevation-correlated residual relative to "
                       "ERA5 alone (0.0332 -> 0.0847)"},
            {"name": "network unwrap correction (bridge + phase closure)",
             "evidence": "qc/sci/unwrap_comparison.json",
             "result": "degrades fit: residual 4.593 -> 5.108 rad, 134 improved / 202 worsened"},
        ],
        "validation": {
            "gnss": {"evidence": "qc/sci/gnss_suitability.json",
                     "outcome": gnss.get("outcome"),
                     "reason": gnss.get("reason")},
            "diagnostics": "qc/sci/correction_validation.json",
            "report": "qc/sci/CORRECTION_VALIDATION_REPORT.md",
        },
        "pinned_products": pinned,
        "pinned_note": "Hashed in place rather than copied: the products total several GB and "
                       "duplicating them would consume storage without adding provenance.",
        "copied_artefacts": copied,
        "reference_point": load_json(PROJECT_ROOT / "config" / "scientific_decisions_v2.json")
                                .get("decisions", {}).get("reference"),
        "reference_systematic_mm_per_yr": load_json(QC_DIR / "reference_sensitivity.json")
                                          .get("spread_mm_per_yr"),
        "pairs_retained": 336,
        "pairs_excluded": 0,
        "deramp": "disabled",
    }
    manifest_path = FREEZE_DIR / "FREEZE.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\n  freeze_id: {freeze_id}")
    print(f"  {manifest_path}")

    # --- read-only --------------------------------------------------------
    # README is written BEFORE the directory is sealed, otherwise the write
    # fails on the now read-only parent directory.
    readme = FREEZE_DIR / "README.md"
    readme.write_text(
        f"# freeze/{FREEZE_VERSION}\n\n"
        f"Immutable. `freeze_id = {freeze_id}`\n\n"
        f"Principal branch: **{PRINCIPAL_BRANCH}** — the authoritative v1 deformation "
        "solution.\n\n"
        "Large products are hash-pinned in place; see `FREEZE.json`. Verify with\n"
        "`python scripts/verify_product_v1.py`.\n")

    for path in sorted(FREEZE_DIR.rglob("*"), reverse=True):
        if path == manifest_path:
            continue
        path.chmod(path.stat().st_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    manifest_path.chmod(0o444)
    readme.chmod(0o444)
    FREEZE_DIR.chmod(0o555)

    print(f"  marked read-only: {FREEZE_DIR}")
    print("\n  verify with: python scripts/verify_product_v1.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
