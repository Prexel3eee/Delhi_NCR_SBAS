#!/usr/bin/env python
"""
Curated-network proposal and graph audit (FULL vs CURATED).

Takes the RAW-336 candidate bad pairs and asks what removing them would do to
the network's integrity. Excluding interferograms is not free: it can isolate
acquisitions, split the graph into components, and create bridges, all of which
would silently degrade the time-series inversion.

The audit is therefore run on BOTH networks with identical criteria, and the
comparison decides whether the proposed curation is acceptable as-is or needs
revision (e.g. keeping a bridging pair, or dropping an acquisition entirely).

Nothing is applied here: this produces a PROPOSAL for the owner.

Outputs
-------
qc/sci/network_comparison.json
qc/sci/curated_network_pairs.csv
qc/sci/network_degree_comparison.csv
qc/sci/network_comparison.png

Usage
-----
    python scripts/19_network_curation.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "qc" / "sci"
PAIRS_CSV = PROJECT_ROOT / "manifests" / "sbas_pairs.csv"
ACC_CSV = PROJECT_ROOT / "manifests" / "accepted_acquisitions.csv"
CANDIDATES_CSV = OUT_DIR / "bad_pair_candidates.csv"

MIN_DEGREE_TARGET = 3


def audit(pairs: pd.DataFrame, nodes: list[str]) -> tuple[dict, nx.Graph]:
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(zip(pairs["reference_date"], pairs["secondary_date"]))

    degrees = dict(graph.degree())
    values = list(degrees.values()) or [0]
    components = list(nx.connected_components(graph))
    bridges = list(nx.bridges(graph)) if graph.number_of_edges() else []
    articulation = list(nx.articulation_points(graph)) if graph.number_of_nodes() else []

    dates = sorted(pd.to_datetime(nodes))
    gaps = pd.Series(dates).diff().dt.days.dropna().astype(int)

    summary = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "components": len(components),
        "component_sizes": sorted((len(c) for c in components), reverse=True),
        "isolated_nodes": sorted(nx.isolates(graph)),
        "bridges": len(bridges),
        "articulation_points": len(articulation),
        "degree_min": int(min(values)),
        "degree_mean": round(float(pd.Series(values).mean()), 4),
        "degree_median": float(pd.Series(values).median()),
        "degree_max": int(max(values)),
        "degree_distribution": {int(k): int(v) for k, v in
                                pd.Series(values).value_counts().sort_index().items()},
        "acquisition_gaps": {int(k): int(v) for k, v in gaps.value_counts().sort_index().items()},
        "max_gap_days": int(gaps.max()) if len(gaps) else 0,
    }
    criteria = {
        "single_component": summary["components"] == 1,
        "no_isolated_nodes": len(summary["isolated_nodes"]) == 0,
        "no_bridges": summary["bridges"] == 0,
        "no_articulation_points": summary["articulation_points"] == 0,
        "min_degree_at_least_3": summary["degree_min"] >= MIN_DEGREE_TARGET,
    }
    summary["criteria"] = criteria
    summary["accepted"] = all(criteria.values())
    return summary, graph


def main() -> int:
    full = pd.read_csv(PAIRS_CSV)
    acc = pd.read_csv(ACC_CSV)
    nodes = sorted(acc["date"])
    candidates = pd.read_csv(CANDIDATES_CSV) if CANDIDATES_CSV.exists() else pd.DataFrame()

    print("=" * 88)
    print("NETWORK CURATION PROPOSAL AND GRAPH AUDIT")
    print("=" * 88)

    full_summary, full_graph = audit(full, nodes)

    excluded_ids = set(candidates["date12"]) if not candidates.empty else set()
    curated = full[~full["pair_id"].isin(excluded_ids)].copy() if excluded_ids else full.copy()

    print(f"\n  FULL    : {full_summary['nodes']} nodes / {full_summary['edges']} pairs")
    print(f"  CURATED : {curated['reference_date'].nunique() and len(nodes)} nodes / {len(curated)} pairs "
          f"({len(excluded_ids)} candidate pairs removed)")

    curated_summary, curated_graph = audit(curated, nodes)

    rows = []
    for network, summary in (("full_336", full_summary), ("curated", curated_summary)):
        rows.append({
            "network": network,
            "pairs": summary["edges"],
            "components": summary["components"],
            "isolated_nodes": len(summary["isolated_nodes"]),
            "bridges": summary["bridges"],
            "articulation_points": summary["articulation_points"],
            "degree_min": summary["degree_min"],
            "degree_mean": summary["degree_mean"],
            "degree_median": summary["degree_median"],
            "degree_max": summary["degree_max"],
            "max_gap_days": summary["max_gap_days"],
            "accepted": summary["accepted"],
        })
    comparison = pd.DataFrame(rows)
    comparison.to_csv(OUT_DIR / "network_degree_comparison.csv", index=False)

    curated.to_csv(OUT_DIR / "curated_network_pairs.csv", index=False)

    print("\n  " + "-" * 84)
    print(comparison.to_string(index=False))

    # ---- what breaks, if anything ----------------------------------------
    newly_isolated = sorted(set(curated_summary["isolated_nodes"])
                            - set(full_summary["isolated_nodes"]))
    degree_loss = {
        node: full_graph.degree(node) - curated_graph.degree(node)
        for node in nodes
        if full_graph.degree(node) != curated_graph.degree(node)
    }
    worst = sorted(degree_loss.items(), key=lambda kv: -kv[1])[:10]

    print(f"\n  components        : {full_summary['components']} -> {curated_summary['components']}")
    print(f"  isolated nodes    : {len(full_summary['isolated_nodes'])} -> "
          f"{len(curated_summary['isolated_nodes'])}")
    print(f"  bridges           : {full_summary['bridges']} -> {curated_summary['bridges']}")
    print(f"  articulation pts  : {full_summary['articulation_points']} -> "
          f"{curated_summary['articulation_points']}")
    print(f"  min degree        : {full_summary['degree_min']} -> {curated_summary['degree_min']}")
    if newly_isolated:
        print(f"  NEWLY ISOLATED    : {newly_isolated}")
    if worst:
        print("  largest degree losses:")
        for node, loss in worst:
            print(f"    {node}: {full_graph.degree(node)} -> {curated_graph.degree(node)} (-{loss})")

    # ---- alternative: keep bridge pairs ----------------------------------
    # ---- greedy repair ----------------------------------------------------
    # A component-count check alone is not enough: the first proposal stayed
    # connected yet introduced a bridge, two articulation points and a node of
    # degree 1. Repair therefore targets the FULL criteria set, restoring the
    # fewest excluded pairs that make the network acceptable again.
    def score(summary: dict) -> tuple:
        return (
            summary["components"] - 1,
            len(summary["isolated_nodes"]),
            summary["bridges"],
            summary["articulation_points"],
            max(0, MIN_DEGREE_TARGET - summary["degree_min"]),
        )

    rejected = full[full["pair_id"].isin(excluded_ids)]
    restored: list[str] = []
    current = curated.copy()
    current_summary = curated_summary
    while not current_summary["accepted"] and len(rejected):
        best_pair, best_summary, best_score = None, None, score(current_summary)
        for pair_id in rejected["pair_id"]:
            candidate = pd.concat(
                [current, rejected[rejected["pair_id"] == pair_id]]
            ).drop_duplicates("pair_id")
            summary, _ = audit(candidate, nodes)
            s = score(summary)
            if s < best_score:
                best_score, best_pair, best_summary = s, pair_id, summary
        if best_pair is None:
            break
        current = pd.concat([current, rejected[rejected["pair_id"] == best_pair]]
                            ).drop_duplicates("pair_id")
        current_summary = best_summary
        restored.append(best_pair)
        rejected = rejected[rejected["pair_id"] != best_pair]

    alt_summary = current_summary if restored else None
    if restored:
        print(f"\n  REVISED proposal: restore {len(restored)} bridging pair(s) "
              f"-> {len(current)} pairs, accepted={current_summary['accepted']}")
        print(f"    restored: {restored}")
        current.to_csv(OUT_DIR / "curated_network_pairs_repaired.csv", index=False)

    # ---- plot ------------------------------------------------------------
    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, (name, summary, graph) in zip(
        axes,
        (("FULL 336 pairs", full_summary, full_graph),
         (f"CURATED {len(curated)} pairs", curated_summary, curated_graph)),
    ):
        degrees = [d for _, d in graph.degree()]
        ax.hist(degrees, bins=range(0, max(degrees) + 2), color="tab:blue",
                edgecolor="black", align="left")
        ax.set_title(f"{name}\ncomponents={summary['components']} bridges={summary['bridges']} "
                     f"min degree={summary['degree_min']}", fontsize=9)
        ax.set_xlabel("node degree")
        ax.set_ylabel("acquisitions")
        ax.grid(alpha=0.3)
    figure.suptitle("Network integrity: full vs curated", fontsize=11)
    figure.tight_layout()
    figure.savefig(OUT_DIR / "network_comparison.png", dpi=150)
    plt.close(figure)

    # ---- alternative strategy: prune under-supported acquisitions --------
    # Keeping a known-bad interferogram to preserve a node is the wrong trade.
    # Where an acquisition is supported almost only by bad pairs, dropping the
    # ACQUISITION is cleaner. Iterate until every remaining node meets the
    # degree target.
    prune_nodes = list(nodes)
    prune_pairs = curated.copy()
    pruned_dates: list[str] = []
    while True:
        s, g = audit(prune_pairs, prune_nodes)
        low = sorted(n for n, d in g.degree() if d < MIN_DEGREE_TARGET)
        if not low:
            break
        pruned_dates.extend(low)
        prune_nodes = [n for n in prune_nodes if n not in low]
        prune_pairs = prune_pairs[
            prune_pairs["reference_date"].isin(prune_nodes)
            & prune_pairs["secondary_date"].isin(prune_nodes)
        ]
    prune_summary, _ = audit(prune_pairs, prune_nodes)
    if pruned_dates:
        prune_pairs.to_csv(OUT_DIR / "curated_network_pruned.csv", index=False)
        print(f"\n  ALTERNATIVE proposal: prune {len(pruned_dates)} under-supported "
              f"acquisition(s) -> {len(prune_pairs)} pairs / {len(prune_nodes)} dates, "
              f"accepted={prune_summary['accepted']}")
        print(f"    pruned dates: {pruned_dates}")

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PROPOSAL ONLY - nothing applied to the frozen input",
        "alternative_strategy_acquisition_pruning": {
            "pruned_acquisitions": pruned_dates,
            "n_pruned": len(pruned_dates),
            "pairs": int(len(prune_pairs)),
            "dates": len(prune_nodes),
            "accepted": bool(prune_summary["accepted"]),
            "summary": prune_summary,
            "rationale": "retaining a known-bad interferogram merely to keep a node in the "
                         "graph is the wrong trade; dropping the under-supported acquisition "
                         "is cleaner and leaves only QC-acceptable pairs",
        },
        "full": full_summary,
        "curated": curated_summary,
        "removed_pairs": len(excluded_ids),
        "removed_pair_ids": sorted(excluded_ids),
        "newly_isolated_acquisitions": newly_isolated,
        "largest_degree_losses": [{"date": n, "full_degree": full_graph.degree(n),
                                   "curated_degree": curated_graph.degree(n)}
                                  for n, _ in worst],
        "revised_proposal_to_restore_bridges": {
            "restored_pairs": restored,
            "n_restored": len(restored),
            "resulting_pairs": int(len(current)),
            "resulting_summary": alt_summary,
        },
        "repair_targets": (
            "minimise (components-1, isolated nodes, bridges, articulation points, "
            f"max(0, {MIN_DEGREE_TARGET} - min degree)) by restoring the fewest excluded pairs"
        ),
        "decision": (
            "curated network retains the required graph properties"
            if curated_summary["accepted"] else
            "curated network FAILS one or more graph criteria - revision required"
        ),
        "final_proposal": {
            "pairs": int(len(current)),
            "pairs_removed": int(len(excluded_ids) - len(restored)),
            "accepted": bool(current_summary["accepted"]),
            "summary": current_summary,
        },
    }
    (OUT_DIR / "network_comparison.json").write_text(json.dumps(report, indent=2, default=str))

    print(f"\n  decision: {report['decision']}")
    print(f"\n  {OUT_DIR / 'network_comparison.json'}")
    print(f"  {OUT_DIR / 'curated_network_pairs.csv'}")
    print(f"  {OUT_DIR / 'network_comparison.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
