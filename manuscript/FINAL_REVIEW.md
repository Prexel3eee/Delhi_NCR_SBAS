# Final evidence and hostile manuscript review

Review date: **23 September 2026**  
Target at the time of this internal review: **International Journal of Applied Earth Observation and Geoinformation — Research paper**. The corresponding author subsequently requested an ISPRS venue; the submission target is now *ISPRS Open Journal of Photogrammetry and Remote Sensing*. The scientific evidence findings below remain applicable, while journal-specific formatting must be checked against its live guide.
Reviewed package: manuscript, supplement, claim ledger, bibliography, 12-figure registry and provenance, three main tables, two supplementary tables, cover letter, journal compliance matrix, and submission audit.

This is an **internal evidence review performed by the manuscript lead**, not an external independent peer review. Its checks are reproducible from the listed project records, but journal reviewers and the human authors remain independent decision-makers.

## Disposition

Unresolved fatal flaws: **0**  
Unresolved correctable major concerns: **0**  
Irreducible scientific limitations: **8**, all retained as **DISCLOSED LIMITATION** in the Abstract where central, the Discussion, and/or the dedicated Limitations section.  
Submission blockers owned by the authors: identity, declarations, data-repository decision, and exclusive-submission approval in `AUTHOR_INPUT_REQUIRED.md`.

The package is scientifically coherent and journal-shaped. It is not authorized for portal submission until the human-author fields are completed.

## Evidence-review quality result

**SUPPORTED WITH QUALIFICATIONS.** Every material project claim traces to frozen internal evidence, and every retained literature-dependent sentence has direct or explicitly indirect support. The decisive qualifications are the eight disclosed scientific limitations and the author-owned submission fields. Five supplied comparator/regional PDFs were inspected in full; the remaining literature was checked through DOI metadata, abstracts, and source records, and no numerical claim from an abstract-only source was introduced. Kumar et al. (2022) still requires a full-text recheck before adding any numerical quotation or finer-grained assertion.

## Hostile scientific review

The review assumed that a skeptical reader would try to explain the positive result through selection, shared processing, reference choice, temporal mismatch, observability, or narrative overreach.

