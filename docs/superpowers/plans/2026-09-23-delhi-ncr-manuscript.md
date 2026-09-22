# Delhi-NCR Cross-Geometry InSAR Manuscript Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one full, submission-ready research article and supplement whose numbers, classifications, citations, figures, and claim strength are traceable to the frozen Delhi-NCR SBAS-InSAR evidence.

**Architecture:** Preserve `publication_v1` and its journal-neutral files as an immutable historical package. Build a new submission layer from frozen evidence: structured literature records feed a versioned manuscript builder, selected existing figures feed a main/supplement registry, and a dedicated audit enforces numerical, terminology, citation, and provenance gates without reopening scientific processing.

**Tech Stack:** Python 3.11/3.12, Markdown, CSV, BibTeX, pandas, pytest, existing publication scripts and frozen JSON/CSV artefacts, DOI/journal metadata from original sources.

**Spec:** `docs/superpowers/specs/2026-09-23-delhi-ncr-manuscript-design.md`

## Global Constraints

- Produce one full research article, not a short communication or multiple minimally separated papers.
- Target 5,500-7,000 main-text words, excluding references and captions.
- Target 6-8 main figures and 2-3 main tables.
- Keep `freeze/publication_v1`, all upstream freezes, and `MANUSCRIPT_FINAL_JOURNAL_NEUTRAL.md` unchanged as the v1 record.
- Do not alter frozen measurements, classifications, thresholds, masks, or evidence states.
- Never describe relative LOS deformation as measured vertical displacement.
- Never describe independently supported spatial/mean-rate behavior as independently validated time history.
- Keep `NO EVIDENCE`, `NOT ADEQUATELY TESTED`, and `NOT TESTABLE` distinct.
- Treat `22.6 km2` as a mask-dependent ascending operating extent and `6.66 km2` as the summed H001+H004 Phase-I zone area supported at hotspot level.
- Keep H005 as an unresolved contradiction and exclude it from causal tests.
- Keep statistical, reference, processing, temporal, and structural uncertainty terms separate.
- Do not invent bibliographic fields, author identities, affiliations, funding, conflicts, or contribution roles.
- Treat student-prepared material as background guidance only; citation requires the original source.

## File Structure

### New evidence files

- `manuscript/PAPER_CARDS.md` - structured records for every core cited paper.
- `manuscript/LITERATURE_MATRIX.csv` - thematic comparison of methods and evidence.
- `manuscript/REFERENCE_LIBRARY.bib` - verified bibliography.
- `manuscript/CLAIM_EVIDENCE_LEDGER.csv` - one row per material claim.
- `manuscript/FIGURE_CLAIM_REGISTRY.csv` - figure placement and claim mapping.
- `manuscript/AUTHOR_INPUT_REQUIRED.md` - exact human-owned metadata and declarations.

### New submission outputs

- `manuscript/SUBMISSION_MANUSCRIPT.md`
- `manuscript/SUBMISSION_SUPPLEMENT.md`
- `manuscript/SUBMISSION_READINESS_V2.md`
- `manuscript/SUBMISSION_AUDIT.json`

### New code and tests

- `scripts/77_build_submission_manuscript.py`
- `scripts/78_submission_audit.py`
- `tests/test_submission_manuscript.py`

### Existing files read but not modified

- `freeze/**`
- `qc/sci/phase4/final_hotspot_table.csv`
- `qc/sci/phase4/final_evidence_matrix.csv`
- `qc/sci/phase4/uncertainty_table.json`
- `manuscript/MANUSCRIPT_FINAL_JOURNAL_NEUTRAL.md`
- `manuscript/SUPPLEMENT_FINAL_JOURNAL_NEUTRAL.md`
- `manuscript/FIGURE_PROVENANCE.json`

## Review Focus

1. **Stale duplicated values:** any rate, area, count, or evidence state differing from its frozen source must fail the audit.
2. **Geometry overstatement:** unqualified conversion from LOS to vertical motion or use of `validated` for mean-rate support must fail.
3. **Citation-topic substitution:** a relevant paper that does not entail the sentence must remain uncited for that claim.
4. **Negative-result suppression:** omission of H002, H003, H005, or a final evidence state must fail.
5. **Generated drift:** two consecutive builds must be identical and must not modify publication-v1 files.

