# Delhi-NCR SBAS-InSAR via HyP3 Multi-Burst + MintPy
## Autonomous Implementation Brief for the Execution Agent

**Document status:** Implementation-ready  
**Primary objective:** Build a research-grade Sentinel-1 SBAS-InSAR time-series workflow for the Delhi-NCR AOI using **ASF HyP3 `INSAR_ISCE_MULTI_BURST`** for interferogram generation and **MintPy** for time-series inversion, QC, displacement, velocity, and interpretation.

---

## 0. Executive directive to the agent

You are the implementation agent for this project.

Your job is to **carry the workflow from burst discovery through a validated HyP3 multi-burst interferogram stack and into a MintPy-ready time-series dataset**, while preserving scientific reproducibility and avoiding unnecessary processing.

Proceed autonomously through all non-consequential engineering and data-discovery work. Do **not** ask the user routine questions that can be resolved by inspection, official ASF documentation, or programmatic checks.

### Hard safety / cost gate

Do **not** submit the full production HyP3 job set until all of the following are true:

1. The exact burst collection is validated.
2. Every retained acquisition date contains the same valid burst set.
3. The burst-level SBAS network has been generated and audited.
4. A pilot set has been processed successfully.
5. Pilot outputs pass QC.
6. Exact production credit cost has been calculated.
7. The user has approved the production submission if it will consume a material amount of HyP3 credits.

A small pilot submission is allowed only after its cost is calculated and shown clearly.

---

# 1. Scientific objective

Use Sentinel-1 C-band SAR data to measure the spatial and temporal evolution of ground deformation over the specified Delhi-NCR study area using **Small Baseline Subset InSAR (SBAS-InSAR)**.

The target scientific outputs are:

- line-of-sight (LOS) displacement time series;
- mean LOS velocity;
- deformation hotspots;
- uncertainty / reliability layers;
- temporal behavior at selected locations;
- optional acceleration / nonlinear trend analysis if justified;
- optional seasonal analysis if supported by the data;
- later comparison with descending geometry if the project is extended.

This is a **time-series deformation study**, not a single-pair DInSAR exercise.

---

# 2. Frozen project inputs

## 2.1 Area of Interest

Use this AOI exactly unless a later scientific decision explicitly changes it:

```text
POLYGON((76.7853 28.4375,77.1951 28.3839,77.2562 28.6599,77.2838 28.8193,76.8905 28.8726,76.7853 28.4375))
```

Coordinate order is:

```text
longitude latitude
```

## 2.2 Time period

Target search interval:

```text
Start: 2021-10-01
End:   2025-10-01
```

The earlier full-scene reconnaissance showed actual usable acquisitions approximately from:

```text
2021-10-06
through
2025-09-27
```

Do **not** assume those exact endpoints until the burst-level search confirms them.

## 2.3 Orbit geometry

Current primary geometry:

```text
Flight direction: ASCENDING
Relative orbit / path: 27
Polarization: VV
Beam mode: IW
```

Use **VV**, not VH, for interferometry.

## 2.4 Processing architecture

The selected architecture is:

```text
Sentinel-1 Burst SLC discovery
        ↓
fixed geographic burst collection
        ↓
burst stack discovery through time
        ↓
burst-level SBAS pair construction
        ↓
network audit
        ↓
HyP3 INSAR_ISCE_MULTI_BURST
        ↓
ISCE2 interferogram generation
        ↓
HyP3 geocoded products
        ↓
common-overlap preparation
        ↓
MintPy
        ↓
SBAS time-series inversion
        ↓
LOS displacement / velocity / QC / interpretation
```

Do not revert to the local full-scene ISCE2 workflow unless HyP3 multi-burst proves technically impossible.

---

# 3. What has already been learned from full-scene reconnaissance

This information is **context and prior evidence**, not the final burst-level network.

The full-scene ASF Vertex investigation found:

```text
Ascending path: 27
Candidate frame: 86
Period searched: 2021-10-01 → 2025-10-01
```

A full-scene SBAS design using:

```text
maximum temporal baseline: 36 days
maximum perpendicular baseline: 250 m
latitudinal overlap: Any Overlap
```

produced the following exported network:

```text
120 unique SLC acquisitions
341 interferometric pairs
first acquisition: 2021-10-06
last acquisition: 2025-09-27
```

Independent audit of the exported ASF CSV showed:

```text
connected components: 1
minimum node degree: 3
maximum node degree: 6
mean node degree: 5.6833
median node degree: 6
bridges: 0
articulation points: 0

acquisition gaps:
117 × 12-day gaps
2 × 24-day gaps
maximum acquisition gap: 24 days

pair temporal-baseline distribution:
114 × 12 days
115 × 24 days
112 × 36 days

pair |B_perp|:
median: 67 m
95th percentile: 181 m
maximum: 239 m
```

The 50% whole-scene latitudinal-overlap filter had reduced the same stack to 99 acquisitions / 278 pairs and excluded the 2025 tail. Switching to “Any Overlap” restored the missing dates. This reinforced the decision to move to burst-based processing because Sentinel-1 burst footprints are geographically consistent through time while full IW-SLC framing can shift.

### Important

**Do not directly submit these 341 full-scene pairs as multi-burst jobs.**

