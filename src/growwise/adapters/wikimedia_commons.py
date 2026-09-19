from __future__ import annotations

from typing import Any

from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search, stable_cache_key
from .http import JsonHttpClient
from .license_filter import is_commercial_safe, normalize_license


def _meta_value(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if isinstance(value, dict):
        return str(value.get("value") or "").strip()
    return ""


class WikimediaCommonsAdapter:
    SOURCE = "wikimedia_commons"
    ATTRIBUTION = "Wikimedia Commons contributors"
    LICENSE_NOTE = "Only commercial-safe files with explicit reusable licenses are surfaced"

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://commons.wikimedia.org/w/api.php",
        ttl_seconds: int = 604_800,
    ) -> None:
        self.cache = cache
        self.http = http or JsonHttpClient()
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def search_images(
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
            cache_key=stable_cache_key("commons:search", descriptor),
            source=self.SOURCE,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            ttl_seconds=self.ttl_seconds,
            offline=offline,
            fetch=lambda: self.http.get_json(
                self.endpoint,
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": normalized,
                    "gsrnamespace": 6,
                    "gsrlimit": limit,
                    "prop": "imageinfo",
                    "iiprop": "url|extmetadata",
                    "format": "json",
                    "formatversion": 2,
                },
            ),
            normalize=self._normalize,
        )

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> list[dict[str, Any]]:
        query = payload.get("query")
        if not isinstance(query, dict):
            return []
        pages = query.get("pages")
        if not isinstance(pages, list):
            return []
        records: list[dict[str, Any]] = []
        for page in pages:
            if not isinstance(page, dict):
                continue
            infos = page.get("imageinfo")
            if not isinstance(infos, list) or not infos or not isinstance(infos[0], dict):
                continue
            info = infos[0]
            metadata = info.get("extmetadata")
            if not isinstance(metadata, dict):
                continue
            raw_license = _meta_value(metadata, "LicenseShortName") or _meta_value(metadata, "UsageTerms")
            if not is_commercial_safe(raw_license):
                continue
            title = str(page.get("title") or "").removeprefix("File:").strip()
            url = str(info.get("url") or "").strip()
            description_url = str(info.get("descriptionurl") or "").strip()
            if not title or not url:
                continue
            records.append(
                {
                    "id": str(page.get("pageid") or title),
                    "title": title,
                    "description": _meta_value(metadata, "ImageDescription")[:6_000],
                    "artist": _meta_value(metadata, "Artist")[:500],
                    "credit": _meta_value(metadata, "Credit")[:1_000],
                    "license": normalize_license(raw_license),
                    "license_url": _meta_value(metadata, "LicenseUrl"),
                    "image_url": url,
                    "source_url": description_url or url,
                }
            )
        return records