---

### Task 1: Establish the submission-v2 builder and immutable-source contract

**Files:**
- Create: `scripts/77_build_submission_manuscript.py`
- Create: `tests/test_submission_manuscript.py`
- Read: `scripts/70_phase5_manuscript.py`
- Read: `qc/sci/phase4/final_hotspot_table.csv`
- Read: `qc/sci/phase4/final_evidence_matrix.csv`
- Read: `qc/sci/phase4/uncertainty_table.json`

**Interfaces:**
- Consumes: `load_frozen_evidence(root: Path) -> FrozenEvidence`.
- Produces: `build_submission(root: Path) -> dict[str, str]` and `write_submission(root: Path) -> list[Path]`.

- [ ] **Step 1: Write failing tests for authoritative values and protected paths**

```python
def test_load_frozen_evidence_preserves_authoritative_hotspots(project_root):
    evidence = submission.load_frozen_evidence(project_root)
    assert evidence.hotspots["H001"].ascending_rate == -30.95
    assert evidence.hotspots["H001"].descending_rate == -36.02
    assert evidence.hotspots["H004"].area_km2 == 1.07
    assert sum(evidence.hotspots[h].area_km2 for h in ("H001", "H004")) == 6.66

def test_builder_never_targets_publication_v1(project_root):
    paths = submission.output_paths(project_root)
    assert all("freeze/publication_v1" not in str(path) for path in paths)
    assert all("MANUSCRIPT_FINAL_JOURNAL_NEUTRAL.md" not in str(path) for path in paths)
```

- [ ] **Step 2: Run tests and verify the builder is missing**

Run: `/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python -m pytest tests/test_submission_manuscript.py -q`

Expected: collection failure for missing `scripts/77_build_submission_manuscript.py`.

- [ ] **Step 3: Implement immutable evidence types and loading**

```python
@dataclass(frozen=True)
class HotspotEvidence:
    hotspot: str
    ascending_rate: float
    descending_rate: float
    area_km2: float
    status: str
    final_interpretation: str

@dataclass(frozen=True)
class FrozenEvidence:
    hotspots: dict[str, HotspotEvidence]
    evidence_states: dict[str, str]
    uncertainty: dict
    source_paths: tuple[Path, ...]
```

Load rates/areas only from `final_hotspot_table.csv`, evidence states only from `final_evidence_matrix.csv`, and uncertainty only from `uncertainty_table.json`.

- [ ] **Step 4: Implement isolated deterministic output**

`output_paths()` returns only `SUBMISSION_MANUSCRIPT.md` and `SUBMISSION_SUPPLEMENT.md`. `build_submission()` returns text without timestamps. Initial output includes the approved title, required headings, and a source-derived hotspot table.

- [ ] **Step 5: Add deterministic rebuild test**

```python
def test_build_is_deterministic(project_root):
    assert submission.build_submission(project_root) == submission.build_submission(project_root)
```

