# START HERE — Delhi-NCR Multi-Burst HyP3 Handoff

This bundle contains the context needed for an implementation agent to continue the project without repeating the earlier full-scene investigation.

## Read in this order

1. `DELHI_NCR_HYP3_MULTIBURST_SBAS_AGENT_BRIEF_V2.md`
2. `AGENT_INPUT_CHECKLIST.md`
3. `config/project.yaml`
4. `geometry/aoi.geojson`
5. historical CSVs under `references/` only if reconciling earlier findings

## What is already known

- Scientific method: SBAS-InSAR
- Processing choice: HyP3 `INSAR_ISCE_MULTI_BURST` + MintPy
- AOI: frozen in `geometry/aoi.*`
- Primary orbit geometry: Ascending, relative orbit/path 27, VV, IW
- Study interval: 2021-10-01 through 2025-10-01
- Full-scene reconnaissance produced a strong 36-day / 250-m network, but that network is NOT the production burst network.
- The production network must be rebuilt from fixed geographic Full Burst IDs.

## What the agent needs from the user/account

The only external account prerequisite is working NASA Earthdata / ASF HyP3 authentication and sufficient HyP3 credits.

Do not ask the user to download raw Sentinel-1 full SLC scenes, a DEM, orbit files, or calibration files before HyP3 processing. HyP3 handles those inputs for multi-burst processing.

## First execution task

Search ASF for S1 Burst products covering the exact AOI, constrained to:

- Ascending
- Relative orbit 27
- VV
- IW

Identify the minimum valid contiguous burst collection covering the AOI, then freeze its Full Burst IDs before building the historical stack.
