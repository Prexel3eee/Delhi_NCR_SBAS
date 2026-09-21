"""
Regression tests for the three ASF/CMR silent-failure modes.

Each of these was observed on live data while building the v1 network, and each
would have silently produced a *wrong but plausible* SBAS network. The tests are
offline: no network access, all ASF/CMR I/O is faked. They exist to pin the
guards in `scripts/asf_client.py` so a future refactor cannot quietly remove
them.

Failure mode 1 - `asf_search.search()` raises `ASFSearchError` for valid windows.
Failure mode 2 - CMR's `POLARIZATION` attribute filter reports more hits than it
                 serves, silently omitting a granule.
Failure mode 3 - `ASFProduct.stack()` returns truncated results, and
                 `check_reference` silently substitutes `stack[0]` as the
                 baseline reference when the fixed reference is absent.
"""

from __future__ import annotations

import json
import urllib.parse
from datetime import date, datetime, timedelta, timezone

import pytest
import asf_search as asf

import asf_client as ac


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

FULL_BURST_ID = "027_056011_IW2"
TARGET_DATE = "2025-05-18"
TARGET_TIME = "2025-05-18T12:55:36.000000Z"


def umm_item(granule_ur: str, polarization: str, begin: str) -> dict:
    """Minimal CMR UMM-JSON item in the shape `_cmr_item_to_record` consumes."""
    return {
        "umm": {
            "GranuleUR": granule_ur,
            "TemporalExtent": {
                "RangeDateTime": {"BeginningDateTime": begin, "EndingDateTime": begin}
            },
            "Platforms": [{"ShortName": "Sentinel-1A"}],
            "RelatedUrls": [{"Type": "GET DATA", "URL": "https://example.invalid/x.tiff"}],
            "AdditionalAttributes": [
                {"Name": "BURST_ID_FULL", "Values": [FULL_BURST_ID]},
                {"Name": "POLARIZATION", "Values": [polarization]},
                {"Name": "BURST_ID_RELATIVE", "Values": ["56011"]},
                {"Name": "BURST_ID_ABSOLUTE", "Values": ["127260595"]},
                {"Name": "BURST_INDEX", "Values": ["8"]},
                {"Name": "SUBSWATH_NAME", "Values": ["IW2"]},
                {"Name": "PATH_NUMBER", "Values": ["27"]},
                {"Name": "ASCENDING_DESCENDING", "Values": ["ASCENDING"]},
                {"Name": "AZIMUTH_TIME", "Values": [begin]},
                {"Name": "AZIMUTH_ANX_TIME", "Values": ["454.1"]},
                {"Name": "BYTE_LENGTH", "Values": ["152943336"]},
                {"Name": "GROUP_ID", "Values": ["S1A_IWDV_0086_0092_059249_027"]},
            ],
        }
    }


def vv_vh_pair(date_str: str, time_str: str) -> list[dict]:
    stamp = f"{date_str}T{time_str}"
    return [
        umm_item(f"S1_056011_IW2_{date_str.replace('-', '')}T{time_str[:6]}_VH_6366-BURST", "VH", stamp),
        umm_item(f"S1_056011_IW2_{date_str.replace('-', '')}T{time_str[:6]}_VV_6366-BURST", "VV", stamp),
    ]


class FakeBaselineProduct:
    """Stand-in for an `S1BurstProduct` carrying baseline values."""

    def __init__(self, scene: str, start: str, temporal=None, perp=None, no_state_vectors=False):
        self.properties = {
            "sceneName": scene,
            "startTime": start,
            "processingLevel": "BURST",
        }
        if temporal is not None:
            self.properties["temporalBaseline"] = temporal
        if perp is not None:
            self.properties["perpendicularBaseline"] = perp
        self.baseline = {"noStateVectors": no_state_vectors}