- [ ] **Step 6: Run tests and commit**

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python -m pytest tests/test_submission_manuscript.py -q
git add scripts/77_build_submission_manuscript.py tests/test_submission_manuscript.py
git commit -m "feat: scaffold evidence-bound submission manuscript"
```

### Task 2: Build the verified literature evidence layer

**Files:**
- Create: `manuscript/PAPER_CARDS.md`
- Create: `manuscript/LITERATURE_MATRIX.csv`
- Create: `manuscript/REFERENCE_LIBRARY.bib`
- Create: `manuscript/CLAIM_EVIDENCE_LEDGER.csv`
- Modify: `tests/test_submission_manuscript.py`

**Interfaces:**
- Consumes: original PDFs and DOI/publisher records.
- Produces: paper IDs `P001...`, claim IDs `C001...`, and verified citation keys.

- [ ] **Step 1: Add schema tests**

Require these exact columns:

```python
LITERATURE_COLUMNS = [
    "paper_id", "citation_key", "region", "period", "sensor", "geometry",
    "method", "validation", "mechanism_claim", "limitation", "manuscript_use"
]
CLAIM_COLUMNS = [
    "claim_id", "claim", "claim_type", "evidence_kind", "evidence_locator",
    "citation_key", "allowed_strength", "manuscript_section"
]
```

Require unique IDs and non-empty evidence locators.

- [ ] **Step 2: Verify tests fail on missing artifacts**

Run the focused test file. Expected: four missing evidence-file failures.

- [ ] **Step 3: Verify the initial core literature against original sources**

Record full metadata and direct-support boundaries for:

1. Garg et al. (2022), DOI `10.1038/s41598-021-04193-9`.
2. Kumar et al. (2022), DOI `10.1016/j.jhydrol.2021.127329`.
3. Yunjun et al. (2019), DOI `10.1016/j.cageo.2019.104331`.
4. Berardino et al. (2002), DOI `10.1109/TGRS.2002.803792`.
5. Ferretti et al. (2001), DOI `10.1109/36.898661`.
6. Crosetto et al. (2016), DOI `10.1016/j.isprsjprs.2015.10.011`.
7. Even and Schulz (2018), DOI `10.3390/rs10050744`.
8. Hussain et al. (2022), DOI `10.3390/rs14163950`.
9. Nadimpalli and Mahammood (2025), DOI `10.7780/kjrs.2025.41.3.9`.
10. Zhu et al. (2022), DOI `10.5194/isprs-archives-XLIII-B3-2022-373-2022`.
11. Elhag et al. (2025), DOI `10.1016/j.kjs.2025.100419`.
12. Poggio et al. (2021), DOI `10.5194/soil-7-217-2021`.
13. Benjamini and Hochberg (1995), DOI `10.1111/j.2517-6161.1995.tb02031.x`.
14. Hersbach et al. (2020), DOI `10.1002/qj.3803`.

Add another source only when it supports a named manuscript claim absent from this set.

- [ ] **Step 4: Write complete paper cards**

Each card contains verified citation, question, region/period, sensor/geometry/method, validation, numerical result, mechanism claim, supporting evidence, limitations, manuscript relevance, allowed claims, prohibited claims, and exact page/section. Use `Not reported in the inspected source` when the source omits a field.

- [ ] **Step 5: Populate literature matrix and BibTeX**

Use one matrix row and one verified BibTeX entry per cited paper. Government/software records without articles use `@misc` with organization, title, URL, version when available, and execution-date access date.

- [ ] **Step 6: Seed the claim ledger**

Create rows C001-C012 for H001/H004 support; H002/H003 non-reproduction; H005 contradiction; 22.6 km2 meaning; 6.66 km2 meaning; non-reproduced histories; groundwater result; shallow-texture result; deep-geology status; construction status; uncertainty policy; and prior Delhi-NCR groundwater-associated interpretation.

- [ ] **Step 7: Run schema tests and commit**

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python -m pytest tests/test_submission_manuscript.py -q
git add manuscript/PAPER_CARDS.md manuscript/LITERATURE_MATRIX.csv manuscript/REFERENCE_LIBRARY.bib manuscript/CLAIM_EVIDENCE_LEDGER.csv tests/test_submission_manuscript.py
git commit -m "docs: add verified manuscript evidence layer"
```

### Task 3: Write title, abstract, Introduction, and reproducible Methods

**Files:**
- Modify: `scripts/77_build_submission_manuscript.py`
- Modify: `tests/test_submission_manuscript.py`
- Generate: `manuscript/SUBMISSION_MANUSCRIPT.md`

**Interfaces:**
- Consumes: `FrozenEvidence`, paper cards, literature matrix, and BibTeX keys.
- Produces: Title, Abstract, Introduction, and Data and methods.

- [ ] **Step 1: Add failing architecture test**

Require the approved title and headings 1, 2.1-2.7 for study design, ascending stack, frozen observations, descending experiment, cross-geometry comparison, mechanism tests, and uncertainty.

- [ ] **Step 2: Write a 250-300-word abstract**

Include 119/336 ascending; 91/219 descending; five zones; H001/H004 support; H002/H003 non-reproduction; H005 contradiction; mechanism evidence states; and the mean-rate/time-history distinction.

- [ ] **Step 3: Write the Introduction in five functional paragraphs**

