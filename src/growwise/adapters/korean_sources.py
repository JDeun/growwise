from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .cache import CachedPayload, SQLiteExternalCache
from .http import JsonHttpClient
from .search_base import CachedSearchAdapter


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _xml_text(element: ET.Element, name: str) -> str:
    child = element.find(name)
    return (child.text or "").strip() if child is not None else ""


class _CachedXmlSearchAdapter:
    SOURCE: str
    ATTRIBUTION: str
    LICENSE_NOTE: str

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        endpoint: str,
        http: JsonHttpClient | None = None,
        ttl_seconds: int = 86_400,
    ) -> None:
        self.cache = cache
        self.endpoint = endpoint
        self.http = http or JsonHttpClient()
        self.ttl_seconds = ttl_seconds

    def search(self, *, query: str, limit: int = 8, offline: bool = False) -> AdapterResult:
        normalized = " ".join(query.split())
        if not 1 <= len(normalized) <= 200:
            raise ValueError("query must be 1-200 characters")
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        descriptor = {"query": normalized, "limit": limit, "endpoint": self.endpoint}
        cache_key = self._cache_key(descriptor)
        fresh = self.cache.get(cache_key)
        if fresh is not None:
            return self._from_cached(fresh, "fresh")
        stale = self.cache.get(cache_key, allow_stale=True)
        if offline:
            if stale is None:
                raise ExternalUnavailable(
                    f"{self.SOURCE} is unavailable offline and no cache exists"
                )
            return self._from_cached(stale, "stale" if stale.stale else "fresh")
        try:
            raw = self.http.get_text(self.endpoint, params=self._params(normalized, limit))
            records = self._parse(raw, limit=limit)
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
        except (ExternalAdapterError, ET.ParseError):
            if stale is None:
                raise
            return self._from_cached(stale, "stale")

    def _params(self, query: str, limit: int) -> dict[str, str | int | float]:
        raise NotImplementedError

    def _parse(self, raw: str, *, limit: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    @classmethod
    def _cache_key(cls, descriptor: dict[str, Any]) -> str:
        encoded = json.dumps(descriptor, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return f"{cls.SOURCE}:search:{hashlib.sha256(encoded).hexdigest()}"

    @staticmethod
    def _from_cached(cached: CachedPayload, status: str) -> AdapterResult:
        records = cached.payload.get("records", [])
        return AdapterResult(
            source=cached.source,
            records=[item for item in records if isinstance(item, dict)]
            if isinstance(records, list)
            else [],
            attribution=cached.attribution,
            license_note=cached.license_note,
            fetched_at=cached.fetched_at,
            cache_status="stale" if status == "stale" else "fresh",
        )


class KoreanHeritageAdapter(_CachedXmlSearchAdapter):
    SOURCE = "korean_heritage"
    ATTRIBUTION = "국가유산청 국가유산정보 Open API"
    LICENSE_NOTE = "국가유산청 공식 공개정보; 출처를 표시하고 개별 이미지 권리를 별도 확인할 것"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://www.khs.go.kr/cha/SearchKindOpenapiList.do")
        super().__init__(**kwargs)

    def _params(self, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "ccbaMnm1": query,
            "pageUnit": min(limit, 50),
            "pageIndex": 1,
            "ccbaCncl": "N",
        }

    def _parse(self, raw: str, *, limit: int) -> list[dict[str, Any]]:
        root = ET.fromstring(raw)
        records: list[dict[str, Any]] = []
        for item in root.iter("item"):
            name = _xml_text(item, "ccbaMnm1") or _xml_text(item, "ccbamnm1")
            if not name:
                continue
            kind = _xml_text(item, "ccbaKdcd") or _xml_text(item, "ccbakdcd")
            number = _xml_text(item, "ccbaAsno") or _xml_text(item, "ccbaasno")
            province = _xml_text(item, "ccbaCtcd") or _xml_text(item, "ccbactcd")
            type_name = _xml_text(item, "ccmaName") or _xml_text(item, "ccmaname")
            province_name = _xml_text(item, "ccbaCtcdNm") or _xml_text(item, "ccbactcdnm")
            district = _xml_text(item, "ccsiName") or _xml_text(item, "ccsiname")
            records.append(
                {
                    "source_key": ":".join(v for v in (kind, number, province) if v) or name,
                    "title": name,
                    "summary": " · ".join(v for v in (type_name, province_name, district) if v) or None,
                    "url": "https://www.heritage.go.kr/heri/cul/culSelectDetail.do",
                    "author": None,
                    "resource_kind": "web",
                    "tags": ["탐방", "역사", "국가유산"],
                    "metadata": {
                        key: value
                        for key, value in {
                            "kind_code": kind,
                            "serial": number,
                            "province_code": province,
                            "province": province_name,
                            "district": district,
                            "latitude": _xml_text(item, "latitude"),
                            "longitude": _xml_text(item, "longitude"),
                        }.items()
                        if value
                    },
                }
            )
            if len(records) >= limit:
                break
        return records


class KrdictAdapter(_CachedXmlSearchAdapter):
    SOURCE = "krdict"
    ATTRIBUTION = "국립국어원 한국어기초사전"
    LICENSE_NOTE = "CC BY-SA 2.0 KR; 사전의 개별 미디어는 별도 권리 확인"

    def __init__(self, *, api_key: str, **kwargs: Any) -> None:
        if not api_key.strip():
            raise ValueError("api_key is required")
        self.api_key = api_key
        kwargs.setdefault("endpoint", "https://krdict.korean.go.kr/api/search")
        super().__init__(**kwargs)

    def _params(self, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "key": self.api_key,
            "q": query,
            "start": 1,
            "num": max(10, min(limit, 100)),
            "sort": "dict",
            "part": "word",
            "translated": "n",
        }

    def _parse(self, raw: str, *, limit: int) -> list[dict[str, Any]]:
        root = ET.fromstring(raw)
        records: list[dict[str, Any]] = []
        for item in root.iter("item"):
            word = _xml_text(item, "word")
            if not word:
                continue
            sense = item.find("sense")
            definition = _xml_text(sense, "definition") if sense is not None else ""
            target_code = _xml_text(item, "target_code")
            records.append(
                {
                    "source_key": target_code or word,
                    "title": word,
                    "summary": definition or None,
                    "url": _xml_text(item, "link") or None,
                    "author": None,
                    "resource_kind": "web",
                    "tags": ["언어", "어휘", "한국어"],
                    "metadata": {
                        key: value
                        for key, value in {
                            "target_code": target_code,
                            "pronunciation": _xml_text(item, "pronunciation"),
                            "grade": _xml_text(item, "word_grade"),
                            "pos": _xml_text(item, "pos"),
                        }.items()
                        if value
                    },
                }
            )
            if len(records) >= limit:
                break
        return records


class OpenDictAdapter(_CachedXmlSearchAdapter):
    SOURCE = "opendict"
    ATTRIBUTION = "국립국어원 우리말샘"
    LICENSE_NOTE = "CC BY-SA 2.0 KR; attribution/share-alike required"

    def __init__(
        self,
        *,
        api_key: str,
        cert_key_no: str | None = None,
        **kwargs: Any,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.cert_key_no = (cert_key_no or "").strip()
        kwargs.setdefault("endpoint", "https://opendict.korean.go.kr/api/search")
        super().__init__(**kwargs)

    def _params(self, query: str, limit: int) -> dict[str, str | int | float]:
        params: dict[str, str | int | float] = {
            "key": self.api_key,
            "target_type": "search",
            "part": "word",
            "q": query,
            "sort": "dict",
            "start": 1,
            "num": max(10, min(limit, 100)),
        }
        if self.cert_key_no:
            params["certkey_no"] = self.cert_key_no
        return params

    def _parse(self, raw: str, *, limit: int) -> list[dict[str, Any]]:
        root = ET.fromstring(raw)
        records: list[dict[str, Any]] = []
        for item in root.iter("item"):
            word = _xml_text(item, "word")
            if not word:
                continue
            senses = [
                (_xml_text(sense, "definition") or _xml_text(sense, "definition_original"))
                for sense in item.findall("sense")
            ]
            definitions = [value for value in senses if value]
            target_code = _xml_text(item, "target_code")
            records.append(
                {
                    "source_key": target_code or word,
                    "title": word,
                    "summary": " / ".join(definitions[:3]) or None,
                    "url": _xml_text(item, "link") or None,
                    "author": None,
                    "resource_kind": "web",
                    "tags": ["언어", "어휘", "우리말"],
                    "metadata": {
                        key: value
                        for key, value in {
                            "target_code": target_code,
                            "pos": _xml_text(item, "pos"),
                            "word_type": _xml_text(item, "word_type"),
                        }.items()
                        if value
                    },
                }
            )
            if len(records) >= limit:
                break
        return records


class ConfiguredPublicDataAdapter(CachedSearchAdapter):
    """Configurable JSON adapter for public-data APIs whose deployment endpoint is account-bound.

    This is used for eMuseum/KBR connectors. It fails closed until an explicit HTTPS endpoint and
    service key are configured, avoiding scraping or guessing provider URLs.
    """

    def __init__(
        self,
        *,
        source: str,
        attribution: str,
        license_note: str,
        service_key: str,
        query_param: str,
        **kwargs: Any,
    ) -> None:
        if not service_key.strip():
            raise ValueError("service_key is required")
        self.SOURCE = source
        self.ATTRIBUTION = attribution
        self.LICENSE_NOTE = license_note
        self.service_key = service_key
        self.query_param = query_param
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "serviceKey": self.service_key,
            "pageNo": 1,
            "numOfRows": min(limit, 50),
            "_type": "json",
            self.query_param: query,
        }

    @classmethod
    def _walk_records(cls, value: object) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if not isinstance(value, dict):
            return []
        for key in ("items", "item", "results", "result", "data", "list"):
            child = value.get(key)
            found = cls._walk_records(child)
            if found:
                return found
        for child in value.values():
            found = cls._walk_records(child)
            if found:
                return found
        return []

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in self._walk_records(payload)[:limit]:
            title = _text(
                item.get("title")
                or item.get("name")
                or item.get("itemNm")
                or item.get("relicNm")
                or item.get("korNm")
                or item.get("speciesNm")
            )
            if not title:
                continue
            identifier = _text(
                item.get("id")
                or item.get("itemId")
                or item.get("relicNo")
                or item.get("speciesId")
            )
            summary = _text(
                item.get("description")
                or item.get("summary")
                or item.get("itemDc")
                or item.get("era")
                or item.get("scientificNm")
            )
            url = _text(item.get("url") or item.get("homepage") or item.get("detailUrl"))
            records.append(
                {
                    "source_key": identifier or title,
                    "title": title,
                    "summary": summary[:4_000] or None,
                    "url": url or None,
                    "author": None,
                    "resource_kind": "web",
                    "tags": [self.SOURCE],
                    "metadata": {
                        str(key): _text(value)[:500]
                        for key, value in item.items()
                        if value is not None and isinstance(value, (str, int, float, bool))
                    },
                }
            )
        return records


class KbrAdapter(CachedSearchAdapter):
    SOURCE = "kbr"
    ATTRIBUTION = "국가생물다양성 정보공유체계(KBR)"
    LICENSE_NOTE = (
        "KBR 분류군 텍스트 메타데이터 중심으로 사용하며 개별 이미지/미디어 재사용 권리는 "
        "별도 확인할 것"
    )

    def __init__(self, *, api_key: str, endpoint: str, **kwargs: Any) -> None:
        if not api_key.strip():
            raise ValueError("api_key is required")
        if not endpoint.strip():
            raise ValueError("endpoint is required")
        self.api_key = api_key
        super().__init__(endpoint=endpoint, **kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "access_key": self.api_key,
            "taxon_knm": query,
            "page_index": 1,
            "page_size": min(limit, 50),
        }

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        raw = payload.get("bioList")
        if not isinstance(raw, list):
            return []
        records: list[dict[str, Any]] = []
        for item in raw[:limit]:
            if not isinstance(item, dict):
                continue
            korean_name = _text(item.get("taxon_knm"))
            scientific_name = _text(item.get("taxon_nm"))
            title = korean_name or scientific_name
            ktsn = _text(item.get("ktsn"))
            if not title or not ktsn:
                continue
            records.append(
                {
                    "source_key": ktsn,
                    "title": title,
                    "summary": " · ".join(
                        value
                        for value in (
                            scientific_name,
                            _text(item.get("comm_group_nm")),
                            _text(item.get("cls_step_nm")),
                        )
                        if value
                    )
                    or None,
                    "url": f"https://www.kbr.go.kr/home/rsc/rsc01002v.do?ktsn={ktsn}",
                    "author": None,
                    "resource_kind": "web",
                    "tags": ["과학", "생물", "한국 자생생물"],
                    "metadata": {
                        key: value
                        for key, value in {
                            "ktsn": ktsn,
                            "parent_ktsn": _text(item.get("ktsn_p")),
                            "scientific_name": scientific_name,
                            "group": _text(item.get("comm_group_nm")),
                            "taxonomic_step": _text(item.get("cls_step_nm")),
                        }.items()
                        if value
                    },
                }
            )
        return records


class KmaForecastAdapter(CachedSearchAdapter):
    SOURCE = "kma_forecast"
    ATTRIBUTION = "기상청 단기예보 조회서비스"
    LICENSE_NOTE = "공공저작물 출처표시 제1유형(KOGL Type 1)"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        if not service_key.strip():
            raise ValueError("service_key is required")
        self.service_key = service_key
        self._location_request: tuple[int, int, str, str, float, float] | None = None
        kwargs.setdefault(
            "endpoint",
            "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
        )
        super().__init__(**kwargs)

    @staticmethod
    def _grid(latitude: float, longitude: float) -> tuple[int, int]:
        re_km = 6371.00877
        grid_km = 5.0
        slat1 = 30.0
        slat2 = 60.0
        olon = 126.0
        olat = 38.0
        xo = 43.0
        yo = 136.0
        degrad = math.pi / 180.0
        re_grid = re_km / grid_km
        slat1r = slat1 * degrad
        slat2r = slat2 * degrad
        olonr = olon * degrad
        olatr = olat * degrad
        sn = math.log(math.cos(slat1r) / math.cos(slat2r)) / math.log(
            math.tan(math.pi * 0.25 + slat2r * 0.5)
            / math.tan(math.pi * 0.25 + slat1r * 0.5)
        )
        sf = (
            math.tan(math.pi * 0.25 + slat1r * 0.5) ** sn
            * math.cos(slat1r)
            / sn
        )
        ro = (
            re_grid
            * sf
            / math.tan(math.pi * 0.25 + olatr * 0.5) ** sn
        )
        ra = (
            re_grid
            * sf
            / math.tan(math.pi * 0.25 + latitude * degrad * 0.5) ** sn
        )
        theta = longitude * degrad - olonr
        if theta > math.pi:
            theta -= 2.0 * math.pi
        if theta < -math.pi:
            theta += 2.0 * math.pi
        theta *= sn
        x = int(ra * math.sin(theta) + xo + 0.5)
        y = int(ro - ra * math.cos(theta) + yo + 0.5)
        return x, y

    @staticmethod
    def _latest_base(now: datetime) -> tuple[str, str]:
        kst = timezone(timedelta(hours=9))
        current = now.astimezone(kst)
        slots = (2, 5, 8, 11, 14, 17, 20, 23)
        available = [
            current.replace(hour=hour, minute=10, second=0, microsecond=0)
            for hour in slots
            if current >= current.replace(hour=hour, minute=10, second=0, microsecond=0)
        ]
        base = max(available) if available else (
            current - timedelta(days=1)
        ).replace(hour=23, minute=10, second=0, microsecond=0)
        return base.strftime("%Y%m%d"), base.strftime("%H00")

    def search_location(
        self,
        *,
        latitude: float,
        longitude: float,
        offline: bool = False,
        now: datetime | None = None,
    ) -> AdapterResult:
        nx, ny = self._grid(latitude, longitude)
        date, base_time = self._latest_base(now or datetime.now(UTC))
        query = f"{date}:{base_time}:{nx}:{ny}"
        self._location_request = (nx, ny, date, base_time, latitude, longitude)
        return self.search(query=query, limit=1, offline=offline)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        del query, limit
        if self._location_request is None:
            raise ValueError("KMA forecast requires an explicit location")
        nx, ny, date, base_time, _, _ = self._location_request
        return {
            "serviceKey": self.service_key,
            "pageNo": 1,
            "numOfRows": 1000,
            "dataType": "JSON",
            "base_date": date,
            "base_time": base_time,
            "nx": nx,
            "ny": ny,
        }

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        del limit
        response = payload.get("response")
        response_dict = response if isinstance(response, dict) else {}
        body = response_dict.get("body")
        body_dict = body if isinstance(body, dict) else {}
        items = body_dict.get("items")
        items_dict = items if isinstance(items, dict) else {}
        raw_items = items_dict.get("item")
        if not isinstance(raw_items, list):
            return []
        grouped: dict[tuple[str, str], dict[str, str]] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            date = _text(item.get("fcstDate"))
            time = _text(item.get("fcstTime"))
            category = _text(item.get("category"))
            value = _text(item.get("fcstValue"))
            if date and time and category:
                grouped.setdefault((date, time), {})[category] = value
        if not grouped:
            return []
        first_key = sorted(grouped)[0]
        values = grouped[first_key]
        if self._location_request is None:
            raise ValueError("KMA forecast requires an explicit location")
        _, _, _, _, latitude, longitude = self._location_request
        sky_label = {"1": "맑음", "3": "구름많음", "4": "흐림"}.get(values.get("SKY", ""), "")
        precipitation = values.get("POP", "")
        temperature = values.get("TMP", "")
        humidity = values.get("REH", "")
        summary = " · ".join(
            part
            for part in (
                sky_label,
                f"기온 {temperature}℃" if temperature else "",
                f"강수확률 {precipitation}%" if precipitation else "",
                f"습도 {humidity}%" if humidity else "",
            )
            if part
        )
        return [
            {
                "source_key": f"{first_key[0]}:{first_key[1]}:{latitude:.4f}:{longitude:.4f}",
                "title": f"{first_key[0]} {first_key[1]} 탐방 날씨",
                "summary": summary or "기상청 단기예보",
                "url": "https://www.weather.go.kr",
                "author": None,
                "resource_kind": "web",
                "tags": ["과학", "날씨", "탐방"],
                "metadata": {
                    "forecast_date": first_key[0],
                    "forecast_time": first_key[1],
                    "latitude": f"{latitude:.6f}",
                    "longitude": f"{longitude:.6f}",
                },
            }
        ]