The burst-level stack must be rebuilt from the selected Full Burst IDs. The earlier 36-day / 250-m design should be treated as a **strong starting hypothesis**, then revalidated at burst level.

---

# 4. Why Multi-Burst HyP3 is the selected approach

ASF’s current burst InSAR system uses **ISCE2**.

The `INSAR_ISCE_MULTI_BURST` job type:

- accepts multiple Sentinel-1 burst SLCs;
- merges them into one interferogram;
- supports 1–15 contiguous along-track bursts;
- is currently submitted through the HyP3 API / Python SDK rather than Vertex;
- returns geocoded interferometric products including coherence, unwrapped phase and connected components;
- avoids processing the enormous unused portion of a full IW-SLC scene;
- keeps burst geography stable through time.

This is especially appropriate here because the research AOI is much smaller than a complete Sentinel-1 IW SLC footprint.

---

# 5. Official multi-burst constraints — treat these as hard validation rules

Before any HyP3 multi-burst submission, validate all of the following.

## 5.1 Burst collection rules

A valid reference or secondary burst set must satisfy:

- 1 to 15 bursts total;
- bursts must be contiguous along a single relative orbit path;
- reference and secondary sets must contain the same number of bursts;
- all bursts must use the same co-polarization;
- use **VV** for this project;
- corresponding reference and secondary bursts must have the same relative orbit number;
- corresponding reference and secondary bursts must have the same burst number / geographic burst identity;
- all reference bursts must have been acquired within two minutes of one another;
- all secondary bursts must have been acquired within two minutes of one another;
- reference acquisition must be earlier than secondary acquisition;
- antimeridian-crossing burst collections are unsupported;
- if bursts span neighboring sub-swaths, their along-track offset must not exceed one burst;
- build a compact rectangular / gap-free collection;
- do not construct L-shaped or T-shaped burst collections.

## 5.2 Spatial design principle

Choose the **smallest valid burst collection that fully covers the scientific AOI with sensible edge margin**.

Do not include extra bursts merely because they are available. Every additional burst can increase processing credits, file size and processing time.

---

# 6. Phase A — repository and reproducibility setup

Create a project directory similar to:

```text
delhi_ncr_multiburst_sbas/
├── README.md
├── environment.yml
├── requirements-lock.txt
├── config/
│   └── project.yaml
├── notebooks/
├── scripts/
│   ├── 01_discover_bursts.py
│   ├── 02_build_burst_stacks.py
│   ├── 03_build_sbas_network.py
│   ├── 04_audit_network.py
│   ├── 05_estimate_hyp3_cost.py
│   ├── 06_submit_pilot.py
│   ├── 07_qc_pilot.py
│   ├── 08_submit_production.py
│   ├── 09_download_products.py
│   └── 10_prepare_mintpy.py
├── manifests/
│   ├── geographic_reference_bursts.csv
│   ├── acquisition_burst_matrix.csv
│   ├── accepted_acquisitions.csv
│   ├── sbas_pairs.csv
│   ├── hyp3_jobs.csv
│   └── product_inventory.csv
├── geometry/
│   ├── aoi.geojson
│   ├── selected_bursts.geojson
│   └── coverage_report.json
├── qc/
│   ├── network/
│   ├── pilot/
│   └── production/
├── logs/
├── state/
└── data/
    ├── hyp3_zips/
    ├── hyp3_extracted/
    └── mintpy/
```

Do not store Earthdata passwords, tokens, cookies or `.netrc` contents in the repository.

Record package versions in every run:

```python
import importlib.metadata as md

for package in ["asf_search", "hyp3_sdk", "mintpy", "networkx", "pandas"]:
    try:
        print(package, md.version(package))
    except Exception:
        pass
```

---

# 7. Recommended environment

ASF’s current burst-to-MintPy tutorial uses modern `asf_search`, `hyp3_sdk` and MintPy.

A reasonable environment is:

```bash
conda create -n delhi-hyp3-sbas python=3.12 -y
conda activate delhi-hyp3-sbas

conda install -c conda-forge \
  "asf_search>=7.0.0" \
  "hyp3_sdk>=7.7.0" \
  "mintpy>=1.6.3" \
  pandas \
  networkx \
  shapely \
  geopandas \
  rasterio \
  gdal \
  matplotlib \
  jupyter \
  ipympl
```

After the first fully successful run, freeze the actual environment:

```bash
conda env export --from-history > environment.yml
python -m pip freeze > requirements-lock.txt
```

Do not blindly downgrade current `asf_search` just to make old examples work. If a public API changed, inspect the installed package signature and current ASF documentation, then adapt.

---

# 8. Project configuration file

Create `config/project.yaml` with a structure like:

```yaml
project:
  name: delhi_ncr_multiburst_sbas
  description: Delhi-NCR Sentinel-1 ascending SBAS-InSAR with HyP3 multi-burst + MintPy

aoi:
  wkt: "POLYGON((76.7853 28.4375,77.1951 28.3839,77.2562 28.6599,77.2838 28.8193,76.8905 28.8726,76.7853 28.4375))"

search:
  start: "2021-10-01T00:00:00Z"
  end: "2025-10-01T23:59:59Z"
  platform: "Sentinel-1"
  beam_mode: "IW"
  polarization: "VV"
  flight_direction: "ASCENDING"
  relative_orbit: 27

sbas:
  temporal_baseline_days_initial: 36
  perpendicular_baseline_m_initial: 250

hyp3:
  service: "basic"
  looks_pilot: "10x2"
  apply_water_mask_pilot: true

production:
  submission_requires_approval: true
```