1. Urban InSAR value and interpretive vulnerabilities.
2. Prior Delhi-NCR observations, centred on Garg and Kumar.
3. Unresolved reproducibility and causal-selectivity problem.
4. Independent-geometry and negative-control design.
5. Three objectives: surviving zones, candidate explanations against controls, and inference limits.

- [ ] **Step 4: Write Methods with exact parameters**

Report AOI, dates, orbits, subswaths, polarization, burst/pair counts, network thresholds, HyP3 product, looks, pixel size, MintPy version, correction decisions, hotspot thresholds, common domain, descending correction, groundwater screening, lag/FDR rules, geology/urban datasets, and uncertainty policy.

- [ ] **Step 5: Add protected-language tests**

Assert required counts and `relative LOS` occur. Fail on `measured vertical displacement` and `independently validated`.

- [ ] **Step 6: Build, inspect, test, and commit**

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python scripts/77_build_submission_manuscript.py
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python -m pytest tests/test_submission_manuscript.py -q
git add scripts/77_build_submission_manuscript.py tests/test_submission_manuscript.py manuscript/SUBMISSION_MANUSCRIPT.md
git commit -m "docs: write manuscript introduction and methods"
```

### Task 4: Write complete Results with negative and contradictory findings

**Files:**
- Modify: `scripts/77_build_submission_manuscript.py`
- Modify: `tests/test_submission_manuscript.py`
- Generate: `manuscript/SUBMISSION_MANUSCRIPT.md`

**Interfaces:**
- Consumes: frozen Phase-I-IV sources.
- Produces: Results and 2-3 main tables.

- [ ] **Step 1: Require result sections 3.1-3.8**

Test for ascending field, descending reliability, common domain, H001/H004, H002/H003, H005, temporal/uncertainty, and mechanism-test outcomes.

- [ ] **Step 2: Write Sections 3.1-3.3**

Report ascending distribution/detection, quality-dependent 22.6 km2, descending raw failure, seven-of-seven correction improvement, common-domain size, and moderate global agreement.

- [ ] **Step 3: Write Sections 3.4-3.6**

For every hotspot report area, ascending/descending rates, quality basis, classification, and history status. Give H002/H003 equal prominence and H005 a standalone subsection.

- [ ] **Step 4: Write Sections 3.7-3.8**

Report uncertainty terms without summing. Reproduce every final evidence-matrix row with exact state and quantitative basis.

- [ ] **Step 5: Add value-regression tests**

Parse the generated hotspot table and compare all ten rates to `final_hotspot_table.csv`. Require every evidence state verbatim. Assert H005 is absent from causal test samples.

- [ ] **Step 6: Build, test, and commit**

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python scripts/77_build_submission_manuscript.py
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python -m pytest tests/test_submission_manuscript.py -q
git add scripts/77_build_submission_manuscript.py tests/test_submission_manuscript.py manuscript/SUBMISSION_MANUSCRIPT.md
git commit -m "docs: add complete cross-geometry results"
```

### Task 5: Write Discussion, Limitations, and Conclusion

**Files:**
- Modify: `scripts/77_build_submission_manuscript.py`
- Modify: `manuscript/CLAIM_EVIDENCE_LEDGER.csv`
- Modify: `tests/test_submission_manuscript.py`
- Generate: `manuscript/SUBMISSION_MANUSCRIPT.md`

**Interfaces:**
- Consumes: Results, literature records, and claim ledger.
- Produces: Discussion, Limitations, and Conclusion.

- [ ] **Step 1: Add failing discussion tests**

Require selective reproducibility, negative controls, prior Delhi-NCR comparison, failed causal selectivity, remaining alternatives, methodological implications, and every limitation from the spec.

- [ ] **Step 2: Write eight evidence-bound discussion arguments**

Follow the approved order: H001/H004 meaning; time-history/vertical limits; H002/H003; H005; Garg/Kumar comparison; failed candidate explanations; untested alternatives; urban-InSAR implications. Map every paragraph to C### rows.

- [ ] **Step 3: Write limitations as inference consequences**

For local geodetic reference, LOS projection, partial descending coverage, temporal mismatch, coherence ambiguity, aquifer-depth specificity, construction chronology, and H005, state what evidence is missing, what result it affects, and what claim cannot be made.

