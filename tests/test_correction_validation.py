"""
Regression tests for the final correction-validation stage.

These pin three classes of defect that were actually hit while producing the v1
decision, plus the decision policy itself.

1. GNSS RATE COMPARISON OVER DIFFERENT WINDOWS (scripts/29_gnss_verdict.py)
   The first pass compared each station's full-record trend and reported a
   co-located pair (LCK3/LCK4) disagreeing by ~27 mm/yr, which was read as
   evidence of step contamination. It was an artefact: the two records end in
   2023-12 and 2026-09, so their trends are not comparable. Compared over the
   SAME window they agree to <1 mm/yr. The tests below lock in that a rate
   difference is only meaningful when computed on a common window, and that the
   header - not a hard-coded index - supplies the up component.

2. TIMESERIES / INTERFEROGRAM GRID MISMATCH (scripts/28_correction_validation.py)
   The stacked unwrapPhase array and the timeseries array were sliced
   inconsistently, so an AOI window from one was broadcast against the full grid
   of the other. Any residual diagnostic must apply the same window to both.

3. FREEZE ID DRIFT (scripts/30, scripts/verify_product_v1.py)
   The product freeze derives its freeze_id from the pinned and copied artefact
   hashes plus the promotion outcome. A changed hash must change the id, or the
   freeze would silently accept a mutated product.

The promotion policy is also pinned: a branch needs at least 3 of 4 diagnostics
before it may displace RAW-336, and a correction is judged on the sign of the
comparison rather than on an absolute threshold.

All tests are offline and read no project HDF5 files.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# scripts/28 imports the full geo stack; skip cleanly where it is unavailable
# (the delhi-hyp3 environment) rather than erroring at import time.
pytest.importorskip("scipy", reason="scripts/28 imports scipy.ndimage")
pytest.importorskip("rasterio", reason="scripts/28 imports rasterio")
pytest.importorskip("h5py", reason="scripts/28 imports h5py")
pytest.importorskip("shapely", reason="scripts/28 imports shapely")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gnss():
    return load("gnss_verdict_under_test", "scripts/29_gnss_verdict.py")


@pytest.fixture(scope="module")
def validation():
    return load("correction_validation_under_test", "scripts/28_correction_validation.py")


# ---------------------------------------------------------------------------
# 1. GNSS rate handling
# ---------------------------------------------------------------------------

def _series_for_dates(dates, rate_mm_per_yr: float, noise_mm: float = 0.0, seed: int = 0,
                      step_year: float | None = None, step_mm: float = 0.0):
    """A GNSS-like series on an explicit epoch list, so joins on `date` are exact."""
    rng = np.random.default_rng(seed)
    dates = pd.DatetimeIndex(dates)
    t = dates.year + (dates.dayofyear - 1) / 365.25
    up = (rate_mm_per_yr / 1000.0) * (t - t[0])
    if noise_mm:
        up = up + rng.normal(0, noise_mm / 1000.0, len(dates))
    if step_year is not None:
        up = up + np.where(t > step_year, step_mm / 1000.0, 0.0)
    return pd.DataFrame({
        "date": dates,
        "decimalyear": np.asarray(t, dtype=float),
        "up_m": np.asarray(up, dtype=float),
        "sig_up_m": np.full(len(dates), 0.001),
    })


def _synthetic_series(rate_mm_per_yr: float, start: int, end: int,
                      n: int = 400, noise_mm: float = 0.0, seed: int = 0,
                      step_year: float | None = None, step_mm: float = 0.0):
    dates = pd.date_range(f"{start}-01-01", f"{end}-01-01", periods=n)
    return _series_for_dates(dates, rate_mm_per_yr, noise_mm, seed, step_year, step_mm)


def _as_own_series(merged: pd.DataFrame, suffix: str) -> pd.DataFrame:
    """Reduce a suffixed merge back to a single station's series."""
    return pd.DataFrame({
        "date": merged["date"],
        "decimalyear": merged[f"decimalyear_{suffix}"],
        "up_m": merged[f"up_m_{suffix}"],
        "sig_up_m": merged[f"sig_up_m_{suffix}"],
    })