class FakeSearchResults(list):
    """Minimal stand-in for `ASFSearchResults`.

    `_asf_search_once` calls `raise_if_incomplete()`, so fakes must provide it.
    By default it is a no-op (a complete search); set `incomplete=True` to make
    it raise the way a truncated real CMR response does.
    """

    searchComplete = True

    def __init__(self, *args, incomplete: bool = False):
        super().__init__(*args)
        self.searchComplete = not incomplete
        self._incomplete = incomplete

    def raise_if_incomplete(self):
        if self._incomplete:
            raise ASFSearchError("Results are incomplete due to a search error.")
        return self


class ASFSearchError(Exception):
    """Local stand-in so tests do not depend on the library's class path."""


# ---------------------------------------------------------------------------
# Failure mode 1: asf_search raising on valid windows
# ---------------------------------------------------------------------------


def test_soft_split_records_day_level_failures_without_raising(monkeypatch):
    """A window that always fails must be split to day level and recorded, not fatal."""
    calls: list[tuple[str, str]] = []

    def always_fail(fullBurstID=None, start=None, end=None, polarization=None, **kwargs):
        calls.append((start, end))
        raise ASFSearchError("Results are incomplete due to a search error.")

    monkeypatch.setattr(ac.asf, "search", always_fail)

    failures: list[dict] = []
    products = ac._asf_search_windowed_soft(
        FULL_BURST_ID,
        "2025-05-01T00:00:00Z",
        "2025-05-05T00:00:00Z",
        "VV",
        tries=1,
        depth=0,
        failures=failures,
    )

    assert products == []
    # It really did recurse rather than give up on the whole span.
    assert len(calls) > 1
    assert failures, "a failing window must be recorded, never silently dropped"
    assert all("start" in f and "error" in f for f in failures)


