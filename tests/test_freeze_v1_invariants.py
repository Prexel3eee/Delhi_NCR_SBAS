"""
Guards for the frozen v1 production baseline.

`scripts/verify_freeze.py` is the operator-facing check. These tests are the
same guarantee wired into the test-suite, so an accidental re-run of
`03_inventory_bursts.py` / `04_build_sbas_network.py` (which rewrite the
manifests a paid HyP3 submission depends on) fails CI immediately instead of
being noticed after credits are spent.

If a test here fails because the working tree legitimately moved on, that means
someone has changed the network: re-freeze deliberately as v2, do not relax the
test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FREEZE_MANIFEST = PROJECT_ROOT / "freeze" / "v1" / "FREEZE_v1.json"

pytestmark = pytest.mark.skipif(
    not FREEZE_MANIFEST.exists(),
    reason="freeze/v1 not present; run scripts/06_freeze_v1.py",
)

EXPECTED_ACQUISITIONS = 119
EXPECTED_PAIRS = 336
EXPECTED_K = 4
EXPECTED_EXCLUDED = ["2025-05-18"]


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(FREEZE_MANIFEST.read_text())


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_freeze_id_is_self_consistent(manifest):
    """The decision block must hash to the recorded freeze_id."""
    canonical = json.dumps(manifest["decision"], sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode()).hexdigest() == manifest["freeze_id"]


def test_frozen_snapshot_files_are_untouched(manifest):
    """Every file under freeze/v1 must still hash to its recorded value."""
    for entry in manifest["artefacts"]:
        snapshot = PROJECT_ROOT / entry["snapshot"]
        assert snapshot.exists(), f"missing frozen file {entry['snapshot']}"
        assert sha256_of(snapshot) == entry["sha256"], f"frozen file altered: {entry['snapshot']}"


def test_working_tree_still_matches_the_freeze(manifest):
    """Critical artefacts must not have drifted from the frozen v1 baseline."""
    drifted = []
    for entry in manifest["artefacts"]:
        if not entry["critical"]:
            continue
        live = PROJECT_ROOT / entry["path"]
        if not live.exists() or sha256_of(live) != entry["sha256"]:
            drifted.append(entry["path"])
    assert not drifted, (
        "critical artefacts drifted from freeze v1: "
        f"{drifted}. Re-freeze as v2 if this was intentional."
    )


def test_v1_decision_is_119_acquisitions_and_336_pairs():
    accepted = pd.read_csv(PROJECT_ROOT / "manifests/accepted_acquisitions.csv")
    pairs = pd.read_csv(PROJECT_ROOT / "manifests/sbas_pairs.csv")
    excluded = pd.read_csv(PROJECT_ROOT / "manifests/excluded_acquisitions.csv")

    assert len(accepted) == EXPECTED_ACQUISITIONS
    assert len(pairs) == EXPECTED_PAIRS
    assert set(pairs["burst_count"]) == {EXPECTED_K}
    assert sorted(excluded["date"].tolist()) == EXPECTED_EXCLUDED


def test_2025_05_18_is_not_recovered_for_v1(manifest):
    """The v1 policy is explicit: do not chase this acquisition."""
    assert manifest["decision"]["policy"]["recover_2025_05_18"] is False

    pairs = pd.read_csv(PROJECT_ROOT / "manifests/sbas_pairs.csv")
    assert not pairs["reference_date"].eq("2025-05-18").any()
    assert not pairs["secondary_date"].eq("2025-05-18").any()

    accepted = pd.read_csv(PROJECT_ROOT / "manifests/accepted_acquisitions.csv")
    assert not accepted["date"].eq("2025-05-18").any()


def test_no_pair_may_reference_an_unfrozen_burst(manifest):
    """Every emitted job payload must use exactly the frozen burst identities."""
    frozen = sorted(manifest["summary"]["full_burst_ids"])
    pairs = pd.read_csv(PROJECT_ROOT / "manifests/sbas_pairs.csv")
    assert all(json.loads(s) == frozen for s in pairs["reference_burst_ids_json"])
    assert all(json.loads(s) == frozen for s in pairs["secondary_burst_ids_json"])


def test_production_has_not_been_submitted(manifest):
    """v1 is frozen pending pilot QC; production stays blocked."""
    cost = json.loads((PROJECT_ROOT / "qc/cost_estimate.json").read_text())
    assert manifest["summary"]["production_submitted"] is False
    assert cost["production_submitted"] is False
