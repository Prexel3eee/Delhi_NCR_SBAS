# Definitive figure set

Main figures carry only what the paper argues. Engineering and diagnostic figures are moved to the supplement.

| # | Figure | Source | Status |
|---|---|---|---|
| F1 | Study design: AOI, ascending and descending tracks, burst coverage | `qc/sci/phase4/figures/F01_study_design.png` | READY |
| F2 | Ascending authoritative relative LOS velocity field | `qc/sci/phase4/figures/F02_ascending_velocity.png` | READY |
| F3 | Hotspot cross-geometry classification | `qc/sci/phase4/figures/F03_hotspot_classification.png` | READY |
| F4 | Cross-track agreement, D0 vs D2, and hotspot selectivity | `qc/sci/phase4/figures/F04_cross_geometry_agreement.png` | READY |
| F5 | H001 and H004 independent support | `qc/sci/phase4/figures/F05_supported_features.png` | READY |
| F6 | H002/H003 negative-control result (matched comparison) | `qc/sci/phase4/figures/F06_negative_controls.png` | READY |
| F7 | H005 cross-geometry contradiction | `qc/sci/phase4/figures/F07_H005_contradiction.png` | READY |
| F8 | Rate-versus-history caveat | `qc/sci/phase4/figures/F08_rate_vs_history.png` | READY |
| F9 | Groundwater falsification result | `qc/sci/phase3/figures/GW06_lag_curves.png` | READY |
| F10 | Soil-texture comparison | `qc/sci/phase3/figures/GB01_substrate.png` | READY |
| F11 | Urban built-intensity comparison | `qc/sci/phase3/figures/UC01_built_intensity.png` | READY |
| F12 | Competing-hypothesis evidence matrix | `qc/sci/phase4/figures/F12_evidence_matrix.png` | READY |

**Supplementary / archive:** station maps and completeness plots (GW01, GW02), series plots (GW03–GW05, GW07, GW08, GW09, GW10), substrate specificity and coherence confounding (GB02, GB03), urban coherence confounding (UC02), network audits, threshold-sensitivity grids, and all engineering diagnostics.

No figure carries a causal arrow.

## Figure provenance

Every panel is rendered from the frozen evidence set; no quantity is recomputed and no dataset is added. Per-pixel paired ascending/descending values were not retained in the freeze, so F4 reports the retained aggregate agreement metrics rather than a scatter — reconstructing a distribution from reported moments would misrepresent the data. For the same reason F8 shows retained cumulative totals rather than reconstructed time-series curves.

F6 deliberately excludes H001: at −30.9 / −36.0 mm/yr it would dominate the y-range and crush the H004-versus-controls contrast that carries the selectivity argument. H001 is shown in F5.
