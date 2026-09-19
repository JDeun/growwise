from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from growwise.api.dependencies import get_model_provider, get_store
from growwise.domain import LearningWiki
from growwise.services.learning_wiki import LearningWikiService
from growwise.storage import EntityStore

router = APIRouter(tags=["learning-wiki"])


@router.get("/children/{child_id}/learning-wiki", response_model=LearningWiki)
def get_learning_wiki(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> LearningWiki:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    service = LearningWikiService(store, provider=get_model_provider())
    existing = service.get(str(child_id))
    return existing if existing is not None else service.refresh(str(child_id))


@router.post("/children/{child_id}/learning-wiki/rebuild", response_model=LearningWiki)
def rebuild_learning_wiki(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> LearningWiki:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return LearningWikiService(store, provider=get_model_provider()).refresh(
        str(child_id),
        force=True,
    )
