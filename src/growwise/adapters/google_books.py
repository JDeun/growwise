from __future__ import annotations

from typing import Any

from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search, stable_cache_key
from .http import JsonHttpClient


class GoogleBooksAdapter:
    SOURCE = "google_books"
    ATTRIBUTION = "Google Books"
    LICENSE_NOTE = "Google Books API metadata terms apply; cover/preview reuse rights vary by volume"

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        api_key: str | None = None,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://www.googleapis.com/books/v1/volumes",
        ttl_seconds: int = 86_400,
    ) -> None:
        self.cache = cache
        self.api_key = (api_key or "").strip() or None
        self.http = http or JsonHttpClient()
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def search_books(
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
        if not 1 <= limit <= 40:
            raise ValueError("limit must be 1-40")
        descriptor = {"query": normalized, "limit": limit, "language": language}
        params: dict[str, str | int] = {
            "q": normalized,
            "maxResults": limit,
            "printType": "books",
            "langRestrict": language,
        }
        if self.api_key:
            params["key"] = self.api_key
        return cached_search(
            cache=self.cache,
            cache_key=stable_cache_key("googlebooks:search", descriptor),
            source=self.SOURCE,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            ttl_seconds=self.ttl_seconds,
            offline=offline,
            fetch=lambda: self.http.get_json(self.endpoint, params=params),
            normalize=self._normalize,
        )

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> list[dict[str, Any]]:
        items = payload.get("items")
        if not isinstance(items, list):
            return []
        records: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            info = item.get("volumeInfo")
            if not isinstance(info, dict):
                continue
            title = str(info.get("title") or "").strip()
            volume_id = str(item.get("id") or "").strip()
            if not title or not volume_id:
                continue
            authors = info.get("authors")
            categories = info.get("categories")
            identifiers = info.get("industryIdentifiers")
            isbn = ""
            if isinstance(identifiers, list):
                for identifier in identifiers:
                    if isinstance(identifier, dict) and identifier.get("type") == "ISBN_13":
                        isbn = str(identifier.get("identifier") or "")
                        break
            records.append(
                {
                    "id": volume_id,
                    "title": title,
                    "authors": ", ".join(str(v) for v in authors[:5]) if isinstance(authors, list) else "",
                    "publisher": str(info.get("publisher") or ""),
                    "published_date": str(info.get("publishedDate") or ""),
                    "description": str(info.get("description") or "")[:8_000],
                    "categories": [str(v) for v in categories[:10]] if isinstance(categories, list) else [],
                    "isbn13": isbn,
                    "source_url": str(info.get("infoLink") or f"https://books.google.com/books?id={volume_id}"),
                }
            )
        return records
