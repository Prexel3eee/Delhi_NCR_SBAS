#!/usr/bin/env python
"""
Phase G - pilot MintPy preparation and ingestion test.

Runs in `delhi-mintpy`. Two separate concerns, deliberately not conflated:

1. **Common overlap** - the intersection of every accepted product's raster
   extent. The AOI must lie inside it. All layers are then clipped to ONE
   identical grid; individual products are never cropped independently.

2. **Ingestion test** - build a MintPy template over the clipped layers and run
   `smallbaselineApp.py --dostep load_data` to prove MintPy can read these HyP3
   multi-burst products. This is a *loadability* test, not a scientific
   inversion: the pilot pairs are not a connected time series, so a full SBAS
   inversion is neither expected nor attempted.

Only water-mask=ON configurations are used, because the control product lacks
the water-mask layer and MintPy needs a consistent layer set across the network.
The water-mask comparison lives in `09_qc_pilot.py`.

Outputs (mintpy/)
-----------------
pilot_clipped/            clipped layers on a common grid
mintpy_pilot.txt          MintPy template for the pilot subset
<stem>_common_overlap.json    overlap geometry and clipping provenance
<stem>_ingestion_report.json  what MintPy actually loaded
                              (stem = pilot | production)

Usage
-----
    python scripts/10_prepare_mintpy.py --scope pilot       # 7 pilot configurations
    python scripts/10_prepare_mintpy.py --scope production  # full 336-pair corpus

smallbaselineApp.log      raw MintPy output

Usage
-----
    python scripts/10_prepare_mintpy_pilot.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import Window
from shapely.geometry import shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "manifests"
MINTpy_DIR = PROJECT_ROOT / "mintpy"
GEOMETRY_DIR = PROJECT_ROOT / "geometry"

#: Scope-dependent settings, assigned by `configure_scope`.
#:   pilot      - the 7 pilot configurations, pilot inventory and work dirs
#:   production - the full 336-pair corpus (all water mask ON)
CLIP_DIR: Path = MINTpy_DIR / "pilot_clipped"
WORK_DIR: Path = MINTpy_DIR / "pilot_work"
TEMPLATE_PATH: Path = MINTpy_DIR / "mintpy_pilot.txt"
INVENTORY_PATH: Path = MANIFEST_DIR / "product_inventory.csv"
QC_DIR: Path = PROJECT_ROOT / "qc" / "pilot"
REPORT_STEM = "pilot"
MASKED_ONLY = True
SCOPE = "pilot"


def configure_scope(scope: str) -> None:
    """Point every module-level path at the requested scope.

    Helper functions read these as globals, so reassigning them here is enough
    to reuse the whole validated pipeline for production.
    """
    global CLIP_DIR, WORK_DIR, TEMPLATE_PATH, INVENTORY_PATH, QC_DIR, REPORT_STEM, MASKED_ONLY, SCOPE
    SCOPE = scope
    if scope == "production":
        CLIP_DIR = MINTpy_DIR / "production_clipped"
        WORK_DIR = MINTpy_DIR / "production_work"
        TEMPLATE_PATH = MINTpy_DIR / "mintpy_production.txt"
        INVENTORY_PATH = MANIFEST_DIR / "production_product_inventory.csv"
        QC_DIR = PROJECT_ROOT / "qc" / "production"
        REPORT_STEM = "production"
        MASKED_ONLY = False  # every production product was submitted with the mask ON
    else:
        CLIP_DIR = MINTpy_DIR / "pilot_clipped"
        WORK_DIR = MINTpy_DIR / "pilot_work"
        TEMPLATE_PATH = MINTpy_DIR / "mintpy_pilot.txt"
        INVENTORY_PATH = MANIFEST_DIR / "product_inventory.csv"
        QC_DIR = PROJECT_ROOT / "qc" / "pilot"
        REPORT_STEM = "pilot"
        MASKED_ONLY = True

#: Layers MintPy loads, in template-key order.
LAYER_SUFFIXES = {
    "unwFile": "_unw_phase.tif",
    "corFile": "_corr.tif",
    "connCompFile": "_conncomp.tif",
    "demFile": "_dem.tif",
    "incAngleFile": "_lv_theta.tif",
    "azAngleFile": "_lv_phi.tif",
    "waterMaskFile": "_water_mask.tif",
}


def load_aoi():
    """The AOI as stored, in EPSG:4326 (lon/lat)."""
    payload = json.loads((GEOMETRY_DIR / "aoi.geojson").read_text())
    return shape(payload["features"][0]["geometry"])


def aoi_in_crs(aoi, crs):
    """Reproject the AOI into the raster CRS (products are UTM, the AOI is lon/lat)."""
    return shape(transform_geom("EPSG:4326", crs, aoi.__geo_interface__))


def find_layers(product_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in product_dir.rglob("*"):
        if not path.is_file() or not path.name.endswith(".tif"):
            continue
        for key, suffix in LAYER_SUFFIXES.items():
            if path.name.endswith(suffix):
                found[key] = path
    return found


def select_products(inventory: pd.DataFrame) -> pd.DataFrame:
    """One copy per unique configuration.

    Pilot: only water-mask=ON products (the control lacks the mask layer, and
    MintPy needs a consistent layer set).
    Production: every product was submitted with the mask ON, so all are used.
    In both scopes a duplicate job name keeps only one copy.
    """
    ok = inventory[inventory["download_ok"].fillna(False).astype(bool)].copy()
    if MASKED_ONLY:
        ok = ok[ok["apply_water_mask"] == True]  # noqa: E712
    return (
        ok.sort_values("extracted_bytes", ascending=False)
        .drop_duplicates(subset=["pair_id", "apply_water_mask"])
        .sort_values("pair_id")
        .reset_index(drop=True)
    )


def common_overlap(products: pd.DataFrame) -> tuple[list[float], dict, str]:
    """Intersection of all product extents, in the shared CRS."""
    bounds_list = []
    crs_list = []
    for row in products.itertuples():
        layers = find_layers(PROJECT_ROOT / row.extract_dir)
        geometry_layer = layers.get("demFile") or layers.get("corFile")
        with rasterio.open(geometry_layer) as src:
            bounds_list.append(src.bounds)
            crs_list.append(str(src.crs))

    if len(set(crs_list)) != 1:
        raise SystemExit(f"FAIL: products span multiple CRSs: {sorted(set(crs_list))}")

    left = max(b.left for b in bounds_list)
    bottom = max(b.bottom for b in bounds_list)
    right = min(b.right for b in bounds_list)
    top = min(b.top for b in bounds_list)
    if left >= right or bottom >= top:
        raise SystemExit("FAIL: products have no common overlap")

    return [left, bottom, right, top], {
        "crs": crs_list[0],
        "products": len(products),
        "per_product_bounds": [[round(v, 3) for v in b] for b in bounds_list],
    }, crs_list[0]


def clip_all(products: pd.DataFrame, overlap: list[float], aoi) -> tuple[list[dict], dict]:
    """Clip every layer of every product onto ONE identical target grid.

    Products are NOT on byte-identical grids: each pair geocodes to slightly
    different extents (different burst coverage), so a naive
    "assert same transform and read the same window" approach fails. They do
    share CRS and pixel size, and their origins differ by whole pixels, so a
    single target grid is defined from the common overlap and every layer is
    read boundlessly onto it (padding with nodata where a product is smaller).

    Never crop products independently: the same window is used for all layers of
    all pairs.
    """
    CLIP_DIR.mkdir(parents=True, exist_ok=True)

    # ---- 1. define the single target grid --------------------------------
    first_layers = find_layers(PROJECT_ROOT / products.iloc[0].extract_dir)
    first_geo = first_layers.get("demFile") or first_layers.get("corFile")
    with rasterio.open(first_geo) as src:
        target_crs = src.crs
        target_res = (abs(src.transform.a), abs(src.transform.e))
        raw = rasterio.windows.from_bounds(*overlap, transform=src.transform)
        win = Window(
            int(np.floor(raw.col_off)),
            int(np.floor(raw.row_off)),
            int(np.ceil(raw.width)),
            int(np.ceil(raw.height)),
        ).intersection(Window(0, 0, src.width, src.height))
        target_transform = rasterio.windows.transform(win, src.transform)
        target_h, target_w = int(win.height), int(win.width)
        target_bounds = rasterio.transform.array_bounds(target_h, target_w, target_transform)

    aoi_local = aoi_in_crs(aoi, target_crs)
    inside = geometry_mask(
        [aoi_local.__geo_interface__],
        out_shape=(target_h, target_w),
        transform=target_transform,
        invert=True,
    )
    if not inside.any():
        raise SystemExit("FAIL: AOI does not intersect the common overlap")
    aoi_fully_inside = bool(
        target_bounds[0] <= aoi_local.bounds[0]
        and target_bounds[1] <= aoi_local.bounds[1]
        and target_bounds[2] >= aoi_local.bounds[2]
        and target_bounds[3] >= aoi_local.bounds[3]
    )

    # ---- 2. read every layer of every product onto that grid -------------
    records: list[dict] = []
    alignment_notes: list[str] = []

    for row in products.itertuples():
        layers = find_layers(PROJECT_ROOT / row.extract_dir)
        written: list[str] = []

        for key, path in sorted(layers.items()):
            with rasterio.open(path) as src:
                if src.crs != target_crs:
                    raise SystemExit(f"FAIL: {path.name} CRS {src.crs} != {target_crs}")
                res = (abs(src.transform.a), abs(src.transform.e))
                if not (
                    abs(res[0] - target_res[0]) < 1e-6
                    and abs(res[1] - target_res[1]) < 1e-6
                ):
                    raise SystemExit(
                        f"FAIL: {path.name} resolution {res} != target {target_res}"
                    )

                raw = rasterio.windows.from_bounds(*target_bounds, transform=src.transform)
                col_off, row_off = round(raw.col_off), round(raw.row_off)
                # origins must differ by whole pixels in this shared grid
                snapped = (
                    src.transform.c + col_off * src.transform.a,
                    src.transform.f + row_off * src.transform.e,
                )
                drift = max(abs(snapped[0] - target_bounds[0]), abs(snapped[1] - target_bounds[3]))
                if drift > 1e-6:
                    alignment_notes.append(
                        f"{row.pair_id} {key}: {drift:.6f} m grid offset (snapped)"
                    )

                data = src.read(
                    1,
                    window=Window(col_off, row_off, target_w, target_h),
                    boundless=True,
                    fill_value=src.nodata if src.nodata is not None else 0,
                )
                profile = src.profile.copy()
                profile.update(
                    width=target_w,
                    height=target_h,
                    transform=target_transform,
                    compress="deflate",
                    tiled=False,
                )

            # Keep the ORIGINAL HyP3 stem: MintPy's hyp3 prep parses the product
            # name (which encodes both acquisition dates) from the filename. A
            # renamed file such as "20250211_20250223_unwFile_clipped.tif" makes
            # prep_hyp3 raise "Failed to parse product name from filename".
            out_name = f"{path.stem}_clipped{path.suffix}"
            with rasterio.open(CLIP_DIR / out_name, "w", **profile) as dst:
                dst.write(data, 1)
            written.append(out_name)

        # The HyP3 metadata .txt must sit beside the clipped rasters: prep_hyp3
        # looks for "<product_name>.txt" in the raster's own directory.
        metadata_copied = []
        for txt in sorted((PROJECT_ROOT / row.extract_dir).rglob("*.txt")):
            if "README" in txt.name:
                continue
            target = CLIP_DIR / txt.name
            shutil.copy2(txt, target)
            metadata_copied.append(txt.name)

        records.append(
            {
                "pair_id": row.pair_id,
                "product_dir": row.extract_dir,
                "layers_clipped": written,
                "layers_available": sorted(layers),
                "metadata_copied": metadata_copied,
            }
        )

    provenance = {
        "common_overlap_bounds": [round(v, 3) for v in overlap],
        "target_grid": {
            "crs": str(target_crs),
            "transform": [round(v, 6) for v in list(target_transform)[:6]],
            "width": target_w,
            "height": target_h,
            "res": [round(v, 3) for v in target_res],
            "bounds": [round(v, 3) for v in target_bounds],
            "aoi_pixels": int(inside.sum()),
        },
        "aoi_fully_inside_common_overlap": aoi_fully_inside,
        "aoi_bounds_in_target_crs": [round(v, 3) for v in aoi_local.bounds],
        "aoi_source_crs": "EPSG:4326",
        "grid_alignment_notes": alignment_notes,
        "note": "products are not byte-identical grids; all layers are read onto "
        "one shared target grid derived from the common overlap",
    }
    return records, provenance


def write_template(records: list[dict], provenance: dict) -> Path:
    """MintPy template using explicit globs over the clipped layers."""
    lines = [
        "# Delhi-NCR multi-burst pilot - MintPy ingestion test",
        f"# Generated by scripts/10_prepare_mintpy_pilot.py (scope={SCOPE})",
        f"# common overlap bounds: {provenance['common_overlap_bounds']}",
        "",
        "mintpy.load.processor        = hyp3",
        "",
        "## interferograms",
        f"mintpy.load.unwFile          = {CLIP_DIR}/*_unw_phase_clipped.tif",
        f"mintpy.load.corFile          = {CLIP_DIR}/*_corr_clipped.tif",
        f"mintpy.load.connCompFile     = {CLIP_DIR}/*_conncomp_clipped.tif",
        "",
        "## geometry",
        f"mintpy.load.demFile          = {CLIP_DIR}/*_dem_clipped.tif",
        f"mintpy.load.incAngleFile     = {CLIP_DIR}/*_lv_theta_clipped.tif",
        f"mintpy.load.azAngleFile      = {CLIP_DIR}/*_lv_phi_clipped.tif",
        f"mintpy.load.waterMaskFile    = {CLIP_DIR}/*_water_mask_clipped.tif",
        "",
        "## pilot ingestion test settings",
        "mintpy.network.coherenceBased = no",
        "mintpy.troposphericDelay.method = no",
        "mintpy.plot                  = no",
        "",
    ]
    TEMPLATE_PATH.write_text("\n".join(lines))
    return TEMPLATE_PATH


def run(cmd: list[str], log_path: Path, label: str) -> tuple[int, str]:
    print(f"\n  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    output = (result.stdout or "") + (result.stderr or "")
    log_path.write_text(
        f"# {label}\n# command: {' '.join(str(c) for c in cmd)}\n# exit: {result.returncode}\n\n{output}"
    )
    return result.returncode, output


def main() -> int:
    MINTpy_DIR.mkdir(parents=True, exist_ok=True)
    QC_DIR.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("pilot", "production"), default="pilot",
                        help="pilot (default) or the full 336-pair production corpus")
    args = parser.parse_args()
    configure_scope(args.scope)

    inventory_path = INVENTORY_PATH
    if not inventory_path.exists():
        print(f"FAIL: {inventory_path} not found. Download products first.")
        return 1
    inventory = pd.read_csv(inventory_path)
    products = select_products(inventory)
    if products.empty:
        print("FAIL: no downloadable water-mask=ON products yet.")
        return 1

    aoi = load_aoi()

    print("=" * 88)
    print("PHASE G - PILOT MINTPY PREPARATION AND INGESTION TEST")
    print("=" * 88)
    print(f"\nProducts selected for ingestion: {len(products)}")
    for row in products.itertuples():
        print(f"  {row.pair_id}  {row.extract_dir}")

    overlap, overlap_meta, crs = common_overlap(products)
    print(f"\nCommon overlap (CRS {crs}): {[round(v, 3) for v in overlap]}")

    records, provenance = clip_all(products, overlap, aoi)
    provenance.update(overlap_meta)
    provenance["generated_utc"] = datetime.now(timezone.utc).isoformat()

    grid = provenance["target_grid"]
    print(f"\nTarget grid : {grid['width']}x{grid['height']} px @ {grid['res'][0]} m, {grid['crs']}")
    print(f"Target bounds: {grid['bounds']}")
    print(f"AOI inside common overlap: {provenance['aoi_fully_inside_common_overlap']}")
    for record in records:
        print(f"  clipped {record['pair_id']}: {len(record['layers_clipped'])} layers")

    template = write_template(records, provenance)
    print(f"\nTemplate: {template}")

    # ---- prep_hyp3.py (ROI_PAC .rsc metadata) ----------------------------
    print("\n" + "-" * 88)
    print("prep_hyp3.py")
    print("-" * 88)
    clipped_tifs = sorted(str(p) for p in CLIP_DIR.glob("*_clipped.tif"))
    prep_code, _prep_output = run(
        ["prep_hyp3.py", *clipped_tifs], MINTpy_DIR / "prep_hyp3.log", "prep_hyp3.py"
    )
    prep_ok = prep_code == 0
    rsc_count = len(list(CLIP_DIR.glob("*.rsc")))
    print(f"  exit={prep_code} {'OK' if prep_ok else '(non-fatal: the MintPy hyp3 loader reads GeoTIFF metadata directly)'}")
    print(f"  .rsc files created: {rsc_count}")

    # ---- ingestion test --------------------------------------------------
    print("\n" + "-" * 88)
    print("smallbaselineApp.py --dostep load_data")
    print("-" * 88)
    load_code, output = run(
        [
            "smallbaselineApp.py",
            "--dir",
            str(WORK_DIR),
            "--dostep",
            "load_data",
            str(template),
        ],
        MINTpy_DIR / "smallbaselineApp.log",
        "MintPy load_data ingestion test",
    )
    ingestion_ok = load_code == 0

    # what did MintPy actually load?
    work = WORK_DIR
    loaded: dict = {"work_dir": str(work), "exists": work.exists()}
    if work.exists():
        files = sorted(p.name for p in work.rglob("*") if p.is_file())
        loaded["files"] = files[:40]
        loaded["file_count"] = len(files)
        for candidate in ("inputs/ifgramStack.h5", "ifgramStack.h5"):
            target = work / candidate
            if target.exists():
                loaded["ifgram_stack"] = candidate
                try:
                    import h5py

                    with h5py.File(target, "r") as handle:
                        loaded["ifgram_stack_keys"] = sorted(handle.keys())
                        if "date" in handle:
                            loaded["n_interferograms"] = int(handle["date"].shape[0])
                            dates = np.array(handle["date"]).astype(str)
                            loaded["acquisition_dates"] = sorted(
                                {d for pair in dates for d in pair}
                            )
                        if "bperp" in handle:
                            loaded["bperp_shape"] = list(handle["bperp"].shape)
                except Exception as exc:  # noqa: BLE001
                    loaded["ifgram_stack_error"] = f"{type(exc).__name__}: {exc}"
                break

    report = {
        "generated_utc": provenance["generated_utc"],
        "phase": "G",
        "scope": "pilot ingestion test only - no inversion attempted",
        "rationale": "the pilot pairs are not a connected time series, so a full SBAS "
        "inversion is neither expected nor meaningful at this stage",
        "products_ingested": int(len(products)),
        "pair_ids": list(products["pair_id"]),
        "common_overlap": provenance,
        "prep_hyp3": {
            "exit_code": prep_code,
            "rsc_files_created": rsc_count,
            "ok": prep_ok,
            "note": "non-fatal if it fails; the MintPy hyp3 loader reads GeoTIFF metadata directly",
        },
        "load_data": {"exit_code": load_code, "ok": ingestion_ok},
        "loaded": loaded,
        "log_tail": output.strip().splitlines()[-25:],
    }
    (MINTpy_DIR / f"{REPORT_STEM}_common_overlap.json").write_text(json.dumps(provenance, indent=2))
    (MINTpy_DIR / f"{REPORT_STEM}_ingestion_report.json").write_text(json.dumps(report, indent=2, default=str))
    (QC_DIR / "mintpy_ingestion.json").write_text(json.dumps(report, indent=2, default=str))

    print("\n" + "=" * 88)
    print("MINTPY INGESTION RESULT")
    print("=" * 88)
    print(f"  prep_hyp3 exit        : {prep_code} ({rsc_count} .rsc files)")
    print(f"  load_data exit        : {load_code}")
    print(f"  ifgram stack          : {loaded.get('ifgram_stack', 'NOT FOUND')}")
    if "n_interferograms" in loaded:
        print(f"  interferograms loaded : {loaded['n_interferograms']}")
        print(f"  acquisition dates     : {len(loaded.get('acquisition_dates', []))}")
    print(f"  report                : {MINTpy_DIR / f'{REPORT_STEM}_ingestion_report.json'}")

    if not ingestion_ok:
        print("\n  MintPy output tail:")
        for line in output.strip().splitlines()[-20:]:
            print(f"    {line}")
    return 0 if ingestion_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