| Challenge | Severity tested | Evidence examined | Resolution | Final status |
|---|---|---|---|---|
| Circular hotspot definition | Fatal | `scripts/32_hotspots.py`; frozen Phase-I observations; Methods 2.3; Supplement S5; H001–H005 retained regardless of later outcome | Zones were defined only from the authoritative ascending field using fixed rate, coherence, and area thresholds before descending interpretation. The descending result did not redefine polygons or delete failed zones. Threshold sensitivity is reported without reselection. | RESOLVED |
| Shared-data leakage | Fatal | Independent orbit/subswath, acquisition lists, networks, masks, references, and branch records; Figure F1; Methods 2.4; Supplement S3–S4 | The geometries share no burst, acquisition, interferogram, mask, or reference pixel, and no descending pair was selected by zone intersection. Both observe the same region and broad period, but no dates are exactly shared; the manuscript calls this an independent measurement design rather than total physical independence. | RESOLVED |
| Reference dependence | Major | `qc/sci/reference_sensitivity.json`; `qc/sci/phase2/common_domain.json`; uncertainty table; Methods 2.5 and 2.7; Limitation “Local geodetic reference” | Native products retain local references; direct comparison uses one declared stable-control alignment. The 4.78 mm yr-1 zero-level range is reported separately, absolute velocity is not claimed, and zone contrasts are identified as reference-invariant. | DISCLOSED LIMITATION |
| Temporal mismatch | Major | Acquisition spans and gaps; no exactly shared dates; retained cumulative endpoints; Figure S2/F8; Results 3.7; dedicated limitation | Mean-rate support is explicitly separated from detailed time-history reproduction. H001's contradictory cumulative summaries and r = 0.007 are retained rather than smoothed or reconstructed. | DISCLOSED LIMITATION |
| Coherence confounding | Major | Phase-III matched-band contrasts; coherence-stratification records; Results 3.5 and 3.8; Discussion 4.3 and 4.6; dedicated limitation | H002/H003 have adequate descending coherence and comparable ascending matched-band contrasts, while H001/H004 survive band matching. This opposes coherence as the sole explanation but does not identify the physical origin of the velocity–coherence association. | DISCLOSED LIMITATION |
| Unsupported causation | Fatal | Frozen mechanism protocol and evidence matrix; Tables 3/S1; Discussion 4.6–4.7; terminology audit | No candidate mechanism is promoted from plausibility to cause. Groundwater, shallow texture, and urban variables retain `NO EVIDENCE`; deep susceptibility remains `NOT ADEQUATELY TESTED`; construction remains `NOT TESTABLE`. H005 is excluded from mechanism samples. | RESOLVED |
| Novelty overstatement | Major | Title, Abstract, Introduction, cover letter, highlights, and global search for “first,” “novel,” and “unprecedented” | The contribution is framed as an auditable inference design and selective reproduction result. No priority claim appears, and the cover letter does not call the study the first of its kind. | RESOLVED |
| Contradictory literature | Major | Delhi-NCR papers by Garg et al. and Kumar et al.; urban comparators from Lahore, Kakinada, Fuzhou, and Makkah; Discussion 4.5 | Earlier groundwater-associated interpretations are stated, not suppressed. The manuscript explains why different periods, polygons, sensors, reference frames, and hydrogeological measurements prevent direct causal transfer. Its groundwater result is neither framed as a replication nor a refutation of earlier regional attribution. | RESOLVED |
| Partial descending coverage | Major | Orbit-136 coverage records; common-domain mask; Figure F1; Limitation “Partial descending coverage” | All five zones fall inside the descending footprint, but only 69.63% of the AOI is in the common valid domain. The result is restricted to the five polygons and is not generalized to the full ascending field. | DISCLOSED LIMITATION |
| LOS-to-vertical conversion | Fatal | Viewing geometry, withdrawn component estimate, Methods 2.1/2.5, Discussion 4.2, terminology audit | All measurements are labeled relative LOS. No invalid component decomposition is retained, and the manuscript repeatedly states that cross-geometry agreement is not a vertical solution. | DISCLOSED LIMITATION |
| Aquifer specificity | Major | Well registry, missing screened intervals, H001 outages, SoilGrids depth, Discussion 4.6 and dedicated limitation | The completed groundwater test is restricted to its observed station composites. Deep aquifer susceptibility is not treated as measured; borehole and screened-interval evidence are specified as future needs. | DISCLOSED LIMITATION |
| Construction chronology | Major | WorldCover/GHSL variables and product epochs; unavailable structural metadata; Results 3.8; dedicated limitation | Built fraction is used only as a static setting proxy. Height, foundation, load, construction date, excavation, tunneling, and dewatering are not inferred; construction loading remains not testable. | DISCLOSED LIMITATION |
| H005 contradiction | Major | Frozen rates -14.21 and +61.39 mm yr-1; Figure F6; Results 3.6; dedicated limitation | The contradiction remains in the main result and is not forced into either class. No geometry or cause is preferred, and the zone contributes to no causal test. | DISCLOSED LIMITATION |

## Citation-entailment review

Classification rules: `DIRECT` means the cited source explicitly supports the sentence at the stated locator. `INDIRECT` means the sentence is a clearly signposted synthesis or inference from directly supported source facts. The two failing categories—partial support and no support—were not permitted to remain.

Each row below is one cited sentence or one inseparable compound sentence in the manuscript. Internal project results are checked by the claim ledger rather than assigned to external literature.

