from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from growwise.config import Settings
from growwise.domain import ChildProfile, ResourceRecord
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services.discovery import (
    DiscoveryResponse,
    DiscoverySuggestion,
    EducationDiscoveryService,
)
from growwise.storage import EntityStore

router = APIRouter(tags=["education-discovery"])


@lru_cache
def get_discovery_settings() -> Settings:
    return Settings()


def get_discovery_store(
    settings: Annotated[Settings, Depends(get_discovery_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


def _child(store: EntityStore, child_id: UUID) -> ChildProfile:
    payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return ChildProfile.model_validate(payload)


def _service(settings: Settings, store: EntityStore) -> EducationDiscoveryService:
    return EducationDiscoveryService(
        settings=settings,
        store=store,
        ingestor=ResourceIngestor(HybridRagIndex(settings.rag_index_path)),
    )


@router.get(
    "/children/{child_id}/discover",
    response_model=DiscoveryResponse,
)
def discover_education_resources(
    child_id: UUID,
    settings: Annotated[Settings, Depends(get_discovery_settings)],
    store: Annotated[EntityStore, Depends(get_discovery_store)],
    query: Annotated[str | None, Query(max_length=200)] = None,
    latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    limit: Annotated[int, Query(ge=1, le=30)] = 12,
    offline: bool = False,
) -> DiscoveryResponse:
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="latitude_longitude_must_be_provided_together")
    child = _child(store, child_id)
    return _service(settings, store).discover(
        child=child,
        query=query,
        latitude=latitude,
        longitude=longitude,
        limit=limit,
        offline=offline,
    )


@router.post(
    "/children/{child_id}/discover/save",
    response_model=ResourceRecord,
)
def save_discovered_resource(
    child_id: UUID,
    suggestion: DiscoverySuggestion,
    settings: Annotated[Settings, Depends(get_discovery_settings)],
    store: Annotated[EntityStore, Depends(get_discovery_store)],
) -> ResourceRecord:
    child = _child(store, child_id)
    return _service(settings, store).save(child=child, suggestion=suggestion)