The burst IDs are not yet known. Add them only after Phase B validation.

---

# 9. Phase B — identify the geographic reference burst collection

## Goal

Find the exact set of Full Burst IDs that covers the AOI on ascending path 27.

## Preferred discovery procedure

Use ASF Vertex:

```text
Search Type: Geographic
Dataset: S1 Bursts
AOI: exact WKT above
Flight Direction: Ascending
Relative Orbit: 27
Polarization: VV
Beam Mode: IW
```

Use one representative acquisition date with known coverage, preferably near the middle or end of the target period.

The official ASF multi-burst tutorial explicitly recommends using Vertex Geographic Search to identify the initial geographic burst collection.

## What to record for every candidate burst

At minimum:

```text
sceneName / burst granule ID
Full Burst ID
relative burst ID
sub-swath (IW1 / IW2 / IW3)
relative orbit
flight direction
polarization
acquisition time
geometry
platform
```

## Selection algorithm

1. Collect all VV bursts intersecting the AOI for one representative date.
2. Build the union geometry.
3. Find the smallest valid contiguous set whose union fully covers the AOI.
4. Prefer a compact rectangular collection.
5. Add a small margin only if needed to avoid placing AOI boundaries directly on burst edges.
6. Validate all multi-burst rules.
7. Save the selected burst geometries to:
   - `geometry/selected_bursts.geojson`
   - `manifests/geographic_reference_bursts.csv`

## Required acceptance gate

Do not proceed until:

```text
AOI fully contained in selected-burst union: YES
burst count <= 15: YES
single relative orbit: YES (27)
single polarization: YES (VV)
contiguous / gap-free: YES
valid cross-subswath geometry: YES
```

Also record the exact number of bursts `K`, because HyP3 credit cost depends strongly on `K`.

---

# 10. Phase C — discover the same burst footprints through time

Once the geographic reference burst names are known, follow the ASF multi-burst pattern.

The official tutorial does:

```python
results = asf.granule_search(geo_ref_bursts)

opts = asf.ASFSearchOptions(
    start=start_date,
    end=end_date,
)

stacks = [slc.stack(opts=opts) for slc in results]
```

Adapt that idea to this project.

## Critical requirement

Every accepted acquisition date must contain the **same geographic burst identities**.

Construct an acquisition × burst matrix:

```text
date        burst_A  burst_B  burst_C  ...
2021-10-06  yes      yes      yes
2021-10-18  yes      yes      yes
...
2025-09-27  yes      yes      yes
```

Save as:

```text
manifests/acquisition_burst_matrix.csv
```

## Fail-closed rule

If an acquisition date is missing even one required burst:

- do not silently create a smaller burst set for that date;
- do not submit a mismatched multi-burst pair;
- exclude the incomplete acquisition from the homogeneous production stack unless there is a documented, scientifically justified redesign of the entire burst collection.

## Also check

For every date:

- all bursts are path 27;
- all are ascending;
- all are VV;
- all burst identities match the geographic reference set;
- acquisition times within the set are within the HyP3 limit;
- geometry is stable.

---

# 11. Phase D — build the burst-level SBAS pair network

## Starting thresholds

Begin with the empirically supported full-scene values:

```text
max temporal baseline: 36 days
max perpendicular baseline: 250 m
```

These are **starting values**, not immutable truth.

The burst-level network must be recomputed.

## Important implementation improvement over a simple positional `zip`

ASF’s tutorial demonstrates constructing a pair list for each burst stack and then transposing the lists with `zip(*pairs)`.

For production-grade code, do **not** rely solely on list position because unequal pair lists could silently truncate or misalign.

Instead:

### 11.1 Build a pair dictionary per geographic burst

Use a canonical pair key such as:

```python
(ref_acquisition_date, sec_acquisition_date)
```

For each burst stack:

```python
pair_map[burst_id][pair_key] = pair
```

### 11.2 Compute common pair keys

```python
common_pair_keys = intersection_of_all_pair_key_sets
```

Only pair dates available for **every selected burst** can become a valid multi-burst interferogram.

### 11.3 Construct one HyP3 job payload per pair key

For each accepted pair key:

```text
reference = [burst_A_ref, burst_B_ref, burst_C_ref, ...]
secondary = [burst_A_sec, burst_B_sec, burst_C_sec, ...]
```

The ordering of bursts must be deterministic and identical between reference and secondary lists.

### 11.4 Validate before accepting

For each multi-burst pair:

```text
len(reference) == len(secondary) == K
all same polarization
all same relative orbit
reference older than secondary
pairwise burst identities match
temporal baseline <= configured maximum
perpendicular baseline <= configured maximum
```

Save final pair manifest:

```text
manifests/sbas_pairs.csv
```

Include:

```text
pair_id
reference_date
secondary_date
temporal_baseline_days
perpendicular_baseline_m
burst_count
reference_burst_ids_json
secondary_burst_ids_json
```

---

# 12. Network audit — mandatory before HyP3 production

Treat acquisition dates as graph nodes and candidate multi-burst interferograms as graph edges.

Use `networkx`.

Calculate and report:

```text
number of acquisition nodes
number of pair edges
number of connected components
node degree distribution
minimum / mean / median / maximum degree
bridge edges
articulation points
acquisition-date gaps
pair temporal-baseline distribution
pair perpendicular-baseline distribution
```

Generate:

```text
qc/network/network_summary.json
qc/network/network_edges.csv
qc/network/network_degree.csv
qc/network/baseline_time_plot.png
qc/network/degree_histogram.png
```

## Preferred acceptance criteria

The production network should ideally satisfy:

```text
connected components = 1
no isolated nodes
bridges = 0
articulation points = 0
minimum degree >= 3, allowing temporal endpoints to be the weakest nodes
no unexplained long acquisition gaps
```

If those criteria are not satisfied, adjust the baseline thresholds deliberately.

## Threshold tuning policy

Do not over-optimize.

Use this order:

1. Preserve acquisition continuity.
2. Preserve graph connectivity.
3. Preserve redundancy.
4. Then minimize temporal and perpendicular baselines.

A 36-day network with moderate redundancy is preferable to a 12-day near-chain that is fragile.

---

# 13. Phase E — estimate HyP3 cost before submitting anything

HyP3 Basic currently provides **8,000 free credits per month**.

Multi-burst credit cost depends on:

- number of burst pairs inside each multi-burst job (`K`);
- requested looks.

## Current HyP3 Basic burst-InSAR credit table

### 20x4 looks
Approx. 160 m resolution / 80 m pixel spacing:

```text
K = 1–4    → 1 credit/job
K = 5–12   → 5 credits/job
K = 13–15  → 10 credits/job
```

### 10x2 looks
Approx. 80 m resolution / 40 m pixel spacing:

```text
K = 1–3    → 1 credit/job
K = 4–9    → 5 credits/job
K = 10–15  → 10 credits/job
```

### 5x1 looks
Approx. 40 m resolution / 20 m pixel spacing:

```text
K = 1  → 1
K = 2  → 5
K = 3  → 10
K = 4  → 15
K = 5  → 20
K = 6  → 25
K = 7  → 30
K = 8  → 35
K = 9  → 40
K = 10 → 45
K = 11 → 90
K = 12 → 95
K = 13 → 100
K = 14 → 105
K = 15 → 110
credits/job
```

Implement `scripts/05_estimate_hyp3_cost.py`.

It must print:

```text
number of bursts K
number of multi-burst interferograms N
looks
credits/job
total credits
percentage of monthly HyP3 Basic allocation
```

Do not assume the old 341 full-scene pair count will equal the burst-level count.

---

# 14. Recommended output resolution strategy

## Initial recommendation

For an urban subsidence study, begin the pilot with:

```text
looks = "10x2"
pixel spacing = 40 m
nominal resolution = 80 m
```

This is a practical middle ground between spatial detail and storage / processing cost.

Do not immediately process the full stack at `5x1`.

If the scientific question later proves that 40-m pixels are insufficient, compare a small pilot pair at `5x1` before committing to a high-cost production run.

---

# 15. Water mask strategy

HyP3 water masking is optional and is applied before phase unwrapping.

For Delhi-NCR, the Yamuna and other water bodies make water masking worth testing.

Recommended pilot strategy:

```text
Primary pilot: apply_water_mask=True
```

For one representative pair, optionally process the same pair with:

```text
apply_water_mask=False
```

Compare unwrapping and connected-components behavior near water.

Do not automatically conclude that masking is always superior; use the pilot.

Note: for multi-burst products, the water-mask GeoTIFF is included only when the water mask option is selected.

---

# 16. Phase F — pilot before production

Do not submit the full network first.

Select approximately 4–6 representative multi-burst pairs.

The pilot should include examples such as:

```text
one 12-day pair with low |B_perp|
one 24-day pair
one 36-day pair
one pair near the upper accepted |B_perp|
one monsoon-season pair if available
one dry-season pair if available
```

Try to cover early, middle and late portions of the time series.

## Pilot submission API

Current HyP3 SDK interface:

```python
hyp3.submit_insar_isce_multi_burst_job(
    reference=[...],
    secondary=[...],
    name="delhi_ncr_multiburst_pilot",
    apply_water_mask=True,
    looks="10x2",
)
```

The official SDK currently accepts:

```text
looks = "20x4" | "10x2" | "5x1"
```

## Authentication

Use NASA Earthdata Login.

Do not hardcode credentials.

ASF examples use:

```python
import hyp3_sdk as sdk

hyp3 = sdk.HyP3(prompt="password")
```

If using `.netrc`, ensure it is outside version control and has restrictive permissions.

---

# 17. Pilot QC gate

For every completed pilot product:

1. Download and extract the product.
2. Verify required files exist.
3. Verify CRS / pixel size / dimensions.
4. Verify AOI is fully covered.
5. Inspect coherence.
6. Inspect unwrapped phase.
7. Inspect connected components.
8. Inspect edge artifacts.
9. Inspect behavior around water.
10. Confirm reference/secondary dates and metadata.
11. Confirm all multi-burst output geometry is consistent between jobs.

