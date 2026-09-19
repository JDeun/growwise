from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search, stable_cache_key
from .http import JsonHttpClient

_TAG_RE = re.compile(r"<[^>]+>")


class WikipediaAdapter:
    SOURCE = "wikipedia_ko"
    ATTRIBUTION = "Wikipedia contributors"
    LICENSE_NOTE = (
        "Wikipedia text requires attribution/share-alike compliance; "
        "media rights vary by file"
    )

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://ko.wikipedia.org/w/rest.php/v1/search/page",
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
            cache_key=stable_cache_key("wikipedia:search", descriptor),
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
        pages = payload.get("pages")
        if not isinstance(pages, list):
            return []
        records: list[dict[str, Any]] = []
        for page in pages:
            if not isinstance(page, dict):
                continue
            title = str(page.get("title") or "").strip()
            key = str(page.get("key") or title.replace(" ", "_")).strip()
            if not title:
                continue
            excerpt = _TAG_RE.sub("", str(page.get("excerpt") or "")).strip()
            description = str(page.get("description") or "").strip()
            thumbnail = page.get("thumbnail")
            thumbnail_url = str(thumbnail.get("url") or "") if isinstance(thumbnail, dict) else ""
            records.append(
                {
                    "id": str(page.get("id") or key),
                    "title": title,
                    "description": description,
                    "excerpt": excerpt[:6_000],
                    "thumbnail_url": thumbnail_url,
                    "source_url": f"https://ko.wikipedia.org/wiki/{quote(key, safe='_()/')}",
                }
            )
        return records
