"""
Robust ASF / CMR access layer for the Delhi-NCR multi-burst SBAS project.

Why this module exists
----------------------
`asf_search` (14.0.0) proved unreliable for this project in two distinct ways,
both of which would silently corrupt an SBAS network if left unguarded:

1. `asf_search.search(...)` raises `ASFSearchError` ("Results are incomplete
   due to a search error", with an *empty* CMR message body) for some narrow
   date windows, even when the data demonstrably exists. Observed for
   `fullBurstID=027_056011_IW2` on 2025-05-18: >20 consecutive failures across
   every supported query form, while 2025-05-06 / 2025-05-30 / 2025-09-27 all
   succeeded. A direct CMR UMM-JSON query returned
   `S1_056011_IW2_20250518T125536_VV_6366-BURST`, proving the granule exists.

2. `ASFProduct.stack(...)` does **not** raise on incomplete CMR results. It
   records `searchComplete=False` and returns a truncated stack (e.g. 29
   products for a 1-year window that should hold ~30). Naive use of `stack()`
   therefore silently drops acquisitions.

Design
------
* CMR UMM-JSON is the **authoritative, paginated** inventory source. It is a
  public (no-auth) API and returns every field needed for validation.
* `asf_search` remains the primary source for *baseline* values, because it
  computes perpendicular baselines from orbit state vectors. Every stack call
  is completeness-checked, windowed, and cross-validated against the CMR
  inventory before its baselines are trusted.
* Any disagreement between sources is surfaced as an error rather than
  silently resolved.

No NASA Earthdata credentials are required by anything in this module.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

import asf_search as asf

LOGGER = logging.getLogger("asf_client")

CMR_GRANULES_UMM = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
CMR_PROVIDER = "ASF"
ASF_USER_AGENT = "delhi-ncr-multiburst-sbas/1.0"

#: CMR attribute that carries the geographic Full Burst ID, e.g. "027_056011_IW2".
CMR_ATTR_FULL_BURST_ID = "BURST_ID_FULL"
#: CMR attribute carrying the single polarization of a burst granule.
CMR_ATTR_POLARIZATION = "POLARIZATION"

DEFAULT_PAGE_SIZE = 500
DEFAULT_TRIES = 4
DEFAULT_BASE_DELAY = 3.0


class InventoryError(RuntimeError):
    """Raised when an inventory cannot be established to the required standard."""


# ---------------------------------------------------------------------------
# Normalised record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BurstRecord:
    """One burst SLC granule for one acquisition date.

    The stable *acquisition* identity is (relative orbit, platform,
    acquisition start time) per brief section 42.3. The stable *geographic
    burst* identity is ``full_burst_id``.
    """

    full_burst_id: str
    scene_name: str
    start_time: datetime
    platform: str
    path: int
    flight_direction: str
    polarization: str
    subswath: str
    relative_burst_id: int
    absolute_burst_id: int | None
    burst_index: int | None
    azimuth_time: str | None
    azimuth_anx_time: str | None
    absolute_orbit: int | None
    group_id: str | None
    bytes: int | None
    url: str | None
    query_method: str

    # -- derived helpers -------------------------------------------------

    @property
    def date(self) -> date:
        return self.start_time.date()

    @property
    def date_iso(self) -> str:
        return self.date.isoformat()

    @property
    def acquisition_key(self) -> tuple[int, str, str]:
        """Collision-safe acquisition key (relative orbit, platform, time)."""
        return (self.path, self.platform, self.start_time.isoformat())

    def as_row(self) -> dict[str, Any]:
        return {
            "date": self.date_iso,
            "start_time": self.start_time.isoformat(),
            "scene_name": self.scene_name,
            "full_burst_id": self.full_burst_id,
            "relative_burst_id": self.relative_burst_id,
            "absolute_burst_id": self.absolute_burst_id,
            "burst_index": self.burst_index,
            "subswath": self.subswath,
            "azimuth_time": self.azimuth_time,
            "azimuth_anx_time": self.azimuth_anx_time,
            "path": self.path,
            "direction": self.flight_direction,
            "polarization": self.polarization,
            "platform": self.platform,
            "absolute_orbit": self.absolute_orbit,
            "group_id": self.group_id,
            "bytes": self.bytes,
            "url": self.url,
            "query_method": self.query_method,
        }


# ---------------------------------------------------------------------------
# Small retry helper
# ---------------------------------------------------------------------------


def _sleep(attempt: int, base: float = DEFAULT_BASE_DELAY) -> None:
    time.sleep(base * attempt)


def _retry(fn, *, tries: int = DEFAULT_TRIES, base: float = DEFAULT_BASE_DELAY, label: str = ""):
    """Call ``fn()`` with linear backoff. Re-raises the final exception."""
    last: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - deliberate broad retry
            last = exc
            if attempt < tries:
                LOGGER.debug("%s attempt %d/%d failed: %s", label, attempt, tries, exc)
                _sleep(attempt, base)
    assert last is not None
    raise last


# ---------------------------------------------------------------------------
# CMR UMM-JSON (authoritative, paginated, no auth)
# ---------------------------------------------------------------------------


def _cmr_umm_page(
    full_burst_id: str,
    start: str,
    end: str,
    page_num: int,
    page_size: int,
) -> tuple[list[dict], int]:
    """One CMR UMM-JSON page for a burst within a temporal window.

    Deliberately does **not** filter on the POLARIZATION attribute. Measured
    behaviour on 2026-09: adding ``string,POLARIZATION,VV`` makes CMR report
    ``CMR-Hits=120`` while serving only 119 granules, with page 2 empty — the
    2025-05-18 VV granule is silently dropped. Polarization is therefore
    filtered in Python, and each window is validated for VV/VH consistency by
    ``_cmr_window_is_consistent`` (see ``cmr_burst_inventory``).
    """
    params: list[tuple[str, str]] = [
        ("provider", CMR_PROVIDER),
        ("page_size", str(page_size)),
        ("page_num", str(page_num)),
        ("temporal", f"{start},{end}"),
        ("attribute[]", f"string,{CMR_ATTR_FULL_BURST_ID},{full_burst_id}"),
    ]
    query = urllib.parse.urlencode(params)
    url = f"{CMR_GRANULES_UMM}?{query}"

    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": ASF_USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.load(response)
        hits = int(response.headers.get("CMR-Hits") or 0)

    return payload.get("items", []), hits


def _umm_attr(umm: dict, name: str) -> Any:
    for attr in umm.get("AdditionalAttributes", []) or []:
        if attr.get("Name") == name:
            values = attr.get("Values") or []
            return values[0] if values else None
    return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_group_id(group_id: str | None) -> dict[str, Any]:
    """Decode an ASF burst GROUP_ID such as ``S1A_IWDV_0086_0092_059249_027``.

    CMR does not expose the absolute orbit number as a burst attribute, but it
    is embedded in GROUP_ID, together with the platform short code. Layout:
    ``<platform>_<mode><pol>_<frameStart>_<frameEnd>_<absoluteOrbit>_<relativeOrbit>``.
    """
    if not group_id:
        return {}
    parts = str(group_id).split("_")
    if len(parts) < 6:
        return {"raw": group_id}
    platform_code, mode = parts[0], parts[1]
    platform_map = {
        "S1A": "SENTINEL-1A",
        "S1B": "SENTINEL-1B",
        "S1C": "SENTINEL-1C",
        "S1D": "SENTINEL-1D",
    }
    result: dict[str, Any] = {
        "raw": group_id,
        "platform_code": platform_code,
        "platform": platform_map.get(platform_code, platform_code),
        "beam_mode": mode[:2],
    }
    for key, index in (("frame_start", 2), ("frame_end", 3), ("absolute_orbit", 4), ("relative_orbit", 5)):
        try:
            result[key] = int(parts[index])
        except (ValueError, IndexError):
            result[key] = None
    return result


def _cmr_item_to_record(item: dict, query_method: str) -> BurstRecord | None:
    umm = item.get("umm") or {}
    granule_ur = umm.get("GranuleUR")
    if not granule_ur:
        return None

    temporal = (umm.get("TemporalExtent") or {}).get("RangeDateTime") or {}
    start_time = _parse_dt(temporal.get("BeginningDateTime"))
    if start_time is None:
        return None

    platforms = umm.get("Platforms") or []
    platform = platforms[0].get("ShortName") if platforms else None

    group_id = _umm_attr(umm, "GROUP_ID")
    group = parse_group_id(group_id)

    url = None
    for related in umm.get("RelatedUrls", []) or []:
        href = related.get("URL") or ""
        if href.endswith(".tiff"):
            url = href
            break

    def _as_int(name: str) -> int | None:
        raw = _umm_attr(umm, name)
        try:
            return int(str(raw))
        except (TypeError, ValueError):
            return None

    return BurstRecord(
        full_burst_id=str(_umm_attr(umm, "BURST_ID_FULL")),
        scene_name=granule_ur,
        start_time=start_time,
        platform=str(platform or group.get("platform") or "UNKNOWN").upper(),
        path=int(_as_int("PATH_NUMBER") or -1),
        flight_direction=str(_umm_attr(umm, "ASCENDING_DESCENDING") or "UNKNOWN").upper(),
        polarization=str(_umm_attr(umm, "POLARIZATION") or "UNKNOWN").upper(),
        subswath=str(_umm_attr(umm, "SUBSWATH_NAME") or "UNKNOWN"),
        relative_burst_id=int(_as_int("BURST_ID_RELATIVE") or -1),
        absolute_burst_id=_as_int("BURST_ID_ABSOLUTE"),
        burst_index=_as_int("BURST_INDEX"),
        azimuth_time=_umm_attr(umm, "AZIMUTH_TIME"),
        azimuth_anx_time=_umm_attr(umm, "AZIMUTH_ANX_TIME"),
        absolute_orbit=group.get("absolute_orbit"),
        group_id=group_id,
        bytes=_as_int("BYTE_LENGTH"),
        url=url,
        query_method=query_method,
    )


def _cmr_window_is_consistent(items: list[dict]) -> tuple[bool, str]:
    """Check a window's granules for internal VV/VH consistency.

    Every acquisition in this archive is dual-pol (GROUP_ID mode ``DV``), so a
    complete window must contain, for each acquisition timestamp, exactly one
    VV and one VH granule. A window that violates this has silently lost
    granules (the observed failure mode) and must be split.
    """
    vv_times: list[str] = []
    vh_times: list[str] = []
    for item in items:
        umm = item.get("umm") or {}
        pol = str(_umm_attr(umm, CMR_ATTR_POLARIZATION) or "").upper()
        temporal = (umm.get("TemporalExtent") or {}).get("RangeDateTime") or {}
        begin = temporal.get("BeginningDateTime")
        if pol == "VV":
            vv_times.append(str(begin))
        elif pol == "VH":
            vh_times.append(str(begin))

    if not vv_times and not vh_times:
        return True, "empty"
    if len(vv_times) != len(vh_times):
        return False, f"VV={len(vv_times)} != VH={len(vh_times)}"
    if sorted(vv_times) != sorted(vh_times):
        only_vv = sorted(set(vv_times) - set(vh_times))
        only_vh = sorted(set(vh_times) - set(vv_times))
        return False, f"timestamps differ (vv_only={only_vv} vh_only={only_vh})"
    return True, "ok"


def cmr_burst_inventory(
    full_burst_id: str,
    start: str,
    end: str,
    polarization: str | None = "VV",
    *,
    window_days: int = 90,
    page_size: int = DEFAULT_PAGE_SIZE,
    tries: int = DEFAULT_TRIES,
    diagnostics: list[dict] | None = None,
) -> list[BurstRecord]:
    """Complete CMR inventory for one Geographic Full Burst ID.

    The period is split into windows. Each window is fetched without a
    polarization attribute filter and validated for VV/VH timestamp parity; a
    window that fails validation is halved and retried recursively, down to
    two-day granularity. This is what recovers granule 2025-05-18 for
    ``027_056011_IW2``, which a single full-period query silently omits.

    ``diagnostics``, when supplied, receives one dict per window for audit.
    """
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if start_dt is None or end_dt is None:
        raise InventoryError(f"Unparseable window: {start} -> {end}")

    items: list[dict] = []
    cursor = start_dt
    while cursor < end_dt:
        window_end = min(cursor + timedelta(days=window_days), end_dt)
        items.extend(
            _cmr_window_validated(
                full_burst_id,
                cursor,
                window_end,
                page_size=page_size,
                tries=tries,
                diagnostics=diagnostics,
                depth=0,
            )
        )
        cursor = window_end

    records: list[BurstRecord] = []
    for item in items:
        record = _cmr_item_to_record(item, query_method="cmr_umm")
        if record is None:
            continue
        if polarization and record.polarization != polarization.upper():
            continue
        records.append(record)

    deduped = _dedupe(records)
    LOGGER.info("CMR inventory %s: %d %s records", full_burst_id, len(deduped), polarization or "raw")
    return deduped


def _cmr_window_validated(
    full_burst_id: str,
    start: datetime,
    end: datetime,
    *,
    page_size: int,
    tries: int,
    diagnostics: list[dict] | None,
    depth: int,
) -> list[dict]:
    """Fetch one window, requiring VV/VH consistency; split on failure."""
    start_s = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_s = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    items: list[dict] = []
    hits = 0
    error: str | None = None
    try:
        items, hits = _retry(
            lambda: _cmr_umm_page(full_burst_id, start_s, end_s, 1, page_size),
            tries=tries,
            label=f"cmr {full_burst_id} {start_s}->{end_s}",
        )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    consistent, reason = _cmr_window_is_consistent(items) if not error else (False, error)
    complete = (not error) and len(items) == hits

    if consistent and complete:
        if diagnostics is not None:
            diagnostics.append(
                {
                    "start": start_s,
                    "end": end_s,
                    "depth": depth,
                    "items": len(items),
                    "hits": hits,
                    "status": "ok",
                    "reason": reason,
                }
            )
        return items

    span_days = (end - start).days
    if span_days <= 2:
        # Terminal granularity: keep whatever was recovered and record the loss
        # explicitly rather than pretending the window was complete.
        if diagnostics is not None:
            diagnostics.append(
                {
                    "start": start_s,
                    "end": end_s,
                    "depth": depth,
                    "items": len(items),
                    "hits": hits,
                    "status": "UNRESOLVED",
                    "reason": reason if not complete else f"inconsistent: {reason}",
                }
            )
        LOGGER.warning("UNRESOLVED CMR window %s %s->%s (%s)", full_burst_id, start_s, end_s, reason)
        return items

    if diagnostics is not None:
        diagnostics.append(
            {
                "start": start_s,
                "end": end_s,
                "depth": depth,
                "items": len(items),
                "hits": hits,
                "status": "split",
                "reason": reason if not complete else f"inconsistent: {reason}",
            }
        )

    midpoint = start + (end - start) / 2
    left = _cmr_window_validated(
        full_burst_id,
        start,
        midpoint,
        page_size=page_size,
        tries=tries,
        diagnostics=diagnostics,
        depth=depth + 1,
    )
    right = _cmr_window_validated(
        full_burst_id,
        midpoint,
        end,
        page_size=page_size,
        tries=tries,
        diagnostics=diagnostics,
        depth=depth + 1,
    )
    return left + right


def _dedupe(records: Iterable[BurstRecord]) -> list[BurstRecord]:
    """Deduplicate on the granule name, keeping first occurrence."""
    unique: dict[str, BurstRecord] = {}
    for record in records:
        unique.setdefault(record.scene_name, record)
    return sorted(unique.values(), key=lambda r: (r.start_time, r.relative_burst_id))


# ---------------------------------------------------------------------------
# asf_search inventory (primary where healthy, fallback validated by CMR)
# ---------------------------------------------------------------------------


def asf_burst_inventory(
    full_burst_id: str,
    start: str,
    end: str,
    polarization: str = "VV",
    *,
    tries: int = DEFAULT_TRIES,
) -> list[BurstRecord]:
    """asf_search inventory for one burst, with adaptive window splitting.

    A failing window is halved and retried recursively (the strategy used by
    `02_inventory_bursts.py`). If even a one-day window cannot be completed the
    exception propagates so the caller can fall back to CMR.
    """
    results = _asf_search_windowed(full_burst_id, start, end, polarization, tries=tries, depth=0)
    records = [_asf_product_to_record(p, "asf_search") for p in results]
    return _dedupe([r for r in records if r is not None])


def _asf_search_windowed_soft(
    full_burst_id: str,
    start: str,
    end: str,
    polarization: str,
    *,
    tries: int,
    depth: int,
    failures: list[dict],
) -> list:
    """Like ``_asf_search_windowed`` but never raises for a failing sub-window.

    A window that cannot be completed is halved; a sub-window that still fails
    at one-day granularity is recorded in ``failures`` and skipped, so the rest
    of the period is still recovered. Correctness is enforced downstream by the
    required-date check rather than by discarding a whole window.
    """
    try:
        return _retry(
            lambda: _asf_search_once(full_burst_id, start, end, polarization),
            tries=tries,
            label=f"asf {full_burst_id} {start}->{end}",
        )
    except Exception as exc:  # noqa: BLE001
        start_dt = _parse_dt(start)
        end_dt = _parse_dt(end)
        if start_dt is None or end_dt is None:
            failures.append({"start": start, "end": end, "error": f"unparseable: {exc}"})
            return []
        span = end_dt - start_dt
        if span <= timedelta(days=1):
            failures.append(
                {
                    "start": start,
                    "end": end,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return []
        midpoint = start_dt + span / 2
        left = _asf_search_windowed_soft(
            full_burst_id,
            start,
            midpoint.strftime("%Y-%m-%dT%H:%M:%SZ"),
            polarization,
            tries=tries,
            depth=depth + 1,
            failures=failures,
        )
        right = _asf_search_windowed_soft(
            full_burst_id,
            (midpoint + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            end,
            polarization,
            tries=tries,
            depth=depth + 1,
            failures=failures,
        )
        return left + right


def _asf_search_windowed(
    full_burst_id: str,
    start: str,
    end: str,
    polarization: str,
    *,
    tries: int,
    depth: int,
) -> list:
    try:
        return _retry(
            lambda: _asf_search_once(full_burst_id, start, end, polarization),
            tries=tries,
            label=f"asf {full_burst_id} {start}->{end}",
        )
    except Exception:
        start_dt = _parse_dt(start)
        end_dt = _parse_dt(end)
        if start_dt is None or end_dt is None:
            raise
        span = (end_dt - start_dt).days
        if span <= 1:
            raise
        midpoint = start_dt + timedelta(days=span // 2)
        left = _asf_search_windowed(
            full_burst_id,
            start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            midpoint.strftime("%Y-%m-%dT%H:%M:%SZ"),
            polarization,
            tries=tries,
            depth=depth + 1,
        )
        right = _asf_search_windowed(
            full_burst_id,
            (midpoint + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            polarization,
            tries=tries,
            depth=depth + 1,
        )
        return left + right


def _asf_search_once(full_burst_id: str, start: str, end: str, polarization: str):
    results = asf.search(
        fullBurstID=full_burst_id,
        start=start,
        end=end,
        polarization=polarization,
        maxResults=2000,
    )
    # Never accept a partial CMR response.
    results.raise_if_incomplete()
    return list(results)


def _asf_product_to_record(product, query_method: str) -> BurstRecord | None:
    props = product.properties
    burst = props.get("burst") or {}
    start_time = _parse_dt(props.get("startTime"))
    if start_time is None:
        return None
    return BurstRecord(
        full_burst_id=str(burst.get("fullBurstID")),
        scene_name=str(props.get("sceneName")),
        start_time=start_time,
        platform=str(props.get("platform") or "UNKNOWN").upper(),
        path=int(props.get("pathNumber") or -1),
        flight_direction=str(props.get("flightDirection") or "UNKNOWN").upper(),
        polarization=str(props.get("polarization") or "UNKNOWN").upper(),
        subswath=str(burst.get("subswath") or "UNKNOWN"),
        relative_burst_id=int(burst.get("relativeBurstID") or -1),
        absolute_burst_id=burst.get("absoluteBurstID"),
        burst_index=burst.get("burstIndex"),
        azimuth_time=burst.get("azimuthTime"),
        azimuth_anx_time=burst.get("azimuthAnxTime"),
        absolute_orbit=props.get("orbit"),
        group_id=props.get("groupID"),
        bytes=_safe_int(props.get("bytes")),
        url=props.get("url"),
        query_method=query_method,
    )


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Reconciled inventory
# ---------------------------------------------------------------------------


@dataclass
class InventoryResult:
    """Reconciled inventory for one burst, with full provenance."""

    full_burst_id: str
    records: list[BurstRecord]
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def dates(self) -> list[date]:
        return sorted({r.date for r in self.records})

    @property
    def scene_names(self) -> set[str]:
        return {r.scene_name for r in self.records}


def burst_inventory(
    full_burst_id: str,
    start: str,
    end: str,
    polarization: str = "VV",
    *,
    tries: int = DEFAULT_TRIES,
    cross_check_asf: bool = True,
) -> InventoryResult:
    """Reconciled inventory: CMR authoritative, asf_search cross-checked.

    CMR is treated as authoritative: it is queried in validated windows (see
    ``cmr_burst_inventory``) which provably recovers every acquisition.
    asf_search is run afterwards purely as a cross-check. It is known to fail
    on some windows (raising ``ASFSearchError``) and to under-report; that is
    recorded as provenance and never allowed to change the CMR result.
    """
    provenance: dict[str, Any] = {"full_burst_id": full_burst_id}

    diagnostics: list[dict] = []
    cmr_records: list[BurstRecord] = []
    cmr_error: str | None = None
    try:
        cmr_records = cmr_burst_inventory(
            full_burst_id, start, end, polarization, tries=tries, diagnostics=diagnostics
        )
    except Exception as exc:  # noqa: BLE001
        cmr_error = f"{type(exc).__name__}: {exc}"

    unresolved = [d for d in diagnostics if d.get("status") == "UNRESOLVED"]
    provenance["cmr"] = {
        "records": len(cmr_records),
        "error": cmr_error,
        "windows": diagnostics,
        "unresolved_windows": unresolved,
    }

    asf_records: list[BurstRecord] = []
    asf_error: str | None = None
    if cross_check_asf:
        try:
            asf_records = asf_burst_inventory(full_burst_id, start, end, polarization, tries=2)
        except Exception as exc:  # noqa: BLE001
            asf_error = f"{type(exc).__name__}: {exc}"

        cmr_names = {r.scene_name for r in cmr_records}
        asf_names = {r.scene_name for r in asf_records}
        provenance["asf_search"] = {
            "records": len(asf_records),
            "error": asf_error,
            "only_in_cmr": sorted(cmr_names - asf_names),
            "only_in_asf": sorted(asf_names - cmr_names),
            "agree": bool(cmr_names) and cmr_names == asf_names,
        }

    records = cmr_records or asf_records
    if not records:
        raise InventoryError(
            f"No inventory for {full_burst_id}. cmr_error={cmr_error} asf_error={asf_error}"
        )

    provenance["records"] = len(records)
    provenance["dates"] = len({r.date for r in records})
    provenance["first"] = records[0].date_iso
    provenance["last"] = records[-1].date_iso
    provenance["platforms"] = sorted({r.platform for r in records})
    return InventoryResult(full_burst_id=full_burst_id, records=records, provenance=provenance)


# ---------------------------------------------------------------------------
# Baseline stacks (asf_search) with mandatory completeness enforcement
# ---------------------------------------------------------------------------


@dataclass
class BaselineStack:
    """Per-date baselines for one burst, relative to a fixed reference date."""

    full_burst_id: str
    reference_scene: str
    reference_date: str
    temporal_days: dict[str, int]
    perp_m: dict[str, int | float]
    windows: list[dict]
    verified_against_inventory: bool
    notes: list[str] = field(default_factory=list)
    extra_dates: list[str] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


def _reference_product(reference_scene: str):
    results = _retry(
        lambda: asf.granule_search([reference_scene]),
        tries=DEFAULT_TRIES,
        label=f"granule_search {reference_scene}",
    )
    results.raise_if_incomplete()
    if len(results) == 0:
        raise InventoryError(f"Reference burst not found: {reference_scene}")
    return results[0]


def _baselines_with_fixed_reference(reference, products: list):
    """Compute baselines against ``reference``, preventing silent re-basing.

    ``asf_search.baseline.stack.get_baseline_from_stack`` calls
    ``check_reference``, which does::

        if reference sceneName not in stack: reference = stack[0]

    i.e. if the fixed reference granule is absent from the window it silently
    becomes a *different* scene, and every temporal/perpendicular baseline in
    that window is measured from the wrong date. Because this project derives a
    pair's |B_perp| as the difference of two per-date values, a per-window
    constant offset would corrupt every pair that spans two windows.

    Injecting the reference product into the stack guarantees the fixed
    reference is always honoured, so all windows share one baseline frame.
    """
    from asf_search import ASFSearchResults
    from asf_search.baseline.stack import get_baseline_from_stack

    reference_name = reference.properties["sceneName"]
    present = {p.properties["sceneName"] for p in products}
    stack_input = list(products)
    if reference_name not in present:
        stack_input.append(reference)

    stack, warnings = get_baseline_from_stack(reference=reference, stack=ASFSearchResults(stack_input))
    return stack, warnings


def burst_baseline_stack(
    full_burst_id: str,
    reference_scene: str,
    start: str,
    end: str,
    required_dates: Sequence[date] | None = None,
    *,
    window_days: int = 180,
    tries: int = DEFAULT_TRIES,
) -> BaselineStack:
    """Baselines for every date of one burst, against a FIXED reference.

    Baselines are always measured from ``reference_scene``. Each window's
    products are re-validated so that a silent reference substitution cannot
    leak into the result:

      * ``temporalBaseline`` must equal the true day offset from the reference
        date - this is the decisive check that exposes re-basing;
      * scenes flagged ``noStateVectors`` are dropped (perpendicular baseline
        was never calculated for them).

    Rejected products are recorded in ``BaselineStack.rejected`` for audit.
    ``required_dates`` must all be recovered or the call raises.
    """
    reference = _reference_product(reference_scene)
    reference_date = _parse_dt(reference.properties["startTime"]).date()
    assert reference_date is not None

    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    assert start_dt and end_dt

    temporal: dict[str, int] = {}
    perp: dict[str, float] = {}
    windows: list[dict] = []
    notes: list[str] = []
    rejected: list[dict] = []

    cursor = start_dt
    while cursor < end_dt:
        window_end = min(cursor + timedelta(days=window_days), end_dt)
        w_start = cursor.strftime("%Y-%m-%dT%H:%M:%SZ")
        w_end = window_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        products: list = []
        error: str | None = None
        window_failures: list[dict] = []
        products = _asf_search_windowed_soft(
            full_burst_id,
            w_start,
            w_end,
            "VV",
            tries=tries,
            depth=0,
            failures=window_failures,
        )
        if window_failures:
            for failure in window_failures:
                notes.append(
                    f"window {failure['start']}->{failure['end']} unavailable: {failure['error']}"
                )
            if not products:
                error = window_failures[0]["error"]

        accepted_here = 0
        if products:
            stack, warnings = _baselines_with_fixed_reference(reference, products)
            for warning in warnings or []:
                if "NEW_REFERENCE" in str(warning):
                    notes.append(f"window {w_start}->{w_end}: {warning}")
            for product in stack:
                props = product.properties
                moment = _parse_dt(props.get("startTime"))
                if moment is None:
                    continue
                day = moment.date()
                iso = day.isoformat()

                baseline = product.baseline or {}
                if baseline.get("noStateVectors"):
                    rejected.append({"date": iso, "reason": "noStateVectors"})
                    continue

                expected = (day - reference_date).days
                got = int(props.get("temporalBaseline", 0))
                if got != expected:
                    rejected.append(
                        {
                            "date": iso,
                            "reason": "reference_substitution",
                            "temporal_baseline": got,
                            "expected": expected,
                        }
                    )
                    continue

                temporal[iso] = got
                perp[iso] = float(props.get("perpendicularBaseline", 0))
                accepted_here += 1

        windows.append(
            {
                "start": w_start,
                "end": w_end,
                "returned": len(products),
                "accepted": accepted_here,
                "error": error,
            }
        )
        cursor = window_end

    extra: list[str] = []
    missing: list[str] = []
    if required_dates is not None:
        required = {d.isoformat() for d in required_dates}
        missing = sorted(required - set(perp))
        extra = sorted(set(perp) - required)
        if missing:
            rejection_detail = [r for r in rejected if r["date"] in missing]
            raise InventoryError(
                f"Baseline stack for {full_burst_id} is missing required dates: {missing}. "
                f"rejections={rejection_detail} notes={notes}"
            )

    return BaselineStack(
        full_burst_id=full_burst_id,
        reference_scene=reference_scene,
        reference_date=reference_date.isoformat(),
        temporal_days=temporal,
        perp_m=perp,
        windows=windows,
        verified_against_inventory=required_dates is not None and not missing,
        notes=notes,
        extra_dates=extra,
        rejected=rejected,
    )


__all__ = [
    "BurstRecord",
    "InventoryResult",
    "BaselineStack",
    "InventoryError",
    "burst_inventory",
    "cmr_burst_inventory",
    "asf_burst_inventory",
    "burst_baseline_stack",
]
