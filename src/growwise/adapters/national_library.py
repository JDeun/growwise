from __future__ import annotations

from typing import Any

from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search, stable_cache_key
from .http import JsonHttpClient


class NationalLibraryIsbnAdapter:
    SOURCE = "national_library_isbn"
    ATTRIBUTION = "국립중앙도서관 ISBN 서지정보"
    LICENSE_NOTE = "국립중앙도서관 Open API 이용조건; 공공데이터포털 이용허락범위 제한 없음"

    def __init__(
        self,
        *,
        api_key: str,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://www.nl.go.kr/seoji/SearchApi.do",
        ttl_seconds: int = 604_800,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.cache = cache
        self.http = http or JsonHttpClient()
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def search_books(
        self,
        *,
        query: str,
        limit: int = 10,
        offline: bool = False,
    ) -> AdapterResult:
        normalized = " ".join(query.split())
        if not 1 <= len(normalized) <= 200:
            raise ValueError("query must be 1-200 characters")
        bounded = max(1, min(limit, 100))
        descriptor = {"query": normalized, "limit": bounded}
        return cached_search(
            cache=self.cache,
            cache_key=stable_cache_key("nl:isbn", descriptor),
            source=self.SOURCE,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            ttl_seconds=self.ttl_seconds,
            offline=offline,
            fetch=lambda: self.http.get_json(
                self.endpoint,
                params={
                    "cert_key": self.api_key,
                    "result_style": "json",
                    "page_no": 1,
                    "page_size": bounded,
                    "title": normalized,
                },
            ),
            normalize=self._normalize,
        )

    @classmethod
    def _normalize(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = cls._record_lists(payload)
        records: list[dict[str, Any]] = []
        for item in candidates:
            title = cls._field(item, "TITLE", "title")
            isbn = cls._field(item, "EA_ISBN", "ISBN", "isbn")
            if not title:
                continue
            records.append(
                {
                    "id": isbn or cls._field(item, "REC_KEY", "id") or title,
                    "title": title,
                    "author": cls._field(item, "AUTHOR", "author"),
                    "publisher": cls._field(item, "PUBLISHER", "publisher"),
                    "isbn13": isbn,
                    "publish_date": cls._field(
                        item,
                        "PUBLISH_PREDATE",
                        "PUBLISH_DATE",
                        "publish_date",
                    ),
                    "keywords": cls._field(item, "KEYWORD", "keywords"),
                    "language": cls._field(item, "TITLE_URL", "LANG", "language"),
                    "source_url": "https://www.nl.go.kr/",
                }
            )
        return records

    @classmethod
    def _record_lists(cls, value: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if any(str(key).upper() == "TITLE" for key in item):
                        found.append(item)
                    else:
                        found.extend(cls._record_lists(item))
            return found
        if isinstance(value, dict):
            if any(str(key).upper() == "TITLE" for key in value):
                found.append(value)
            else:
                for child in value.values():
                    found.extend(cls._record_lists(child))
        return found

    @staticmethod
    def _field(item: dict[str, Any], *names: str) -> str:
        for name in names:
            for key, value in item.items():
                if str(key).casefold() == name.casefold() and value is not None:
                    return str(value).strip()
        return ""
