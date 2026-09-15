from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC
from typing import Any

from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .cache import CachedPayload, SQLiteExternalCache
from .http import JsonHttpClient

_ALLOWED_AMENITIES = frozenset(
    {
        "arts_centre",
        "community_centre",
        "library",
        "museum",
        "school",
        "theatre",
    }
)


class OverpassAdapter:
    SOURCE = "openstreetmap_overpass"
    ATTRIBUTION = "© OpenStreetMap contributors"
    LICENSE_NOTE = "OpenStreetMap data: ODbL 1.0; attribution required"

    def __init__(
        self,
        *,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        endpoint: str = "https://overpass-api.de/api/interpreter",
        ttl_seconds: int = 86_400,
    ) -> None:
        self.cache = cache
        self.http = http or JsonHttpClient(timeout_seconds=25.0)
        self.endpoint = endpoint
        self.ttl_seconds = ttl_seconds

    def nearby_places(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int = 2_000,
        amenities: tuple[str, ...] = ("library", "museum", "community_centre"),
        offline: bool = False,
    ) -> AdapterResult:
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("invalid latitude/longitude")
        if not 50 <= radius_m <= 20_000:
            raise ValueError("radius_m must be between 50 and 20000")
        normalized = tuple(sorted(set(amenities)))
        if not normalized or not set(normalized) <= _ALLOWED_AMENITIES:
            raise ValueError("unsupported amenity filter")

        query_descriptor = {
            "lat": round(latitude, 5),
            "lon": round(longitude, 5),
            "radius_m": radius_m,
            "amenities": normalized,
        }
        cache_key = self._cache_key(query_descriptor)
        fresh = self.cache.get(cache_key)
        if fresh is not None:
            return self._from_cached(fresh, status="fresh")
        stale = self.cache.get(cache_key, allow_stale=True)
        if offline:
            if stale is None:
                raise ExternalUnavailable(
                    "Overpass data is unavailable offline and no cache exists"
                )
            return self._from_cached(stale, status="stale" if stale.stale else "fresh")

        query = self._build_query(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            amenities=normalized,
        )
        try:
            payload = self.http.post_form_json(self.endpoint, form={"data": query})
            normalized_payload = {"records": self._normalize_elements(payload.get("elements"))}
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
                records=normalized_payload["records"],
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
        encoded = json.dumps(descriptor, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return f"overpass:nearby:{hashlib.sha256(encoded).hexdigest()}"

    @staticmethod
    def _build_query(
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        amenities: tuple[str, ...],
    ) -> str:
        pattern = "|".join(re.escape(value) for value in amenities)
        around = f"around:{radius_m},{latitude:.6f},{longitude:.6f}"
        return (
            "[out:json][timeout:20];("
            f'node({around})["amenity"~"^({pattern})$"];'
            f'way({around})["amenity"~"^({pattern})$"];'
            f'relation({around})["amenity"~"^({pattern})$"];'
            ");out center tags;"
        )

    @staticmethod
    def _normalize_elements(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        records: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            raw_tags = item.get("tags")
            tags: dict[str, Any] = raw_tags if isinstance(raw_tags, dict) else {}
            raw_center = item.get("center")
            center: dict[str, Any] = raw_center if isinstance(raw_center, dict) else {}
            lat = item.get("lat", center.get("lat"))
            lon = item.get("lon", center.get("lon"))
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            records.append(
                {
                    "osm_type": str(item.get("type", "")),
                    "osm_id": item.get("id"),
                    "name": tags.get("name") or tags.get("name:ko") or "",
                    "amenity": tags.get("amenity") or "",
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "website": tags.get("website") or tags.get("contact:website"),
                }
            )
        return records

    @staticmethod
    def _from_cached(
        cached: CachedPayload,
        *,
        status: str,
    ) -> AdapterResult:
        records = cached.payload.get("records", [])
        if not isinstance(records, list):
            records = []
        return AdapterResult(
            source=cached.source,
            records=[item for item in records if isinstance(item, dict)],
            attribution=cached.attribution,
            license_note=cached.license_note,
            fetched_at=cached.fetched_at.astimezone(UTC),
            cache_status="stale" if status == "stale" else "fresh",
        )
