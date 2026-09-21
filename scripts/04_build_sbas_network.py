#!/usr/bin/env python
"""
Phase D - burst-level SBAS pair network, joined by identity, plus audit.

Starting thresholds (brief section 11, empirically supported by the earlier
full-scene reconnaissance):

    max temporal baseline      : 36 days
    max |perpendicular| baseline: 250 m

Identity, not list position
---------------------------
Candidate pairs are built per geographic burst as
``pair_map[burst_id][(ref_date, sec_date)] = (ref_scene, sec_scene)``. The
accepted pair set is the **intersection** of the per-burst key sets, so a pair is
only emitted when *every* selected burst can supply both sides. This replaces
the tutorial's positional ``zip(*pairs)``, which silently truncates or
misaligns when bursts have unequal pair lists.

Baseline handling (brief section 42.2)
-------------------------------------
Perpendicular baselines are computed per burst against one fixed reference
acquisition. A pair's value per burst is ``perp[secondary] - perp[reference]``.
Gating uses the **maximum absolute value across the selected bursts**, and the
per-burst min / median / max-abs values are retained in the manifest.

Outputs
-------
manifests/sbas_pairs.csv
qc/network/network_summary.json
qc/network/network_edges.csv
qc/network/network_degree.csv
qc/network/baseline_time_plot.png
qc/network/degree_histogram.png
qc/network/baseline_table.csv

Usage
-----
    python scripts/04_build_sbas_network.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timezone
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asf_client as ac  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
QC_DIR = PROJECT_ROOT / "qc" / "network"

START = "2021-10-01T00:00:00Z"
END = "2025-10-01T00:00:00Z"

DEFAULT_MAX_TEMPORAL_DAYS = 36
DEFAULT_MAX_PERP_M = 250.0

MAX_WORKERS = 4


@dataclass(frozen=True)
class MultiBurstPair:
    """One HyP3 multi-burst interferogram job payload."""

    pair_id: str
    reference_date: str
    secondary_date: str
    temporal_baseline_days: int
    perpendicular_baseline_max_abs_m: float
    perpendicular_baseline_min_m: float
    perpendicular_baseline_median_m: float
    burst_count: int
    reference_burst_ids: tuple[str, ...]
    secondary_burst_ids: tuple[str, ...]
    reference_scene_names: tuple[str, ...]
    secondary_scene_names: tuple[str, ...]


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def load_accepted() -> pd.DataFrame:
    path = MANIFEST_DIR / "accepted_acquisitions.csv"
    if not path.exists():
        raise SystemExit(f"FAIL: {path} not found. Run scripts/03_inventory_bursts.py first.")
    frame = pd.read_csv(path)
    if frame.empty:
        raise SystemExit("FAIL: accepted acquisition list is empty.")
    if frame["date"].duplicated().any():
        raise SystemExit("FAIL: duplicate dates in accepted acquisitions.")
    return frame.sort_values("date").reset_index(drop=True)


def load_inventory() -> pd.DataFrame:
    path = MANIFEST_DIR / "burst_inventory_2021_2025.csv"
    if not path.exists():
        raise SystemExit(f"FAIL: {path} not found.")
    return pd.read_csv(path)


def compute_baselines(burst_id: str, reference_scene: str, required_dates: list[date]):
    return ac.burst_baseline_stack(
        full_burst_id=burst_id,
        reference_scene=reference_scene,
        start=START,
        end=END,
        required_dates=required_dates,
        window_days=180,
        tries=3,
    )


# ---------------------------------------------------------------------------
# Network construction
# ---------------------------------------------------------------------------


def build_pairs(
    accepted: pd.DataFrame,
    inventory: pd.DataFrame,
    burst_order: list[str],
    baseline_tables: dict[str, ac.BaselineStack],
    max_temporal_days: int,
    max_perp_m: float,
) -> tuple[list[MultiBurstPair], dict]:
    """Identity-joined multi-burst pair construction."""

    # scene lookup: (burst_id, date) -> scene_name
    scene_of: dict[tuple[str, str], str] = {
        (row.full_burst_id, row.date): row.scene_name for row in inventory.itertuples()
    }

    accepted_dates = [datetime.fromisoformat(d).date() for d in accepted["date"]]
    date_index = {d.isoformat(): d for d in accepted_dates}

    # ---- 1. candidate pairs per burst, keyed canonically -------------------
    pair_map: dict[str, dict[tuple[str, str], tuple[str, str]]] = {b: {} for b in burst_order}
    per_burst_candidates: dict[str, int] = {}

    for burst_id in burst_order:
        table = baseline_tables[burst_id]
        perp = table.perp_m
        available = [d.isoformat() for d in accepted_dates if d.isoformat() in perp]
        candidates: dict[tuple[str, str], tuple[str, str]] = {}

        for ref_iso, sec_iso in combinations(available, 2):
            ref_d = date_index[ref_iso]
            sec_d = date_index[sec_iso]
            temporal = (sec_d - ref_d).days
            if temporal > max_temporal_days:
                continue
            bperp = abs(perp[sec_iso] - perp[ref_iso])
            if bperp > max_perp_m:
                continue
            ref_scene = scene_of.get((burst_id, ref_iso))
            sec_scene = scene_of.get((burst_id, sec_iso))
            if not ref_scene or not sec_scene:
                continue
            candidates[(ref_iso, sec_iso)] = (ref_scene, sec_scene)

        pair_map[burst_id] = candidates
        per_burst_candidates[burst_id] = len(candidates)

    # ---- 2. common pair keys (identity intersection) ----------------------
    key_sets = [set(pair_map[b]) for b in burst_order]
    common_keys = set.intersection(*key_sets) if key_sets else set()

    diagnostics = {
        "per_burst_candidate_pairs": per_burst_candidates,
        "common_pair_keys": len(common_keys),
        "union_pair_keys": len(set.union(*key_sets)) if key_sets else 0,
        "pair_keys_dropped_for_missing_burst": len(set.union(*key_sets)) - len(common_keys)
        if key_sets
        else 0,
    }

    # ---- 3. build and validate one payload per accepted pair key ----------
    pairs: list[MultiBurstPair] = []
    rejected: list[dict] = []

    for ref_iso, sec_iso in sorted(common_keys):
        ref_d = date_index[ref_iso]
        sec_d = date_index[sec_iso]
        temporal = (sec_d - ref_d).days

        reference_bursts: list[str] = []
        secondary_bursts: list[str] = []
        reference_scenes: list[str] = []
        secondary_scenes: list[str] = []
        bperps: list[float] = []
        problems: list[str] = []

        for burst_id in burst_order:
            ref_scene, sec_scene = pair_map[burst_id][(ref_iso, sec_iso)]
            reference_bursts.append(burst_id)
            secondary_bursts.append(burst_id)
            reference_scenes.append(ref_scene)
            secondary_scenes.append(sec_scene)
            perp = baseline_tables[burst_id].perp_m
            bperps.append(float(perp[sec_iso]) - float(perp[ref_iso]))

        # validate the emitted payload against the hard rules
        if len(reference_bursts) != len(secondary_bursts):
            problems.append("reference/secondary burst count mismatch")
        if len(reference_bursts) != len(burst_order):
            problems.append("burst count != frozen K")
        if not 1 <= len(reference_bursts) <= 15:
            problems.append("burst count outside 1-15")
        if ref_d >= sec_d:
            problems.append("reference not earlier than secondary")
        if temporal > max_temporal_days:
            problems.append(f"temporal baseline {temporal} > {max_temporal_days}")
        max_abs = max(abs(v) for v in bperps) if bperps else 0.0
        if max_abs > max_perp_m:
            problems.append(f"|B_perp| {max_abs:.1f} > {max_perp_m}")
        if reference_bursts != secondary_bursts:
            problems.append("burst identities differ between reference and secondary")
        if not all(
            reference_scenes[i].split("_")[2] == secondary_scenes[i].split("_")[2]
            for i in range(len(reference_bursts))
        ):
            problems.append("burst scene sub-swath mismatch")

        if problems:
            rejected.append(
                {
                    "reference_date": ref_iso,
                    "secondary_date": sec_iso,
                    "problems": problems,
                    "burst_count": len(reference_bursts),
                    "temporal_baseline_days": temporal,
                    "perpendicular_baseline_max_abs_m": max_abs,
                }
            )
            continue

        pairs.append(
            MultiBurstPair(
                pair_id=f"{ref_iso.replace('-', '')}_{sec_iso.replace('-', '')}",
                reference_date=ref_iso,
                secondary_date=sec_iso,
                temporal_baseline_days=temporal,
                perpendicular_baseline_max_abs_m=round(max_abs, 1),
                perpendicular_baseline_min_m=round(min(bperps), 1),
                perpendicular_baseline_median_m=round(float(pd.Series(bperps).median()), 1),
                burst_count=len(reference_bursts),
                reference_burst_ids=tuple(reference_bursts),
                secondary_burst_ids=tuple(secondary_bursts),
                reference_scene_names=tuple(reference_scenes),
                secondary_scene_names=tuple(secondary_scenes),
            )
        )

    diagnostics["pairs_emitted"] = len(pairs)
    diagnostics["pairs_rejected_at_validation"] = len(rejected)
    diagnostics["rejections"] = rejected[:50]
    return pairs, diagnostics


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def audit_network(pairs: list[MultiBurstPair], accepted: pd.DataFrame) -> tuple[dict, nx.Graph]:
    graph = nx.Graph()
    graph.add_nodes_from(accepted["date"])
    for pair in pairs:
        graph.add_edge(pair.reference_date, pair.secondary_date)

    degrees = dict(graph.degree())
    degree_values = list(degrees.values())
    components = list(nx.connected_components(graph))
    bridges = list(nx.bridges(graph)) if graph.number_of_edges() else []
    articulation = list(nx.articulation_points(graph)) if graph.number_of_nodes() else []

    dates = sorted(pd.to_datetime(accepted["date"]))
    gaps = pd.Series(dates).diff().dt.days.dropna().astype(int)
    gap_distribution = {int(k): int(v) for k, v in gaps.value_counts().sort_index().items()}

    temporal = pd.Series([p.temporal_baseline_days for p in pairs])
    bperp = pd.Series([p.perpendicular_baseline_max_abs_m for p in pairs])

    summary = {
        "nodes_acquisitions": graph.number_of_nodes(),
        "edges_pairs": graph.number_of_edges(),
        "connected_components": len(components),
        "isolated_nodes": sorted(nx.isolates(graph)),
        "bridges": len(bridges),
        "bridge_edges": sorted([tuple(sorted(e)) for e in bridges])[:20],
        "articulation_points": len(articulation),
        "articulation_point_dates": sorted(articulation)[:20],
        "degree": {
            "min": int(min(degree_values)) if degree_values else 0,
            "mean": round(float(pd.Series(degree_values).mean()), 4) if degree_values else 0.0,
            "median": float(pd.Series(degree_values).median()) if degree_values else 0.0,
            "max": int(max(degree_values)) if degree_values else 0,
            "distribution": {int(k): int(v) for k, v in pd.Series(degree_values).value_counts().sort_index().items()},
        },
        "acquisition_gaps": {
            "distribution": gap_distribution,
            "max_days": int(gaps.max()) if len(gaps) else 0,
            "min_days": int(gaps.min()) if len(gaps) else 0,
        },
        "pair_temporal_baseline_days": {
            "distribution": {int(k): int(v) for k, v in temporal.value_counts().sort_index().items()},
            "min": int(temporal.min()) if len(temporal) else 0,
            "max": int(temporal.max()) if len(temporal) else 0,
        },
        "pair_perpendicular_baseline_m": {
            "min": round(float(bperp.min()), 1) if len(bperp) else 0.0,
            "median": round(float(bperp.median()), 1) if len(bperp) else 0.0,
            "p95": round(float(bperp.quantile(0.95)), 1) if len(bperp) else 0.0,
            "max": round(float(bperp.max()), 1) if len(bperp) else 0.0,
        },
    }

    # preferred acceptance criteria (brief section 12)
    criteria = {
        "connected_components_equals_1": len(components) == 1,
        "no_isolated_nodes": len(list(nx.isolates(graph))) == 0,
        "no_bridges": len(bridges) == 0,
        "no_articulation_points": len(articulation) == 0,
        "min_degree_at_least_3": (min(degree_values) >= 3) if degree_values else False,
        "explained_max_gap": summary["acquisition_gaps"]["max_days"] <= 48,
    }
    summary["acceptance_criteria"] = criteria
    summary["acceptance_passed"] = all(criteria.values())
    return summary, graph


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


def plot_baseline_time(pairs: list[MultiBurstPair], graph: nx.Graph, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(13, 7))
    nodes = sorted(graph.nodes)
    position = {node: i for i, node in enumerate(nodes)}

    for pair in pairs:
        x = [position[pair.reference_date], position[pair.secondary_date]]
        y = [0, pair.perpendicular_baseline_max_abs_m]
        axis.plot(x, y, color="tab:blue", alpha=0.30, linewidth=0.7)

    axis.scatter(range(len(nodes)), [0] * len(nodes), color="black", s=12, zorder=3)
    axis.set_xlabel("Acquisition index (chronological)")
    axis.set_ylabel("|Perpendicular baseline| (m)")
    axis.set_title(
        f"Burst-level SBAS network - {len(pairs)} pairs / {len(nodes)} acquisitions\n"
        f"max temporal 36 d, max |B_perp| 250 m (plotted as baseline magnitude)"
    )
    axis.grid(alpha=0.3)
    tick_step = max(1, len(nodes) // 12)
    axis.set_xticks(range(0, len(nodes), tick_step))
    axis.set_xticklabels(
        [nodes[i] for i in range(0, len(nodes), tick_step)], rotation=45, ha="right", fontsize=8
    )
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def plot_degree_histogram(graph: nx.Graph, path: Path) -> None:
    degrees = [d for _, d in graph.degree()]
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.hist(degrees, bins=range(min(degrees), max(degrees) + 2), color="tab:green",
              edgecolor="black", align="left")
    axis.set_xlabel("Node degree (number of connected interferometric pairs)")
    axis.set_ylabel("Number of acquisitions")
    axis.set_title(f"SBAS network degree distribution ({len(degrees)} acquisitions)")
    axis.grid(alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-temporal-days", type=int, default=DEFAULT_MAX_TEMPORAL_DAYS)
    parser.add_argument("--max-perp-m", type=float, default=DEFAULT_MAX_PERP_M)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    QC_DIR.mkdir(parents=True, exist_ok=True)

    accepted = load_accepted()
    inventory = load_inventory()

    frozen_path = MANIFEST_DIR / "geographic_reference_bursts.csv"
    if not frozen_path.exists():
        raise SystemExit(f"FAIL: {frozen_path} not found.")
    frozen = pd.read_csv(frozen_path)
    burst_order = sorted(frozen["full_burst_id"].tolist(), key=lambda b: int(b.split("_")[1]))

    print("=" * 88)
    print("PHASE D - BURST-LEVEL SBAS NETWORK (IDENTITY-JOINED)")
    print("=" * 88)
    print(f"\nAccepted acquisitions : {len(accepted)}")
    print(f"K (bursts per job)    : {len(burst_order)}")
    print(f"  {burst_order}")
    print(f"Max temporal baseline : {args.max_temporal_days} days")
    print(f"Max |B_perp|          : {args.max_perp_m} m")

    # ---- baselines per burst, fixed reference = first accepted date --------
    accepted_dates = [datetime.fromisoformat(d).date() for d in accepted["date"]]
    reference_date = accepted["date"].iloc[0]
    reference_scenes = {
        b: json.loads(accepted["burst_scene_names_json"].iloc[0])[b] for b in burst_order
    }

    print(f"\nComputing per-burst baselines against fixed reference {reference_date}")
    for b in burst_order:
        print(f"  {b} -> {reference_scenes[b]}")

    def job(burst_id: str):
        return burst_id, compute_baselines(burst_id, reference_scenes[burst_id], accepted_dates)

    baseline_tables: dict[str, ac.BaselineStack] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for burst_id, table in pool.map(job, burst_order):
            baseline_tables[burst_id] = table
            print(
                f"  {burst_id}: {len(table.perp_m)} baseline rows "
                f"({len(table.windows)} windows, {len(table.notes)} notes, "
                f"extra dates {table.extra_dates}, rejected {len(table.rejected)})"
            )
            for rejection in table.rejected[:5]:
                print(f"      REJECTED {rejection}")

    # ---- baseline table (audit artefact) ----------------------------------
    baseline_rows = []
    for date_iso in accepted["date"]:
        row = {"date": date_iso}
        for b in burst_order:
            table = baseline_tables[b]
            row[f"{b}__temporal_days"] = table.temporal_days.get(date_iso)
            row[f"{b}__perp_m"] = table.perp_m.get(date_iso)
        baseline_rows.append(row)
    baseline_table = pd.DataFrame(baseline_rows)
    baseline_table.to_csv(QC_DIR / "baseline_table.csv", index=False)

    # ---- build network ----------------------------------------------------
    pairs, diagnostics = build_pairs(
        accepted, inventory, burst_order, baseline_tables, args.max_temporal_days, args.max_perp_m
    )

    print("\n" + "-" * 88)
    print("PAIR CONSTRUCTION (joined by burst/acquisition identity)")
    print("-" * 88)
    print("  Candidate pairs per burst (single-burst temporal+|B_perp| gate):")
    for b, count in diagnostics["per_burst_candidate_pairs"].items():
        print(f"    {b}: {count}")
    print(f"  Union of pair keys                        : {diagnostics['union_pair_keys']}")
    print(f"  Intersection (valid for ALL bursts)       : {diagnostics['common_pair_keys']}")
    print(f"  Dropped: key present in some bursts only  : {diagnostics['pair_keys_dropped_for_missing_burst']}")
    print(f"  Pairs emitted                             : {diagnostics['pairs_emitted']}")
    print(f"  Rejected at payload validation            : {diagnostics['pairs_rejected_at_validation']}")

    if not pairs:
        raise SystemExit("FAIL: no valid multi-burst pairs were constructed.")

    # ---- persist pairs ----------------------------------------------------
    pair_rows = []
    for pair in pairs:
        pair_rows.append(
            {
                "pair_id": pair.pair_id,
                "reference_date": pair.reference_date,
                "secondary_date": pair.secondary_date,
                "temporal_baseline_days": pair.temporal_baseline_days,
                "perpendicular_baseline_m": pair.perpendicular_baseline_max_abs_m,
                "perpendicular_baseline_max_abs_m": pair.perpendicular_baseline_max_abs_m,
                "perpendicular_baseline_min_m": pair.perpendicular_baseline_min_m,
                "perpendicular_baseline_median_m": pair.perpendicular_baseline_median_m,
                "burst_count": pair.burst_count,
                "reference_burst_ids_json": json.dumps(list(pair.reference_burst_ids)),
                "secondary_burst_ids_json": json.dumps(list(pair.secondary_burst_ids)),
                "reference_scene_names_json": json.dumps(list(pair.reference_scene_names)),
                "secondary_scene_names_json": json.dumps(list(pair.secondary_scene_names)),
            }
        )
    pairs_df = pd.DataFrame(pair_rows).sort_values(["reference_date", "secondary_date"])
    pairs_path = MANIFEST_DIR / "sbas_pairs.csv"
    pairs_df.to_csv(pairs_path, index=False)

    # ---- audit ------------------------------------------------------------
    summary, graph = audit_network(pairs, accepted)
    summary["phase"] = "D"
    summary["generated_utc"] = datetime.now(timezone.utc).isoformat()
    summary["thresholds"] = {
        "max_temporal_baseline_days": args.max_temporal_days,
        "max_perpendicular_baseline_m": args.max_perp_m,
    }
    summary["burst_order"] = burst_order
    summary["baseline_reference"] = {
        "date": reference_date,
        "per_burst_reference_scene": reference_scenes,
        "convention": "pair |B_perp| = max over bursts of |perp[secondary] - perp[reference]|, "
        "baselines measured against one fixed reference acquisition",
        "re_basing_guard": "The fixed reference product is injected into every baseline window "
        "because asf_search.baseline.stack.check_reference silently substitutes stack[0] when the "
        "reference granule is absent, which would offset every pair spanning two windows. "
        "temporalBaseline is additionally validated against the true day offset from the reference.",
        "per_burst_recovered_rows": {b: len(baseline_tables[b].perp_m) for b in burst_order},
        "per_burst_rejected": {b: len(baseline_tables[b].rejected) for b in burst_order},
    }
    summary["pair_construction_diagnostics"] = {
        k: v for k, v in diagnostics.items() if k != "rejections"
    }

    edges_path = QC_DIR / "network_edges.csv"
    degree_path = QC_DIR / "network_degree.csv"
    summary_path = QC_DIR / "network_summary.json"

    pd.DataFrame(
        [
            {
                "reference_date": p.reference_date,
                "secondary_date": p.secondary_date,
                "temporal_baseline_days": p.temporal_baseline_days,
                "perpendicular_baseline_max_abs_m": p.perpendicular_baseline_max_abs_m,
            }
            for p in pairs
        ]
    ).to_csv(edges_path, index=False)

    pd.DataFrame(
        sorted(graph.degree(), key=lambda x: (-x[1], x[0])), columns=["date", "degree"]
    ).to_csv(degree_path, index=False)

    plot_baseline_time(pairs, graph, QC_DIR / "baseline_time_plot.png")
    plot_degree_histogram(graph, QC_DIR / "degree_histogram.png")

    summary_path.write_text(json.dumps(summary, indent=2))

    # ---- report -----------------------------------------------------------
    print("\n" + "=" * 88)
    print("NETWORK AUDIT")
    print("=" * 88)
    print(f"\nAcquisition nodes      : {summary['nodes_acquisitions']}")
    print(f"Pair edges             : {summary['edges_pairs']}")
    print(f"Connected components   : {summary['connected_components']}")
    print(f"Isolated nodes         : {len(summary['isolated_nodes'])}")
    print(f"Bridges                : {summary['bridges']}")
    print(f"Articulation points    : {summary['articulation_points']}")
    deg = summary["degree"]
    print(f"Degree min/mean/median/max : {deg['min']} / {deg['mean']} / {deg['median']} / {deg['max']}")
    print(f"Degree distribution    : {deg['distribution']}")
    print(f"\nAcquisition gaps       : {summary['acquisition_gaps']['distribution']} (max {summary['acquisition_gaps']['max_days']} d)")
    print(f"Pair temporal baseline : {summary['pair_temporal_baseline_days']['distribution']}")
    pb = summary["pair_perpendicular_baseline_m"]
    print(f"Pair |B_perp| (m)      : min {pb['min']} / median {pb['median']} / p95 {pb['p95']} / max {pb['max']}")

    print("\nAcceptance criteria (brief section 12):")
    for name, passed in summary["acceptance_criteria"].items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

    print("\n" + "=" * 88)
    print(f"FINAL BURST-LEVEL PAIR COUNT: {len(pairs)}")
    print("=" * 88)
    for path in (
        pairs_path,
        summary_path,
        edges_path,
        degree_path,
        QC_DIR / "baseline_time_plot.png",
        QC_DIR / "degree_histogram.png",
        QC_DIR / "baseline_table.csv",
    ):
        print(f"  {path}")

    if not summary["acceptance_passed"]:
        print("\nNOTE: preferred network criteria not all met; inspect before production.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