Expected important layers include:

```text
*_corr.tif
*_unw_phase.tif
*_conncomp.tif
*_dem.tif
*_lv_theta.tif
*_lv_phi.tif
*_water_mask.tif    # only when water mask requested
```

HyP3 multi-burst outputs are geocoded GeoTIFF products in an appropriate UTM projection.

## Suggested quantitative pilot metrics

Inside the AOI calculate:

```text
valid-pixel fraction
median coherence
25th percentile coherence
fraction of pixels above selected coherence thresholds
largest connected-component coverage
number of connected components intersecting AOI
nodata fraction
```

Do not invent universal pass/fail coherence numbers. Use spatial inspection and distribution statistics together.

---

# 18. Pilot pass criteria

Proceed to production only if:

```text
AOI fully covered in all pilot products
no gross geolocation mismatch
no systematic edge clipping
unwrapped phase is usable over the land area
connected components are sensible
water-mask choice is justified
product geometry is consistent
MintPy preparation test succeeds on the pilot subset
```

If a pilot fails, diagnose before submitting more jobs.

---

# 19. Phase G — production submission

After user approval and pilot pass:

1. Freeze the pair manifest.
2. Hash it.
3. Freeze the selected-burst manifest.
4. Freeze HyP3 options.
5. Calculate exact credits.
6. Submit jobs in deterministic batches.
7. Persist HyP3 job IDs immediately.

Use a stable job name prefix such as:

```text
delhi_ncr_sbas_a27_v1
```

Do not rely only on date-of-submission to find jobs later.

Persist:

```text
job_id
pair_id
reference_date
secondary_date
status
submitted_at
HyP3 options
```

to:

```text
manifests/hyp3_jobs.csv
```

## Idempotency

Before submitting any pair, check whether a job with the same project name and pair identity already exists.

Do not duplicate paid/credit-consuming processing after a script restart.

---

# 20. Monitoring and retry policy

Use HyP3 SDK batch monitoring.

ASF’s tutorial uses:

```python
multiburst_jobs = hyp3.watch(multiburst_jobs)
```

For production:

- monitor status;
- persist failures;
- retry only failed jobs;
- do not resubmit completed jobs;
- record failure message verbatim;
- separate transient service failure from invalid-input failure.

Fail closed if the failure suggests an invalid burst collection.

---

# 21. Product retention and download urgency

HyP3 Basic currently retains output products for **14 days**.

Therefore:

- download completed products promptly;
- verify local file integrity;
- do not assume HyP3 will serve as permanent storage.

Save downloads to:

```text
data/hyp3_zips/
```

Extract to:

```text
data/hyp3_extracted/
```

Maintain a product inventory including:

```text
job_id
pair_id
zip filename
product directory
download timestamp
file size
hash
processing status
```

---

# 22. Phase H — MintPy preparation

The official ASF ISCE2-burst + MintPy tutorial performs the following high-level workflow:

1. download/extract HyP3 products;
2. determine the common spatial overlap of all product GeoTIFFs;
3. clip the MintPy input layers to the common overlap;
4. configure MintPy with `processor = hyp3`;
5. load unwrapped phase, coherence, connected components, DEM and look vectors;
6. run `smallbaselineApp.py`.

## Common overlap

Do **not** assume every geocoded product has byte-identical raster extents.

Compute the common overlap from the product DEM / raster corners.

Clip all MintPy-relevant layers consistently.

Required layers typically include:

```text
*_corr.tif
*_conncomp.tif
*_unw_phase.tif
*_dem.tif
*_lv_theta.tif
*_lv_phi.tif
*_water_mask.tif   # if water mask was enabled
```

Use exactly the same crop window for all products/layers.

---

# 23. MintPy configuration starting point

Create a config similar to:

```text
mintpy.load.processor        = hyp3

## interferograms
mintpy.load.unwFile          = <DATA_DIR>/*/*_unw_phase_clipped.tif
mintpy.load.corFile          = <DATA_DIR>/*/*_corr_clipped.tif
mintpy.load.connCompFile     = <DATA_DIR>/*/*_conncomp_clipped.tif

## geometry
mintpy.load.demFile          = <DATA_DIR>/*/*_dem_clipped.tif
mintpy.load.incAngleFile     = <DATA_DIR>/*/*_lv_theta_clipped.tif
mintpy.load.azAngleFile      = <DATA_DIR>/*/*_lv_phi_clipped.tif
mintpy.load.waterMaskFile    = <DATA_DIR>/*/*_water_mask_clipped.tif

mintpy.plot                  = no
```

ASF’s minimal example also uses:

```text
mintpy.network.coherenceBased = no
mintpy.troposphericDelay.method = no
```

Do **not** treat those two settings as scientifically final.

They are a minimal tutorial starting point.

For this research project, atmospheric correction, network QC, reference-area selection and residual-error handling must be considered explicitly after the basic stack is proven to load correctly.

Run:

```bash
smallbaselineApp.py --dir <WORK_DIR> <MINTPY_CONFIG>
```

---