- [ ] **Step 4: Write the Conclusion without new claims**

State the five-zone classification, restricted H001/H004 meaning, evidence-state outcome, and the role of negative controls. Add no number, dataset, mechanism, or citation absent earlier.

- [ ] **Step 5: Add conclusion-subset and claim-strength tests**

Require every material conclusion phrase earlier in the article. Fail on `caused by groundwater`, `confirmed subsidence`, and `validated vertical displacement`.

- [ ] **Step 6: Build, count, test, and commit**

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python scripts/77_build_submission_manuscript.py
python -c "from pathlib import Path; print(len(Path('manuscript/SUBMISSION_MANUSCRIPT.md').read_text().split()))"
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python -m pytest tests/test_submission_manuscript.py -q
git add scripts/77_build_submission_manuscript.py manuscript/CLAIM_EVIDENCE_LEDGER.csv tests/test_submission_manuscript.py manuscript/SUBMISSION_MANUSCRIPT.md
git commit -m "docs: complete manuscript discussion and conclusions"
```

Expected: 5,500-7,000 main-text words by the audit's section-aware count.

### Task 6: Build the supplement and author-input boundary

**Files:**
- Modify: `scripts/77_build_submission_manuscript.py`
- Create: `manuscript/AUTHOR_INPUT_REQUIRED.md`
- Generate: `manuscript/SUBMISSION_SUPPLEMENT.md`
- Modify: `tests/test_submission_manuscript.py`

**Interfaces:**
- Consumes: existing supplement, incident records, network/correction QC, and captions.
- Produces: complete supplement and exact human-owned fields.

- [ ] **Step 1: Require supplementary sections**

Test for study/reference frame, both networks, processing, corrections, hotspot definition, common domain, groundwater, geology/urban tests, uncertainty, tables, incidents, captions, and data/code availability.

- [ ] **Step 2: Expand reproducible methods**

Move paths, thresholds, branch names, filters, lag grids, permutation settings, masks, and registries into the supplement. Link main-text statements to exact sections.

- [ ] **Step 3: Preserve seven scientific incidents**

Include INC-001, INC-002, INC-005, INC-006, INC-007, INC-008, and INC-009 with problem, consequence, detection, correction, and regression protection.

- [ ] **Step 4: Write the human-input boundary**

List author names/order, affiliations, corresponding author/email, CRediT roles, funding, acknowledgements, conflicts, ethics requirement, selected journal, and journal-specific AI disclosure. For each, state: `Not supplied; must be confirmed by the human authors before submission.`

- [ ] **Step 5: Add cross-reference and identity tests**

Require every supplementary callout to resolve. Fail if a guessed person, email, institution, grant, or conflict statement appears.

- [ ] **Step 6: Build, test, and commit**

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python scripts/77_build_submission_manuscript.py
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python -m pytest tests/test_submission_manuscript.py -q
git add scripts/77_build_submission_manuscript.py manuscript/AUTHOR_INPUT_REQUIRED.md manuscript/SUBMISSION_SUPPLEMENT.md tests/test_submission_manuscript.py
git commit -m "docs: complete submission supplement"
```

### Task 7: Define figure placement and verify scientific graphics

**Files:**
- Create: `manuscript/FIGURE_CLAIM_REGISTRY.csv`
- Modify: `scripts/77_build_submission_manuscript.py`
- Modify: `tests/test_submission_manuscript.py`
- Read: `manuscript/FIGURE_PROVENANCE.json`
- Read: `qc/sci/phase4/figures/*.{png,pdf}`

**Interfaces:**
- Consumes: 12 provenance-verified figures.
- Produces: eight main figures, four supplementary figures, and exact callouts.

- [ ] **Step 1: Add registry and provenance tests**

Require columns `submission_id,source_figure,placement,scientific_question,claim_ids,source_paths,limitations,caption_file`. Require every source in provenance, every claim in the ledger, and 6-8 main IDs.

- [ ] **Step 2: Populate the eight-figure main set**

Map submission F1-F8 to existing F1, F2, F3, F5, F6, F7, F9, and F12. Place existing F4, F8, F10, and F11 in the supplement. Preserve source provenance IDs.

