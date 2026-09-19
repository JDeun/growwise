from __future__ import annotations

from typing import Any

from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search, stable_cache_key
from .http import JsonHttpClient


class OpenLibraryAdapter:
    SOURCE = "open_library"
    ATTRIBUTION = "Open Library (Internet Archive)"
    LICENSE_NOTE = (
        "Open Library catalog metadata/API terms apply; "
        "verify edition text/cover rights before reuse"
    )

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://openlibrary.org/search.json",
        ttl_seconds: int = 86_400,
    ) -> None:
        self.cache = cache
        self.http = http or JsonHttpClient()
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def search_books(
        self,
        *,
        query: str,
        limit: int = 8,
        offline: bool = False,
    ) -> AdapterResult:
        normalized = " ".join(query.split())
        if not 1 <= len(normalized) <= 200:
            raise ValueError("query must be 1-200 characters")
        if not 1 <= limit <= 50:
            raise ValueError("limit must be 1-50")
        descriptor = {"query": normalized, "limit": limit}
        return cached_search(
            cache=self.cache,
            cache_key=stable_cache_key("openlibrary:search", descriptor),
            source=self.SOURCE,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            ttl_seconds=self.ttl_seconds,
            offline=offline,
            fetch=lambda: self.http.get_json(
                self.endpoint,
                params={
                    "q": normalized,
                    "limit": limit,
                    "fields": (
                        "key,title,author_name,first_publish_year,subject,isbn,cover_i,"
                        "language,edition_count"
                    ),
                },
            ),
            normalize=self._normalize,
        )

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> list[dict[str, Any]]:
        docs = payload.get("docs")
        if not isinstance(docs, list):
            return []
        records: list[dict[str, Any]] = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            title = str(doc.get("title") or "").strip()
            key = str(doc.get("key") or "").strip()
            if not title or not key:
                continue
            authors = doc.get("author_name")
            subjects = doc.get("subject")
            isbns = doc.get("isbn")
            records.append(
                {
                    "id": key,
                    "title": title,
                    "authors": (
                        ", ".join(str(v) for v in authors[:5])
                        if isinstance(authors, list)
                        else ""
                    ),
                    "first_publish_year": str(doc.get("first_publish_year") or ""),
                    "subjects": (
                        [str(v) for v in subjects[:12]]
                        if isinstance(subjects, list)
                        else []
                    ),
                    "isbn": str(isbns[0]) if isinstance(isbns, list) and isbns else "",
                    "edition_count": int(doc.get("edition_count") or 0),
                    "source_url": f"https://openlibrary.org{key}",
                }
            )
        return records
