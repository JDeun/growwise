from __future__ import annotations

import math
from typing import Any

from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search
from .http import JsonHttpClient


class MuseumArtGalleryAdapter:
    SOURCE = "korea_museum_standard"
    ATTRIBUTION = "공공데이터포털 전국박물관미술관정보표준데이터"
    LICENSE_NOTE = "공공데이터포털 제공조건 및 각 제공기관의 원 데이터 조건을 확인할 것"

    def __init__(
        self,
        *,
        service_key: str,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://api.data.go.kr/openapi/tn_pubr_public_museum_artgr_info_api",
        ttl_seconds: int = 604_800,
    ) -> None:
        if not service_key.strip():
            raise ValueError("service_key is required")
        self.service_key = service_key
        self.cache = cache
        self.http = http or JsonHttpClient(timeout_seconds=20.0)
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        limit: int = 10,
        offline: bool = False,
    ) -> AdapterResult:
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("invalid latitude/longitude")
        all_result = cached_search(
            cache=self.cache,
            cache_key="museum-standard:all:v1",
            source=self.SOURCE,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            ttl_seconds=self.ttl_seconds,
            offline=offline,
            fetch=lambda: self.http.get_json(
                self.endpoint,
                params={
                    "serviceKey": self.service_key,
                    "pageNo": 1,
                    "numOfRows": 1000,
                    "type": "json",
                },
            ),
            normalize=self._normalize,
        )
        ranked = sorted(
            all_result.records,
            key=lambda item: self._distance_km(
                latitude,
                longitude,
                self._float(item.get("latitude")),
                self._float(item.get("longitude")),
            ),
        )
        return AdapterResult(
            source=all_result.source,
            records=ranked[: max(1, min(limit, 50))],
            attribution=all_result.attribution,
            license_note=all_result.license_note,
            fetched_at=all_result.fetched_at,
            cache_status=all_result.cache_status,
        )

    @staticmethod
    def _normalize(payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = payload.get("response")
        body = response.get("body") if isinstance(response, dict) else None
        items = body.get("items") if isinstance(body, dict) else None
        raw = items.get("item") if isinstance(items, dict) else items
        if not isinstance(raw, list):
            return []

        records: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("fcltyNm") or "").strip()
            lat = MuseumArtGalleryAdapter._float(item.get("latitude"))
            lon = MuseumArtGalleryAdapter._float(item.get("longitude"))
            if not name or lat is None or lon is None:
                continue
            records.append(
                {
                    "id": "|".join(
                        part
                        for part in (
                            name,
                            str(item.get("rdnmadr") or item.get("lnmadr") or ""),
                        )
                        if part
                    ),
                    "title": name,
                    "facility_type": str(item.get("fcltyType") or ""),
                    "address": str(item.get("rdnmadr") or item.get("lnmadr") or ""),
                    "latitude": lat,
                    "longitude": lon,
                    "homepage_url": str(item.get("homepageUrl") or ""),
                    "introduction": str(item.get("fcltyIntrcn") or "")[:8_000],
                    "closed_days": str(item.get("rstdeInfo") or ""),
                    "child_fee": str(item.get("childChrge") or ""),
                    "institution": str(
                        item.get("operInstitutionNm")
                        or item.get("institutionNm")
                        or ""
                    ),
                }
            )
        return records

    @staticmethod
    def _float(value: object) -> float | None:
        try:
            parsed = float(str(value))
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    @staticmethod
    def _distance_km(
        lat1: float,
        lon1: float,
        lat2: float | None,
        lon2: float | None,
    ) -> float:
        if lat2 is None or lon2 is None:
            return float("inf")
        radius = 6371.0088
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