- [ ] **Step 3: Inspect PNG and PDF renderings**

Check legibility, redundant encoding, units, map scale/orientation, panel labels, geometry, sample/mask definition, and limitation annotations. Record deficiencies in the registry and fix only through owning plotting scripts.

- [ ] **Step 4: Add figure callouts and captions**

Cite each figure immediately after the first supported claim. Do not cite supplementary figures in the main text unless needed for a stated method or limitation.

- [ ] **Step 5: Verify and commit**

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-mintpy/bin/python scripts/74_phase5b_provenance.py --verify
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python -m pytest tests/test_submission_manuscript.py -q
git add manuscript/FIGURE_CLAIM_REGISTRY.csv scripts/77_build_submission_manuscript.py manuscript/SUBMISSION_MANUSCRIPT.md manuscript/SUBMISSION_SUPPLEMENT.md tests/test_submission_manuscript.py
git commit -m "docs: define evidence-linked submission figures"
```

### Task 8: Implement comprehensive submission audits

**Files:**
- Create: `scripts/78_submission_audit.py`
- Modify: `tests/test_submission_manuscript.py`
- Generate: `manuscript/SUBMISSION_AUDIT.json`
- Generate: `manuscript/SUBMISSION_READINESS_V2.md`

**Interfaces:**
- Consumes: manuscript, supplement, BibTeX, claim ledger, figure registry, frozen evidence, and author-input boundary.
- Produces: `run_audit(root: Path) -> AuditReport`; exit 0 only when scientific/citation/provenance gates pass.

- [ ] **Step 1: Write five mutation tests**

Assert audit failure when H001 changes to -31.95, LOS becomes vertical displacement, an unknown citation appears, H002/H005 is removed, or a second build differs.

- [ ] **Step 2: Implement numeric/evidence-state audit**

Check hotspot rates/areas, supported-area sum, operating extent, counts, uncertainty, agreement, and every evidence state against structured sources.

- [ ] **Step 3: Implement terminology/claim audit**

Flag unqualified `vertical`, `validated`, `confirmed`, `proved`, `caused by`, `groundwater-induced`, and `subsidence`. Allow literature attribution or explicit negation only through entries containing line hash, reason, and claim ID.

- [ ] **Step 4: Implement citation/claim coverage audit**

Fail on missing keys, duplicate DOI, empty DOI/URL, missing evidence locator, or material paragraphs without a project claim ID or literature citation. Permit government/software records without DOI only with authoritative URL and access date.

- [ ] **Step 5: Implement structure/figure/determinism audit**

Check headings, 5,500-7,000 words, 6-8 main figures, 2-3 tables, supplement links, provenance membership, and two identical builds.

- [ ] **Step 6: Derive readiness report**

Report scientific freeze, numerical consistency, terminology, claim coverage, citations, figures, structure, reproducibility, and external author input. Scientific gates may pass while author fields remain `AWAITING AUTHOR CONFIRMATION`.

- [ ] **Step 7: Run full verification**

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python scripts/verify_freeze.py
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-mintpy/bin/python scripts/verify_mintpy_input_v1.py
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-mintpy/bin/python scripts/verify_product_v1.py
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-mintpy/bin/python scripts/verify_phase1_observations.py
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-mintpy/bin/python scripts/74_phase5b_provenance.py --verify
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python -m pytest tests/ -o addopts="" -q
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python scripts/78_submission_audit.py
```

- [ ] **Step 8: Commit**

```bash
git add scripts/78_submission_audit.py tests/test_submission_manuscript.py manuscript/SUBMISSION_AUDIT.json manuscript/SUBMISSION_READINESS_V2.md
git commit -m "test: enforce submission manuscript evidence gates"
```

### Task 9: Select target journal and adapt the package

**Files:**
- Create: `manuscript/JOURNAL_SELECTION.md`
- Create: `manuscript/JOURNAL_COMPLIANCE.md`
- Create: `manuscript/COVER_LETTER.md`
- Modify through builders: submission manuscript, bibliography, and readiness report.

**Interfaces:**
- Consumes: current official instructions for three journals.
- Produces: one target, two fallbacks, compliance matrix, final title/format, and cover letter.

- [ ] **Step 1: Screen three journals from official sources**

