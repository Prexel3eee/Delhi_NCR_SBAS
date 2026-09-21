#!/usr/bin/env python
"""
Phase E - exact HyP3 credit estimate and pilot selection (no submission).

Credit model
------------
Implements the official HyP3 burst-InSAR credit table exactly (brief section 32),
verified against https://hyp3-docs.asf.alaska.edu/using/credits/

    20x4 looks (80 m):  K 1-4 -> 1   K 5-12 -> 5   K 13-15 -> 10
    10x2 looks (40 m):  K 1-3 -> 1   K 4-9  -> 5   K 10-15 -> 10
    5x1  looks (20 m):  explicit 1..15 table

Note the material consequence of the K=4 collection: at 10x2 looks the cost per
job jumps from 1 credit (K<=3) to 5 credits (K>=4), a 5x increase. At 20x4 looks
K=4 still costs 1 credit. This script surfaces that trade-off rather than hiding
it.

Pilot selection (brief section 33)
----------------------------------
Coverage of early / middle / late time series and of the baseline space:
  1. lowest |B_perp| 12-day pair
  2. median |B_perp| 24-day pair
  3. upper-quantile |B_perp| 36-day pair
  4. representative monsoon pair (Jun-Sep)
  5. representative dry-season pair (Nov-Mar)
  6. one late-period pair (2025 tail)
plus one duplicate of pair 1 with apply_water_mask=False, per brief section 15.

Outputs
-------
qc/cost_estimate.json
manifests/pilot_pairs.csv
config/pilot.yaml

Nothing is submitted to HyP3 by this script.

Usage
-----
    python scripts/05_estimate_hyp3_cost.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
QC_DIR = PROJECT_ROOT / "qc"
CONFIG_DIR = PROJECT_ROOT / "config"

MONTHLY_ALLOCATION = 8000

LOOks_CHOICES = ("20x4", "10x2", "5x1")

#: Official burst-InSAR credit cost per job.
FIVE_BY_ONE = {
    1: 1, 2: 5, 3: 10, 4: 15, 5: 20, 6: 25, 7: 30, 8: 35,
    9: 40, 10: 45, 11: 90, 12: 95, 13: 100, 14: 105, 15: 110,
}


def burst_insar_credit_cost(looks: str, burst_count: int) -> int:
    """Exact credits for one multi-burst job."""
    if not 1 <= burst_count <= 15:
        raise ValueError("HyP3 multi-burst requires 1-15 burst pairs")

    if looks == "20x4":
        if burst_count <= 4:
            return 1
        if burst_count <= 12:
            return 5
        return 10

    if looks == "10x2":
        if burst_count <= 3:
            return 1
        if burst_count <= 9:
            return 5
        return 10

    if looks == "5x1":
        return FIVE_BY_ONE[burst_count]

    raise ValueError(f"Unsupported looks: {looks}")


# ---------------------------------------------------------------------------
# Pilot selection
# ---------------------------------------------------------------------------


def month_of(iso: str) -> int:
    return int(iso[5:7])


def is_monsoon(ref: str, sec: str) -> bool:
    return all(6 <= month_of(d) <= 9 for d in (ref, sec))


def is_dry(ref: str, sec: str) -> bool:
    return all(month_of(d) in (11, 12, 1, 2, 3) for d in (ref, sec))


def select_pilot(pairs: pd.DataFrame) -> list[dict]:
    chosen: list[dict] = []
    used: set[str] = set()

    def take(row, rationale: str, water_mask: bool = True) -> None:
        key = f"{row.pair_id}|{water_mask}"
        if key in used:
            return
        used.add(key)
        chosen.append(
            {
                "pair_id": row.pair_id,
                "reference_date": row.reference_date,
                "secondary_date": row.secondary_date,
                "temporal_baseline_days": int(row.temporal_baseline_days),
                "perpendicular_baseline_max_abs_m": float(row.perpendicular_baseline_max_abs_m),
                "burst_count": int(row.burst_count),
                "apply_water_mask": water_mask,
                "rationale": rationale,
            }
        )

    def pick(subset: pd.DataFrame, sort_cols, ascending) -> pd.Series | None:
        if subset.empty:
            return None
        return subset.sort_values(sort_cols, ascending=ascending).iloc[0]

    def unused(subset: pd.DataFrame) -> pd.DataFrame:
        return subset[~subset["pair_id"].isin({c["pair_id"] for c in chosen})]

    # 1. lowest |B_perp| 12-day pair
    row = pick(unused(pairs[pairs["temporal_baseline_days"] == 12]),
               ["perpendicular_baseline_max_abs_m"], True)
    if row is not None:
        take(row, "lowest |B_perp| 12-day pair")

    # 2. median |B_perp| 24-day pair
    subset = unused(pairs[pairs["temporal_baseline_days"] == 24]).sort_values(
        "perpendicular_baseline_max_abs_m"
    )
    if not subset.empty:
        take(subset.iloc[len(subset) // 2], "median |B_perp| 24-day pair")

    # 3. upper-quantile |B_perp| 36-day pair
    subset = unused(pairs[pairs["temporal_baseline_days"] == 36]).sort_values(
        "perpendicular_baseline_max_abs_m"
    )
    if not subset.empty:
        row = subset.iloc[min(len(subset) - 1, int(0.9 * (len(subset) - 1)))]
        take(row, "p90 |B_perp| 36-day pair (stress test)")

    # 4. monsoon pair
    monsoon = unused(pairs[pairs.apply(lambda r: is_monsoon(r.reference_date, r.secondary_date), axis=1)])
    row = pick(monsoon, ["perpendicular_baseline_max_abs_m"], True)
    if row is not None:
        take(row, "monsoon-season pair (Jun-Sep)")

    # 5. dry-season pair
    dry = unused(pairs[pairs.apply(lambda r: is_dry(r.reference_date, r.secondary_date), axis=1)])
    row = pick(dry, ["perpendicular_baseline_max_abs_m"], True)
    if row is not None:
        take(row, "dry-season pair (Nov-Mar)")

    # 6. late-period pair (2025 tail)
    late = unused(pairs[pairs["secondary_date"] >= "2025-01-01"])
    row = pick(late, ["perpendicular_baseline_max_abs_m"], True)
    if row is not None:
        take(row, "late-period 2025 pair (time-series tail)")

    # 7. water-mask control: repeat the first selected pair with masking OFF so
    #    the pilot can compare unwrapping / connected components near the Yamuna
    #    (brief section 15). Same acquisition pair, different HyP3 option only.
    if chosen:
        first = chosen[0]
        source = pairs[pairs["pair_id"] == first["pair_id"]].iloc[0]
        take(source, "water-mask control: same pair as #1, apply_water_mask=False", water_mask=False)

    return chosen


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    pairs_path = MANIFEST_DIR / "sbas_pairs.csv"
    if not pairs_path.exists():
        raise SystemExit(f"FAIL: {pairs_path} not found. Run scripts/04_build_sbas_network.py first.")

    pairs = pd.read_csv(pairs_path)
    if pairs.empty:
        raise SystemExit("FAIL: pair manifest is empty.")

    k = int(pairs["burst_count"].iloc[0])
    if not (pairs["burst_count"] == k).all():
        raise SystemExit("FAIL: heterogeneous burst_count in pair manifest.")

    n_pairs = len(pairs)

    print("=" * 88)
    print("PHASE E - HyP3 CREDIT ESTIMATE AND PILOT SELECTION (NO SUBMISSION)")
    print("=" * 88)
    print(f"\nK (bursts per multi-burst job) : {k}")
    print(f"N (multi-burst interferograms) : {n_pairs}")
    print(f"Monthly HyP3 Basic allocation  : {MONTHLY_ALLOCATION} credits")

    scenarios: dict[str, dict] = {}
    print("\n" + "-" * 88)
    print("PRODUCTION CREDIT SCENARIOS")
    print("-" * 88)
    print(f"  {'looks':8s} {'pixel':8s} {'credits/job':>12s} {'total':>10s} {'% allocation':>14s}")
    for looks, pixel in (("20x4", "80 m"), ("10x2", "40 m"), ("5x1", "20 m")):
        per_job = burst_insar_credit_cost(looks, k)
        total = per_job * n_pairs
        pct = 100.0 * total / MONTHLY_ALLOCATION
        scenarios[looks] = {
            "looks": looks,
            "pixel_spacing": pixel,
            "credits_per_job": per_job,
            "total_credits": total,
            "pct_monthly_allocation": round(pct, 2),
        }
        marker = "  <- primary pilot config" if looks == "10x2" else ""
        print(f"  {looks:8s} {pixel:8s} {per_job:>12d} {total:>10d} {pct:>13.2f}%{marker}")

    primary = scenarios["10x2"]
    print("\n  Note: at K=4 the 10x2 tier moves from 1 to 5 credits/job,")
    print("        a 5x increase versus a K<=3 collection. 20x4 stays at 1 credit/job.")

    # ---- pilot ------------------------------------------------------------
    pilot = select_pilot(pairs)
    pilot_per_job = burst_insar_credit_cost("10x2", k)
    pilot_cost = pilot_per_job * len(pilot)

    print("\n" + "-" * 88)
    print(f"PILOT SELECTION ({len(pilot)} jobs at 10x2 / 40 m, water mask per row)")
    print("-" * 88)
    for i, entry in enumerate(pilot, 1):
        wm = "water_mask=ON " if entry["apply_water_mask"] else "water_mask=OFF"
        print(
            f"  {i}. {entry['pair_id']}  {entry['reference_date']} -> {entry['secondary_date']}  "
            f"t={entry['temporal_baseline_days']:>2}d  |B_perp|={entry['perpendicular_baseline_max_abs_m']:>6.1f} m  {wm}"
        )
        print(f"       {entry['rationale']}")

    print(f"\n  Pilot jobs        : {len(pilot)}")
    print(f"  Credits/job       : {pilot_per_job}")
    print(f"  Pilot total       : {pilot_cost} credits "
          f"({100.0 * pilot_cost / MONTHLY_ALLOCATION:.3f}% of monthly allocation)")
    print(f"  Full production   : {primary['total_credits']} credits "
          f"({primary['pct_monthly_allocation']:.2f}% of monthly allocation)")

    # ---- write ------------------------------------------------------------
    QC_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    pilot_df = pd.DataFrame(pilot)
    pilot_path = MANIFEST_DIR / "pilot_pairs.csv"
    pilot_df.to_csv(pilot_path, index=False)

    estimate = {
        "phase": "E",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_pair_manifest": str(pairs_path),
        "burst_count_k": k,
        "interferogram_count_n": n_pairs,
        "monthly_basic_allocation_credits": MONTHLY_ALLOCATION,
        "credit_table_source": "https://hyp3-docs.asf.alaska.edu/using/credits/",
        "scenarios": scenarios,
        "primary_pilot_config": {
            "looks": "10x2",
            "pixel_spacing": "40 m",
            "credits_per_job": pilot_per_job,
            "rationale": "Brief section 14: 40 m pixels are the recommended middle ground "
            "for urban subsidence. Retained as primary; 20x4 is not adopted merely to "
            "save credits unless the pilot shows 80 m pixels are adequate.",
        },
        "pilot": {
            "jobs": pilot,
            "job_count": len(pilot),
            "credits_per_job": pilot_per_job,
            "total_credits": pilot_cost,
            "pct_monthly_allocation": round(100.0 * pilot_cost / MONTHLY_ALLOCATION, 4),
        },
        "production_submitted": False,
        "notes": [
            "No HyP3 job has been submitted by this script.",
            "Re-check the live credit table immediately before any large submission.",
            "Production remains blocked on pilot QC and explicit user approval.",
        ],
    }
    estimate_path = QC_DIR / "cost_estimate.json"
    estimate_path.write_text(json.dumps(estimate, indent=2))

    pilot_config = {
        "phase": "pilot",
        "frozen": datetime.now(timezone.utc).isoformat(),
        "hyp3": {
            "job_type": "INSAR_ISCE_MULTI_BURST",
            "service": "basic",
            "looks": "10x2",
            "pixel_spacing": "40 m",
            "apply_water_mask_default": True,
            "note": "One pilot pair is repeated with apply_water_mask=False per brief section 15.",
        },
        "network": {
            "max_temporal_baseline_days": 36,
            "max_perpendicular_baseline_m": 250,
        },
        "bursts": {
            "count": k,
            "full_burst_ids": json.loads(pairs["reference_burst_ids_json"].iloc[0]),
        },
        "submission": {
            "requires_approval": True,
            "production_submitted": False,
        },
    }
    pilot_config_path = CONFIG_DIR / "pilot.yaml"
    pilot_config_path.write_text(yaml.safe_dump(pilot_config, sort_keys=False))

    print("\n" + "=" * 88)
    print("FILES WRITTEN")
    print("=" * 88)
    print(f"  {estimate_path}")
    print(f"  {pilot_path}")
    print(f"  {pilot_config_path}")
    print("\nNO HyP3 JOB SUBMITTED. Production requires pilot QC and explicit approval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
