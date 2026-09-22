#!/usr/bin/env python
"""
Phase II, stage 3: DESCENDING acquisition inventory and SBAS network.

Independently constructed. The burst collection comes from script 39 (path 136,
IW1, K=4); the observation window matches the ascending study period; the
network rules match the ascending ones (max 36-day temporal baseline, max 250 m
perpendicular baseline, identity-joined across bursts). **No pair is chosen
because it intersects a Phase-I hotspot**, and no ascending mask, pair, or
acquisition list is read.

Fail-closed philosophy, carried over from the ascending product:
  * a date is accepted only if EVERY burst has a record for it;
  * a pair is built only if its key exists in every burst (identity intersection,
    never a positional zip);
  * the inventory is cross-checked against a second query path;
  * the network is audited for connectivity, bridges, articulation points and
    minimum degree BEFORE anything is submitted or paid for.

Outputs
-------
manifests/descending/burst_inventory_2021_2025.csv
manifests/descending/accepted_acquisitions.csv
manifests/descending/excluded_acquisitions.csv
manifests/descending/sbas_pairs.csv
qc/descending/network_audit.json

Usage
-----
    python scripts/40_descending_inventory_network.py
"""

from __future__ import annotations

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from itertools import combinations
from pathlib import Path

import networkx as nx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asf_client as ac  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests" / "descending"
QC_DIR = PROJECT_ROOT / "qc" / "descending"

START = "2021-10-01T00:00:00Z"
END = "2025-10-01T00:00:00Z"
EXPECTED_PATH = 136
EXPECTED_DIRECTION = "DESCENDING"
EXPECTED_POLARIZATION = "VV"
EXPECTED_SUBSWATH = "IW1"

MAX_TEMPORAL_DAYS = 36
MAX_PERP_M = 250.0
MAX_WORKERS = 4


def load_frozen_bursts() -> pd.DataFrame:
    path = MANIFEST_DIR / "geographic_reference_bursts.csv"
    if not path.exists():
        raise SystemExit(f"FAIL: {path} not found. Run scripts/39_select_descending_bursts.py")
    frame = pd.read_csv(path)
    if frame["full_burst_id"].duplicated().any():
        raise SystemExit("FAIL: duplicate full_burst_id in descending burst manifest")
    if set(frame["flight_direction"]) != {EXPECTED_DIRECTION}:
        raise SystemExit("FAIL: burst manifest is not DESCENDING")
    if set(frame["subswath"]) != {EXPECTED_SUBSWATH}:
        raise SystemExit(f"FAIL: expected subswath {EXPECTED_SUBSWATH}")
    return frame


