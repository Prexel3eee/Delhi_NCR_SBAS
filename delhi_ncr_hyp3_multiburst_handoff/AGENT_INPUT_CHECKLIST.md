# Agent Input / File Checklist

## Included and immediately usable

- [x] Detailed execution brief (V2)
- [x] AOI in WKT
- [x] AOI in GeoJSON
- [x] Starter project configuration
- [x] Starter conda environment specification
- [x] Historical ASF 99-scene / 278-pair CSV
- [x] Historical ASF 120-scene / 341-pair CSV
- [x] April 2025 IIRS/ISRO MintPy tutorial PDF
- [x] Current official reference links
- [x] Bundle manifest with SHA-256 hashes

## Do NOT require from the user before starting

- [ ] Full Sentinel-1 SLC ZIP files — **not needed**
- [ ] Manually downloaded S1 burst files — **not needed**
- [ ] DEM — **not needed for HyP3 preprocessing**
- [ ] Precise orbit files — **not needed for HyP3 preprocessing**
- [ ] ISCE2 local installation — **not needed for HyP3 preprocessing**
- [ ] Existing MintPy outputs — **none exist yet**

## Required external/account state

- [ ] NASA Earthdata Login works
- [ ] ASF / HyP3 access works
- [ ] Current HyP3 credit balance is checked before pilot
- [ ] Secure authentication is available locally (interactive or protected `.netrc`)
- [ ] Sufficient disk space exists before production download

## Files the agent must generate before pilot

- [ ] `manifests/geographic_reference_bursts.csv`
- [ ] `geometry/selected_bursts.geojson`
- [ ] `manifests/acquisition_burst_matrix.csv`
- [ ] `manifests/accepted_acquisitions.csv`
- [ ] `manifests/sbas_pairs.csv`
- [ ] `qc/network/network_summary.json`
- [ ] `qc/network/baseline_time_plot.png`
- [ ] `qc/cost_estimate.json`
- [ ] `state/project_state.json`

## Files the agent must generate after pilot

- [ ] `manifests/hyp3_jobs.csv`
- [ ] `manifests/product_inventory.csv`
- [ ] `qc/pilot/pilot_qc.json`
- [ ] disk-space estimate from real pilot products
- [ ] final frozen HyP3 processing options

## Production is blocked until

- [ ] burst geometry valid
- [ ] AOI fully covered
- [ ] same burst identities on all retained dates
- [ ] network connected and audited
- [ ] pilot passes QC
- [ ] exact credit cost known
- [ ] local storage estimate passes
- [ ] user approves production submission if material credits will be consumed
