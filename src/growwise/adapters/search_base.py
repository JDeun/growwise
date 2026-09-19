from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .cache import CachedPayload, SQLiteExternalCache
from .http import JsonHttpClient


class CachedSearchAdapter(ABC):
    """Shared bounded-cache contract for public education search adapters.

    Secrets are deliberately excluded from the cache descriptor. Subclasses may include
    credentials in the outbound request, but only normalized public results are persisted.
    """

    SOURCE: str
    ATTRIBUTION: str
    LICENSE_NOTE: str

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        endpoint: str,
        http: JsonHttpClient | None = None,
        ttl_seconds: int = 86_400,
    ) -> None:
        self.cache = cache
        self.endpoint = endpoint
        self.http = http or JsonHttpClient()
        self.ttl_seconds = ttl_seconds

    def search(
        self,
        *,
        query: str,
        limit: int = 8,
        offline: bool = False,
    ) -> AdapterResult:
        normalized_query = " ".join(query.split())
        if not 1 <= len(normalized_query) <= 200:
            raise ValueError("query must be 1-200 characters")
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")

        descriptor = {
            "query": normalized_query,
            "limit": limit,
            "endpoint": self.endpoint,
        }
        cache_key = self._cache_key(descriptor)
        fresh = self.cache.get(cache_key)
        if fresh is not None:
            return self._from_cached(fresh, status="fresh")

        stale = self.cache.get(cache_key, allow_stale=True)
        if offline:
            if stale is None:
                raise ExternalUnavailable(
                    f"{self.SOURCE} is unavailable offline and no cache exists"
                )
            return self._from_cached(stale, status="stale" if stale.stale else "fresh")

        try:
            payload = self._fetch(normalized_query, limit)
            records = self._normalize(payload, limit=limit)
            cached = self.cache.put(
                cache_key=cache_key,
                payload={"records": records},
                source=self.SOURCE,
                attribution=self.ATTRIBUTION,
                license_note=self.LICENSE_NOTE,
                ttl_seconds=self.ttl_seconds,
            )
            return AdapterResult(
                source=self.SOURCE,
                records=records,
                attribution=self.ATTRIBUTION,
                license_note=self.LICENSE_NOTE,
                fetched_at=cached.fetched_at,
                cache_status="live",
            )
        except ExternalAdapterError:
            if stale is None:
                raise
            return self._from_cached(stale, status="stale")

    def _fetch(self, query: str, limit: int) -> dict[str, Any]:
        return self.http.get_json(
            self.endpoint,
            params=self._params(query=query, limit=limit),
        )

    @abstractmethod
    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        raise NotImplementedError

    @abstractmethod
    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    @classmethod
    def _cache_key(cls, descriptor: dict[str, Any]) -> str:
        encoded = json.dumps(descriptor, ensure_ascii=False, sort_keys=True).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        return f"{cls.SOURCE}:search:{digest}"

    @staticmethod
    def text(value: object) -> str:
        return str(value).strip() if value is not None else ""

    @staticmethod
    def list_of_dicts(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def dict_value(value: object) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _from_cached(cached: CachedPayload, *, status: str) -> AdapterResult:
        records = cached.payload.get("records", [])
        if not isinstance(records, list):
            records = []
        return AdapterResult(
            source=cached.source,
            records=[item for item in records if isinstance(item, dict)],
            attribution=cached.attribution,
            license_note=cached.license_note,
            fetched_at=cached.fetched_at,
            cache_status="stale" if status == "stale" else "fresh",
        )
