from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore

router = APIRouter(tags=["child-profile"])


class ChildProfileUpdateRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=120)
    stage: Stage
    age_months: int | None = Field(default=None, ge=0, le=240)
    interests: list[str] = Field(default_factory=list, max_length=100)
    primary_language: str = Field(default="ko-KR", min_length=2, max_length=35)
    additional_languages: list[str] = Field(default_factory=list, max_length=20)
    learning_goals: list[str] = Field(default_factory=list, max_length=100)
    notes: str | None = Field(default=None, max_length=10_000)


@lru_cache
def get_child_profile_settings() -> Settings:
    return Settings()


def get_child_profile_store(
    settings: Annotated[Settings, Depends(get_child_profile_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@router.put("/children/{child_id}", response_model=ChildProfile)
def update_child_profile(
    child_id: UUID,
    request: ChildProfileUpdateRequest,
    store: Annotated[EntityStore, Depends(get_child_profile_store)],
) -> ChildProfile:
    payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")

    current = ChildProfile.model_validate(payload)
    updated_payload = current.model_dump()
    updated_payload.update(request.model_dump())
    # Keep the canonical name aligned with the low-identification nickname used by the desktop UI.
    updated_payload["name"] = request.nickname
    updated_payload["updated_at"] = datetime.now(UTC)
    updated = ChildProfile.model_validate(updated_payload)
    store.save(updated)
    return updated