Compare `International Journal of Applied Earth Observation and Geoinformation`, `Remote Sensing of Environment`, and `IEEE Journal of Selected Topics in Applied Earth Observations and Remote Sensing` on scope, article type, length/figure rules, access model, data/code policy, AI policy, and submission components. Record official URLs and retrieval date.

- [ ] **Step 2: Select by declared weighting**

Score scientific fit 40%, methodological fit 25%, format compatibility 15%, data/code fit 10%, and publication constraints 10%. Select the highest total unless official scope excludes the article.

- [ ] **Step 3: Adapt format without changing claims**

Apply title/abstract limits, heading style, figure/table limits, reference metadata, data availability, and AI-disclosure location. If fewer than eight figures are permitted, consolidate hotspot evidence or move the lowest-ranked registry entry to the supplement without deleting its finding.

- [ ] **Step 4: Write factual cover letter**

State title, article type, central contribution, scope fit, exclusive submission, data/code availability, and author-owned declarations awaiting confirmation. Do not claim `first` unless literature verification supports it.

- [ ] **Step 5: Complete compliance matrix and rerun audits**

Every official requirement records paraphrased requirement, URL, manuscript location, status `PASS` or `AWAITING AUTHOR CONFIRMATION`, and action owner.

- [ ] **Step 6: Commit journal package**

```bash
git add manuscript/JOURNAL_SELECTION.md manuscript/JOURNAL_COMPLIANCE.md manuscript/COVER_LETTER.md manuscript/SUBMISSION_MANUSCRIPT.md manuscript/REFERENCE_LIBRARY.bib manuscript/SUBMISSION_READINESS_V2.md scripts/77_build_submission_manuscript.py scripts/78_submission_audit.py
git commit -m "docs: finalize journal submission package"
```

### Task 10: Conduct final independent review and handoff

**Files:**
- Create: `manuscript/FINAL_REVIEW.md`
- Modify through owning sources as findings require: builder, claim ledger, bibliography, generated manuscript/supplement/audits.

**Interfaces:**
- Consumes: complete journal-specific package.
- Produces: resolved hostile-review findings and author handoff.

- [ ] **Step 1: Run hostile scientific review**

Test circular hotspot definition, shared-data leakage, reference dependence, temporal mismatch, coherence confounding, unsupported causation, novelty overstatement, and missing contradictory literature.

- [ ] **Step 2: Run citation-entailment review**

Classify each literature-dependent sentence as `DIRECT`, `INDIRECT`, `PARTIAL`, or `NONE`. Revise or remove every `PARTIAL`/`NONE` sentence.

- [ ] **Step 3: Run figure/table review**

Verify each item answers its registered question, matches manuscript values, states limitations, is readable at journal size, and does not encode a conclusion only by colour.

- [ ] **Step 4: Resolve fatal and major findings**

Record finding, evidence, resolution, affected files, and verification in `FINAL_REVIEW.md`. An irreducible major issue remains only as `DISCLOSED LIMITATION` already visible in Abstract, Discussion, and Limitations.

- [ ] **Step 5: Run final verification**

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python scripts/77_build_submission_manuscript.py
/opt/homebrew/Caskroom/miniforge/base/envs/delhi-hyp3/bin/python scripts/78_submission_audit.py
git diff --check
git status --short
```

Expected: audit exits 0, no generated drift, zero unresolved fatal flaws, and zero unresolved correctable major concerns.

- [ ] **Step 6: Commit and hand off**

```bash
git add manuscript/FINAL_REVIEW.md manuscript/SUBMISSION_MANUSCRIPT.md manuscript/SUBMISSION_SUPPLEMENT.md manuscript/SUBMISSION_AUDIT.json manuscript/SUBMISSION_READINESS_V2.md manuscript/CLAIM_EVIDENCE_LEDGER.csv manuscript/REFERENCE_LIBRARY.bib scripts/77_build_submission_manuscript.py
git commit -m "docs: complete independent manuscript review"
```

Deliver the manuscript, supplement, figure registry, cover letter, compliance matrix, readiness report, and `AUTHOR_INPUT_REQUIRED.md`. Ask only for the identity and declaration fields listed there.

