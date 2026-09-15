"""Optional public-data enrichment routes that never receive child-private context."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from growwise.adapters import (
    AdapterResult,
    Data4LibraryAdapter,
    ExternalAdapterError,
    ExternalUnavailable,
    OverpassAdapter,
    SQLiteExternalCache,
)
from growwise.config import Settings

router = APIRouter(prefix="/v1/external", tags=["external-enrichment"])


@lru_cache
def get_external_settings() -> Settings:
    return Settings()


def get_external_cache(
    settings: Annotated[Settings, Depends(get_external_settings)],
) -> SQLiteExternalCache:
    return SQLiteExternalCache(settings.external_cache_path)


def _require_enabled(settings: Settings) -> None:
    if not settings.external_enrichment_enabled:
        raise HTTPException(status_code=503, detail="external_enrichment_disabled")


def _adapter_error(error: ExternalAdapterError) -> HTTPException:
    if isinstance(error, ExternalUnavailable):
        return HTTPException(status_code=503, detail="external_enrichment_unavailable")
    return HTTPException(status_code=502, detail="external_upstream_error")


@router.get("/books", response_model=AdapterResult)
def search_public_books(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    settings: Annotated[Settings, Depends(get_external_settings)],
    cache: Annotated[SQLiteExternalCache, Depends(get_external_cache)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    offline: bool = False,
) -> AdapterResult:
    """Search Data4Library using only a public keyword query."""
    _require_enabled(settings)
    auth_key = (settings.data4library_auth_key or "").strip()
    if not auth_key:
        raise HTTPException(status_code=503, detail="data4library_not_configured")
    adapter = Data4LibraryAdapter(
        auth_key=auth_key,
        cache=cache,
        ttl_seconds=settings.external_cache_ttl_seconds,
    )
    try:
        return adapter.search_books(
            keyword=q,
            page=page,
            page_size=page_size,
            offline=offline,
        )
    except ExternalAdapterError as error:
        raise _adapter_error(error) from error


@router.get("/places", response_model=AdapterResult)
def search_public_places(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    settings: Annotated[Settings, Depends(get_external_settings)],
    cache: Annotated[SQLiteExternalCache, Depends(get_external_cache)],
    radius_m: Annotated[int, Query(ge=50, le=20_000)] = 2_000,
    amenities: str = "library,museum,community_centre",
    offline: bool = False,
) -> AdapterResult:
    """Search public nearby places without sending any GrowWise private record."""
    _require_enabled(settings)
    normalized_amenities = tuple(
        value.strip() for value in amenities.split(",") if value.strip()
    )
    adapter = OverpassAdapter(
        cache=cache,
        ttl_seconds=settings.external_cache_ttl_seconds,
    )
    try:
        return adapter.nearby_places(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            amenities=normalized_amenities,
            offline=offline,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ExternalAdapterError as error:
        raise _adapter_error(error) from error
