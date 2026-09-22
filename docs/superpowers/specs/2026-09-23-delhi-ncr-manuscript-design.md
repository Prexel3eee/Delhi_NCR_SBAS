# Delhi-NCR Cross-Geometry InSAR Manuscript Design

## Purpose

Produce one complete, defensible, submission-ready research article from the
project's frozen Delhi-NCR SBAS-InSAR evidence. The article will report the
observations to the strength supported by the data, distinguish reproducible
features from non-reproducing and contradictory features, and keep physical
mechanism claims within the limits established by the preregistered tests.

The manuscript will be written for an international remote-sensing or applied
Earth-observation journal. It will remain journal-neutral until a target is
selected, after which structure, length, title, references, declarations, and
cover material will be adapted to that journal without changing the underlying
scientific claims.

## Authoritative evidence

The scientific source of truth is the frozen project evidence in this
repository. Authority descends in this order:

1. Hash-pinned freezes and their verification records.
2. Phase-IV synthesis tables and uncertainty records.
3. Phase-specific structured outputs and reports.
4. The project incident and errata record.
5. Verified external literature for context and comparison only.

External papers cannot override project results. The supplied student material
is background guidance, not an authoritative or automatically citable source.
If an idea originating there is important, its original peer-reviewed source
must be located and verified before use.

No frozen measurement, classification, threshold, or evidence state will be
changed during manuscript preparation. Any newly discovered numerical conflict
will be treated as a submission blocker and resolved through the provenance
chain rather than silently reconciled in prose.

## Article type and scale

The deliverable is a full research article, not a short communication and not a
series of minimally separated papers.

Target scale before journal adaptation:

- Main text: approximately 5,500-7,000 words, excluding references and captions.
- Main figures: 6-8 composite figures.
- Main tables: 2-3 concise tables.
- Supplement: reproducible methods, extended diagnostics, incident summary,
  supporting tables, and non-essential figures.

The current compact manuscript is the starting evidence skeleton. It will be
expanded only where scientific reasoning, reproducibility, or literature
positioning requires additional detail.

## Central scientific argument

The article's organizing claim is:

> Independent ascending and descending Sentinel-1 observations selectively
> support localized mean-rate relative LOS deformation at H001 and H004, do not
> reproduce H002 and H003 despite adequate descending quality, and leave H005 as
> an unresolved cross-geometry contradiction. The supported observations do not
> establish matching temporal histories, vertical displacement, an absolute
> rate, or a physical mechanism.

This is supported by four linked contributions:

1. **Independent observation design.** The descending stack was constructed
   without sharing bursts, pairs, masks, or acquisition selection with the
   ascending stack.
2. **Selective reproduction.** H001 and H004 reproduce at the spatial/mean-rate
   level; H002 and H003 are negative controls; H005 contradicts across geometry.
3. **Causal restraint through explicit tests.** Groundwater, shallow texture,
   and urban intensity were tested under declared rules and did not support the
   proposed mechanisms; deep structure and construction remain inadequately
   tested or not testable.
4. **Auditable uncertainty.** Statistical, reference, processing, temporal, and
   structural uncertainties remain separate rather than being collapsed into an
   unjustified single error term.

The paper will not be framed primarily as a new subsidence map. Its novelty is
the evidence design used to separate reproducible observations from attractive
but unsupported interpretation.

## Protected terminology and claim boundaries

The following distinctions are mandatory throughout the article, supplement,
captions, abstract, title, and cover material:

- Relative LOS deformation is not vertical displacement.
- Relative velocity is not an absolute geodetic rate.
- Independently supported spatial/mean-rate behavior is not independently
  validated time history.
- `NO EVIDENCE` is not equivalent to disproved or ruled out.
- `NOT ADEQUATELY TESTED` is distinct from a negative result.
- `NOT TESTABLE` identifies absence of a suitable dataset.
- The 22.6 km2 value is a mask-dependent operating extent.
- The 6.66 km2 value is the summed Phase-I zone area for H001 and H004 supported
  at hotspot level, not a validated continuous deformation footprint.
- H005 must remain an unresolved contradiction and must not enter causal tests.
- Uncertainty components will not be summed without a valid probabilistic model.

Words such as `validated`, `confirmed`, `proved`, `subsidence`, and `caused by`
will be used only when the exact sentence has evidence appropriate to that
strength. Otherwise the manuscript will use `supports`, `is consistent with`,
`suggests`, or an explicit statement of insufficiency.

## Manuscript architecture

### Title

The journal-neutral working title is:

**Selective reproducibility of localized LOS deformation in Delhi-NCR from
ascending and descending Sentinel-1 InSAR**

