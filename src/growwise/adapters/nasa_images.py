from __future__ import annotations

from typing import Any

from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search, stable_cache_key
from .http import JsonHttpClient


class NasaImagesAdapter:
    SOURCE = "nasa_images"
    ATTRIBUTION = "NASA Image and Video Library"
    LICENSE_NOTE = (
        "NASA media is generally reusable as U.S. government material, but logos, insignia and "
        "third-party credited assets require separate review"
    )

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://images-api.nasa.gov/search",
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
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1-100")
        descriptor = {"query": normalized, "limit": limit}
        return cached_search(
            cache=self.cache,
            cache_key=stable_cache_key("nasa:images", descriptor),
            source=self.SOURCE,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            ttl_seconds=self.ttl_seconds,
            offline=offline,
            fetch=lambda: self.http.get_json(
                self.endpoint,
                params={"q": normalized, "media_type": "image", "page_size": limit},
            ),
            normalize=lambda payload: self._normalize(payload, limit=limit),
        )

    @staticmethod
    def _normalize(payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        collection = payload.get("collection")
        if not isinstance(collection, dict):
            return []
        items = collection.get("items")
        if not isinstance(items, list):
            return []
        records: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            data = item.get("data")
            links = item.get("links")
            if not isinstance(data, list) or not data or not isinstance(data[0], dict):
                continue
            entry = data[0]
            nasa_id = str(entry.get("nasa_id") or "").strip()
            title = str(entry.get("title") or "").strip()
            if not nasa_id or not title:
                continue
            image_url = ""
            if isinstance(links, list):
                for link in links:
                    if isinstance(link, dict) and str(link.get("render") or "") == "image":
                        image_url = str(link.get("href") or "")
                        break
            keywords = entry.get("keywords")
            records.append(
                {
                    "id": nasa_id,
                    "title": title,
                    "description": str(entry.get("description") or entry.get("description_508") or "")[:10_000],
                    "date_created": str(entry.get("date_created") or ""),
                    "center": str(entry.get("center") or ""),
                    "keywords": [str(v) for v in keywords[:20]] if isinstance(keywords, list) else [],
                    "image_url": image_url,
                    "source_url": f"https://images.nasa.gov/details/{nasa_id}",
                }
            )
            if len(records) >= limit:
                break
        return records
