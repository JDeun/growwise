from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from growwise.config import Settings
from growwise.domain.links import EntityLinkRelation
from growwise.services.entity_links import EntityLinkError, EntityLinkService
from growwise.storage import EntityStore

router = APIRouter(tags=["entity-links"])


class EntityLinkCreateRequest(BaseModel):
    source_id: UUID
    target_id: UUID
    relation: EntityLinkRelation = EntityLinkRelation.RELATED
    label: str | None = Field(default=None, max_length=240)


@lru_cache
def get_link_settings() -> Settings:
    return Settings()


def get_link_store(
    settings: Annotated[Settings, Depends(get_link_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@router.post("/links")
def create_entity_link(
    request: EntityLinkCreateRequest,
    store: Annotated[EntityStore, Depends(get_link_store)],
) -> dict[str, object]:
    try:
        link = EntityLinkService(store).create(
            source_id=request.source_id,
            target_id=request.target_id,
            relation=request.relation,
            label=request.label,
        )
    except EntityLinkError as exc:
        detail = str(exc)
        status_code = 404 if detail.endswith("_not_found") else 422
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return link.model_dump(mode="json")


@router.get("/links/{entity_id}")
def get_entity_backlinks(
    entity_id: UUID,
    store: Annotated[EntityStore, Depends(get_link_store)],
) -> dict[str, list[dict[str, object]]]:
    if store.index.get_entity(str(entity_id)) is None:
        raise HTTPException(status_code=404, detail="entity_not_found")
    return EntityLinkService(store).backlinks(entity_id)


@router.delete("/links/{link_id}")
def delete_entity_link(
    link_id: UUID,
    store: Annotated[EntityStore, Depends(get_link_store)],
) -> dict[str, bool]:
    return {"deleted": EntityLinkService(store).delete(link_id)}