| ID | Manuscript claim unit | Source and locator | Class | Review action |
|---|---|---|---|---|
| E01 | Urban InSAR can reveal localized surface motion, but a coherent velocity map alone does not guarantee interpretation. | Ferretti et al. (2001), method/experiments; Berardino et al. (2002), algorithm/demonstration; Crosetto et al. (2016), review of products and validation | INDIRECT | Retained as a bounded synthesis; it makes no site-specific performance claim. |
| E02 | Relative LOS estimates depend on viewing geometry and reference and can retain atmospheric, unwrapping, decorrelation, and sampling effects. | Crosetto et al. (2016), PSI processing, products, limitations; Yunjun et al. (2019), unwrapping/noise framework | DIRECT | Retained; wording matches the measurement boundary. |
| E03 | Spatial coincidence with pumping, sediment, or construction does not isolate a physical cause. | Crosetto et al. (2016), validation limitations; comparator papers' observational designs | INDIRECT | Retained as an explicit causal-inference boundary, not attributed to one experiment. |
| E04 | Delhi-NCR combines groundwater stress with previously reported localized InSAR deformation. | Garg et al. (2022), Abstract/Results/Discussion; Kumar et al. (2022), title and abstract-level record | DIRECT | Retained without importing a mechanism into current polygons. |
| E05 | Garg et al. mapped 2014–2020 deformation and related its evolution to groundwater decline. | Garg et al. (2022), Abstract and locality Results/Discussion | DIRECT | Retained; period and interpretive strength are accurate. |
| E06 | Kumar et al. supplied ALOS-1/Sentinel-1 regional context and advanced groundwater overexploitation. | Kumar et al. (2022), DOI metadata, title, abstract-level record | DIRECT | Retained; no numerical quotation is made because full-text numerical verification is incomplete. |
| E07 | Prior physical interpretation cannot be transferred automatically to later dates, polygons, processing choices, and reference frames. | Differences documented in the two regional source records and the present Methods | INDIRECT | Retained as study-design logic; it does not allege an error in the earlier papers. |
| E08 | Unwrapping correction and ERA5 are established method/data contexts, but their benefit is product-specific here. | Yunjun et al. (2019), correction/noise method; Hersbach et al. (2020), ERA5 construction/evaluation | DIRECT | Retained; branch performance remains an internal result, not a claim sourced to either paper. |
| E09 | Benjamini–Hochberg controls the false-discovery rate across the declared forward-lag family. | Benjamini and Hochberg (1995), procedure/theorem sections | DIRECT | Retained; q = 0.05 and the 16-test family are declared project choices. |
| E10 | SoilGrids supplies 250 m shallow-soil predictions at standard depths to 2 m. | Poggio et al. (2021), Abstract and Methods/product sections | DIRECT | Retained; wording explicitly refuses deep-geology interpretation. |
| E11 | Earlier Delhi-NCR studies report groundwater-associated deformation, while the present analysis tests a later and different design. | Garg et al. (2022); Kumar et al. (2022); present frozen observation interval | DIRECT | Retained with the comparison boundary in the same paragraph. |
| E12 | Differences in periods, boundaries, sensors/branches, references, and hydrogeological records preclude direct equivalence. | Regional paper records plus current Methods/claim C015 | INDIRECT | Retained as an explicit non-transfer argument. |
| E13 | Lahore, Kakinada, Fuzhou, and Makkah studies combine radar time series with groundwater, sediment, land-cover, or urban evidence. | Hussain et al. (2022), Abstract/Methods; Nadimpalli and Mahammood (2025), Abstract/Discussion; Zhu et al. (2022), Abstract/Methods; Elhag et al. (2025), Abstract/Methods | DIRECT | Retained; no comparator magnitude is transferred. |
| E14 | Geometry, monitoring duration, ground data, and mechanism strength vary across comparator studies. | The four comparator study designs and limitations in `PAPER_CARDS.md` | DIRECT | Retained; differences are source-observable. |
| E15 | Comparator associations motivate candidate mechanisms but cannot replace selectivity within the present dataset. | Comparator evidence plus current preregistered contrast | INDIRECT | Retained as the synthesis concluding the comparison, not as a source-specific finding. |

No literature-dependent sentence remains with inadequate entailment. Citation keys, DOI uniqueness, and nonempty evidence locators also pass the machine audit.

## Figure and table review

All 12 PNGs were inspected at rendered size. Their dimensions range from 2,928 × 1,771 to 4,188 × 2,166 pixels, with paired PDF vector outputs in provenance. Every submission item resolves to the frozen source paths in `FIGURE_CLAIM_REGISTRY.csv`. Conclusions are reinforced by numerical labels, text, marker shape, hatching, line style, or category wording rather than colour alone.

