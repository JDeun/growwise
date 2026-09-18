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
from growwise.domain.models import LanguageCode, ShortText, TagText
from growwise.domain.photo import PhotoAsset
from growwise.services.child_lock import child_operation_lock
from growwise.services.photo_activity import PhotoAssetStore, PhotoUpload, PhotoValidationError
from growwise.services.photo_image_validation import (
    PhotoImageValidationError,
    validate_image_dimensions,
)
from growwise.storage import EntityStore

router = APIRouter(tags=["child-profile"])


_MAX_ENCODED_AVATAR_CHARS = 21_000_000


class ChildAvatarRequest(BaseModel):
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


def _decode_avatar(request: ChildAvatarRequest, settings: Settings) -> PhotoUpload:
    try:
        data = base64.b64decode(request.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid_avatar_base64") from exc
    if len(data) > settings.photo_max_file_bytes:
        raise HTTPException(status_code=413, detail="avatar_too_large")
    try:
        validate_image_dimensions(
            data,
            max_width=settings.photo_max_width,
            max_height=settings.photo_max_height,
            max_pixels=settings.photo_max_pixels,
        )
    except PhotoImageValidationError as exc:
        detail = str(exc)
        status_code = 413 if detail == "image_dimensions_too_large" else 422
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return PhotoUpload(
        filename=request.filename,
        mime_type=request.mime_type,
        data=data,
    )


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



@router.put("/children/{child_id}/avatar", response_model=ChildProfile)
def update_child_avatar(
    child_id: UUID,
    request: ChildAvatarRequest,
    settings: Annotated[Settings, Depends(get_child_profile_settings)],
    store: Annotated[EntityStore, Depends(get_child_profile_store)],
) -> ChildProfile:
    upload = _decode_avatar(request, settings)
    child_key = str(child_id)
    asset_store = PhotoAssetStore(
        settings.assets_dir,
        max_file_bytes=settings.photo_max_file_bytes,
    )

    with child_operation_lock(child_key):
        payload = store.index.get_entity(child_key, entity_type="child_profile")
        if payload is None:
            raise HTTPException(status_code=404, detail="child_not_found")
        profile = ChildProfile.model_validate(payload)

        previous_asset: PhotoAsset | None = None
        if profile.avatar_asset_id is not None:
            previous_payload = store.index.get_entity(
                str(profile.avatar_asset_id),
                entity_type="photo_asset",
            )
            if previous_payload is not None:
                candidate = PhotoAsset.model_validate(previous_payload)
                if candidate.child_id == child_id:
                    previous_asset = candidate

        try:
            avatar, created = asset_store.store(
                child_id=child_key,
                upload=upload,
                namespace="avatars",
            )
            store.save(avatar)
        except PhotoValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        previous_avatar_id = profile.avatar_asset_id
        profile.avatar_asset_id = avatar.id
        profile.updated_at = datetime.now(UTC)
        try:
            store.save(profile)
        except Exception:
            with suppress(Exception):
                store.delete(avatar)
            if created:
                with suppress(Exception):
                    asset_store.delete_asset(avatar)
            raise

        if previous_asset is not None and previous_avatar_id != avatar.id:
            with suppress(Exception):
                store.delete(previous_asset)
            if previous_asset.relative_path != avatar.relative_path:
                with suppress(Exception):
                    asset_store.delete_asset(previous_asset)

        return profile


@router.delete("/children/{child_id}/avatar", response_model=ChildProfile)
def delete_child_avatar(
    child_id: UUID,
    settings: Annotated[Settings, Depends(get_child_profile_settings)],
    store: Annotated[EntityStore, Depends(get_child_profile_store)],
) -> ChildProfile:
    child_key = str(child_id)
    asset_store = PhotoAssetStore(
        settings.assets_dir,
        max_file_bytes=settings.photo_max_file_bytes,
    )

    with child_operation_lock(child_key):
        payload = store.index.get_entity(child_key, entity_type="child_profile")
        if payload is None:
            raise HTTPException(status_code=404, detail="child_not_found")
        profile = ChildProfile.model_validate(payload)
        avatar_id = profile.avatar_asset_id
        if avatar_id is None:
            return profile

        asset_payload = store.index.get_entity(str(avatar_id), entity_type="photo_asset")
        avatar = PhotoAsset.model_validate(asset_payload) if asset_payload is not None else None
        if avatar is not None and avatar.child_id != child_id:
            avatar = None

        profile.avatar_asset_id = None
        profile.updated_at = datetime.now(UTC)
        store.save(profile)

        if avatar is not None:
            with suppress(Exception):
                store.delete(avatar)
            with suppress(Exception):
                asset_store.delete_asset(avatar)

        return profile
