#!/usr/bin/env python
"""
Phase G - pilot QC on the 7 unique scientific configurations.

Runs in the `delhi-mintpy` environment (rasterio / GDAL / geopandas / shapely).

What this does
--------------
1. **Product QC** for every unique scientific configuration
   (pair + water-mask setting): required layers, CRS/pixel size/dimensions, AOI
   coverage, coherence distribution, unwrapped-phase validity, connected
   components, nodata fraction and a simple edge-artefact metric.
2. **Reproducibility test** - the pilot was submitted twice by accident
   (INC-001). Both copies are preserved and compared layer by layer, turning an
   error into a genuine determinism check on HyP3 multi-burst processing.
3. **Water-mask ON/OFF comparison** around the Yamuna, using the water mask from
   the masked product to define the water pixels and comparing coherence,
   connected components and valid-pixel fraction inside and outside water.
4. **Storage projection** from measured ZIP and extracted sizes to the full
   336-pair production run.

Outputs (qc/pilot/)
-------------------
pilot_qc.json                 per-configuration QC results
pilot_qc_summary.csv          flat per-configuration metrics
reproducibility.json          duplicate-copy comparison
water_mask_comparison.json    ON vs OFF around water
storage_estimate.json         measured + projected storage
coherence_histogram.png
conncomp_maps.png
water_mask_comparison.png

Usage
-----
    python scripts/09_qc_pilot.py
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from rasterio.features import geometry_mask  # noqa: E402
from rasterio.warp import transform_geom  # noqa: E402
from shapely.geometry import shape  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
QC_DIR = PROJECT_ROOT / "qc" / "pilot"
DATA_DIR = PROJECT_ROOT / "data" / "hyp3_extracted"
GEOMETRY_DIR = PROJECT_ROOT / "geometry"

COHERENCE_THRESHOLDS = (0.2, 0.3, 0.5)
EDGE_BAND_PX = 5
PRODUCTION_PAIRS = 336


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_aoi():
    """The AOI as stored, in EPSG:4326 (lon/lat)."""
    payload = json.loads((GEOMETRY_DIR / "aoi.geojson").read_text())
    return shape(payload["features"][0]["geometry"])


def aoi_in_crs(aoi, crs):
    """Reproject the AOI into a raster's CRS.

    HyP3 multi-burst products are geocoded to UTM (EPSG:32643 here) while the
    frozen AOI is lon/lat. Masking with unreprojected coordinates silently
    produces an all-False mask, which looks like 'zero valid pixels' rather than
    an obvious error.
    """
    return shape(transform_geom("EPSG:4326", crs, aoi.__geo_interface__))


def find_layers(product_dir: Path) -> dict[str, Path]:
    """Map layer suffix -> file path for one extracted product."""
    layers: dict[str, Path] = {}
    for path in product_dir.rglob("*"):
        if not path.is_file() or not path.name.endswith(".tif"):
            continue
        for suffix in (
            "_unw_phase.tif",
            "_corr.tif",
            "_conncomp.tif",
            "_dem.tif",
            "_lv_theta.tif",
            "_lv_phi.tif",
            "_water_mask.tif",
        ):
            if path.name.endswith(suffix):
                layers[suffix] = path
    return layers


def raster_profile(path: Path) -> dict:
    with rasterio.open(path) as src:
        return {
            "crs": str(src.crs),
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtype": src.dtypes[0],
            "res": [abs(src.transform.a), abs(src.transform.e)],
            "bounds": [round(v, 6) for v in src.bounds],
            "nodata": src.nodata,
        }


def aoi_mask_for(path: Path, aoi) -> tuple[np.ndarray, dict]:
    """Boolean mask of AOI pixels, plus the AOI's footprint fraction."""
    with rasterio.open(path) as src:
        aoi_local = aoi_in_crs(aoi, src.crs)
        inside = geometry_mask(
            [aoi_local.__geo_interface__],
            out_shape=(src.height, src.width),
            transform=src.transform,
            invert=True,
        )
        bounds = src.bounds
    aoi_bounds = aoi_local.bounds
    aoi_fully_inside = (
        bounds.left <= aoi_bounds[0]
        and bounds.bottom <= aoi_bounds[1]
        and bounds.right >= aoi_bounds[2]
        and bounds.top >= aoi_bounds[3]
    )
    return inside, {
        "aoi_pixels": int(inside.sum()),
        "aoi_fully_inside_product": bool(aoi_fully_inside),
        "aoi_coverage_of_product": round(float(inside.sum()) / inside.size, 6),
    }