The final title may change after journal selection, but it must retain the
cross-geometry design, Delhi-NCR scope, and non-causal wording.

### Abstract

The abstract will follow a five-part logical sequence without headings unless
required by the journal:

1. Why urban deformation interpretation requires independent observation.
2. Ascending and independently built descending Sentinel-1/MintPy datasets.
3. Numerical hotspot-level cross-geometry outcomes.
4. Results of the preregistered mechanism tests and uncertainty qualification.
5. The methodological implication: reproduction is selective, and mechanism
   does not follow automatically from a coherent deformation feature.

Every number in the abstract must have a direct frozen source. The abstract
will not contain citations unless required by the target journal.

### 1. Introduction

The introduction will be an argument rather than a catalogue of studies:

1. Urban deformation matters, but InSAR interpretation is vulnerable to
   geometry, reference, atmosphere, coherence, unwrapping, and causal
   confounding.
2. Delhi-NCR has reported deformation and groundwater stress, with Garg et al.
   as the principal regional comparator.
3. Prior spatial association does not by itself test reproducibility or causal
   selectivity.
4. The unresolved problem is whether localized anomalies survive an independent
   viewing geometry and whether proposed mechanisms explain supported zones
   better than negative controls.
5. State the study objectives and the preregistered logic.

The literature review will be thematic: Delhi-NCR evidence, multigeometry
validation, uncertainty/reference effects, and mechanism attribution. It will
not summarize papers one by one.

### 2. Data and methods

The main text will present enough detail for scientific evaluation while the
supplement retains operational implementation detail.

Required subsections:

1. Study area and observation period.
2. Ascending burst inventory, SBAS network, HyP3 processing, and MintPy
   inversion.
3. Correction-branch testing and selection of the authoritative RAW-336 branch.
4. Phase-I hotspot definition and frozen observation set.
5. Independent descending design, network, processing, reliability tests, and
   selected unwrap-corrected product.
6. Common-domain alignment and hotspot-level cross-geometry comparison.
7. Preregistered groundwater analysis and falsification lags.
8. Geological and urban evidence tests.
9. Uncertainty framework and evidence-state definitions.

Methods will report actual parameter values, software versions, thresholds,
sample sizes, exclusions, and decision rules. No method will be described as
`advanced`, `robust`, or `high accuracy` without a measurable definition.

### 3. Results

Results will report observations without importing physical explanations.

Required order:

1. Ascending deformation field and quality-limited zone definition.
2. Descending product reliability and correction decision.
3. Common-domain cross-geometry comparison.
4. H001/H004 independently supported mean-rate observations.
5. H002/H003 non-reproduction as negative controls.
6. H005 contradiction.
7. Temporal-history disagreement and non-stationarity.
8. Uncertainty and sensitivity results.
9. Outcomes of groundwater, shallow geology, deep geology, urban intensity,
   expansion, and construction tests.

The results section will preserve negative findings with the same numerical
specificity as supported findings.

### 4. Discussion

The discussion will proceed claim by claim:

1. What independent reproduction establishes for H001 and H004.
2. Why it does not establish vertical motion or matching temporal history.
3. Why H002/H003 are scientifically informative negative controls.
4. Why H005 prevents a single simple interpretation of all detected zones.
5. Comparison with Garg et al. and other regional studies, explicitly accounting
   for different periods, locations, methods, and causal evidence.
6. Why groundwater, shallow texture, and generic urbanization fail the
   selectivity test in this dataset.
7. Plausible remaining explanations, labelled as alternatives rather than
   conclusions.
8. Implications for how urban InSAR studies should validate anomalies and infer
   mechanisms.

Contradictory literature will be retained. The discussion will not manufacture
agreement by averaging incompatible study designs.

### 5. Limitations

Limitations will state the affected inference and consequence:

- No independent in-AOI continuous geodetic reference: absolute rate remains
  uncertain.
- LOS projection and weak north-south sensitivity: no published vertical/east
  decomposition.
- Incomplete descending AOI coverage: inference is restricted to the common
  domain and frozen hotspot polygons.
- Different temporal sampling between geometries: mean-rate reproduction does
  not validate detailed time histories.
- Coherence-velocity association remains unresolved.
- Hydrogeological observations lack sufficient depth/aquifer specificity.
- Construction chronology is unavailable.
- H005 remains unresolved.

### 6. Conclusion

The conclusion will contain only claims already demonstrated in the Results and
qualified in the Discussion. It will end with the scientific consequence of the
negative controls, not a generic call for more research.

## Figure and table architecture

### Main figures

