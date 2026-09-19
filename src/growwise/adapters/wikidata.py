from __future__ import annotations

from typing import Any

from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search, stable_cache_key
from .http import JsonHttpClient


class WikidataAdapter:
    SOURCE = "wikidata"
    ATTRIBUTION = "Wikidata contributors"
    LICENSE_NOTE = "Wikidata structured data is CC0; verify linked external media separately"

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://www.wikidata.org/w/api.php",
        ttl_seconds: int = 604_800,
    ) -> None:
        self.cache = cache
        self.http = http or JsonHttpClient()
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def search(
        self,
        *,
        query: str,
        limit: int = 8,
        language: str = "ko",
        offline: bool = False,
    ) -> AdapterResult:
        normalized = " ".join(query.split())
        if not 1 <= len(normalized) <= 200:
            raise ValueError("query must be 1-200 characters")
        descriptor = {"query": normalized, "limit": limit, "language": language}
        return cached_search(
            cache=self.cache,
            cache_key=stable_cache_key("wikidata:search", descriptor),
            source=self.SOURCE,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            ttl_seconds=self.ttl_seconds,
            offline=offline,
            fetch=lambda: self.http.get_json(
                self.endpoint,
                params={
                    "action": "wbsearchentities",
                    "search": normalized,
                    "language": language,
                    "uselang": language,
                    "format": "json",
                    "limit": limit,
                },
            ),
            normalize=self._normalize,
        )

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> list[dict[str, Any]]:
        search = payload.get("search")
        if not isinstance(search, list):
            return []
        records: list[dict[str, Any]] = []
        for item in search:
            if not isinstance(item, dict):
                continue
            entity_id = str(item.get("id") or "").strip()
            label = str(item.get("label") or "").strip()
            if not entity_id or not label:
                continue
            records.append(
                {
                    "id": entity_id,
                    "title": label,
                    "description": str(item.get("description") or "")[:4_000],
                    "source_url": str(item.get("concepturi") or f"https://www.wikidata.org/wiki/{entity_id}"),
                }
            )
        return records