def read_valid(path: Path, mask: np.ndarray | None = None):
    with rasterio.open(path) as src:
        array = src.read(1).astype("float64")
        nodata = src.nodata
    if nodata is not None:
        array[array == nodata] = np.nan
    if mask is not None:
        array = np.where(mask, array, np.nan)
    return array


def finite_stats(values: np.ndarray) -> dict:
    valid = np.isfinite(values)
    n = int(valid.sum())
    if n == 0:
        return {"valid_pixels": 0, "valid_fraction": 0.0}
    data = values[valid]
    return {
        "valid_pixels": n,
        "valid_fraction": round(float(n) / values.size, 6),
        "min": round(float(np.min(data)), 4),
        "p25": round(float(np.percentile(data, 25)), 4),
        "median": round(float(np.median(data)), 4),
        "p75": round(float(np.percentile(data, 75)), 4),
        "max": round(float(np.max(data)), 4),
        "mean": round(float(np.mean(data)), 4),
        "std": round(float(np.std(data)), 4),
    }


def edge_artifact_metric(values: np.ndarray, band: int = EDGE_BAND_PX) -> dict:
    """Compare a band just inside the DATA extent against the interior.

    The product's outer raster border is nodata by design (HyP3 pads the
    geocoded grid), so a raster-border ring is always empty and useless. The
    meaningful edge for a multi-burst product is the boundary of the valid data
    footprint, where burst coverage tapers. This compares validity and coherence
    there against the interior.
    """
    valid = np.isfinite(values)
    if not valid.any():
        return {"available": False, "reason": "no valid data"}

    rows = np.where(valid.any(axis=1))[0]
    cols = np.where(valid.any(axis=0))[0]
    r0, r1 = int(rows[0]), int(rows[-1])
    c0, c1 = int(cols[0]), int(cols[-1])

    sub_valid = valid[r0 : r1 + 1, c0 : c1 + 1]
    sub_values = values[r0 : r1 + 1, c0 : c1 + 1]
    h, w = sub_valid.shape
    if h <= 2 * band or w <= 2 * band:
        return {"available": False, "reason": "data extent too small for edge probe"}

    ring = np.zeros_like(sub_valid)
    ring[:band, :] = True
    ring[-band:, :] = True
    ring[:, :band] = True
    ring[:, -band:] = True
    interior = ~ring

    ring_valid = sub_valid & ring
    interior_valid = sub_valid & interior
    ring_total = int(ring.sum())
    interior_total = int(interior.sum())

    out: dict = {
        "available": True,
        "band_px": band,
        "data_extent_rows": [r0, r1],
        "data_extent_cols": [c0, c1],
        "edge_valid_fraction": round(float(ring_valid.sum()) / ring_total, 6),
        "interior_valid_fraction": round(float(interior_valid.sum()) / interior_total, 6),
    }
    out["edge_minus_interior_valid"] = round(
        out["edge_valid_fraction"] - out["interior_valid_fraction"], 6
    )

    ring_values = sub_values[ring_valid]
    interior_values = sub_values[interior_valid]
    if ring_values.size and interior_values.size:
        out["edge_median"] = round(float(np.median(ring_values)), 4)
        out["interior_median"] = round(float(np.median(interior_values)), 4)
        out["edge_minus_interior_median"] = round(
            out["edge_median"] - out["interior_median"], 4
        )
    return out


