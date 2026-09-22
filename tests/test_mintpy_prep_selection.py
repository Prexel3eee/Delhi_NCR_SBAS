"""
Regression test for the MintPy preparation product selection.

Pins a schema mismatch that killed the first production preparation run:
`manifests/production_product_inventory.csv` is written by
`13_download_production.py`, which did not record an `apply_water_mask` column
(the pilot inventory from `08_download_pilot.py` did). `select_products()`
unconditionally deduplicated on that column and died with

    KeyError: Index(['apply_water_mask'], dtype='str')

before clipping a single raster.

The fix derives the flag from the HyP3 job name when the column is absent, so a
schema drift between the pilot and production inventories cannot break the
pipeline again.

Requires rasterio (module-level import in script 10), so this file skips in the
search/submission environment and runs in `delhi-mintpy`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("rasterio", reason="script 10 imports rasterio at module level")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "10_prepare_mintpy.py"
PREFIX = "delhi_ncr_sbas_a27_v1_prod"


@pytest.fixture(scope="module")
def prep():
    spec = importlib.util.spec_from_file_location("mintpy_prep_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_inventory(with_mask_column: bool, include_nomask: bool = False) -> pd.DataFrame:
    """Fake inventory.

    `include_nomask` mirrors the PILOT, which had a water-mask control copy.
    Production submitted every pair with the mask ON, so it has none.
    """
    rows = []
    for pair_id in ("20211006_20211018", "20211006_20211030", "20211018_20211030"):
        rows.append(
            {
                "job_id": f"id-{pair_id}",
                "job_name": f"{PREFIX}_{pair_id}",
                "pair_id": pair_id,
                "download_ok": True,
                "extracted_bytes": 126_000_000,
            }
        )
    if include_nomask:
        rows.append(
            {
                "job_id": "id-nomask",
                "job_name": f"{PREFIX}_20211006_20211018_nomask",
                "pair_id": "20211006_20211018",
                "download_ok": True,
                "extracted_bytes": 126_000_000,
            }
        )
    frame = pd.DataFrame(rows)
    if with_mask_column:
        frame["apply_water_mask"] = ~frame["job_name"].str.endswith("_nomask")
    return frame


def test_select_products_tolerates_a_missing_mask_column(prep):
    """The production inventory has no apply_water_mask column."""
    prep.configure_scope("production")
    inventory = make_inventory(with_mask_column=False)
    assert "apply_water_mask" not in inventory.columns

    selected = prep.select_products(inventory)

    assert len(selected) > 0, "selection must not fail on the legacy schema"
    assert selected["apply_water_mask"].all(), "derived flag must be True without a _nomask name"


def test_select_products_derives_the_flag_from_the_job_name(prep):
    """A _nomask job name must derive apply_water_mask=False."""
    prep.configure_scope("production")
    inventory = make_inventory(with_mask_column=False, include_nomask=True)
    selected = prep.select_products(inventory)
    nomask = selected[selected["job_name"].str.endswith("_nomask")]
    assert len(nomask) == 1
    assert bool(nomask["apply_water_mask"].iloc[0]) is False


def test_select_products_is_one_row_per_pair(prep):
    prep.configure_scope("production")
    inventory = make_inventory(with_mask_column=False)
    selected = prep.select_products(inventory)
    assert selected["pair_id"].is_unique, "exactly one product per pair"


def test_pilot_scope_still_keeps_only_masked_products(prep):
    prep.configure_scope("pilot")
    inventory = make_inventory(with_mask_column=True, include_nomask=True)
    selected = prep.select_products(inventory)
    assert selected["apply_water_mask"].all(), "pilot ingestion must exclude the control"
    assert not selected["job_name"].str.endswith("_nomask").any()


def test_scope_switching_is_reversible(prep):
    prep.configure_scope("production")
    production = (prep.CLIP_DIR.name, prep.REPORT_STEM, prep.MASKED_ONLY)
    prep.configure_scope("pilot")
    pilot = (prep.CLIP_DIR.name, prep.REPORT_STEM, prep.MASKED_ONLY)

    assert production == ("production_clipped", "production", False)
    assert pilot == ("pilot_clipped", "pilot", True)