def test_soft_split_recovers_good_subwindows_around_a_bad_one(monkeypatch):
    """Only the failing day is lost; neighbouring days are still returned."""
    bad_day = datetime(2025, 5, 18, tzinfo=timezone.utc)

    def flaky(fullBurstID=None, start=None, end=None, polarization=None, **kwargs):
        start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if start_dt <= bad_day <= end_dt:
            raise ASFSearchError("Results are incomplete due to a search error.")
        return FakeSearchResults([FakeBaselineProduct(f"scene_{start[:10]}", start)])

    monkeypatch.setattr(ac.asf, "search", flaky)

    failures: list[dict] = []
    products = ac._asf_search_windowed_soft(
        FULL_BURST_ID,
        "2025-05-06T00:00:00Z",
        "2025-05-30T00:00:00Z",
        "VV",
        tries=1,
        depth=0,
        failures=failures,
    )

    assert products, "good sub-windows must survive a failing neighbour"
    assert failures, "the failing day must be recorded"
    # Every recorded failure must be a window that genuinely contains the bad day;
    # nothing outside it may be abandoned.
    for failure in failures:
        start_dt = datetime.strptime(failure["start"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        end_dt = datetime.strptime(failure["end"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        assert start_dt <= bad_day <= end_dt, f"unexpected failure window {failure}"


def test_inventory_uses_cmr_and_records_asf_failure(monkeypatch):
    """asf_search failing must not change or block the authoritative CMR result."""
    served = vv_vh_pair("2025-05-18", "12:55:36")

    monkeypatch.setattr(
        ac, "cmr_burst_inventory", lambda *a, **k: [ac._cmr_item_to_record(served[0], "cmr_umm")]
    )

    def asf_explodes(*args, **kwargs):
        raise ASFSearchError("Results are incomplete due to a search error.")

    monkeypatch.setattr(ac, "asf_burst_inventory", asf_explodes)

    result = ac.burst_inventory(FULL_BURST_ID, "2025-05-18T00:00:00Z", "2025-05-19T00:00:00Z")

    assert len(result.records) == 1
    assert result.records[0].scene_name.endswith("VH_6366-BURST")
    assert "ASFSearchError" in result.provenance["asf_search"]["error"]
    assert result.provenance["asf_search"]["agree"] is False


# ---------------------------------------------------------------------------
# Failure mode 2: CMR polarization filter silently omitting granules
# ---------------------------------------------------------------------------


def test_cmr_request_never_sends_a_polarization_attribute_filter(monkeypatch):
    """Guard the exact regression: the POLARIZATION filter drops a granule."""
    captured: dict[str, str] = {}

    class FakeResponse:
        headers = {"CMR-Hits": "0"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"items": []}).encode()

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setattr(ac.urllib.request, "urlopen", fake_urlopen)

    ac._cmr_umm_page(FULL_BURST_ID, "2021-10-01T00:00:00Z", "2025-10-01T00:00:00Z", 1, 500)

    url = captured["url"]
    assert "BURST_ID_FULL" in urllib.parse.unquote(url)
    assert "POLARIZATION" not in urllib.parse.unquote(url), (
        "the POLARIZATION attribute filter makes CMR report hits it will not serve"
    )


def test_vv_vh_consistency_check_detects_missing_granule():
    vh_only = vv_vh_pair("2025-05-18", "12:55:36")[0:1]  # VH only
    consistent, reason = ac._cmr_window_is_consistent(vh_only)
    assert consistent is False
    assert "VV=0" in reason and "VH=1" in reason

    both = vv_vh_pair("2025-05-18", "12:55:36")
    consistent, reason = ac._cmr_window_is_consistent(both)
    assert consistent is True

    # Mismatched timestamps must also be caught, not just a missing sibling.
    skewed = [both[0], umm_item("S1_056011_IW2_20250518T125536_VV_zzzz-BURST", "VV", "2025-05-19T00:00:00Z")]
    consistent, reason = ac._cmr_window_is_consistent(skewed)
    assert consistent is False
    assert "timestamps differ" in reason


def test_cmr_inventory_splits_a_window_and_recovers_the_missing_granule(monkeypatch):
    """Reproduce the live bug: wide windows drop VV, narrow ones serve it."""
    drop_above_days = 10.0

    def fake_page(full_burst_id, start, end, page_num, page_size):
        span = (
            datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ")
            - datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
        ).total_seconds() / 86400.0
        items = vv_vh_pair("2025-05-18", "12:55:36")
        if span > drop_above_days:
            # Emulate CMR: the VV granule is counted in hits but not served.
            items = [i for i in items if "_VH_" in i["umm"]["GranuleUR"]]
        # CMR always counts 2 hits, regardless of what it serves.
        return items, 2

    monkeypatch.setattr(ac, "_cmr_umm_page", fake_page)

    diagnostics: list[dict] = []
    records = ac.cmr_burst_inventory(
        FULL_BURST_ID,
        "2025-05-01T00:00:00Z",
        "2025-06-01T00:00:00Z",
        "VV",
        window_days=90,
        tries=1,
        diagnostics=diagnostics,
    )

    assert [r.polarization for r in records] == ["VV"], "the VV granule must be recovered by splitting"
    assert any(d["status"] == "split" for d in diagnostics), "splitting must be recorded"
    assert not [d for d in diagnostics if d["status"] == "UNRESOLVED"]


def test_cmr_inventory_records_unresolved_and_never_fabricates(monkeypatch):
    """When CMR never serves the granule we record it; we do not invent it."""

    def fake_page(full_burst_id, start, end, page_num, page_size):
        # Only ever serve VH, exactly like the live 2025-05-18 behaviour.
        return [vv_vh_pair("2025-05-18", "12:55:36")[0]], 2

    monkeypatch.setattr(ac, "_cmr_umm_page", fake_page)

    diagnostics: list[dict] = []
    records = ac.cmr_burst_inventory(
        FULL_BURST_ID,
        "2025-05-18T00:00:00Z",
        "2025-05-19T00:00:00Z",
        "VV",
        window_days=90,
        tries=1,
        diagnostics=diagnostics,
    )

    assert records == [], "a VV record must never be fabricated from a VH granule"
    unresolved = [d for d in diagnostics if d["status"] == "UNRESOLVED"]
    assert unresolved, "an unresolvable window must be recorded explicitly"
    assert "VV=0" in unresolved[0]["reason"]


def test_burst_inventory_fails_closed_when_no_granule_is_available(monkeypatch):
    """If neither source yields the requested granule we raise, never invent one."""

    def fake_page(full_burst_id, start, end, page_num, page_size):
        # Only VH is ever served, so a VV inventory cannot be established.
        return [vv_vh_pair("2025-05-18", "12:55:36")[0]], 2

    monkeypatch.setattr(ac, "_cmr_umm_page", fake_page)
    monkeypatch.setattr(
        ac,
        "asf_burst_inventory",
        lambda *a, **k: (_ for _ in ()).throw(ASFSearchError("incomplete")),
    )

    with pytest.raises(ac.InventoryError) as excinfo:
        ac.burst_inventory(FULL_BURST_ID, "2025-05-18T00:00:00Z", "2025-05-19T00:00:00Z")

    assert "No inventory" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Failure mode 3: stack() truncation and silent reference substitution
# ---------------------------------------------------------------------------


def test_fixed_reference_is_injected_into_every_baseline_window(monkeypatch):
    """The guard that stops `check_reference` substituting `stack[0]`."""
    reference_scene = "S1_056011_IW2_20211006T125536_VV_4BD1-BURST"
    reference = FakeBaselineProduct(reference_scene, "2021-10-06T12:55:36.000000Z")
    monkeypatch.setattr(ac, "_reference_product", lambda scene: reference)

    injected: list[list[str]] = []

    def fake_get_baseline_from_stack(reference, stack):
        names = [p.properties["sceneName"] for p in stack]
        injected.append(names)
        # Emulate the real function: it would re-base on stack[0] if the
        # reference were absent. Here the reference is always present.
        return list(stack), []

    import asf_search.baseline.stack as baseline_stack_module

    monkeypatch.setattr(baseline_stack_module, "get_baseline_from_stack", fake_get_baseline_from_stack)

    # Two windows; the reference scene is absent from the returned products of both.
    def fake_search(fullBurstID=None, start=None, end=None, polarization=None, **kwargs):
        return FakeSearchResults([FakeBaselineProduct(f"scene_{start[:10]}", start, temporal=0, perp=0)])

    monkeypatch.setattr(ac.asf, "search", fake_search)

    ac.burst_baseline_stack(
        FULL_BURST_ID,
        reference_scene,
        "2021-10-01T00:00:00Z",
        "2022-04-01T00:00:00Z",
        required_dates=None,
        window_days=90,
        tries=1,
    )

    assert injected, "baseline computation must have run"
    for names in injected:
        assert reference_scene in names, (
            "the fixed reference must be injected into every window, otherwise "
            "check_reference silently substitutes stack[0] and offsets the baselines"
        )


def test_reference_substitution_is_detected_and_rejected(monkeypatch):
    """A product whose temporalBaseline betrays re-basing must be dropped."""
    reference_scene = "S1_056011_IW2_20211006T125536_VV_4BD1-BURST"
    reference = FakeBaselineProduct(reference_scene, "2021-10-06T12:55:36.000000Z")
    monkeypatch.setattr(ac, "_reference_product", lambda scene: reference)

    # Emulate the substituted-reference corruption: 2025-06-11 gets temporal 0
    # even though the fixed reference is 2021-10-06 (true offset -1438 days).
    def fake_get_baseline_from_stack(reference, stack):
        return [
            FakeBaselineProduct(
                "S1_056011_IW2_20250611T125535_VV_69BA-BURST",
                "2025-06-11T12:55:35.000000Z",
                temporal=0,      # <- wrong: should be -1438
                perp=0,
            )
        ], [{"NEW_REFERENCE": "A new reference scene had to be selected"}]

    import asf_search.baseline.stack as baseline_stack_module

    monkeypatch.setattr(baseline_stack_module, "get_baseline_from_stack", fake_get_baseline_from_stack)
    monkeypatch.setattr(
        ac.asf,
        "search",
        lambda *a, **k: FakeSearchResults([FakeBaselineProduct("x", "2025-06-11T12:55:35.000000Z")]),
    )



    with pytest.raises(ac.InventoryError) as excinfo:
        ac.burst_baseline_stack(
            FULL_BURST_ID,
            reference_scene,
            "2025-06-01T00:00:00Z",
            "2025-07-01T00:00:00Z",
            required_dates=[date(2025, 6, 11)],
            window_days=90,
            tries=1,
        )

    assert "missing required dates" in str(excinfo.value)
    assert "2025-06-11" in str(excinfo.value)


def test_missing_state_vector_scenes_are_rejected(monkeypatch):
    reference_scene = "S1_056011_IW2_20211006T125536_VV_4BD1-BURST"
    reference = FakeBaselineProduct(reference_scene, "2021-10-06T12:55:36.000000Z")
    monkeypatch.setattr(ac, "_reference_product", lambda scene: reference)

    def fake_get_baseline_from_stack(reference, stack):
        return [
            FakeBaselineProduct(
                "S1_056011_IW2_20250611T125535_VV_69BA-BURST",
                "2025-06-11T12:55:35.000000Z",
                temporal=None,
                perp=None,
                no_state_vectors=True,
            )
        ], []

    import asf_search.baseline.stack as baseline_stack_module

    monkeypatch.setattr(baseline_stack_module, "get_baseline_from_stack", fake_get_baseline_from_stack)
    monkeypatch.setattr(
        ac.asf,
        "search",
        lambda *a, **k: FakeSearchResults([FakeBaselineProduct("x", "2025-06-11T12:55:35.000000Z")]),
    )

    table = ac.burst_baseline_stack(
        FULL_BURST_ID,
        reference_scene,
        "2025-06-01T00:00:00Z",
        "2025-07-01T00:00:00Z",
        required_dates=None,
        window_days=90,
        tries=1,
    )

    assert table.perp_m == {}, "a scene without state vectors has no perpendicular baseline"
    assert table.rejected and table.rejected[0]["reason"] == "noStateVectors"


def test_temporal_baseline_validation_accepts_a_correctly_referenced_window(monkeypatch):
    """The guard must not reject a correctly referenced product."""
    reference_scene = "S1_056011_IW2_20211006T125536_VV_4BD1-BURST"
    reference = FakeBaselineProduct(reference_scene, "2021-10-06T12:55:36.000000Z")
    monkeypatch.setattr(ac, "_reference_product", lambda scene: reference)

    def fake_get_baseline_from_stack(reference, stack):
        return [
            FakeBaselineProduct(
                "S1_056011_IW2_20250611T125535_VV_69BA-BURST",
                "2025-06-11T12:55:35.000000Z",
                temporal=(date(2025, 6, 11) - date(2021, 10, 6)).days,
                perp=-42,
            )
        ], []

    import asf_search.baseline.stack as baseline_stack_module

    monkeypatch.setattr(baseline_stack_module, "get_baseline_from_stack", fake_get_baseline_from_stack)
    monkeypatch.setattr(
        ac.asf,
        "search",
        lambda *a, **k: FakeSearchResults([FakeBaselineProduct("x", "2025-06-11T12:55:35.000000Z")]),
    )

    table = ac.burst_baseline_stack(
        FULL_BURST_ID,
        reference_scene,
        "2025-06-01T00:00:00Z",
        "2025-07-01T00:00:00Z",
        required_dates=[date(2025, 6, 11)],
        window_days=90,
        tries=1,
    )

    assert not table.rejected
    assert table.perp_m == {"2025-06-11": -42.0}
    assert table.temporal_days == {"2025-06-11": (date(2025, 6, 11) - date(2021, 10, 6)).days}


# ---------------------------------------------------------------------------
# Cross-cutting: group-id parsing used to recover the absolute orbit
# ---------------------------------------------------------------------------


def test_group_id_parsing_supplies_absolute_orbit_and_platform():
    parsed = ac.parse_group_id("S1A_IWDV_0086_0092_059249_027")
    assert parsed["platform"] == "SENTINEL-1A"
    assert parsed["absolute_orbit"] == 59249
    assert parsed["relative_orbit"] == 27
    assert parsed["frame_start"] == 86 and parsed["frame_end"] == 92

    # Must degrade gracefully rather than raise on unexpected input.
    assert ac.parse_group_id(None) == {}
    assert ac.parse_group_id("garbage") == {"raw": "garbage"}