# 24. MintPy validation sequence

Do not run every correction blindly at once.

Use staged validation.

## Stage 1 — ingestion

Confirm:

```text
all expected interferograms loaded
all expected dates loaded
geometry rasters valid
connected-components files recognized
no unexpected dimension/CRS mismatch
```

## Stage 2 — network

Compare MintPy’s loaded network against:

```text
manifests/sbas_pairs.csv
```

The counts and pair identities must agree.

## Stage 3 — raw time series

Produce the initial displacement time series and velocity.

## Stage 4 — reference selection

Select a physically stable reference area using:

- temporal coherence;
- spatial stability;
- geology / land-use context;
- absence of known active subsidence if possible.

Do not simply accept an automatically selected pixel without inspection.

## Stage 5 — unwrapping / network QC

Use connected components, coherence and residual behavior to identify poor interferograms.

Do not remove pairs solely because they look visually noisy; document objective reasoning.

## Stage 6 — atmospheric / residual corrections

Evaluate relevant MintPy correction options separately.

Compare corrected and uncorrected results.

Do not interpret a deformation hotspot until atmospheric artifacts have been considered.

---

# 25. Core scientific outputs

At minimum deliver:

```text
mean LOS velocity map
cumulative LOS displacement maps
displacement time series
temporal coherence / reliability information
network plot
coherence summaries
connected-component QC
selected stable reference area
uncertainty / residual diagnostics
```

Optional if supported:

```text
acceleration
seasonal harmonic component
change-point behavior
hotspot polygons
spatial statistics
```

Do not label LOS velocity as vertical subsidence unless geometric decomposition or another defensible assumption is explicitly applied.

---

# 26. Research-quality validation

The final analysis should include multiple layers of validation.

## Internal validation

- network sensitivity;
- reference-area sensitivity;
- corrected vs uncorrected time series;
- coherence / connected-components checks;
- spatial consistency of neighboring pixels;
- temporal consistency.

## External validation if data are available

Examples:

- GNSS;
- levelling;
- field measurements;
- published subsidence zones;
- groundwater observations;
- lithology / geology;
- construction / extraction activity;
- rainfall.

Do not force causal interpretation from correlation alone.

---

# 27. Stop conditions

Stop and investigate if any of these occur:

```text
selected burst union does not fully cover AOI
burst count > 15
burst collection is not contiguous
burst sets differ between dates
different burst identities appear between reference and secondary
mixed polarization appears
mixed relative orbit appears
network has >1 connected component
unexpectedly large date gaps appear
HyP3 rejects burst geometry
pilot products clip the AOI
pilot unwrapping fails systematically
MintPy pair count does not match manifest
production credit estimate exceeds available allocation without approval
```

Do not work around an invalid condition by silently dropping data.

---

# 28. Required machine-readable deliverables

The agent must create these before production submission:

```text
config/project.yaml

manifests/geographic_reference_bursts.csv
manifests/acquisition_burst_matrix.csv
manifests/accepted_acquisitions.csv
manifests/sbas_pairs.csv

qc/network/network_summary.json
qc/network/baseline_time_plot.png

qc/cost_estimate.json

state/project_state.json
```

After HyP3 processing:

```text
manifests/hyp3_jobs.csv
manifests/product_inventory.csv

qc/pilot/pilot_qc.json
qc/production/production_qc.json
```

After MintPy:

```text
mintpy_config.txt
MintPy output directory
final network plot
velocity output
timeseries output
reference-selection record
processing log
```

---

# 29. Project-state file

Maintain a simple state file so the workflow can resume safely.

Example:

```json
{
  "phase": "BURST_DISCOVERY",
  "aoi_locked": true,
  "relative_orbit": 27,
  "direction": "ASCENDING",
  "polarization": "VV",
  "burst_selection_frozen": false,
  "network_frozen": false,
  "pilot_submitted": false,
  "pilot_passed": false,
  "production_approved": false,
  "production_submitted": false,
  "mintpy_complete": false
}
```

Update it only after each phase passes its acceptance gate.

---

# 30. Human-readable execution report

Maintain:

```text
RUNLOG.md
```

For each major step record:

```text
timestamp
action
inputs
package versions
result
counts
warnings
decision
generated files
next step
```

The report should be concise and factual, not a stream-of-consciousness log.

---

# 31. Suggested Python data model

Use explicit types rather than loose dictionaries where practical.

Example:

```python
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class Acquisition:
    date: date
    burst_scene_names: tuple[str, ...]

@dataclass(frozen=True)
class MultiBurstPair:
    reference_date: date
    secondary_date: date
    temporal_baseline_days: int
    perpendicular_baseline_m: float
    reference: tuple[str, ...]
    secondary: tuple[str, ...]
```

Generate stable `pair_id` values such as:

```text
20211006_20211018
```

---

# 32. Exact production-credit estimator

Implement this logic rather than estimating informally.

```python
def burst_insar_credit_cost(looks: str, burst_count: int) -> int:
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
        table = {
            1: 1,
            2: 5,
            3: 10,
            4: 15,
            5: 20,
            6: 25,
            7: 30,
            8: 35,
            9: 40,
            10: 45,
            11: 90,
            12: 95,
            13: 100,
            14: 105,
            15: 110,
        }
        return table[burst_count]

    raise ValueError(f"Unsupported looks: {looks}")
```