1. Study area, independent geometries, and analysis design.
2. Ascending relative LOS velocity and frozen Phase-I zones.
3. Cross-geometry classification of H001-H005.
4. H001/H004 independently supported spatial and mean-rate behavior.
5. H002/H003 negative controls under adequate descending quality.
6. H005 unresolved contradiction and geometry-specific evidence.
7. Groundwater temporal forcing and falsification-lag diagnostic.
8. Final competing-hypothesis evidence matrix.

If journal limits require six figures, Figures 4-6 will be consolidated into a
single multi-panel hotspot evidence figure. No figure will be redrawn in a way
that changes the frozen sample definition.

### Main tables

1. Data, network, processing, and product summary by geometry.
2. Hotspot-level ascending/descending measurements, quality, and classification.
3. Hypothesis, prediction, test, result, and evidence state, if not fully carried
   by Figure 8.

### Supplement

The supplement will contain detailed network diagnostics, correction branches,
reference sensitivity, uncertainty components, groundwater station screening,
geology and urban dataset registries, extended tables, figure provenance, and
the condensed reproducibility incident record.

Every figure must answer a declared scientific question and map to at least one
manuscript claim. Decorative or duplicative figures will be removed or moved to
the supplement.

## Literature and citation protocol

Each core source receives a paper record containing:

- Verified citation and DOI.
- Study region and period.
- Sensor, geometry, and method.
- Validation design.
- Main numerical result.
- Claimed mechanism and actual supporting evidence.
- Author-acknowledged limitations.
- Exact relevance to this manuscript.
- Exact pages or sections supporting each cited claim.

Garg et al. is the principal Delhi-NCR comparator. It will be discussed fairly:
its observations and interpretation will be reported accurately, while the new
study's later period, frozen zones, independent descending construction,
negative controls, and preregistered causal tests will define the difference.

The other supplied papers may support method or regional context after direct
claim verification. They will not be cited merely because they concern urban
subsidence. Discovery sources and student-prepared notes are not citations.

No citation enters the manuscript until the original paper or authoritative
record has been opened and shown to support the exact sentence. Bibliographic
metadata will be verified against DOI and journal records; missing metadata will
remain visibly unresolved rather than invented.

## Authorship and declarations

The following will remain structured placeholders until the owner supplies or
confirms them:

- Author names and order.
- Affiliations.
- Corresponding author and email.
- CRediT contributions.
- Funding.
- Acknowledgements.
- Conflicts of interest.
- Ethics statements if required by the journal.
- AI-assistance disclosure in the form required by the selected journal.

AI tools will not be listed as authors. Human authors retain responsibility for
the science, wording, citations, originality, and final submission.

## Quality assurance and acceptance gates

The manuscript is complete only when all gates pass:

### Scientific consistency

- Every main numerical value matches a frozen authoritative source.
- H001-H005 classifications match the final hotspot table.
- No withdrawn decomposition result is presented as valid.
- Evidence states retain their exact meanings.

### Claim traceability

- Every abstract and conclusion sentence maps to a result, evidence-table row,
  or verified literature source.
- Every causal statement is either directly tested or clearly labelled as a
  hypothesis/alternative.
- Negative and contradictory evidence is not omitted.

### Citation integrity

- Every citation exists and has verified metadata.
- Every cited source supports the exact sentence.
- No citation is introduced from an unverified AI suggestion.
- The final reference list contains no placeholders.

### Reproducibility

- All project freezes verify with zero drift.
- Figure provenance verifies.
- Main methods expose the scientific decision rules; implementation detail is
  available in the supplement and repository.
- Data and code availability statements match actual repository contents and
  access limitations.

### Communication

- Results and Discussion remain distinct.
- Title and abstract avoid causal or vertical-motion overstatement.
- All maps include units, scale, orientation, projection/context, geometry,
  reference convention, and sample/mask definition as applicable.
- Figures remain legible at journal reproduction size and do not depend on
  colour alone.

### Independent review

- A hostile scientific review identifies no unresolved fatal flaw.
- A methodological review identifies no undocumented decision affecting a
  conclusion.
- A citation audit has no unsupported or partially supported main-text claims.
- Journal instructions are satisfied after target selection.

## Execution boundaries

Manuscript preparation may revise prose, organization, figure composition,
captions, references, and submission documents. It may read and verify frozen
artefacts and regenerate publication views from frozen inputs.

It may not:

- Alter frozen scientific data or decisions.
- Introduce a new correction or processing branch as if it belonged to the
  completed study.
- Reclassify a hotspot without reopening the scientific investigation under a
  separately approved protocol.
- Attribute deformation to groundwater, geology, urbanisation, or construction
  beyond the frozen evidence state.
- Invent author details, affiliations, funding, conflicts, or citations.

Any improvement requiring new scientific analysis will be documented as a
future study rather than silently added to the submission dataset.

