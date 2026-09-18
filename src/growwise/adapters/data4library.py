from __future__ import annotations

import hashlib
import json
from typing import Any

from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .cache import CachedPayload, SQLiteExternalCache
from .http import JsonHttpClient, validate_public_endpoint


class Data4LibraryAdapter:
    SOURCE = "data4library"
    ATTRIBUTION = "도서관 정보나루 (data4library.kr)"
    LICENSE_NOTE = "도서관 정보나루 Open API 이용조건 및 원 데이터 권리표시를 확인할 것"

    def __init__(
        self,
        *,
        auth_key: str,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://data4library.kr/api/srchBooks",
        ttl_seconds: int = 86_400,
    ) -> None:
        if not auth_key.strip():
            raise ValueError("auth_key is required")
        self.auth_key = auth_key
        self.cache = cache
        self.http = http or JsonHttpClient()
        self.endpoint = validate_public_endpoint(endpoint)
        self.ttl_seconds = ttl_seconds

    def search_books(
        self,
        *,
        keyword: str,
        page: int = 1,
        page_size: int = 10,
        offline: bool = False,
    ) -> AdapterResult:
        normalized_keyword = " ".join(keyword.split())
        if len(normalized_keyword) < 1 or len(normalized_keyword) > 200:
            raise ValueError("keyword must be 1-200 characters")
        if page < 1:
            raise ValueError("page must be positive")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")

        descriptor = {
            "keyword": normalized_keyword,
            "page": page,
            "page_size": page_size,
        }
        cache_key = self._cache_key(descriptor)
        fresh = self.cache.get(cache_key)
        if fresh is not None:
            return self._from_cached(fresh, status="fresh")
        stale = self.cache.get(cache_key, allow_stale=True)
        if offline:
            if stale is None:
                raise ExternalUnavailable("Data4Library is unavailable offline and no cache exists")
            return self._from_cached(stale, status="stale" if stale.stale else "fresh")

        try:
            payload = self.http.get_json(
                self.endpoint,
                params={
                    "authKey": self.auth_key,
                    "keyword": normalized_keyword,
                    "pageNo": page,
                    "pageSize": page_size,
                    "format": "json",
                },
            )
            records = self._normalize_response(payload)
            normalized_payload = {"records": records}
            cached = self.cache.put(
                cache_key=cache_key,
                payload=normalized_payload,
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

    @staticmethod
    def _cache_key(descriptor: dict[str, Any]) -> str:
        # Deliberately excludes authKey so credentials never enter the local cache database.
        encoded = json.dumps(descriptor, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return f"data4library:search:{hashlib.sha256(encoded).hexdigest()}"

    @classmethod
    def _normalize_response(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = payload.get("response")
        if not isinstance(response, dict):
            return []
        docs = response.get("docs")
        if not isinstance(docs, list):
            return []
        records: list[dict[str, Any]] = []
        for wrapper in docs:
            if not isinstance(wrapper, dict):
                continue
            doc = wrapper.get("doc", wrapper)
            if not isinstance(doc, dict):
                continue
            isbn = cls._text(doc.get("isbn13") or doc.get("isbn"))
            records.append(
                {
                    "title": cls._text(doc.get("bookname") or doc.get("title")),
                    "authors": cls._text(doc.get("authors") or doc.get("author")),
                    "publisher": cls._text(doc.get("publisher")),
                    "publication_year": cls._text(doc.get("publication_year")),
                    "isbn13": isbn,
                    "class_name": cls._text(doc.get("class_nm")),
                    "book_image_url": cls._text(doc.get("bookImageURL")) or None,
                    "book_detail_url": cls._text(doc.get("bookDtlUrl")) or None,
                }
            )
        return records

    @staticmethod
    def _text(value: object) -> str:
        return str(value).strip() if value is not None else ""

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