Then:

```python
credits_per_job = burst_insar_credit_cost(looks, K)
total_credits = credits_per_job * number_of_pairs
```

Always re-check ASF’s current credit page immediately before a large submission in case pricing changes.

---

# 33. Recommended pilot selection algorithm

Do not hand-pick only the easiest pairs.

Select from the accepted network:

```text
lowest |B_perp| 12-day pair
median |B_perp| 24-day pair
upper-quantile |B_perp| 36-day pair
representative monsoon pair
representative dry-season pair
```

If fewer jobs are desired, prioritize:

```text
12-day low baseline
36-day upper-baseline
monsoon
dry season
```

This provides a meaningful stress test.

---

# 34. Production options to freeze after pilot

Once the pilot is accepted, write the final options to:

```text
config/production.yaml
```

Example:

```yaml
hyP3:
  job_type: INSAR_ISCE_MULTI_BURST
  looks: "10x2"
  apply_water_mask: true

network:
  max_temporal_baseline_days: 36
  max_perpendicular_baseline_m: 250
```

Do not allow scripts to silently use defaults after this point.

---

# 35. Known HyP3 processing characteristics relevant to interpretation

HyP3 multi-burst processing:

- uses ISCE2;
- downloads/repackages selected burst SLCs into SAFE structures;
- uses Copernicus GLO-30 DEM data for topographic phase handling;
- calculates offsets/coregisters;
- forms wrapped interferograms;
- merges multi-burst interferograms;
- applies Goldstein-Werner filtering;
- optionally applies a water mask;
- unwraps phase using SNAPHU;
- geocodes outputs.

This means the output is already an interferometric product; MintPy is being used for the **time-series layer**, not raw SLC focusing/coregistration.

The user’s IIRS/ISRO MintPy tutorial also explicitly notes that MintPy can ingest interferograms produced by HyP3, which is consistent with this architecture.

---

# 36. Things the agent must NOT do

Do not:

```text
download all full SLC scenes first
revert to Frame 86/91 full-scene processing without reason
use the old 341-pair CSV as final multi-burst input
mix ascending and descending data in one SBAS network
mix path numbers
mix burst identities between dates
use VH interferograms
submit full production before pilot validation
hardcode Earthdata credentials
discard acquisitions silently
silently change thresholds
accept a disconnected network
assume "more pairs" is always better
call LOS velocity "vertical subsidence" without justification
```

---

# 37. Immediate next action

The next action is:

```text
1. Search S1 Bursts over the exact AOI.
2. Restrict to ASCENDING / path 27 / VV / IW.
3. Select one representative acquisition.
4. Identify the minimum valid contiguous burst collection that fully covers the AOI.
5. Record the exact Full Burst IDs and geometries.
6. Produce geographic_reference_bursts.csv and selected_bursts.geojson.
```

Do not proceed to HyP3 submission before this burst geometry is frozen.

---

# 38. Expected phase-by-phase status messages to the user

The agent should report progress only at meaningful checkpoints.

Examples:

```text
PHASE B COMPLETE
Selected 4 geographic bursts on ascending path 27.
AOI coverage: complete.
Collection validity: passed.
Next: historical burst-stack discovery.
```

```text
PHASE D COMPLETE
118 acquisitions retained.
334 burst-level SBAS interferograms.
Network components: 1.
Bridges: 0.
Estimated 10x2 production cost: 1,670 credits.
Next: pilot submission.
```

Do not send dozens of tiny “next” updates.

---

# 39. Completion definition

The project is not complete merely because HyP3 jobs finish.

Completion means:

```text
burst geometry frozen
historical stack verified
SBAS network audited
pilot passed
production interferograms complete
all products downloaded and inventoried
MintPy ingestion reproducible
time-series inversion complete
velocity and displacement outputs generated
QC documented
scientific limitations documented
all manifests and configuration files preserved
```

---

# 40. Official references to use as source of truth

Use current ASF documentation first whenever an API, credit value or processing constraint differs from an old example.

Primary references:

```text
ASF HyP3 Burst InSAR Product Guide
https://hyp3-docs.asf.alaska.edu/guides/burst_insar_product_guide/

ASF HyP3 Tutorials
https://hyp3-docs.asf.alaska.edu/tutorials/

Official Multi-Burst SBAS notebook
https://github.com/ASFHyP3/hyp3-docs/blob/main/docs/tutorials/multiburst_sbas.ipynb

Official ISCE2 Burst + MintPy notebook
https://github.com/ASFHyP3/hyp3-docs/blob/main/docs/tutorials/hyp3_isce2_burst_stack_for_ts_analysis.ipynb

HyP3 SDK API reference
https://hyp3-docs.asf.alaska.edu/using/sdk_api/

HyP3 Credits
https://hyp3-docs.asf.alaska.edu/using/credits/

ASF Search documentation
https://docs.asf.alaska.edu/asf_search/basics/
```

---

# 41. Final instruction to the agent

Implement this as a **reproducible scientific pipeline**, not as an interactive one-off notebook.

Use notebooks for exploration and plots, but move stable logic into scripts/modules.