def along_track_seam_check(
    values: np.ndarray,
    window: int = 51,
    z: float = 6.0,
    min_effect: float = 0.05,
    margin: int = 30,
) -> dict:
    """Detect along-track (azimuth-line) discontinuities: burst merge seams.

    A 4-burst product is merged along track, so a mis-merge would appear as one
    or a few anomalous azimuth rows.

    Two guards make the verdict trustworthy rather than alarmist:

    * **effect size** - a row is only flagged if the robust z-score exceeds
      ``z`` *and* the absolute deviation exceeds ``min_effect``. Without this, an
      almost-constant row-median series produces a near-zero MAD and therefore
      enormous but meaningless z-scores.
    * **boundary margin** - rows within ``margin`` of the first/last valid row are
      excluded, because the mosaic is a parallelogram: as its valid span shifts
      with row, the row median changes for purely geometric reasons.
    """
    valid = np.isfinite(values)
    rows_with_data = np.where(valid.any(axis=1))[0]
    if rows_with_data.size < window + 2 * margin:
        return {"available": False, "reason": "too few rows with data"}

    keep = rows_with_data[margin : -margin]
    row_median = np.full(values.shape[0], np.nan)
    for r in keep:
        row_median[r] = np.median(values[r][valid[r]])

    series = pd.Series(row_median)
    baseline = series.rolling(window=window, center=True, min_periods=window // 4).median()
    residual = (series - baseline).dropna()
    if residual.empty:
        return {"available": False, "reason": "no residual computed"}

    mad = float(np.median(np.abs(residual - np.median(residual))))
    scale = 1.4826 * mad if mad > 0 else float(residual.std() or 1e-9)
    zscores = (residual - float(np.median(residual))) / scale

    flagged = (np.abs(zscores) > z) & (np.abs(residual) > min_effect)
    n_flagged = int(flagged.sum())

    return {
        "available": True,
        "rows_evaluated": int(len(keep)),
        "robust_scale": round(scale, 6),
        "max_abs_residual": round(float(np.abs(residual).max()), 4),
        "max_abs_z": round(float(np.abs(zscores).max()), 2),
        "min_effect_threshold": min_effect,
        "flagged_rows": n_flagged,
        "flagged_row_indices": [int(i) for i in residual.index[flagged.to_numpy()][:20]],
        "verdict": "no seam detected" if n_flagged == 0 else "possible burst seam",
    }


def connected_component_stats(path: Path, mask: np.ndarray) -> dict:
    """Component count / coverage inside the AOI (conncomp id 0 = nodata)."""
    with rasterio.open(path) as src:
        array = src.read(1)
    values = array[mask]
    if values.size == 0:
        return {"available": False}
    nonzero = values[values > 0]
    if nonzero.size == 0:
        return {
            "available": True,
            "components_in_aoi": 0,
            "largest_component_fraction_of_aoi": 0.0,
            "valid_fraction_of_aoi": 0.0,
        }
    ids, counts = np.unique(nonzero, return_counts=True)
    largest = int(counts.max())
    return {
        "available": True,
        "components_in_aoi": int(ids.size),
        "largest_component_pixels": largest,
        "largest_component_fraction_of_aoi": round(float(largest) / values.size, 6),
        "valid_fraction_of_aoi": round(float(nonzero.size) / values.size, 6),
    }


def sha256_of(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Per-configuration QC
# ---------------------------------------------------------------------------


def qc_configuration(config_key: str, rows: pd.DataFrame, aoi) -> dict:
    primary = rows.iloc[0]
    product_dir = PROJECT_ROOT / primary["extract_dir"]
    layers = find_layers(product_dir)

    result: dict = {
        "config_key": config_key,
        "pair_id": primary["pair_id"],
        "job_name": primary["job_name"],
        "job_id": primary["job_id"],
        "apply_water_mask": bool(primary["apply_water_mask"]),
        "status": primary["status"],
        "copies": int(len(rows)),
        "job_ids": list(rows["job_id"].astype(str)),
        "product_dir": primary["extract_dir"],
        "layers_found": sorted(k.strip("_") for k in layers),
        "layers_missing": [],
        "zip_bytes": int(primary["zip_bytes"]),
        "extracted_bytes": int(primary["extracted_bytes"]),
        "extracted_files": int(primary["extracted_files"]),
    }

    required = ["_unw_phase.tif", "_corr.tif", "_conncomp.tif", "_dem.tif",
                "_lv_theta.tif", "_lv_phi.tif"]
    if bool(primary["apply_water_mask"]):
        required.append("_water_mask.tif")
    result["layers_missing"] = [s.strip("_") for s in required if s not in layers]

    geometry_layer = layers.get("_dem.tif") or layers.get("_corr.tif")
    if geometry_layer is None:
        result["error"] = "no geometry raster available"
        return result

    result["raster"] = raster_profile(geometry_layer)
    mask, coverage = aoi_mask_for(geometry_layer, aoi)
    result.update(coverage)

    # coherence
    if "_corr.tif" in layers:
        corr = read_valid(layers["_corr.tif"], mask)
        result["coherence"] = finite_stats(corr)
        finite = corr[np.isfinite(corr)]
        result["coherence_fraction_above"] = {
            str(t): round(float(np.mean(finite > t)), 6) if finite.size else 0.0
            for t in COHERENCE_THRESHOLDS
        }
        # Edge probe must use the UNMASKED raster: the AOI occupies only the
        # middle ~17% of the product, so an AOI-masked border ring is empty and
        # the metric would silently report nothing.
        result["coherence_edge"] = edge_artifact_metric(read_valid(layers["_corr.tif"]))
        aoi_pixels = int(mask.sum())
        if aoi_pixels:
            result["coherence"]["valid_fraction_of_aoi"] = round(
                result["coherence"]["valid_pixels"] / aoi_pixels, 6
            )

    # unwrapped phase
    if "_unw_phase.tif" in layers:
        unw = read_valid(layers["_unw_phase.tif"], mask)
        result["unw_phase"] = finite_stats(unw)
        result["unw_phase_edge"] = edge_artifact_metric(read_valid(layers["_unw_phase.tif"]))
        aoi_pixels = int(mask.sum())
        if aoi_pixels:
            result["unw_phase"]["valid_fraction_of_aoi"] = round(
                result["unw_phase"]["valid_pixels"] / aoi_pixels, 6
            )

        # Land-relative validity. Where a water mask was applied, water pixels
        # are deliberately left with no unwrapped phase, so the plain AOI
        # fraction understates usability. The AOI contains ~1.85% water (more
        # than the ~0.91% raster average, because the Yamuna crosses it).
        if "_water_mask.tif" in layers:
            with rasterio.open(layers["_water_mask.tif"]) as wsrc:
                wm = wsrc.read(1)
                wnod = wsrc.nodata
            land = wm == 1
            if wnod is not None:
                land &= wm != wnod
            land_aoi = mask & land
            if land_aoi.sum():
                land_arr = read_valid(layers["_unw_phase.tif"], land_aoi)
                n_land = int(np.isfinite(land_arr).sum())
                result["unw_phase"]["valid_fraction_of_aoi_land"] = round(
                    n_land / int(land_aoi.sum()), 6
                )
                result["land_pixels_in_aoi"] = int(land_aoi.sum())
                result["water_pixels_in_aoi"] = int((mask & (wm == 0)).sum())

    # connected components
    if "_conncomp.tif" in layers:
        result["conncomp"] = connected_component_stats(layers["_conncomp.tif"], mask)

    # multi-burst specific: along-track merge seams
    if "_corr.tif" in layers:
        result["coherence_seam_check"] = along_track_seam_check(read_valid(layers["_corr.tif"]))
    if "_unw_phase.tif" in layers:
        result["unw_phase_seam_check"] = along_track_seam_check(read_valid(layers["_unw_phase.tif"]))
    # NOTE: the footprint edge metric is informational only. For a merged
    # multi-burst mosaic the data bounding box includes large nodata corners, so
    # edge-vs-interior validity mostly reflects the mosaic outline, not an
    # artefact. Seam checks above are the meaningful multi-burst test.


    # nodata fraction over the whole raster
    with rasterio.open(geometry_layer) as src:
        full = src.read(1).astype("float64")
        nodata = src.nodata
    if nodata is not None:
        result["nodata_fraction_full_raster"] = round(float(np.mean(full == nodata)), 6)

    return result


# ---------------------------------------------------------------------------
# Reproducibility of duplicate copies
# ---------------------------------------------------------------------------


def compare_copies(rows: pd.DataFrame) -> dict:
    """Layer-by-layer comparison of the two copies of one configuration."""
    a = PROJECT_ROOT / rows.iloc[0]["extract_dir"]
    b = PROJECT_ROOT / rows.iloc[1]["extract_dir"]
    la, lb = find_layers(a), find_layers(b)

    out: dict = {
        "pair_id": rows.iloc[0]["pair_id"],
        "apply_water_mask": bool(rows.iloc[0]["apply_water_mask"]),
        "job_ids": list(rows["job_id"].astype(str)),
        "layers_compared": 0,
        "layers_identical": 0,
        "layers_differing": [],
        "zip_bytes": [int(rows.iloc[0]["zip_bytes"]), int(rows.iloc[1]["zip_bytes"])],
        "layer_detail": {},
    }

    for suffix in sorted(set(la) & set(lb)):
        out["layers_compared"] += 1
        detail: dict = {}
        try:
            with rasterio.open(la[suffix]) as sa, rasterio.open(lb[suffix]) as sb:
                detail["shape_equal"] = (sa.height, sa.width) == (sb.height, sb.width)
                detail["crs_equal"] = str(sa.crs) == str(sb.crs)
                detail["transform_equal"] = tuple(sa.transform)[:6] == tuple(sb.transform)[:6]
                arr_a = sa.read(1).astype("float64")
                arr_b = sb.read(1).astype("float64")
            if arr_a.shape == arr_b.shape:
                detail["array_equal"] = bool(np.array_equal(arr_a, arr_b))
                if not detail["array_equal"]:
                    diff = np.abs(arr_a - arr_b)
                    finite = np.isfinite(diff)
                    detail["max_abs_diff"] = (
                        round(float(diff[finite].max()), 6) if finite.any() else None
                    )
                    detail["fraction_differing"] = round(
                        float(np.mean(arr_a != arr_b)), 8
                    )
            else:
                detail["array_equal"] = False
        except Exception as exc:  # noqa: BLE001
            detail["error"] = f"{type(exc).__name__}: {exc}"

        out["layer_detail"][suffix.strip("_")] = detail
        if detail.get("array_equal"):
            out["layers_identical"] += 1
        else:
            out["layers_differing"].append(suffix.strip("_"))

    out["all_layers_identical"] = (
        out["layers_compared"] > 0 and not out["layers_differing"]
    )
    return out


# ---------------------------------------------------------------------------
# Water-mask comparison
# ---------------------------------------------------------------------------


def water_mask_comparison(masked_rows: pd.DataFrame, unmasked_rows: pd.DataFrame, aoi) -> dict:
    masked_dir = PROJECT_ROOT / masked_rows.iloc[0]["extract_dir"]
    unmasked_dir = PROJECT_ROOT / unmasked_rows.iloc[0]["extract_dir"]

    m_layers = find_layers(masked_dir)
    u_layers = find_layers(unmasked_dir)
    if "_water_mask.tif" not in m_layers:
        return {"available": False, "reason": "masked product has no water mask layer"}

    with rasterio.open(m_layers["_water_mask.tif"]) as src:
        water = src.read(1)
        nodata = src.nodata
    # HyP3 PRODUCT water mask polarity: 0 = water, 1 = land.
    # This is the OPPOSITE of ASF's reference water-mask tiles (1 = water).
    # Source: https://hyp3-docs.asf.alaska.edu/water_masking/
    #   "Water pixels are assigned a value of 0, and all remaining pixels are
    #    assigned a value of 1 ... In this copy of the water mask, the pixel
    #    values are the same as what is used in InSAR processing."
    # Verified against the data: only 0.9% of pixels are 0, which is the only
    # physically sensible water fraction for Delhi-NCR.
    water_bool = water == 0
    land_bool = water == 1
    if nodata is not None:
        water_bool &= water != nodata
        land_bool &= water != nodata

    out: dict = {
        "available": True,
        "pair_id": masked_rows.iloc[0]["pair_id"],
        "water_mask_layer": str(m_layers["_water_mask.tif"].relative_to(PROJECT_ROOT)),
        "water_pixels": int(water_bool.sum()),
        "land_pixels": int(land_bool.sum()),
        "water_fraction": round(float(water_bool.mean()), 6),
        "water_mask_convention": "0 = water, 1 = land (HyP3 product convention; "
        "opposite of ASF reference tiles)",
        "water_mask_source": "https://hyp3-docs.asf.alaska.edu/water_masking/",
        "comparison": {},
    }

    for label, suffix in (("coherence", "_corr.tif"), ("unw_phase", "_unw_phase.tif"),
                          ("conncomp", "_conncomp.tif")):
        if suffix not in m_layers or suffix not in u_layers:
            continue
        try:
            with rasterio.open(m_layers[suffix]) as src:
                arr_m = src.read(1).astype("float64")
                nod_m = src.nodata
            with rasterio.open(u_layers[suffix]) as src:
                arr_u = src.read(1).astype("float64")
                nod_u = src.nodata
            if arr_m.shape != arr_u.shape:
                out["comparison"][label] = {"shape_mismatch": True}
                continue
            if nod_m is not None:
                arr_m[arr_m == nod_m] = np.nan
            if nod_u is not None:
                arr_u[arr_u == nod_u] = np.nan

            entry: dict = {}
            for region, region_mask in (("water", water_bool), ("land", land_bool)):
                vm, vu = arr_m[region_mask], arr_u[region_mask]
                entry[f"{region}_masked_valid_fraction"] = round(
                    float(np.mean(np.isfinite(vm))), 6
                )
                entry[f"{region}_unmasked_valid_fraction"] = round(
                    float(np.mean(np.isfinite(vu))), 6
                )
                if label == "coherence":
                    fm, fu = vm[np.isfinite(vm)], vu[np.isfinite(vu)]
                    entry[f"{region}_masked_median_coherence"] = (
                        round(float(np.median(fm)), 4) if fm.size else None
                    )
                    entry[f"{region}_unmasked_median_coherence"] = (
                        round(float(np.median(fu)), 4) if fu.size else None
                    )
                if label == "conncomp":
                    for tag, arr in (("masked", vm), ("unmasked", vu)):
                        nz = arr[np.isfinite(arr) & (arr > 0)]
                        entry[f"{region}_{tag}_components"] = (
                            int(np.unique(nz).size) if nz.size else 0
                        )
            out["comparison"][label] = entry
        except Exception as exc:  # noqa: BLE001
            out["comparison"][label] = {"error": f"{type(exc).__name__}: {exc}"}

    return out


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def storage_estimate(successful: pd.DataFrame) -> dict:
    per_config = (
        successful.sort_values("zip_bytes", ascending=False)
        .drop_duplicates(subset=["pair_id", "apply_water_mask"])
    )
    zip_mean = float(per_config["zip_bytes"].mean())
    ext_mean = float(per_config["extracted_bytes"].mean())
    zip_max = float(per_config["zip_bytes"].max())
    ext_max = float(per_config["extracted_bytes"].max())

    # MintPy keeps unpacked rasters plus its own HDF5 time-series products.
    mintpy_multiplier = 1.5
    return {
        "measured": {
            "configurations": int(len(per_config)),
            "zip_mean_bytes": zip_mean,
            "zip_max_bytes": zip_max,
            "extracted_mean_bytes": ext_mean,
            "extracted_max_bytes": ext_max,
            "extracted_to_zip_ratio": round(ext_mean / zip_mean, 3) if zip_mean else None,
        },
        "projection_336_pairs": {
            "zip_total_gb": round(zip_mean * PRODUCTION_PAIRS / 1e9, 2),
            "zip_total_worst_case_gb": round(zip_max * PRODUCTION_PAIRS / 1e9, 2),
            "extracted_total_gb": round(ext_mean * PRODUCTION_PAIRS / 1e9, 2),
            "extracted_total_worst_case_gb": round(ext_max * PRODUCTION_PAIRS / 1e9, 2),
            "mintpy_working_gb": round(ext_mean * PRODUCTION_PAIRS * mintpy_multiplier / 1e9, 2),
            "grand_total_gb": round(
                (zip_mean + ext_mean * (1 + mintpy_multiplier)) * PRODUCTION_PAIRS / 1e9, 2
            ),
        },
        "pilot_actual": {
            "zip_total_bytes": int(successful["zip_bytes"].sum()),
            "extracted_total_bytes": int(successful["extracted_bytes"].sum()),
        },
        "assumptions": {
            "mintpy_multiplier": mintpy_multiplier,
            "note": "production projection uses the mean across the 7 unique configurations; "
            "worst case uses the largest observed product.",
        },
    }


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


def plot_coherence(rows: pd.DataFrame, out: Path) -> None:
    figure, axis = plt.subplots(figsize=(9, 5))
    labels = []
    medians = []
    p25 = []
    for _, row in rows.iterrows():
        layers = find_layers(PROJECT_ROOT / row["extract_dir"])
        if "_corr.tif" not in layers:
            continue
        corr = read_valid(layers["_corr.tif"])
        finite = corr[np.isfinite(corr)]
        if not finite.size:
            continue
        label = f"{row['pair_id']}{'' if row['apply_water_mask'] else ' (nomask)'}"
        labels.append(label)
        medians.append(float(np.median(finite)))
        p25.append(float(np.percentile(finite, 25)))
    axis.barh(labels, medians, color="tab:blue", label="median coherence")
    axis.barh(labels, p25, color="tab:orange", height=0.4, label="p25 coherence")
    axis.set_xlabel("Coherence")
    axis.set_title("Pilot coherence by configuration (full raster)")
    axis.grid(alpha=0.3, axis="x")
    axis.legend()
    figure.tight_layout()
    figure.savefig(out, dpi=150)
    plt.close(figure)


def plot_conncomp(rows: pd.DataFrame, out: Path) -> None:
    n = min(4, len(rows))
    figure, axes = plt.subplots(1, n, figsize=(4 * n, 4.2))
    if n == 1:
        axes = [axes]
    for axis, (_, row) in zip(axes, rows.head(n).iterrows()):
        layers = find_layers(PROJECT_ROOT / row["extract_dir"])
        if "_conncomp.tif" not in layers:
            axis.axis("off")
            continue
        with rasterio.open(layers["_conncomp.tif"]) as src:
            arr = src.read(1)
        axis.imshow(arr, cmap="tab20", interpolation="nearest")
        label = f"{row['pair_id']}\n{'water_mask=ON' if row['apply_water_mask'] else 'water_mask=OFF'}"
        axis.set_title(label, fontsize=8)
        axis.axis("off")
    figure.suptitle("Connected components (pilot)", fontsize=11)
    figure.tight_layout()
    figure.savefig(out, dpi=150)
    plt.close(figure)


def plot_water_comparison(comparison: dict, out: Path) -> None:
    """Two panels: coherence (unchanged by masking) and unwrapped-phase validity.

    The decision-relevant effect is the second panel. The water mask does not
    alter the coherence layer at all; it removes water pixels from phase
    unwrapping. Plotting only coherence would hide the actual result.
    """
    comp = comparison.get("comparison", {})
    coh = comp.get("coherence") or {}
    unw = comp.get("unw_phase") or {}
    if not coh and not unw:
        return

    regions = ["water", "land"]
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))

    ax = axes[0]
    masked = [coh.get(f"{r}_masked_median_coherence") or 0 for r in regions]
    unmasked = [coh.get(f"{r}_unmasked_median_coherence") or 0 for r in regions]
    x = np.arange(len(regions))
    ax.bar(x - 0.2, masked, 0.4, label="water_mask=ON", color="tab:blue")
    ax.bar(x + 0.2, unmasked, 0.4, label="water_mask=OFF", color="tab:orange")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r} pixels" for r in regions])
    ax.set_ylabel("Median coherence")
    ax.set_title("Coherence is unaffected by the mask\n(the mask changes unwrapping, not coherence)", fontsize=9)
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8)

    ax = axes[1]
    masked = [unw.get(f"{r}_masked_valid_fraction") or 0 for r in regions]
    unmasked = [unw.get(f"{r}_unmasked_valid_fraction") or 0 for r in regions]
    ax.bar(x - 0.2, masked, 0.4, label="water_mask=ON", color="tab:blue")
    ax.bar(x + 0.2, unmasked, 0.4, label="water_mask=OFF", color="tab:orange")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r} pixels" for r in regions])
    ax.set_ylabel("Fraction with valid unwrapped phase")
    ax.set_title("Masking removes water from unwrapping\nand leaves land untouched", fontsize=9)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8)

    figure.suptitle(
        f"Water-mask ON/OFF — {comparison.get('pair_id')}  "
        f"(water = {comparison.get('water_fraction', 0) * 100:.2f}% of the product)",
        fontsize=11,
    )
    figure.tight_layout()
    figure.savefig(out, dpi=150)
    plt.close(figure)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    inventory_path = MANIFEST_DIR / "product_inventory.csv"
    if not inventory_path.exists():
        print(f"FAIL: {inventory_path} not found. Run scripts/08_download_pilot.py first.")
        return 1

    inventory = pd.read_csv(inventory_path)
    successful = inventory[inventory["download_ok"].fillna(False).astype(bool)].copy()
    if successful.empty:
        print("FAIL: no successfully downloaded products yet.")
        return 1

    aoi = load_aoi()

    print("=" * 88)
    print("PHASE G - PILOT QC")
    print("=" * 88)
    print(f"\nDownloaded products : {len(successful)}")
    print(f"Unique configs      : {successful.groupby(['pair_id', 'apply_water_mask']).ngroups}")

    # ---- per-configuration QC -------------------------------------------
    configs: list[dict] = []
    reproducibility: list[dict] = []

    for (pair_id, mask), rows in successful.groupby(["pair_id", "apply_water_mask"], sort=True):
        config_key = f"{pair_id}{'' if mask else '_nomask'}"
        print(f"\n  QC {config_key}  ({len(rows)} copy/copies)")
        result = qc_configuration(config_key, rows, aoi)
        configs.append(result)

        if len(rows) > 1:
            comparison = compare_copies(rows)
            reproducibility.append(comparison)
            status = "IDENTICAL" if comparison["all_layers_identical"] else "DIFFERS"
            print(f"    duplicate reproducibility: {status} "
                  f"({comparison['layers_identical']}/{comparison['layers_compared']} layers identical)")

        if result.get("coherence"):
            frac = result.get("coherence_fraction_above", {})
            print(f"    AOI coverage ok={result.get('aoi_fully_inside_product')} "
                  f"aoi_pixels={result.get('aoi_pixels')} "
                  f"validAOI={result['coherence'].get('valid_fraction_of_aoi')} "
                  f"median_coh={result['coherence'].get('median')} "
                  f"frac>0.3={frac.get('0.3')}")
        if result.get("conncomp"):
            print(f"    components_in_aoi={result['conncomp'].get('components_in_aoi')} "
                  f"largest_frac={result['conncomp'].get('largest_component_fraction_of_aoi')}")
        if result["layers_missing"]:
            print(f"    MISSING LAYERS: {result['layers_missing']}")

    # ---- water-mask comparison ------------------------------------------
    print("\n" + "-" * 88)
    print("WATER-MASK ON/OFF COMPARISON")
    print("-" * 88)
    watermark_result: dict = {"available": False, "reason": "no matching pair"}
    masked = successful[(successful["apply_water_mask"] == True)]  # noqa: E712
    unmasked = successful[(successful["apply_water_mask"] == False)]  # noqa: E712
    if not masked.empty and not unmasked.empty:
        shared = set(masked["pair_id"]) & set(unmasked["pair_id"])
        if shared:
            pair_id = sorted(shared)[0]
            watermark_result = water_mask_comparison(
                masked[masked["pair_id"] == pair_id],
                unmasked[unmasked["pair_id"] == pair_id],
                aoi,
            )
            print(f"  pair {pair_id}: water_fraction={watermark_result.get('water_fraction')}")
            for label, entry in (watermark_result.get("comparison") or {}).items():
                print(f"    {label}: {json.dumps(entry)}")

    # ---- storage ---------------------------------------------------------
    storage = storage_estimate(successful)
    print("\n" + "-" * 88)
    print("STORAGE")
    print("-" * 88)
    m = storage["measured"]
    p = storage["projection_336_pairs"]
    print(f"  measured zip mean {m['zip_mean_bytes']/1e6:.1f} MB  max {m['zip_max_bytes']/1e6:.1f} MB")
    print(f"  measured extracted mean {m['extracted_mean_bytes']/1e6:.1f} MB "
          f"(x{m['extracted_to_zip_ratio']} of zip)")
    print(f"  projected 336 pairs: zip {p['zip_total_gb']} GB, extracted {p['extracted_total_gb']} GB, "
          f"grand total {p['grand_total_gb']} GB")

    # ---- plots -----------------------------------------------------------
    unique_rows = successful.drop_duplicates(subset=["pair_id", "apply_water_mask"])
    plot_coherence(unique_rows, QC_DIR / "coherence_histogram.png")
    plot_conncomp(unique_rows, QC_DIR / "conncomp_maps.png")
    if watermark_result.get("available"):
        plot_water_comparison(watermark_result, QC_DIR / "water_mask_comparison.png")

    # ---- persist ---------------------------------------------------------
    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "G",
        "scope": "pilot only - production not submitted",
        "products_evaluated": int(len(successful)),
        "unique_configurations": int(len(configs)),
        "coherence_thresholds": list(COHERENCE_THRESHOLDS),
        "configurations": configs,
    }
    (QC_DIR / "pilot_qc.json").write_text(json.dumps(payload, indent=2, default=str))
    pd.DataFrame(
        [
            {
                "config_key": c["config_key"],
                "pair_id": c["pair_id"],
                "apply_water_mask": c["apply_water_mask"],
                "copies": c["copies"],
                "layers_missing": ",".join(c["layers_missing"]),
                "crs": (c.get("raster") or {}).get("crs"),
                "pixel_size_m": (c.get("raster") or {}).get("res", [None])[0],
                "aoi_fully_inside": c.get("aoi_fully_inside_product"),
                "valid_fraction_of_full_raster": (c.get("coherence") or {}).get("valid_fraction"),
                "valid_fraction_of_aoi": (c.get("coherence") or {}).get("valid_fraction_of_aoi"),
                "median_coherence": (c.get("coherence") or {}).get("median"),
                "p25_coherence": (c.get("coherence") or {}).get("p25"),
                "frac_coh_gt_0.3": (c.get("coherence_fraction_above") or {}).get("0.3"),
                "components_in_aoi": (c.get("conncomp") or {}).get("components_in_aoi"),
                "largest_comp_frac": (c.get("conncomp") or {}).get(
                    "largest_component_fraction_of_aoi"
                ),
                "zip_mb": round(c["zip_bytes"] / 1e6, 2),
                "extracted_mb": round(c["extracted_bytes"] / 1e6, 2),
            }
            for c in configs
        ]
    ).to_csv(QC_DIR / "pilot_qc_summary.csv", index=False)

    (QC_DIR / "reproducibility.json").write_text(
        json.dumps(
            {
                "generated_utc": payload["generated_utc"],
                "origin": "INC-001: the pilot was accidentally submitted twice; both copies "
                "were preserved and are compared here as a determinism test.",
                "configurations_compared": len(reproducibility),
                "all_identical": all(r["all_layers_identical"] for r in reproducibility) if reproducibility else None,
                "results": reproducibility,
            },
            indent=2,
            default=str,
        )
    )
    (QC_DIR / "water_mask_comparison.json").write_text(
        json.dumps(watermark_result, indent=2, default=str)
    )
    (QC_DIR / "storage_estimate.json").write_text(json.dumps(storage, indent=2))

    print("\n" + "=" * 88)
    print("FILES WRITTEN")
    print("=" * 88)
    for name in (
        "pilot_qc.json",
        "pilot_qc_summary.csv",
        "reproducibility.json",
        "water_mask_comparison.json",
        "storage_estimate.json",
        "coherence_histogram.png",
        "conncomp_maps.png",
        "water_mask_comparison.png",
    ):
        print(f"  {QC_DIR / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
