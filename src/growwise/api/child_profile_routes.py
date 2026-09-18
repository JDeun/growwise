from __future__ import annotations

import base64
import binascii
from contextlib import suppress
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.domain.photo import PhotoAsset
from growwise.domain.models import LanguageCode, ShortText, TagText
from growwise.services.child_lock import child_operation_lock
from growwise.services.photo_activity import (
    PhotoAssetStore,
    PhotoUpload,
    PhotoValidationError,
)
from growwise.storage import EntityStore

router = APIRouter(tags=["child-profile"])

_MAX_AVATAR_BYTES = 5 * 1024 * 1024
_MAX_ENCODED_AVATAR_CHARS = 7_100_000


class ChildAvatarUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    data_base64: str = Field(min_length=4, max_length=_MAX_ENCODED_AVATAR_CHARS)


class ChildProfileUpdateRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=120)
    stage: Stage
    age_months: int | None = Field(default=None, ge=0, le=240)
    interests: list[TagText] = Field(default_factory=list, max_length=100)
    primary_language: LanguageCode = "ko-KR"
    additional_languages: list[LanguageCode] = Field(default_factory=list, max_length=20)
    learning_goals: list[ShortText] = Field(default_factory=list, max_length=100)
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



@router.post("/children/{child_id}/avatar", response_model=ChildProfile)
def upload_child_avatar(
    child_id: UUID,
    request: ChildAvatarUploadRequest,
    settings: Annotated[Settings, Depends(get_child_profile_settings)],
    store: Annotated[EntityStore, Depends(get_child_profile_store)],
) -> ChildProfile:
    try:
        data = base64.b64decode(request.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid_avatar_base64") from exc
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="avatar_too_large")

    child_key = str(child_id)
    with child_operation_lock(child_key):
        payload = store.index.get_entity(child_key, entity_type="child_profile")
        if payload is None:
            raise HTTPException(status_code=404, detail="child_not_found")
        current = ChildProfile.model_validate(payload)
        asset_store = PhotoAssetStore(
            settings.assets_dir,
            max_file_bytes=min(settings.photo_max_file_bytes, _MAX_AVATAR_BYTES),
        )
        try:
            avatar, created = asset_store.store_avatar(
                child_id=child_key,
                upload=PhotoUpload(
                    filename=request.filename,
                    mime_type=request.mime_type,
                    data=data,
                ),
            )
        except PhotoValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        saved_asset = False
        try:
            store.save(avatar)
            saved_asset = True
            previous_id = current.avatar_asset_id
            current.avatar_asset_id = avatar.id
            current.updated_at = datetime.now(UTC)
            store.save(current)
        except Exception:
            if saved_asset:
                with suppress(Exception):
                    store.delete(avatar)
            if created:
                with suppress(Exception):
                    asset_store.delete_asset(avatar)
            raise

        if previous_id is not None and previous_id != avatar.id:
            previous_payload = store.index.get_entity(
                str(previous_id),
                entity_type="photo_asset",
            )
            if previous_payload is not None:
                previous = PhotoAsset.model_validate(previous_payload)
                with suppress(Exception):
                    store.delete(previous)
                if previous.relative_path != avatar.relative_path:
                    with suppress(Exception):
                        asset_store.delete_asset(previous)
        return current


@router.delete("/children/{child_id}/avatar", response_model=ChildProfile)
def delete_child_avatar(
    child_id: UUID,
    settings: Annotated[Settings, Depends(get_child_profile_settings)],
    store: Annotated[EntityStore, Depends(get_child_profile_store)],
) -> ChildProfile:
    child_key = str(child_id)
    with child_operation_lock(child_key):
        payload = store.index.get_entity(child_key, entity_type="child_profile")
        if payload is None:
            raise HTTPException(status_code=404, detail="child_not_found")
        current = ChildProfile.model_validate(payload)
        previous_id = current.avatar_asset_id
        if previous_id is None:
            return current

        current.avatar_asset_id = None
        current.updated_at = datetime.now(UTC)
        store.save(current)

        previous_payload = store.index.get_entity(
            str(previous_id),
            entity_type="photo_asset",
        )
        if previous_payload is not None:
            previous = PhotoAsset.model_validate(previous_payload)
            asset_store = PhotoAssetStore(
                settings.assets_dir,
                max_file_bytes=min(settings.photo_max_file_bytes, _MAX_AVATAR_BYTES),
            )
            with suppress(Exception):
                store.delete(previous)
            with suppress(Exception):
                asset_store.delete_asset(previous)
        return current
