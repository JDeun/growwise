from __future__ import annotations

from typing import Any

from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search, stable_cache_key
from .http import JsonHttpClient


class GbifSpeciesAdapter:
    SOURCE = "gbif_species"
    ATTRIBUTION = "GBIF.org"
    LICENSE_NOTE = (
        "GBIF taxonomy metadata is reusable; occurrence and media licenses vary by dataset and "
        "must be checked before media reuse"
    )

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://api.gbif.org/v1/species/search",
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
        offline: bool = False,
    ) -> AdapterResult:
        normalized = " ".join(query.split())
        if not 1 <= len(normalized) <= 200:
            raise ValueError("query must be 1-200 characters")
        descriptor = {"query": normalized, "limit": limit}
        return cached_search(
            cache=self.cache,
            cache_key=stable_cache_key("gbif:species", descriptor),
            source=self.SOURCE,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            ttl_seconds=self.ttl_seconds,
            offline=offline,
            fetch=lambda: self.http.get_json(
                self.endpoint,
                params={"q": normalized, "limit": limit},
            ),
            normalize=self._normalize,
        )

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> list[dict[str, Any]]:
        results = payload.get("results")
        if not isinstance(results, list):
            return []
        records: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            key = item.get("key") or item.get("nubKey")
            title = str(
                item.get("vernacularName")
                or item.get("canonicalName")
                or item.get("scientificName")
                or ""
            ).strip()
            if key is None or not title:
                continue
            records.append(
                {
                    "id": str(key),
                    "title": title,
                    "scientific_name": str(item.get("scientificName") or ""),
                    "canonical_name": str(item.get("canonicalName") or ""),
                    "rank": str(item.get("rank") or ""),
                    "status": str(item.get("taxonomicStatus") or item.get("status") or ""),
                    "kingdom": str(item.get("kingdom") or ""),
                    "phylum": str(item.get("phylum") or ""),
                    "class": str(item.get("class") or ""),
                    "order": str(item.get("order") or ""),
                    "family": str(item.get("family") or ""),
                    "source_url": f"https://www.gbif.org/species/{key}",
                }
            )
        return records
