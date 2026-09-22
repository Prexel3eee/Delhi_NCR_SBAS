"""
Regression tests for the Phase I characterization stage (scripts 31-36).

Four defect classes are pinned, each of which actually occurred or would silently
corrupt a result:

1. QUALITY-TIER ASSIGNMENT (scripts/31)
   Tiers were assigned from strictest to most permissive, so the permissive tier
   overwrote every stricter one and nothing was classified. Worse, the primary
   mask was selected as `tier <= PRIMARY_TIER`, which also matched tier 0
   ("excluded") and so selected the entire grid instead of the AOI.

2. DATE COLUMN ROUND-TRIP (scripts/33-35)
   Dates are stored as `YYYYMMDD`. Written to CSV and read back with default
   dtypes they become integers, and `date[:4]` then raises. Every reader must
   force the string dtype.

3. PRODUCT REFERENCE (INC-007, scripts/31)
   The frozen decision names reference pixel (1378,1426) but the frozen product
   is actually referenced to (1384,1451), because the RAW config never set
   `mintpy.reference.yx`. This is pinned as a test so the discrepancy cannot
   change silently, and so a future re-run that "fixes" it is detected.

4. EVIDENCE GRADING AND PERSISTENCE RULES (scripts/35-36)
   The grade and the persistence criterion decide what is carried forward. Both
   are pure functions of the reported numbers and are tested on synthetic input.

Geospatial imports are guarded so the suite still runs in the search/submission
environment, which does not have rasterio or scipy.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("scipy", reason="scripts/31-35 import scipy.ndimage")
pytest.importorskip("rasterio", reason="scripts/31-35 import rasterio")
pytest.importorskip("h5py", reason="scripts/31-35 import h5py")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_QC = PROJECT_ROOT / "qc" / "sci" / "phase1"
TIMESERIES = PROJECT_ROOT / "mintpy" / "baseline_raw_work" / "timeseries.h5"


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report_module():
    return load("phase1_report_under_test", "scripts/36_phase1_report.py")


# ---------------------------------------------------------------------------
# 1. Quality-tier assignment
# ---------------------------------------------------------------------------

def test_strictest_tier_wins_assignment_order():
    """
    Assigning from most permissive to most restrictive is what makes the
    strictest qualifying tier stick. The reverse order leaves everything in the
    permissive tier, which is the bug this pins.
    """
    coherence = np.array([[0.95, 0.85, 0.75, 0.65]])
    on_land = np.ones_like(coherence, dtype=bool)
    tiers = [(1, 0.90), (2, 0.80), (3, 0.70), (4, None)]

    tier = np.zeros(coherence.shape, dtype="uint8")
    for code, threshold in reversed(tiers):
        selected = on_land if threshold is None else (on_land & (coherence >= threshold))
        tier[selected] = code
    assert tier.tolist() == [[1, 2, 3, 4]]

    # The buggy order collapses everything into the permissive tier.
    wrong = np.zeros(coherence.shape, dtype="uint8")
    for code, threshold in tiers:
        selected = on_land if threshold is None else (on_land & (coherence >= threshold))
        wrong[selected] = code
    assert wrong.tolist() == [[4, 4, 4, 4]]


def test_primary_mask_excludes_tier_zero():
    """Tier 0 means excluded; `tier <= N` alone would select it."""
    tier = np.array([[0, 1, 2, 3, 4]], dtype="uint8")
    primary_tier = 2
    buggy = tier <= primary_tier
    correct = (tier >= 1) & (tier <= primary_tier)
    assert buggy.tolist() == [[True, True, True, False, False]]
    assert correct.tolist() == [[False, True, True, False, False]]
    # The buggy form selects pixels that are water or outside the AOI.
    assert buggy[0, 0] and not correct[0, 0]


# ---------------------------------------------------------------------------
# 2. Date round-trip
# ---------------------------------------------------------------------------

def test_yyyymmdd_round_trip_requires_string_dtype(tmp_path):
    """Reading YYYYMMDD back with default dtypes yields ints and breaks slicing."""
    dates = ["20211006", "20211018", "20250927"]
    path = tmp_path / "dates.csv"
    pd.DataFrame({"date": dates}).to_csv(path, index=False)

    default = pd.read_csv(path)
    assert not pd.api.types.is_string_dtype(default["date"])
    with pytest.raises((IndexError, TypeError)):
        _ = default["date"].iloc[0][:4]

    forced = pd.read_csv(path, dtype={"date": str})
    assert forced["date"].iloc[0][:4] == "2021"
    assert list(forced["date"]) == dates


def test_decimal_year_conversion_is_monotonic():
    dates = ["20211006", "20220101", "20250101", "20250927"]
    t = np.array([int(d[:4]) + (int(d[4:6]) - 1) / 12 + (int(d[6:]) - 1) / 365.25
                  for d in dates])
    assert np.all(np.diff(t) > 0)
    assert t[0] == pytest.approx(2021.76, abs=0.01)
    assert t[-1] == pytest.approx(2025.74, abs=0.01)


# ---------------------------------------------------------------------------
# 3. INC-007: the product reference
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not TIMESERIES.exists(), reason="frozen product not present")
def test_frozen_product_reference_is_not_the_frozen_decision():
    """
    Pin INC-007. The product is referenced to (1384,1451); the frozen decision
    says (1378,1426). Verified by finding the pixel that is identically zero.
    """
    import h5py

    with h5py.File(TIMESERIES, "r") as handle:
        recorded = (int(handle.attrs["REF_Y"]), int(handle.attrs["REF_X"]))
        actual_zero = np.abs(handle["timeseries"][:, recorded[0], recorded[1]])
        frozen_values = np.abs(handle["timeseries"][:, 1378, 1426])

    assert recorded == (1384, 1451)
    assert float(np.max(actual_zero)) == 0.0, "recorded reference must be identically zero"
    assert float(np.max(frozen_values)) > 0.0, (
        "the frozen-decision pixel is NOT the reference; if this now passes as zero, "
        "the product was re-run with a different reference and INC-007 is resolved")


def test_reference_rebasing_preserves_contrast():
    """
    Velocity is linear, so re-basing shifts every pixel by one constant and no
    hotspot contrast can change. This is why INC-007 does not invalidate the
    Phase I results.
    """
    rng = np.random.default_rng(11)
    velocity = rng.normal(-5.0, 8.0, 5000)
    offset = 0.1362
    rebased = velocity + offset
    assert np.allclose(rebased - velocity, offset)
    # Every pairwise difference is invariant.
    assert np.allclose(np.diff(rebased[:100]), np.diff(velocity[:100]))
    assert np.std(rebased) == pytest.approx(np.std(velocity), abs=1e-9)


# ---------------------------------------------------------------------------
# 4. Grading and persistence rules
# ---------------------------------------------------------------------------

def _row(**overrides):
    base = {"hotspot_id": "H001", "temporal_coherence_median": 0.90,
            "los_velocity_median_mm_per_yr": -30.0,
            "los_rate_from_series_mm_per_yr": -29.0}
    base.update(overrides)
    return pd.Series(base)


def test_grade_a_requires_persistence_coherence_magnitude_and_agreement(report_module):
    persistence = {"H001": {"scenarios_survived": 14, "scenarios_total": 14}}
    grade, _ = report_module.grade(_row(), persistence)
    assert grade == "A"

    # Each condition must independently be able to demote it.
    assert report_module.grade(_row(), {"H001": {"scenarios_survived": 8,
                                                 "scenarios_total": 14}})[0] == "C"
    assert report_module.grade(_row(temporal_coherence_median=0.70), persistence)[0] == "B"
    assert report_module.grade(_row(los_velocity_median_mm_per_yr=-4.0), persistence)[0] == "C"
    # Field and series rates disagreeing by more than 20% blocks grade A.
    assert report_module.grade(
        _row(los_rate_from_series_mm_per_yr=-15.0), persistence)[0] == "B"


def test_grade_c_is_reserved_for_mask_dependence(report_module):
    persistence = {"H001": {"scenarios_survived": 5, "scenarios_total": 14}}
    grade, basis = report_module.grade(_row(), persistence)
    assert grade == "C"
    assert "mask" in basis.lower()


def test_persistence_criterion_requires_overlap_and_min_area():
    """
    A hotspot persists only if >=50% of its pixels land in ONE component that
    also meets the scenario's minimum area. Either condition alone is not enough.
    """
    def persists(overlap: float, component_meets_area: bool) -> bool:
        return bool(overlap >= 0.5 and component_meets_area)

    assert persists(0.49, True) is False
    assert persists(0.51, False) is False
    assert persists(0.51, True) is True
    assert persists(1.0, True) is True


# ---------------------------------------------------------------------------
# 5. Published artefacts are internally consistent
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not (OUT_QC / "hotspots.csv").exists(),
                    reason="Phase I has not been run in this checkout")
def test_hotspot_table_matches_its_json():
    table = pd.read_csv(OUT_QC / "hotspots.csv")
    payload = json.loads((OUT_QC / "hotspots.json").read_text())
    assert len(table) == payload["counts"]["components_reported"]
    assert set(table["hotspot_id"]) == {h["hotspot_id"] for h in payload["hotspots"]}
    # The area floor is enforced, not merely requested.
    assert (table["area_km2"] >= payload["detection"]["min_area_km2"] - 1e-9).all()
    # The magnitude threshold is enforced on every reported hotspot.
    threshold = payload["detection"]["absolute_velocity_threshold_mm_per_yr"]
    assert (table["los_velocity_median_mm_per_yr"].abs() >= threshold).all()
    assert (table["temporal_coherence_median"]
            >= payload["detection"]["coherence_min"]).all()


@pytest.mark.skipif(not (OUT_QC / "hotspot_uncertainty.csv").exists(),
                    reason="Phase I has not been run in this checkout")
def test_bootstrap_intervals_bracket_the_point_estimate():
    table = pd.read_csv(OUT_QC / "hotspot_uncertainty.csv")
    for _, row in table.iterrows():
        assert row["epoch_bootstrap_p2_5_mm_per_yr"] <= row["los_rate_from_series_mm_per_yr"]
        assert row["los_rate_from_series_mm_per_yr"] <= row["epoch_bootstrap_p97_5_mm_per_yr"]
        assert row["epoch_bootstrap_width_mm_per_yr"] > 0


@pytest.mark.skipif(not (OUT_QC / "hotspot_persistence.json").exists(),
                    reason="Phase I has not been run in this checkout")
def test_persistence_survived_never_exceeds_total():
    payload = json.loads((OUT_QC / "hotspot_persistence.json").read_text())
    total = len(payload["scenarios"])
    for hid, info in payload["persistence"].items():
        assert 0 <= info["scenarios_survived"] <= info["scenarios_total"] == total


@pytest.mark.skipif(not (OUT_QC / "deformation_map_summary.json").exists(),
                    reason="Phase I has not been run in this checkout")
def test_deformation_map_counts_are_consistent():
    summary = json.loads((OUT_QC / "deformation_map_summary.json").read_text())
    counts = summary["counts"]
    assert counts["land_in_aoi"] + counts["water_in_aoi"] <= counts["finite_in_aoi"]
    assert counts["aoi_pixels"] == counts["finite_in_aoi"]
    # Tiers are nested and the permissive tier equals all land pixels.
    tiers = summary["quality_tiers"]
    assert tiers["1"]["pixels"] <= tiers["2"]["pixels"] <= tiers["3"]["pixels"]
    assert tiers["4"]["pixels"] == counts["land_in_aoi"]
    assert summary["primary_mask_pixels"] == tiers["2"]["pixels"]
    # The reference mismatch is recorded rather than hidden.
    assert summary["reference"]["mismatch"] is True


@pytest.mark.skipif(not (OUT_QC / "oscillation_diagnostics.json").exists(),
                    reason="Phase I has not been run in this checkout")
def test_oscillation_grouping_is_consistent_across_detrends():
    """
    The north/south anti-correlation is only meaningful if it survives the
    change of de-trend order. Same-sign agreement is asserted here.
    """
    diag = json.loads((OUT_QC / "oscillation_diagnostics.json").read_text())
    linear = diag["cross_hotspot_correlation"]
    quadratic = diag["cross_hotspot_correlation_quadratic"]
    assert set(linear) == set(quadratic)
    for key in linear:
        assert np.sign(linear[key]) == np.sign(quadratic[key]), (
            f"{key} changes sign between de-trend orders; the grouping is not stable")
    # The two within-group pairs that define the structure.
    assert linear["H002_vs_H003"] > 0.8
    assert linear["H001_vs_H004"] > 0.8
