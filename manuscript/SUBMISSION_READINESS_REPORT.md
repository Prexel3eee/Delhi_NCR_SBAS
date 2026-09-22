# Submission Readiness Report

Generated 2026-09-22T19:08:11.078858+00:00

## Verdict: READY FOR JOURNAL SELECTION

All scientific and provenance gates PASS.

| Gate | Status | Basis |
|---|---|---|
| Scientific freeze integrity | **PASS** | all frozen artefacts verify; 0 drift across 12 upstream freezes; no frozen result regenerated from unfrozen inputs |
| Numerical consistency | **PASS** | 27 checks against frozen sources, 0 hold. INC-009 corrected (3.17 -> 6.66 km2) |
| Terminology consistency | **PASS** | 14 pattern matches reviewed manually; all are correct usages, including explicit negations and the passages that define the protected distinctions |
| Claim strength | **PASS** | 2 HIGH-severity flags, all explicit negations ("not a validated extent"); 0 unresolved |
| Figure provenance | **PASS** | 12 figures, 17 sources hashed, 24 outputs hashed, 0 missing; fully scripted, no manual editing |
| Figure readability | **PASS** | single style system; redundant encoding by luminance AND hatch so no distinction depends on colour alone; base font 7 pt at 3.35 in single-column width; PNG at 600 dpi plus vector PDF |
| Caption completeness | **PASS** | all 12 captions state geometry/branch, units, quality mask, sample definition, uncertainty meaning, exclusions and limitations; no caption contains a causal interpretation |
| Table consistency | **PASS** | Table 1 rates match final_hotspot_table.csv exactly; detailed QC fields moved to supplement |
| Reference completeness | **HOLD** | 2 of 15 entries have unresolved bibliographic metadata; all others carry at least one unverified field. No metadata was invented |
| Supplement cross-references | **PASS** | main text defers all implementation detail to the supplement; S1-S8 and the condensed appendix are cross-referenced |
| Data/code availability | **PASS** | DATA_CODE_AVAILABILITY.md lists products, external datasets and reuse limitations |
| Reproducibility appendix | **PASS** | 7 incidents retained of 8 recorded; each states problem, consequence, detection, correction and regression protection |

## Outstanding before submission

1. **Reference metadata** (2 hard placeholders plus unverified fields). No metadata invented; must be completed against the chosen journal's style.
2. **Journal selection, cover letter, scope rewriting and final title** are deliberately out of scope for Phase V-B.

## Notes recorded during audit

- Figure exclusions declared on the figure: {'F6': 'H001 omitted for plotting scale only; reported in F5'}
- Figures restricted from synthesising unretained data: {'F4': 'aggregate retained statistics only; no pixel-level scatter, none synthesised', 'F8': 'per-epoch series not retained; NOT reconstructed'}
- Figures using report-transcribed constants (documented with source): ['F10', 'F11']

## Package metrics

- main-text word count: 2232
- main figures: 12
- supplementary: 8 methods sections + 7 incidents + 12 captions
- unresolved citation placeholders: 2
- publication freeze source: freeze/publication_v1
