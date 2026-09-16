from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from growwise.config import Settings
from growwise.domain.links import EntityLink, EntityLinkRelation
from growwise.services.entity_links import EntityLinkError, EntityLinkService
from growwise.storage import EntityStore

router = APIRouter(tags=["entity-links"])


class EntityLinkCreateRequest(BaseModel):
    source_id: UUID
    target_id: UUID
    relation: EntityLinkRelation = EntityLinkRelation.RELATED
    label: str | None = Field(default=None, max_length=240)
    acting_child_id: UUID | None = None


@lru_cache
def get_link_settings() -> Settings:
    return Settings()


def get_link_store(
    settings: Annotated[Settings, Depends(get_link_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


def _require_child_scope_owner(
    *,
    store: EntityStore,
    source_id: UUID,
    acting_child_id: UUID | None,
) -> None:
    source = store.index.get_entity(str(source_id))
    if source is None:
        raise HTTPException(status_code=404, detail="link_source_not_found")
    owner = source.get("child_id")
    if owner is not None and str(acting_child_id) != str(owner):
        raise HTTPException(status_code=403, detail="shared_entity_read_only")


@router.post("/links")
def create_entity_link(
    request: EntityLinkCreateRequest,
    store: Annotated[EntityStore, Depends(get_link_store)],
) -> dict[str, object]:
    if request.relation is EntityLinkRelation.CHILD_SCOPE:
        _require_child_scope_owner(
            store=store,
            source_id=request.source_id,
            acting_child_id=request.acting_child_id,
        )
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
    acting_child_id: UUID | None = None,
) -> dict[str, bool]:
    payload = store.index.get_entity(str(link_id), entity_type="entity_link")
    if payload is None:
        return {"deleted": False}
    link = EntityLink.model_validate(payload)
    if link.relation is EntityLinkRelation.CHILD_SCOPE:
        _require_child_scope_owner(
            store=store,
            source_id=link.source_id,
            acting_child_id=acting_child_id,
        )
    return {"deleted": EntityLinkService(store).delete(link_id)}