Every important data-selection decision must be recoverable from:

```text
configuration
manifest
QC report
run log
```

The correct priority order is:

```text
valid geometry
→ homogeneous acquisitions
→ connected / redundant SBAS graph
→ cost-aware pilot
→ validated HyP3 production
→ reproducible MintPy inversion
→ scientific interpretation
```

Do not optimize for maximum number of images or minimum thresholds. Optimize for a **defensible, homogeneous, auditable deformation time series**.


---

# 42. REVIEW ADDENDUM — REQUIRED CORRECTIONS AND HARDENING

This section supersedes any conflicting earlier language in this document.

## 42.1 MintPy version requirement

For this project, use:

```text
MintPy >= 1.6.3
```

or a newer stable version validated against the current HyP3 multi-burst product format.

Reason: MintPy v1.6.3 explicitly added support for the HyP3 `INSAR_ISCE_MULTI_BURST` job type. Older examples may state `mintpy>=1.5.3` because they pre-date direct multi-burst support.

Before production, record:

```text
mintpy version
asf_search version
hyp3_sdk version
GDAL version
Python version
```

## 42.2 Baseline magnitude must be handled conservatively

When applying a perpendicular-baseline threshold, use the **magnitude** unless current `asf_search` semantics explicitly document the value as already absolute:

```python
abs(pair.perpendicular_baseline) <= max_perpendicular_baseline_m
```

Do not copy a tutorial comparison blindly if it could allow a large negative baseline.

For a multi-burst interferogram, retain all per-burst baseline values and compute at least:

```text
bperp_min
bperp_median
bperp_max_abs
```

Use the **maximum absolute perpendicular baseline across the selected bursts** as the conservative gating value unless current ASF guidance indicates a better multi-burst convention.

## 42.3 Do not key acquisitions only by calendar date

Use acquisition timestamp plus orbit/burst identity for internal keys.

A stable acquisition key should include enough information to prevent collisions, e.g.:

```text
relative_orbit
acquisition_start_time
platform
```

Human-readable reports may display dates, but pair matching must not rely on a date string alone.

## 42.4 Multi-burst pair alignment must be by identity, not list position

Do not depend on:

```python
zip(*pairs)
```

as the production matching mechanism.

The official ASF tutorial uses this pattern for demonstration, but a production workflow must join pair candidates by a canonical pair key and verify that every selected geographic burst has exactly the same reference/secondary acquisition pair.

Fail if pair sets differ unexpectedly.

## 42.5 Common-overlap and AOI cropping are two separate steps

For MintPy preparation:

1. determine the common raster overlap shared by every accepted interferogram;
2. verify that the scientific AOI lies inside that common overlap;
3. clip all required layers to an identical grid;
4. optionally crop further to a rectangular AOI-plus-margin window to reduce MintPy storage and memory.

Never crop individual interferograms independently.

## 42.6 Platform handling

Do not hard-code Sentinel-1A as the only acceptable platform unless the burst-level archive actually supports that choice without unnecessary gaps.

Record the platform for every acquisition.

If Sentinel-1C/D acquisitions appear in the requested time interval / same geographic burst stack, use current ASF compatibility rules and validate them rather than rejecting them merely because the earlier full-scene reconnaissance happened to contain Sentinel-1A.

## 42.7 Authentication / secrets

The handoff bundle must contain **no**:

```text
NASA Earthdata password
API token
cookie
.netrc contents
private key
```

Authentication must be supplied interactively or through a secure local credential mechanism outside source control.

## 42.8 No raw SLC / DEM / orbit download is required before HyP3

Do not pre-download the 120 full Sentinel-1 SLC scenes.

For `INSAR_ISCE_MULTI_BURST`, HyP3 handles the burst SLC retrieval, SAFE repackaging, DEM retrieval, orbit files, auxiliary calibration data, ISCE2 processing, merging, unwrapping and geocoding.

Likewise, do not separately download a DEM or precise orbit files for the HyP3 preprocessing stage unless a later independent validation task specifically requires them.

## 42.9 Disk-space gate

Before production submission, the pilot must be used to estimate:

```text
mean compressed product size/job
mean extracted product size/job
expected total compressed size
expected total extracted size
MintPy working-space requirement
safety margin
```

Production must not be submitted if local storage is inadequate for prompt download and retention.

## 42.10 Previous full-scene CSVs are provenance, not production manifests

Two historical ASF Vertex exports are provided with this handoff:

```text
full_scene_network_50pct_99scenes_278pairs.csv
full_scene_network_any_overlap_120scenes_341pairs.csv
```

They are useful for:

```text
reconciling dates
cross-checking temporal continuity
comparing burst-level pair topology
documenting why burst processing was selected
```

They must **not** be passed directly to `INSAR_ISCE_MULTI_BURST`.

## 42.11 Source precedence

When sources disagree, use this order:

```text
1. current ASF HyP3 product/API documentation
2. current official ASF multi-burst SBAS notebook
3. current MintPy documentation / release behavior
4. this implementation brief
5. the April 2025 IIRS/ISRO tutorial
```

The IIRS tutorial is included as useful conceptual background for MintPy/SBAS, but it is not authoritative for the current HyP3 multi-burst API.

