from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .cache import SQLiteExternalCache
from .cached_search import adapter_result_from_cache, stable_cache_key
from .http import JsonHttpClient


class KrDictAdapter:
    SOURCE = "krdict"
    ATTRIBUTION = "국립국어원 한국어기초사전"
    LICENSE_NOTE = (
        "한국어기초사전 저작권/오픈API 이용조건을 따르며 개별 멀티미디어 권리는 별도 확인"
    )

    def __init__(
        self,
        *,
        api_key: str,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://krdict.korean.go.kr/api/search",
        ttl_seconds: int = 604_800,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.cache = cache
        self.http = http or JsonHttpClient()
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def search(
        self,
        *,
        query: str,
        limit: int = 10,
        offline: bool = False,
    ) -> AdapterResult:
        normalized = " ".join(query.split())
        if not 1 <= len(normalized) <= 200:
            raise ValueError("query must be 1-200 characters")
        bounded_limit = max(10, min(limit, 100))
        descriptor = {"query": normalized, "limit": bounded_limit}
        cache_key = stable_cache_key("krdict:search", descriptor)
        fresh = self.cache.get(cache_key)
        if fresh is not None:
            return adapter_result_from_cache(fresh, stale=False)
        stale = self.cache.get(cache_key, allow_stale=True)
        if offline:
            if stale is None:
                raise ExternalUnavailable("KRDict is unavailable offline and no cache exists")
            return adapter_result_from_cache(stale, stale=stale.stale)

        try:
            raw = self.http.get_text(
                self.endpoint,
                params={
                    "key": self.api_key,
                    "q": normalized,
                    "start": 1,
                    "num": bounded_limit,
                    "sort": "dict",
                    "part": "word",
                    "translated": "n",
                },
            )
            records = self._normalize(raw)
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
            return adapter_result_from_cache(stale, stale=True)

    @staticmethod
    def _normalize(raw: str) -> list[dict[str, Any]]:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ExternalAdapterError("KRDict response is not valid XML") from exc
        if root.tag == "error":
            message = (root.findtext("message") or "KRDict API error").strip()
            raise ExternalAdapterError(message)

        records: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            word = (item.findtext("word") or "").strip()
            target_code = (item.findtext("target_code") or "").strip()
            if not word or not target_code:
                continue
            definitions = [
                (sense.findtext("definition") or "").strip()
                for sense in item.findall(".//sense")
            ]
            definitions = [value for value in definitions if value][:4]
            records.append(
                {
                    "id": target_code,
                    "title": word,
                    "pronunciation": (item.findtext("pronunciation") or "").strip(),
                    "word_grade": (item.findtext("word_grade") or "").strip(),
                    "part_of_speech": (item.findtext("pos") or "").strip(),
                    "definitions": definitions,
                    "source_url": (item.findtext("link") or "").strip()
                    or "https://krdict.korean.go.kr/",
                }
            )
        return records