| Submission item | Question answered and value check | Limitation/readability check | Non-colour cue | Status |
|---|---|---|---|---|
| F1 (source F1) | Shows independent acquisition designs, 119/336 versus 91/219, 72.0% descending AOI coverage, and all five zones. | North arrow, 20 km scale, uncovered-strip hatch, and partial-coverage limitation visible. | Hatching, zone labels, table text, outlines. | PASS |
| F2 (source F2) | Shows the authoritative ascending field and median -0.73 mm yr-1; display saturation at ±20 is declared. | Histogram and colourbar are legible; reference and LOS limitations are printed. | Histogram shape, median line/label, numeric colourbar. | PASS |
| F3 (source F3) | Shows all five frozen rate pairs and classifications matching Table 1. | Values, units, geometry labels, and status strip are readable. | Numeric labels and distinct hatches in bars/status strip. | PASS |
| F4 (source F5) | Shows H001/H004 rates and magnitude ratios 1.16/0.87. | Detailed-history and 6.66 km2 limitations are on-figure/caption. | Value labels, descending hatch, exact-agreement dashed line. | PASS |
| F5 (source F6) | Contrasts H002/H003 with H004 and reports matched-band values. | H001 scale omission and descending-quality evidence are disclosed. | “reproduced/not reproduced” text, values, background region, hatch. | PASS |
| F6 (source F7) | Shows H005 opposite-sign -14.21/+61.39 rates. | Explicitly offers no cause or preferred geometry. | Zero line, signed values, hatch, contradiction annotation. | PASS |
| F7 (source F9) | Shows forward/falsification groundwater lags and the four-zone comparison. | Sign convention, FDR outcome, missing aquifer specificity, and H005 exclusion are stated. | Marker shapes, solid/dashed lines, shaded lag region, hatched comparison bars. | PASS |
| F8 (source F12) | Reproduces every frozen candidate evidence state verbatim. | Category definitions and non-ranking warning are readable. | Full text labels plus different hatch swatches. | PASS |
| S1 (source F4) | Shows aggregate correction improvement and spatially selective overlap. | Explicitly states that retained statistics are not a reconstructed pixel scatter. | Numeric labels, grayscale contrast, hatches, threshold line. | PASS |
| S2 (source F8) | Shows retained cumulative endpoints and the limited scope of reproduction. | No per-epoch series is reconstructed; history mismatch is prominent. | Signed labels, hatch, and explicit reproduced/not-reproduced text. | PASS |
| S3 (source F10) | Shows shallow clay/sand values and background, matching frozen summaries. | Upper-2-m surrogate limitation and exclusion from deep-geology inference are explicit. | Numeric labels, category hatches, dashed background. | PASS |
| S4 (source F11) | Shows two built-intensity products, background, and the H001/H002 ranking reversal. | Projection status and absence of structural loading are explicit. | Numeric labels, category hatches, dashed background, reversal arrow. | PASS |
| Table 1 | All five ascending/descending rates, areas, and status strings match `final_hotspot_table.csv`. | Caption and prose callout added during this review. | Text and signed values. | PASS |
| Table 2 | Five separate uncertainty components match `uncertainty_table.json`. | No unjustified combined interval; consequence column limits interpretation. | Text and units. | PASS |
| Table 3 | Seven mechanism evidence states match `final_evidence_matrix.csv`. | Definitions remain distinct; limitations carried in the basis column and following paragraph. | Verbatim category text. | PASS |
| Supplementary Table S1 | Repeats the frozen five-zone outcomes for reproducibility. | Caption states common-domain polygon means. | Text and signed values. | PASS |
| Supplementary Table S2 | Maps each workflow component to its authoritative record and protection. | Paths and protection mechanism are explicit. | Text. | PASS |

## Corrective findings and resolutions

| Finding | Severity | Resolution | Affected files | Verification |
|---|---|---|---|---|
| Three main tables lacked explicit numbered captions and prose callouts despite the compliance matrix claiming that requirement passed. | Major, correctable | Added numbered captions and callouts for hotspot outcomes, uncertainty components, and mechanism states in the owning manuscript builder. Added a regression test requiring every caption and a second textual occurrence. | `scripts/77_build_submission_manuscript.py`; generated manuscript; tests | Builder regeneration, caption/callout test, table-count audit. |
| The journal's data-deposit requirement and exclusive-submission approval were not represented in the single author-input checklist. | Major submission blocker, non-scientific | Added repository DOI/sharing rationale and exclusive-submission approval to the author-owned checklist, keeping them separate from scientific pass/fail. | `AUTHOR_INPUT_REQUIRED.md`; tests | Placeholder boundary test and compliance matrix. |

No other correctable major concern was found. The remaining scientific limits cannot be repaired by prose and are already disclosed rather than concealed.

## Author handoff

The corresponding author supplied author names and order, affiliation, contact, acknowledgements, competing-interest and ethics declarations, a data-on-request statement, and an explicit exclusive-submission confirmation. These are now recorded in `AUTHOR_DECLARATIONS.json`. The remaining human checks are the proposed CRediT roles, the conditional no-funding statement, the complete AI-use disclosure and final human verification, the scope of data that can actually be shared, and the selected ISPRS journal's live portal requirements. Details are in `AUTHOR_INPUT_REQUIRED.md`.

Re-run the builder and scientific audit after any declaration changes. This internal review is not an external peer-review endorsement or authorization to submit while the author status remains `AWAITING AUTHOR CONFIRMATION`.
