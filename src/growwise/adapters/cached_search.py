from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .cache import CachedPayload, SQLiteExternalCache


def stable_cache_key(prefix: str, descriptor: dict[str, Any]) -> str:
    encoded = json.dumps(descriptor, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()}"


def adapter_result_from_cache(
    cached: CachedPayload,
    *,
    stale: bool,
) -> AdapterResult:
    records = cached.payload.get("records", [])
    if not isinstance(records, list):
        records = []
    return AdapterResult(
        source=cached.source,
        records=[item for item in records if isinstance(item, dict)],
        attribution=cached.attribution,
        license_note=cached.license_note,
        fetched_at=cached.fetched_at,
        cache_status="stale" if stale else "fresh",
    )


def cached_search(
    *,
    cache: SQLiteExternalCache,
    cache_key: str,
    source: str,
    attribution: str,
    license_note: str,
    ttl_seconds: int,
    offline: bool,
    fetch: Callable[[], dict[str, Any]],
    normalize: Callable[[dict[str, Any]], list[dict[str, Any]]],
) -> AdapterResult:
    fresh = cache.get(cache_key)
    if fresh is not None:
        return adapter_result_from_cache(fresh, stale=False)
    stale = cache.get(cache_key, allow_stale=True)
    if offline:
        if stale is None:
            raise ExternalUnavailable(f"{source} is unavailable offline and no cache exists")
        return adapter_result_from_cache(stale, stale=stale.stale)

    try:
        records = normalize(fetch())
        cached = cache.put(
            cache_key=cache_key,
            payload={"records": records},
            source=source,
            attribution=attribution,
            license_note=license_note,
            ttl_seconds=ttl_seconds,
        )
        return AdapterResult(
            source=source,
            records=records,
            attribution=attribution,
            license_note=license_note,
            fetched_at=cached.fetched_at,
            cache_status="live",
        )
    except ExternalAdapterError:
        if stale is None:
            raise
        return adapter_result_from_cache(stale, stale=True)
