from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
from .base import AdapterResult
from .cache import SQLiteExternalCache
from .cached_search import cached_search, stable_cache_key
from .http import JsonHttpClient

_KST = timezone(timedelta(hours=9), name="KST")


def kma_grid_for(latitude: float, longitude: float) -> tuple[int, int]:
    """Convert WGS84 coordinates to the KMA 5 km DFS grid."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("invalid latitude/longitude")

    re = 6371.00877 / 5.0
    slat1 = math.radians(30.0)
    slat2 = math.radians(60.0)
    olon = 126.0
    olat = math.radians(38.0)
    xo = 43.0
    yo = 136.0

    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5)
        / math.tan(math.pi * 0.25 + slat1 * 0.5)
    )
    sf = (
        math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn
        * math.cos(slat1)
        / sn
    )
    ro = re * sf / (math.tan(math.pi * 0.25 + olat * 0.5) ** sn)

    ra = re * sf / (
        math.tan(math.pi * 0.25 + math.radians(latitude) * 0.5) ** sn
    )
    theta = longitude - olon
    if theta > 180:
        theta -= 360
    if theta < -180:
        theta += 360
    theta = math.radians(theta) * sn

    x = int(ra * math.sin(theta) + xo + 0.5)
    y = int(ro - ra * math.cos(theta) + yo + 0.5)
    return x, y


def kma_observation_base(now: datetime | None = None) -> tuple[str, str]:
    current = now.astimezone(_KST) if now is not None else datetime.now(_KST)
    # Ultra-short observations can lag the clock; use the previous completed hour.
    base = current - timedelta(hours=1)
    return base.strftime("%Y%m%d"), base.strftime("%H00")


class KmaWeatherAdapter:
    SOURCE = "kma_weather"
    ATTRIBUTION = "기상청 단기예보 조회서비스"
    LICENSE_NOTE = "공공누리 제1유형(출처표시); 공공데이터포털 이용조건 준수"

    def __init__(
        self,
        *,
        service_key: str,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = (
            "https://apis.data.go.kr/1360000/"
            "VilageFcstInfoService_2.0/getUltraSrtNcst"
        ),
        ttl_seconds: int = 1_800,
    ) -> None:
        if not service_key.strip():
            raise ValueError("service_key is required")
        self.service_key = service_key
        self.cache = cache
        self.http = http or JsonHttpClient()
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def current_conditions(
        self,
        *,
        latitude: float,
        longitude: float,
        now: datetime | None = None,
        offline: bool = False,
    ) -> AdapterResult:
        nx, ny = kma_grid_for(latitude, longitude)
        base_date, base_time = kma_observation_base(now)
        descriptor = {
            "base_date": base_date,
            "base_time": base_time,
            "nx": nx,
            "ny": ny,
        }
        return cached_search(
            cache=self.cache,
            cache_key=stable_cache_key("kma:ultra-ncst", descriptor),
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
                    "numOfRows": 100,
                    "dataType": "JSON",
                    "base_date": base_date,
                    "base_time": base_time,
                    "nx": nx,
                    "ny": ny,
                },
            ),
            normalize=lambda payload: self._normalize(
                payload,
                base_date=base_date,
                base_time=base_time,
                nx=nx,
                ny=ny,
            ),
        )

    @staticmethod
    def _normalize(
        payload: dict[str, Any],
        *,
        base_date: str,
        base_time: str,
        nx: int,
        ny: int,
    ) -> list[dict[str, Any]]:
        response = payload.get("response")
        if not isinstance(response, dict):
            return []
        body = response.get("body")
        if not isinstance(body, dict):
            return []
        items = body.get("items")
        if not isinstance(items, dict):
            return []
        raw = items.get("item")
        if not isinstance(raw, list):
            return []

        values: dict[str, str] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "")
            value = item.get("obsrValue")
            if category and value is not None:
                values[category] = str(value)

        if not values:
            return []
        return [
            {
                "id": f"{base_date}:{base_time}:{nx}:{ny}",
                "base_date": base_date,
                "base_time": base_time,
                "nx": str(nx),
                "ny": str(ny),
                "temperature_c": values.get("T1H", ""),
                "rainfall_mm": values.get("RN1", ""),
                "humidity_pct": values.get("REH", ""),
                "precipitation_type": values.get("PTY", ""),
                "wind_speed_ms": values.get("WSD", ""),
                "wind_direction_deg": values.get("VEC", ""),
            }
        ]