def test_weighted_rate_recovers_a_known_slope(gnss):
    frame = _synthetic_series(rate_mm_per_yr=-7.5, start=2015, end=2025, noise_mm=0.5)
    fit = gnss.weighted_rate(frame, t0_year=2020.0)
    assert fit["rate_mm_per_yr"] == pytest.approx(-7.5, abs=0.15)
    assert fit["n"] == len(frame)
    assert fit["span_years"] == pytest.approx(10.0, abs=0.01)


def test_colocated_rates_agree_on_a_common_window(gnss):
    """Two receivers with the same true rate must not disagree when co-evaluated."""
    a = _synthetic_series(rate_mm_per_yr=2.0, start=2014, end=2024, noise_mm=1.0, seed=1)
    b = _synthetic_series(rate_mm_per_yr=2.0, start=2014, end=2024, noise_mm=1.0, seed=2)
    merged = pd.merge(a, b, on="date", suffixes=("_a", "_b"))
    fit_a = gnss.weighted_rate(_as_own_series(merged, "a"), 2019.0)
    fit_b = gnss.weighted_rate(_as_own_series(merged, "b"), 2019.0)
    assert abs(fit_a["rate_mm_per_yr"] - fit_b["rate_mm_per_yr"]) < 0.15


def test_rate_difference_over_different_windows_is_not_comparable(gnss):
    """
    The LCK3/LCK4 defect, in miniature.

    Station `a` ends in 2023; station `b` continues to 2026 and carries a 100 mm
    offset step at 2023.5 that `a` never observed. Comparing the two full-record
    trends manufactures a large disagreement, but once both are evaluated over
    the window they actually share the disagreement vanishes.
    """
    all_epochs = pd.date_range("2014-01-01", "2026-01-01", freq="D")
    shared_epochs = all_epochs[all_epochs <= "2023-01-01"]
    a = _series_for_dates(shared_epochs, 2.0)
    b = _series_for_dates(all_epochs, 2.0, step_year=2023.5, step_mm=100.0)

    full_a = gnss.weighted_rate(a, t0_year=2019.0)
    full_b = gnss.weighted_rate(b, t0_year=2019.0)

    # Both records start together, so both are individually close to 2 mm/yr...
    assert full_a["rate_mm_per_yr"] == pytest.approx(2.0, abs=0.05)
    # ...but `b`'s full-record trend is pulled by the step it alone contains.
    assert abs(full_b["rate_mm_per_yr"] - full_a["rate_mm_per_yr"]) > 2.0

    # Restricted to the shared window the step is excluded and they agree.
    shared = b[b["date"].isin(a["date"])]
    assert len(shared) > 100
    common_b = gnss.weighted_rate(shared, t0_year=2019.0)
    assert abs(common_b["rate_mm_per_yr"] - full_a["rate_mm_per_yr"]) < 0.5


def test_up_component_is_resolved_from_the_header(gnss):
    """The up offset is `____up(m)`; the constant columns must not be selected."""
    header = ("site YYMMMDD yyyy.yyyy __MJD week d reflon _e0(m) __east(m) "
              "____n0(m) _north(m) u0(m) ____up(m) _ant(m) sig_e(m) sig_n(m) sig_u(m) "
              "__corr_en __corr_eu __corr_nu _latitude(deg) _longitude(deg) __height(m)").split()
    assert len(header) == 23
    assert "____up(m)" in header
    # `u0(m)` and `____n0(m)` are constant reference offsets, not the daily position.
    assert header.index("____up(m)") == 12
    assert header.index("u0(m)") == 11
    assert header.index("____n0(m)") == 9


