#!/usr/bin/env python
"""
Phase III-A4 stage 0: freeze the groundwater analysis protocol BEFORE any
correlation is computed.

No correlation output may exist before this freeze. This script computes no
correlation; it records rules, thresholds, the lag set, the statistical
procedure and the evidence-grading criteria, then hashes the inputs.

Usage
-----
    python scripts/65_phase3a4_protocol.py --freeze
    python scripts/65_phase3a4_protocol.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE = PROJECT_ROOT / "freeze" / "groundwater_protocol_v1"
NWDP = PROJECT_ROOT / "data" / "external" / "nwdp"
OUT = PROJECT_ROOT / "qc" / "sci" / "phase3"

PROTOCOL = {
    "protocol_version": "groundwater_protocol_v1",
    "frozen_before_any_correlation": True,

    "roles_frozen": {
        "primary_positive": ["H001", "H004"],
        "negative_geodetic_controls": ["H002", "H003"],
        "excluded": {"H005": "UNRESOLVED_CONTRADICTION - excluded from groundwater "
                             "hypothesis testing"},
        "note": "roles must not be changed because of groundwater results",
    },

    "station_selection": {
        "primary_max_distance_km": 5.0,
        "secondary_sensitivity_band_km": [5.0, 10.0],
        "excluded_beyond_km": 10.0,
        "distance_basis": "great-circle distance from station coordinates to the frozen "
                          "Phase-I hotspot centroid",
        "select": "ALL quality-passing stations within 5 km; no selection by trend, "
                  "correlation, seasonal behaviour or visual similarity",
        "unequal_station_counts": "expected and reported explicitly; sample size is not "
                                  "forced equal across hotspots",
        "distance_weighting": "NOT used in the primary analysis; sensitivity only",
    },

    "station_qc_rules": {
        "dead_sensor_exact_zero_fraction_gt": 0.50,
        "dead_sensor_constant_fraction_gt": 0.90,
        "insufficient_valid_days_lt": 365,
        "insufficient_coverage_fraction_lt": 0.50,
        "pass_with_gaps_longest_gap_days_gt": 30,
        "classes": ["PASS", "PASS_WITH_GAPS", "FAIL_DEAD_SENSOR",
                    "FAIL_INSUFFICIENT_RECORD", "FAIL_OTHER"],
        "no_automatic_repair": True,
        "zeros_not_globally_assumed_impossible": "provider metadata does not establish a "
                                                 "sentinel convention, so zeros are judged "
                                                 "only through the frozen fraction rules",
        "dead_stations_retained_in_inventory": True,
    },

    "temporal_aggregation": {
        "raw_preserved": "six-hourly observations kept unchanged and authoritative for "
                         "provenance",
        "canonical_input": "daily series",
        "daily_statistic": "median of valid six-hourly observations that day",
        "min_observations_per_day": 2,
        "below_minimum": "daily value = missing",
        "interpolation": "NONE - missing days stay missing",
    },

    "sign_convention": {
        "source_variable": "depth to water level (mbgl)",
        "larger_mbgl_means": "deeper groundwater table / decline relative to land surface",
        "anomaly": "GW_DEPTH_ANOMALY(t) = depth_mbgl(t) - station_median_depth_mbgl",
        "positive_anomaly": "deeper than the station median",
        "negative_anomaly": "shallower than the station median",
        "never_switch_silently": True,
    },

    "station_datum_handling": {
        "absolute_values_never_averaged_across_stations": True,
        "primary_representation": "depth anomaly relative to that station's own record "
                                  "median",
        "composite": "HOTSPOT_GW_COMPOSITE(t) = median of available station anomalies",
        "station_weighting": "equal",
        "distance_weighting": "sensitivity analysis only, never primary",
    },

    "composite_availability_rule": {
        "min_fraction_of_stations_valid": 0.50,
        "min_contributing_stations_when_eligible_ge_2": 2,
        "single_station_hotspot": "reported explicitly as single-station evidence, not as "
                                  "a spatial composite",
    },

    "gap_handling": {
        "interpolation_across_gaps": "FORBIDDEN",
        "the_78_day_H001_outage_must_not_be_bridged": True,
        "preserve_per_station": ["missing_day_mask", "longest_gap", "valid_fraction",
                                 "monthly_completeness"],
        "insar_epoch_in_gap": "unavailable for that test; no extrapolation",
    },

    "insar_alignment": {
        "series_used": "authoritative ASCENDING hotspot time series (product_v1 / RAW-336)",
        "reason": "the ascending product remains the authoritative deformation solution; "
                  "descending validates rate/spatial behaviour for H001/H004 but not their "
                  "detailed displacement histories",
        "descending_merged": False,
        "window_days": 7,
        "window_type": "centred on the InSAR acquisition date, t-3 to t+3",
        "statistic": "median of the daily groundwater composite in that window",
        "min_valid_daily_values_in_window": 4,
        "otherwise": "groundwater value = missing for that epoch",
        "nearest_neighbour_filling": "FORBIDDEN",
    },

    "test_A_long_term": {
        "question": "does groundwater systematically deepen or recover over the study "
                    "period in a way consistent with the broad deformation evolution",
        "estimator": "Theil-Sen robust slope",
        "windows": ["full_record", "first_half", "second_half"],
        "compare_against": ["full-period InSAR rate", "first-half InSAR rate",
                            "second-half InSAR rate"],
        "seasonal_CGWB_snapshots_may_not_be_used_for_trend": True,
        "matching_trends_do_not_imply_causation": True,
    },

    "test_B_detrended": {
        "question": "after removing long-term behaviour, do groundwater anomalies and "
                    "relative LOS displacement covary temporally",
        "groundwater_detrend": "robust linear trend removed (Theil-Sen intercept/slope)",
        "insar_detrend": "robust linear trend removed (Theil-Sen intercept/slope)",
        "high_order_polynomials": "FORBIDDEN",
        "purpose": "evaluate seasonal / sub-annual coupling",
    },

    "lags": {
        "primary_positive_days": [0, 30, 60, 90],
        "interpretation": "lag +30 means the groundwater state precedes the InSAR response "
                          "by approximately 30 days",
        "falsification_negative_days": [-30, -60, -90],
        "negative_lag_role": "falsification diagnostics only; may NOT be used to support "
                             "the groundwater hypothesis",
        "arbitrary_lag_search": "FORBIDDEN",
        "per_hotspot_lag_optimisation": "FORBIDDEN",
    },

    "association_metrics": {
        "primary": "Spearman rho",
        "secondary": "Pearson r",
        "always_report": ["N matched InSAR epochs"],
        "rationale": "neither groundwater nor InSAR residuals should be assumed Gaussian",
    },

    "significance": {
        "method": "circular block permutation",
        "block_days": 90,
        "iid_p_values": "FORBIDDEN - both series are autocorrelated",
        "iterations": 5000,
        "random_seed": 20260922,
        "report": ["effect size", "autocorrelation-aware significance"],
        "p_value_replaces_effect_size": False,
    },

    "multiple_testing": {
        "family": "4 hotspots x 4 primary positive lags = 16 hotspot-composite tests",
        "method": "Benjamini-Hochberg FDR",
        "q": 0.05,
        "station_level_results": "supporting / sensitivity evidence, NOT independent "
                                 "primary hypothesis tests",
        "cherry_picking": "FORBIDDEN",
    },

    "expected_sign": {
        "hypothesis": "groundwater-related compaction",
        "deeper_groundwater": "positive GW_DEPTH_ANOMALY",
        "relevant_deformation": "more negative LOS displacement",
        "expected_association": "negative correlation between GW_DEPTH_ANOMALY and LOS "
                                "displacement, i.e. deeper groundwater -> more negative LOS",
        "forced": False,
        "persistent_opposite_sign": "counter-evidence",
        "caveat": "LOS is not a vertical-only measurement",
    },

    "positive_case_requirement": [
        "multiple nearby stations behave consistently where available",
        "hotspot composite shows the relationship",
        "effect survives reasonable quality-mask choice",
        "positive lags perform at least as well as negative/falsification lags",
        "result is not driven by one short interval",
        "temporal coverage is adequate",
    ],

    "mandatory_controls": {
        "run_same_protocol_for": ["H002", "H003"],
        "reason": "their ascending contrasts are similar to H004 but their rates are NOT "
                  "reproduced in descending despite adequate descending quality; a "
                  "groundwater mechanism becomes less selective if the controls behave "
                  "equally strongly",
        "comparison_is_required": "H001/H004 vs H002/H003, not merely per-hotspot tests",
    },

    "quality_mask_sensitivity": {
        "insar_extractions": ["Q_PRIMARY", "Q_STRICT", "hotspot_core"],
        "hotspot_redesign": "FORBIDDEN",
        "groundwater_series_unchanged": True,
        "if_association_disappears_under_tightening": "classify as processing-sensitive",
    },

    "coherence_confounding": {
        "record_per_hotspot": ["median temporal coherence", "strict-mask result",
                               "core result", "processing sensitivity"],
        "million_pixel_regressions": "FORBIDDEN",
        "test": "does the groundwater association survive using only high-confidence / "
                "strict-quality InSAR pixels",
    },

    "outage_sensitivity": {
        "applies_to": "H001 (long telemetry gaps)",
        "procedure": "remove 30 days before and 30 days after each major gap, then repeat "
                     "any apparently meaningful result",
        "gap_filling": "FORBIDDEN",
    },

    "leave_one_station_out": {
        "threshold_for_test": "hotspots with >= 3 eligible stations",
        "for_H001_with_2_stations": "report both station results individually in addition "
                                    "to the composite",
        "result_dependent_on_one_station": "labelled STATION-SENSITIVE",
    },

    "seasonal_cgwb_validation": {
        "role": "coarse external context only",
        "merge_with_NWDP": "FORBIDDEN",
        "use_to_fill_gaps": "FORBIDDEN",
        "networks_overlap": False,
        "may_not_be_called": "station-level validation",
    },

    "evidence_grading": {
        "scale": ["NO EVIDENCE", "WEAK", "MODERATE", "STRONG"],
        "STRONG": ["expected-direction association in H001 and/or H004",
                   "effect robust across stations/composite",
                   "positive-lag behaviour",
                   "autocorrelation-aware support",
                   "robustness to InSAR quality mask",
                   "groundwater behaviour more specific to supported zones than H002/H003",
                   "no major contradictory evidence"],
        "MODERATE": "multiple lines consistent but one major limitation remains (sparse "
                    "local network, large outage, control ambiguity, limited robustness)",
        "WEAK": "some temporal/spatial consistency but small/unstable effect, station "
                "dependence, similar controls, ambiguous lag direction, or strong data "
                "limitations",
        "NO_EVIDENCE": "no consistent preregistered association, or predominantly "
                       "contradictory evidence",
        "forbidden_language": ["PROVEN", "CAUSED BY", "GROUNDWATER SUBSIDENCE"],
    },

    "interpretation_boundary": {
        "even_a_STRONG_result_means": "strong evidence consistent with groundwater-related "
                                      "deformation",
        "it_does_not_mean": "groundwater depletion caused the observed subsidence",
        "why": ["LOS is not a pure vertical measurement",
                "H001/H004 temporal histories are not independently reproduced by "
                "descending",
                "aquifer/geological metadata are missing",
                "no direct compaction measurements exist"],
    },
}


def sha256_of(path: Path) -> str:
    d = hashlib.sha256()
    with path.open("rb") as h:
        for c in iter(lambda: h.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def collect_hashes() -> dict:
    inputs = {}
    for p in sorted(NWDP.glob("*.csv")):
        inputs[f"data/external/nwdp/{p.name}"] = sha256_of(p)
    for rel in ("qc/sci/phase1/hotspots_corrected.geojson",
                "qc/sci/phase1/hotspots.csv",
                "mintpy/baseline_raw_work/velocity.h5",
                "mintpy/baseline_raw_work/timeseries.h5",
                "mintpy/baseline_raw_work/temporalCoherence.h5",
                "qc/sci/phase3/nwdp_telemetry_station_registry.csv"):
        p = PROJECT_ROOT / rel
        if p.exists():
            inputs[rel] = sha256_of(p)
    return inputs


def freeze() -> int:
    if FREEZE.exists():
        print(f"ERROR: {FREEZE} exists (append-only).", file=sys.stderr)
        return 1
    FREEZE.mkdir(parents=True)
    hashes = collect_hashes()
    doc = dict(PROTOCOL)
    doc["created_utc"] = datetime.now(timezone.utc).isoformat()
    doc["input_hashes"] = hashes
    doc["environment"] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pandas": __import__("pandas").__version__,
        "numpy": __import__("numpy").__version__,
        "scipy": __import__("scipy").__version__,
    }
    doc["no_correlation_exists_yet"] = True
    fid = hashlib.sha256(json.dumps(
        {"protocol": {k: v for k, v in PROTOCOL.items()},
         "hashes": hashes}, sort_keys=True, default=str).encode()).hexdigest()
    doc["protocol_freeze_id"] = fid
    (FREEZE / "GROUNDWATER_PROTOCOL_V1.json").write_text(
        json.dumps(doc, indent=2, default=str))
    for x in sorted(FREEZE.rglob("*"), reverse=True):
        x.chmod(0o444)
    FREEZE.chmod(0o555)
    print("=" * 88)
    print("GROUNDWATER ANALYSIS PROTOCOL FROZEN")
    print("=" * 88)
    print(f"\n  protocol_freeze_id: {fid}")
    print(f"  inputs hashed     : {len(hashes)}")
    print(f"  primary lags      : {PROTOCOL['lags']['primary_positive_days']}")
    print(f"  falsification lags: {PROTOCOL['lags']['falsification_negative_days']}")
    print(f"  block permutation : {PROTOCOL['significance']['block_days']}-day blocks, "
          f"{PROTOCOL['significance']['iterations']} iterations")
    print(f"  FDR               : BH q={PROTOCOL['multiple_testing']['q']} over "
          f"16 hotspot-composite tests")
    print(f"\n  NO CORRELATION HAS BEEN COMPUTED.")
    print(f"  {FREEZE / 'GROUNDWATER_PROTOCOL_V1.json'}")
    return 0


def verify() -> int:
    p = FREEZE / "GROUNDWATER_PROTOCOL_V1.json"
    if not p.exists():
        print(f"ERROR: {p} not found.", file=sys.stderr)
        return 1
    doc = json.loads(p.read_text())
    recomputed = hashlib.sha256(json.dumps(
        {"protocol": {k: v for k, v in PROTOCOL.items()},
         "hashes": doc["input_hashes"]}, sort_keys=True, default=str).encode()).hexdigest()
    bad = [rel for rel, h in doc["input_hashes"].items()
           if (PROJECT_ROOT / rel).exists() and sha256_of(PROJECT_ROOT / rel) != h]
    print(f"  recorded : {doc['protocol_freeze_id']}")
    print(f"  computed : {recomputed}")
    print(f"  match    : {recomputed == doc['protocol_freeze_id']}")
    if bad:
        print(f"  DRIFTED INPUTS: {bad}")
        return 1
    print(f"  inputs unchanged: {len(doc['input_hashes'])} hashed")
    return 0 if recomputed == doc["protocol_freeze_id"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--freeze", action="store_true")
    g.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    return freeze() if args.freeze else verify()


if __name__ == "__main__":
    raise SystemExit(main())
