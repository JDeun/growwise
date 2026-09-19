from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Literal

from .base import AdapterResult, ExternalAdapterError
from .cache import SQLiteExternalCache
from .cached_search import adapter_result_from_cache, stable_cache_key
from .http import JsonHttpClient


class HeritagePalaceAdapter:
    SOURCE = "korean_heritage_palaces"
    ATTRIBUTION = "국가유산청 국가유산정보"
    LICENSE_NOTE = (
        "국가유산청 공공누리 표시는 개별 자료별로 확인해야 하며 "
        "이미지/민간 저작물은 별도 권리 조건을 따름"
    )

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://www.heritage.go.kr/heri/gungDetail/gogungListOpenApi.do",
        ttl_seconds: int = 2_592_000,
    ) -> None:
        self.cache = cache
        self.http = http or JsonHttpClient()
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def search(
        self,
        *,
        query: str,
        offline: bool = False,
    ) -> AdapterResult:
        normalized = " ".join(query.split()).casefold()
        records: list[dict[str, Any]] = []
        cache_status: Literal["live", "fresh", "stale"] = "fresh"
        fetched_at = None

        for palace_number in range(1, 6):
            result = self._palace(palace_number=palace_number, offline=offline)
            records.extend(result.records)
            fetched_at = fetched_at or result.fetched_at
            if result.cache_status == "live":
                cache_status = "live"
            elif result.cache_status == "stale" and cache_status != "live":
                cache_status = "stale"

        filtered = [
            item
            for item in records
            if not normalized
            or normalized in (
                f"{item.get('title', '')} {item.get('description', '')}"
            ).casefold()
        ]
        assert fetched_at is not None
        return AdapterResult(
            source=self.SOURCE,
            records=filtered or records,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            fetched_at=fetched_at,
            cache_status=cache_status,
        )

    def _palace(self, *, palace_number: int, offline: bool) -> AdapterResult:
        cache_key = stable_cache_key("heritage:palace", {"gung_number": palace_number})
        fresh = self.cache.get(cache_key)
        if fresh is not None:
            return adapter_result_from_cache(fresh, stale=False)
        stale = self.cache.get(cache_key, allow_stale=True)
        if offline:
            if stale is None:
                return AdapterResult(
                    source=self.SOURCE,
                    records=[],
                    attribution=self.ATTRIBUTION,
                    license_note=self.LICENSE_NOTE,
                    cache_status="stale",
                )
            return adapter_result_from_cache(stale, stale=stale.stale)

        try:
            raw = self.http.get_text(
                self.endpoint,
                params={"gung_number": palace_number},
            )
            normalized = {"records": self._normalize(raw, palace_number=palace_number)}
            cached = self.cache.put(
                cache_key=cache_key,
                payload=normalized,
                source=self.SOURCE,
                attribution=self.ATTRIBUTION,
                license_note=self.LICENSE_NOTE,
                ttl_seconds=self.ttl_seconds,
            )
            return AdapterResult(
                source=self.SOURCE,
                records=normalized["records"],
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
    def _normalize(raw: str, *, palace_number: int) -> list[dict[str, Any]]:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ExternalAdapterError("heritage palace response is not valid XML") from exc

        records: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            serial = (item.findtext("serial_number") or "").strip()
            detail = (item.findtext("detail_code") or "").strip()
            title = (item.findtext("contents_kor") or item.findtext("gung_name") or "").strip()
            description = (item.findtext("explanation_kor") or "").strip()
            if not title:
                continue
            records.append(
                {
                    "id": f"{palace_number}:{serial}:{detail}",
                    "title": title,
                    "description": description[:10_000],
                    "palace_number": str(palace_number),
                    "serial_number": serial,
                    "detail_code": detail,
                    "image_url": (item.findtext("imgUrl") or "").strip(),
                    "source_url": "https://www.heritage.go.kr/",
                }
            )
        return records