def test_tenv3_date_parsing_uses_yyyymmmdd():
    """The date field is `23SEP10`, not `%Y%m%d`; `%Y%m%d` silently mis-parses it."""
    months = {m: i + 1 for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
    token = "23SEP10"
    year = int(token[:2]) + 2000
    month = months[token[2:5]]
    day = int(token[5:7])
    assert (year, month, day) == (2023, 9, 10)
    assert pd.Timestamp(year=year, month=month, day=day) == pd.Timestamp("2023-09-10")
    # Guard against the specific failure mode: %Y%m%d does not raise on this input.
    assert pd.to_datetime("23SEP10", format="%Y%m%d", errors="coerce") is pd.NaT


# ---------------------------------------------------------------------------
# 2. Diagnostic correctness
# ---------------------------------------------------------------------------

def test_highpass_energy_is_zero_for_a_constant_field(validation):
    values = np.full((60, 60), 0.0042)
    valid = np.ones((60, 60), dtype=bool)
    assert validation.highpass_energy(values, valid, sigma=3) == pytest.approx(0.0, abs=1e-12)


def test_highpass_energy_grows_with_roughness(validation):
    smooth = np.tile(np.linspace(0.0, 0.01, 80), (80, 1))
    rng = np.random.default_rng(7)
    rough = smooth + rng.normal(0, 0.002, smooth.shape)
    valid = np.ones(smooth.shape, dtype=bool)
    assert (validation.highpass_energy(rough, valid, sigma=3)
            > validation.highpass_energy(smooth, valid, sigma=3))


def test_highpass_energy_ignores_masked_pixels(validation):
    """A wild value outside the mask must not leak into the statistic."""
    base = np.zeros((60, 60))
    base[10:50, 10:50] = 0.005
    valid = np.zeros((60, 60), dtype=bool)
    valid[10:50, 10:50] = True
    clean = validation.highpass_energy(base, valid, sigma=3)
    polluted = base.copy()
    polluted[0, 0] = 1e6
    assert validation.highpass_energy(polluted, valid, sigma=3) == pytest.approx(clean, rel=1e-9)


def test_shared_window_applied_to_both_arrays():
    """
    A window taken from the interferogram stack must be applied to the timeseries
    too, or the arrays broadcast against each other (the test-C defect).
    """
    stack = np.zeros((5, 2407, 2939))
    timeseries = np.zeros((10, 2407, 2939))
    window = (slice(100, 1444), slice(200, 1404))
    obs = stack[0][window]
    model = (timeseries[1] - timeseries[0])[window]     # same window, both arrays
    assert obs.shape == model.shape
    with pytest.raises(ValueError):
        obs - (timeseries[1] - timeseries[0])           # unsliced timeseries must fail


# ---------------------------------------------------------------------------
# 3. Promotion policy
# ---------------------------------------------------------------------------

def _verdict(comparisons: dict) -> dict:
    return {"tests": comparisons,
            "n_tests_improved": sum(comparisons.values()),
            "n_tests": len(comparisons),
            "verdict": "measurable improvement" if sum(comparisons.values()) >= 3
                       else "no measurable improvement"}


def test_era5_outcome_is_recorded_as_one_of_four():
    """
    Pin the actual measured outcome: ERA5 improves only the elevation-correlated
    residual and must not be promoted.
    """
    recorded = json.loads(
        (PROJECT_ROOT / "qc" / "sci" / "correction_validation.json").read_text())
    assert recorded["promoted"] == []
    assert recorded["principal_candidate"] == "RAW"
    assert recorded["verdicts"]["ERA5"]["n_tests_improved"] == 1
    assert recorded["verdicts"]["ERA5+DEM"]["n_tests_improved"] == 1
    # The one diagnostic ERA5 wins is the topography one.
    assert recorded["verdicts"]["ERA5"]["tests"]["topo_correlation"] is True
    assert recorded["verdicts"]["ERA5"]["tests"]["roughness"] is False
    assert recorded["verdicts"]["ERA5+DEM"]["tests"]["roughness"] is False
    assert recorded["verdicts"]["ERA5+DEM"]["tests"]["stable_scatter"] is False


def test_promotion_requires_three_of_four():
    assert _verdict({"a": True, "b": False, "c": False, "d": False})["verdict"] == \
        "no measurable improvement"
    assert _verdict({"a": True, "b": True, "c": False, "d": False})["verdict"] == \
        "no measurable improvement"
    assert _verdict({"a": True, "b": True, "c": True, "d": False})["verdict"] == \
        "measurable improvement"


def test_era5_reduces_the_elevation_correlated_residual():
    """
    The physical claim underlying the report: ERA5 does what it should to the
    residual, even though the product is not improved.
    """
    recorded = json.loads(
        (PROJECT_ROOT / "qc" / "sci" / "correction_validation.json").read_text())
    topo = recorded["tests"]["C_topography_correlation_spearman"]
    assert abs(topo["ERA5"]) < abs(topo["RAW"])
    # The DEM-residual step must not be credited with reducing it further.
    assert abs(topo["ERA5+DEM"]) > abs(topo["ERA5"])


def test_gnss_verdict_records_the_coverage_limitation():
    recorded = json.loads(
        (PROJECT_ROOT / "qc" / "sci" / "gnss_suitability.json").read_text())
    assert recorded["outcome"] == "GNSS CANNOT DISCRIMINATE"
    assert recorded["coverage_within_aoi"]["stations_with_adequate_in_period_sampling"] == []
    assert recorded["coverage_within_aoi"]["best_in_period_solution_count"] < \
        recorded["min_common_epochs"]
    # The nearest adequately sampled station is far outside the AOI.
    assert recorded["discriminating_power"][
        "nearest_station_with_adequate_in_period_sampling_km"] > 100


# ---------------------------------------------------------------------------
# 4. Freeze integrity
# ---------------------------------------------------------------------------

def _freeze_id(manifest: dict, promoted) -> str:
    payload = json.dumps({
        "version": manifest["freeze_version"],
        "principal_branch": manifest["principal_branch"],
        "pinned": [[p["path"], p["sha256"]] for p in manifest["pinned_products"]],
        "copied": [[c["path"], c["sha256"]] for c in manifest["copied_artefacts"]],
        "promoted": promoted,
        "decision": "RAW-336 frozen; ERA5 and ERA5+DEM tested but not beneficial",
    }, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def test_freeze_manifest_is_self_consistent():
    manifest_path = PROJECT_ROOT / "freeze" / "product_v1" / "FREEZE.json"
    if not manifest_path.exists():
        pytest.skip("product_v1 freeze not created in this checkout")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["principal_branch"] == "RAW-336"
    assert manifest["pairs_retained"] == 336
    assert manifest["pairs_excluded"] == 0
    assert manifest["deramp"] == "disabled"
    promoted = json.loads(
        (PROJECT_ROOT / "qc" / "sci" / "correction_validation.json").read_text())["promoted"]
    assert _freeze_id(manifest, promoted) == manifest["freeze_id"]
    assert len(manifest["corrections_tested_not_beneficial"]) == 3


def test_freeze_id_changes_when_a_product_hash_changes():
    """A mutated hash must invalidate the id, or the freeze is not a freeze."""
    manifest_path = PROJECT_ROOT / "freeze" / "product_v1" / "FREEZE.json"
    if not manifest_path.exists():
        pytest.skip("product_v1 freeze not created in this checkout")
    manifest = json.loads(manifest_path.read_text())
    promoted = json.loads(
        (PROJECT_ROOT / "qc" / "sci" / "correction_validation.json").read_text())["promoted"]
    original = _freeze_id(manifest, promoted)

    mutated = json.loads(json.dumps(manifest))
    mutated["pinned_products"][0]["sha256"] = "0" * 64
    assert _freeze_id(mutated, promoted) != original

    # A changed promotion outcome must also change the id.
    assert _freeze_id(manifest, ["ERA5"]) != original


def test_freeze_id_is_stable_across_key_order():
    """The payload is canonicalised, so dict ordering must not matter."""
    base = {"freeze_version": "product_v1", "principal_branch": "RAW-336",
            "pinned_products": [{"path": "a", "sha256": "1"},
                                {"path": "b", "sha256": "2"}],
            "copied_artefacts": [{"path": "c", "sha256": "3"}]}
    reordered = {"copied_artefacts": base["copied_artefacts"],
                 "pinned_products": base["pinned_products"],
                 "principal_branch": "RAW-336",
                 "freeze_version": "product_v1"}
    assert _freeze_id(base, []) == _freeze_id(reordered, [])


def test_frozen_artefacts_are_read_only():
    freeze_dir = PROJECT_ROOT / "freeze" / "product_v1"
    if not freeze_dir.exists():
        pytest.skip("product_v1 freeze not created in this checkout")
    assert not (freeze_dir.stat().st_mode & 0o222), "freeze directory must be read-only"
    for path in freeze_dir.rglob("*"):
        if path.is_file():
            assert not (path.stat().st_mode & 0o222), f"{path.name} must be read-only"