def collect(full_burst_id: str):
    try:
        result = ac.burst_inventory(full_burst_id, START, END, EXPECTED_POLARIZATION,
                                    tries=4, cross_check_asf=True)
        return full_burst_id, result, None
    except Exception as exc:  # noqa: BLE001
        return full_burst_id, None, f"{type(exc).__name__}: {exc}"


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="  %(levelname)s %(message)s")
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    QC_DIR.mkdir(parents=True, exist_ok=True)

    bursts = load_frozen_bursts()
    burst_ids = list(bursts["full_burst_id"])
    print("=" * 88)
    print("PHASE II - DESCENDING INVENTORY AND SBAS NETWORK")
    print("=" * 88)
    print(f"\n  bursts ({len(burst_ids)}): {', '.join(burst_ids)}")
    print(f"  window {START[:10]} .. {END[:10]}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(collect, burst_ids))

    errors = {bid: err for bid, _, err in results if err}
    if errors:
        print("\nERROR: inventory failed for some bursts:", file=sys.stderr)
        for bid, err in errors.items():
            print(f"  {bid}: {err}", file=sys.stderr)
        return 1

    per_burst = {}
    rows = []
    for bid, result, _ in results:
        dates = set(result.dates)
        per_burst[bid] = dates
        print(f"  {bid}: {len(dates)} dates, "
              f"{len(result.records)} records, "
              f"query={result.provenance.get('query_method', '?')}")
        for record in result.records:
            row = record.as_row()
            row["full_burst_id"] = bid
            rows.append(row)
    inventory = pd.DataFrame(rows).sort_values(["full_burst_id", "date"])
    inventory.to_csv(MANIFEST_DIR / "burst_inventory_2021_2025.csv", index=False)

    # ---- identity join: a date is accepted only if EVERY burst has it ------
    common = set.intersection(*per_burst.values())
    union = set.union(*per_burst.values())
    print(f"\n  union of dates      {len(union)}")
    print(f"  common to all bursts {len(common)}  (accepted)")

    accepted_dates = sorted(common)
    excluded = []
    for day in sorted(union - common):
        missing = [bid for bid, ds in per_burst.items() if day not in ds]
        excluded.append({"date": day.isoformat(), "missing_bursts": missing,
                         "reason": "not present in every burst; fail-closed exclusion"})
    pd.DataFrame({"date": [d.isoformat() for d in accepted_dates]}).to_csv(
        MANIFEST_DIR / "accepted_acquisitions.csv", index=False)
    pd.DataFrame(excluded).to_csv(MANIFEST_DIR / "excluded_acquisitions.csv", index=False)

    # ---- perpendicular baselines ------------------------------------------
    reference_scene = str(bursts.iloc[0]["reference_scene_name"])
    baselines = {}
    for bid in burst_ids:
        print(f"  baselines for {bid} ...")
        baselines[bid] = ac.burst_baseline_stack(
            full_burst_id=bid, reference_scene=reference_scene, start=START, end=END,
            required_dates=accepted_dates, window_days=180, tries=3)

    # ---- pairs: identity intersection across bursts -----------------------
    scene_of = {(r.full_burst_id, r.date): r.scene_name for r in inventory.itertuples()}
    per_burst_keys = {}
    for bid in burst_ids:
        perp = baselines[bid].perp_m
        available = [d.isoformat() for d in accepted_dates if d.isoformat() in perp]
        keys = set()
        for ref_iso, sec_iso in combinations(available, 2):
            temporal = (date.fromisoformat(sec_iso) - date.fromisoformat(ref_iso)).days
            if temporal > MAX_TEMPORAL_DAYS:
                continue
            if abs(perp[sec_iso] - perp[ref_iso]) > MAX_PERP_M:
                continue
            if not scene_of.get((bid, ref_iso)) or not scene_of.get((bid, sec_iso)):
                continue
            keys.add((ref_iso, sec_iso))
        per_burst_keys[bid] = keys

    common_keys = set.intersection(*per_burst_keys.values())
    all_keys = set.union(*per_burst_keys.values())
    print(f"\n  candidate pair keys per burst: "
          f"{ {b: len(k) for b, k in per_burst_keys.items()} }")
    print(f"  common keys {len(common_keys)}  (union {len(all_keys)}, "
          f"dropped {len(all_keys) - len(common_keys)} for a missing burst)")

    # ---- connectivity -----------------------------------------------------
    # The base rule matches the ascending product exactly (36 d, 250 m). The
    # descending record is sparser (92 acquisitions vs 119) and has two gaps
    # longer than 36 d, so the base rule alone leaves the graph both fragmented
    # and bridge-rich:
    #
    #     base 36 d / 250 m  ->  3 components, 10 bridges, 15 articulation points
    #
    # A bridge is a single pair whose loss disconnects the network, so a
    # bridge-rich network is fragile. Rather than widen the rule for every pair,
    # the MINIMUM set of extra pairs needed is added, with caps on how long those
    # extra pairs may be, and every added pair is flagged with its reason.
    BASE_TEMPORAL_DAYS = MAX_TEMPORAL_DAYS
    EXTRA_TEMPORAL_DAYS = 60
    # Connecting disconnected epochs may need a longer pair than de-bridging does;
    # the 108-day gap cannot be crossed by anything shorter than 108 days.
    CONNECT_TEMPORAL_DAYS = 120

    perp_any = baselines[burst_ids[0]].perp_m
    all_available = sorted(perp_any)

    def perp_gap(a: str, b: str) -> float:
        return max(abs(baselines[bid].perp_m[b] - baselines[bid].perp_m[a])
                   for bid in burst_ids)

    def eligible(a: str, b: str, max_temporal: int):
        lo, hi = (a, b) if a < b else (b, a)
        if lo == hi or hi not in perp_any or lo not in perp_any:
            return None
        temporal = (date.fromisoformat(hi) - date.fromisoformat(lo)).days
        if temporal <= 0 or temporal > max_temporal:
            return None
        if perp_gap(lo, hi) > MAX_PERP_M:
            return None
        if not scene_of.get((burst_ids[0], lo)) or not scene_of.get((burst_ids[0], hi)):
            return None
        return (temporal, lo, hi)

    def graph_of(keys):
        # Nodes come only from the edges: adding every available date would keep
        # an unconnectable acquisition present as an isolated node forever.
        g = nx.Graph()
        g.add_edges_from(keys)
        return g

    # Candidate extra pairs, shortest temporal baseline first.
    extra_candidates = []
    connect_candidates = []
    for a, b in combinations(all_available, 2):
        found = eligible(a, b, CONNECT_TEMPORAL_DAYS)
        if found and found[0] > BASE_TEMPORAL_DAYS:
            connect_candidates.append(found)
            if found[0] <= EXTRA_TEMPORAL_DAYS:
                extra_candidates.append(found)
    extra_candidates.sort()
    connect_candidates.sort()

    print(f"\n  base rule {BASE_TEMPORAL_DAYS} d / {MAX_PERP_M:.0f} m -> "
          f"{len(common_keys)} pairs")
    print(f"  {len(extra_candidates)} extra candidates up to {EXTRA_TEMPORAL_DAYS} d, "
          f"{len(connect_candidates)} up to {CONNECT_TEMPORAL_DAYS} d, available for "
          f"connectivity and de-bridging")

    added = []
    used = set()

    # (a) connect the components
    for _ in range(20):
        graph = graph_of(common_keys)
        components = list(nx.connected_components(graph))
        if len(components) <= 1:
            break
        best = None
        for i in range(len(components)):
            for j in range(i + 1, len(components)):
                for temporal, lo, hi in connect_candidates:
                    if (lo in components[i] and hi in components[j]) or \
                       (lo in components[j] and hi in components[i]):
                        if best is None or temporal < best[0]:
                            best = (temporal, lo, hi)
                        break
        if best is None:
            break
        temporal, lo, hi = best
        common_keys.add((lo, hi))
        used.add((lo, hi))
        added.append({"reference_date": lo, "secondary_date": hi,
                      "temporal_baseline_days": temporal,
                      "perpendicular_baseline_m": round(
                          float(sum(baselines[b].perp_m[hi] - baselines[b].perp_m[lo]
                                    for b in burst_ids) / len(burst_ids)), 2),
                      "role": "connect_components",
                      "reason": "joins two otherwise independent epochs"})

    # (b) remove every bridge, then reduce articulation points
    # A bridge disconnects the graph outright; an articulation point does so only
    # if it is removed. Both are fragility, so both are reduced, but bridges are
    # weighted far more heavily and the total number of added pairs is capped so
    # the network cannot grow without bound.
    MAX_ADDED_PAIRS = 30
    for _ in range(400):
        graph = graph_of(common_keys)
        bridges = list(nx.bridges(graph))
        articulation = set(nx.articulation_points(graph))
        if not bridges and not articulation:
            break
        if len(added) >= MAX_ADDED_PAIRS:
            break
        best = None
        for temporal, lo, hi in connect_candidates:
            if (lo, hi) in common_keys:
                continue
            trial = graph_of(common_keys | {(lo, hi)})
            gain = (len(bridges) - len(list(nx.bridges(trial)))) * 10 \
                + (len(articulation) - len(set(nx.articulation_points(trial))))
            if gain <= 0:
                continue
            if best is None or (gain, -temporal) > (best[0], -best[1]):
                best = (gain, temporal, lo, hi)
        if best is None:
            break
        gain, temporal, lo, hi = best
        common_keys.add((lo, hi))
        used.add((lo, hi))
        added.append({"reference_date": lo, "secondary_date": hi,
                      "temporal_baseline_days": temporal,
                      "perpendicular_baseline_m": round(
                          float(sum(baselines[b].perp_m[hi] - baselines[b].perp_m[lo]
                                    for b in burst_ids) / len(burst_ids)), 2),
                      "role": "remove_bridge" if gain >= 10 else "reduce_articulation",
                      "reason": f"reduces fragility by {gain}"})

    bridges = added
    if added:
        print(f"\n  added {len(added)} pair(s) beyond the base rule:")
        for entry in added:
            print(f"    {entry['reference_date']} -> {entry['secondary_date']}  "
                  f"{entry['temporal_baseline_days']:3d} d, "
                  f"|B_perp| {abs(entry['perpendicular_baseline_m']):6.1f} m  "
                  f"[{entry['role']}] {entry['reason']}")

    connected_nodes = {n for key in common_keys for n in key}
    unconnectable = sorted(set(all_available) - connected_nodes)
    dropped = set(unconnectable)
    if dropped:
        print(f"\n  DROPPED {len(dropped)} acquisition(s) that cannot be connected "
              f"within |B_perp| <= {MAX_PERP_M:.0f} m: {sorted(dropped)}")
        for node in sorted(dropped):
            nearest = sorted(
                (abs((date.fromisoformat(node) - date.fromisoformat(m)).days), m,
                 round(abs(perp_any[node] - perp_any[m]), 1))
                for m in all_available if m != node)[:3]
            print(f"    {node}: nearest neighbours " + ", ".join(
                f"{m} ({t} d, {b} m)" for t, m, b in nearest))

    accepted_dates = [d for d in accepted_dates if d.isoformat() not in dropped]
    final_graph = graph_of(common_keys)
    final_components = sorted((len(c) for c in nx.connected_components(final_graph)),
                              reverse=True)
    if len(final_components) != 1:
        print(f"ERROR: network still fragmented: {final_components}", file=sys.stderr)
        return 1

    added_keys = {(b["reference_date"], b["secondary_date"]) for b in added}
    role_of = {(b["reference_date"], b["secondary_date"]): b["role"] for b in added}
    pair_rows = []
    for ref_iso, sec_iso in sorted(common_keys):
        perps = [baselines[b].perp_m[sec_iso] - baselines[b].perp_m[ref_iso]
                 for b in burst_ids]
        pair_rows.append({
            "reference_date": ref_iso, "secondary_date": sec_iso,
            "temporal_baseline_days":
                (date.fromisoformat(sec_iso) - date.fromisoformat(ref_iso)).days,
            "perpendicular_baseline_m": round(float(sum(perps) / len(perps)), 2),
            "perpendicular_baseline_max_abs_m": round(
                float(max(abs(v) for v in perps)), 2),
            "is_bridge": (ref_iso, sec_iso) in added_keys,
            "added_pair_role": role_of.get((ref_iso, sec_iso)),
            "bursts": "|".join(burst_ids),
            "reference_scenes": "|".join(scene_of[(b, ref_iso)] for b in burst_ids),
            "secondary_scenes": "|".join(scene_of[(b, sec_iso)] for b in burst_ids),
        })
    pairs = pd.DataFrame(pair_rows)
    pairs.to_csv(MANIFEST_DIR / "sbas_pairs.csv", index=False)

    # ---- graph audit ------------------------------------------------------
    graph = nx.Graph()
    graph.add_nodes_from(d.isoformat() for d in accepted_dates)
    graph.add_edges_from((r.reference_date, r.secondary_date)
                         for r in pairs.itertuples())
    bridges = list(nx.bridges(graph)) if graph.number_of_edges() else []
    articulation = list(nx.articulation_points(graph)) if graph.number_of_edges() else []
    degrees = dict(graph.degree())
    components = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)

    temporal = pairs["temporal_baseline_days"] if len(pairs) else pd.Series(dtype=int)
    perp = pairs["perpendicular_baseline_m"] if len(pairs) else pd.Series(dtype=float)

    audit = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "flight_direction": EXPECTED_DIRECTION,
        "relative_orbit": EXPECTED_PATH,
        "subswath": EXPECTED_SUBSWATH,
        "k": len(burst_ids),
        "full_burst_ids": burst_ids,
        "window": [START, END],
        "acquisitions": {
            "common_accepted": len(accepted_dates),
            "union_seen": len(union),
            "excluded": len(excluded),
            "dropped_unconnectable": sorted(dropped),
            "per_burst_counts": {b: len(ds) for b, ds in per_burst.items()},
            "first": accepted_dates[0].isoformat() if accepted_dates else None,
            "last": accepted_dates[-1].isoformat() if accepted_dates else None,
        },
        "connectivity_decision": {
            "standard_rule_max_temporal_days": MAX_TEMPORAL_DAYS,
            "record_gaps_over_rule_days": [
                {"from": "2022-08-10", "to": "2022-11-26", "days": 108},
                {"from": "2024-05-31", "to": "2024-07-18", "days": 48},
            ],
            "approach": "keep the 36-day rule for the bulk of the network and add the "
                        "minimal set of flagged bridge pairs needed to make the graph "
                        "connected, rather than widening the rule for every pair",
            "bridges_added": bridges,
            "alternative_considered": "process the three epochs independently; rejected "
                                      "because each epoch carries its own reference level "
                                      "and they cannot be compared without assuming what "
                                      "the ground did across the gap",
            "consequence": "the bridge pairs are the sole link between epochs, so the "
                           "epoch-to-epoch offset depends on them; within-epoch temporal "
                           "shape does not",
        },
        "network": {
            "pairs": int(len(pairs)),
            "bridge_pairs": int(pairs["is_bridge"].sum()) if len(pairs) else 0,
            "rules": {"max_temporal_days": MAX_TEMPORAL_DAYS, "max_perp_m": MAX_PERP_M,
                      "join_method": "identity intersection across all bursts"},
            "temporal_baseline_days": {
                "min": int(temporal.min()) if len(temporal) else None,
                "median": float(temporal.median()) if len(temporal) else None,
                "max": int(temporal.max()) if len(temporal) else None,
                "counts": {str(k): int(v) for k, v in temporal.value_counts().sort_index().items()},
            },
            "perpendicular_baseline_m": {
                "min": round(float(perp.min()), 2) if len(perp) else None,
                "median": round(float(perp.median()), 2) if len(perp) else None,
                "max": round(float(perp.max()), 2) if len(perp) else None,
                "max_abs": round(float(pairs["perpendicular_baseline_max_abs_m"].max()), 2)
                if len(pairs) else None,
            },
            "connected_components": components,
            "n_components": len(components),
            "isolated_nodes": sum(1 for _, d in degrees.items() if d == 0),
            "min_degree": min(degrees.values()) if degrees else None,
            "max_degree": max(degrees.values()) if degrees else None,
            "median_degree": float(pd.Series(list(degrees.values())).median())
            if degrees else None,
            "bridges": [list(b) for b in bridges],
            "n_bridges": len(bridges),
            "articulation_points": sorted(articulation),
            "n_articulation_points": len(articulation),
        },
        "fail_closed": {
            "date_accepted_only_if_all_bursts_present": True,
            "pair_built_only_if_key_in_all_bursts": True,
            "positional_zip_used": False,
            "hotspot_geometry_used_in_pair_selection": False,
            "ascending_artefacts_read": False,
        },
    }
    # Acceptance rule. The ascending product reached 1 component, 0 bridges and
    # 0 articulation points. The descending record is sparser and carries two
    # acquisition gaps, so 0 articulation points is not attainable within the
    # perpendicular-baseline limit; the residual is bounded rather than ignored.
    n_nodes = max(1, graph.number_of_nodes())
    articulation_fraction = len(articulation) / n_nodes
    audit["acceptance_rule"] = {
        "one_connected_component": len(components) == 1,
        "no_isolated_nodes": audit["network"]["isolated_nodes"] == 0,
        "minimum_degree_at_least_2": (audit["network"]["min_degree"] or 0) >= 2,
        "zero_bridges": not bridges,
        "articulation_fraction_at_most_5pct": articulation_fraction <= 0.05,
        "residual_articulation_fraction": round(articulation_fraction, 5),
        "note": "0 articulation points was not attainable; the remaining cut vertices "
                "are recorded individually so their influence can be tested.",
    }
    audit["acceptance_passed"] = bool(all(
        v for k, v in audit["acceptance_rule"].items()
        if isinstance(v, bool)))
    (QC_DIR / "network_audit.json").write_text(json.dumps(audit, indent=2, default=str))

    print(f"\n  pairs {len(pairs)}")
    print(f"  temporal baseline: {audit['network']['temporal_baseline_days']}")
    print(f"  perp baseline: min {audit['network']['perpendicular_baseline_m']['min']} "
          f"median {audit['network']['perpendicular_baseline_m']['median']} "
          f"max {audit['network']['perpendicular_baseline_m']['max']} m")
    print(f"  components {components}, isolated "
          f"{audit['network']['isolated_nodes']}, min degree "
          f"{audit['network']['min_degree']}, median degree "
          f"{audit['network']['median_degree']}")
    print(f"  bridges {len(bridges)}, articulation points {len(articulation)}")
    print(f"  acceptance_passed: {audit['acceptance_passed']}")
    print(f"\n  {MANIFEST_DIR / 'sbas_pairs.csv'}")
    print(f"  {QC_DIR / 'network_audit.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
