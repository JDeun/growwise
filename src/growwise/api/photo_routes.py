from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from growwise.config import Settings
from growwise.domain.photo import PhotoAsset
from growwise.model.factory import create_model_provider
from growwise.model.provider import ModelProvider
from growwise.model.vision import OllamaVisionProvider
from growwise.services.photo_activity import (
    PhotoActivityService,
    PhotoAssetStore,
    PhotoUpload,
    PhotoValidationError,
)
from growwise.storage import EntityStore

router = APIRouter(prefix="/v1", tags=["photo-activity"])


class PhotoUploadInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    data_base64: str = Field(min_length=4)


class PhotoDraftRequest(BaseModel):
    files: list[PhotoUploadInput] = Field(min_length=1, max_length=12)
    user_context: str | None = Field(default=None, max_length=10_000)


class PhotoCommitRequest(BaseModel):
    observation: str | None = Field(default=None, max_length=10_000)


@lru_cache
def get_photo_settings() -> Settings:
    return Settings()


def get_photo_store(
    settings: Annotated[Settings, Depends(get_photo_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@lru_cache
def get_photo_text_provider() -> ModelProvider | None:
    settings = get_photo_settings()
    if not settings.llm_features_enabled:
        return None
    try:
        return create_model_provider(settings)
    except Exception:
        return None


@lru_cache
def get_photo_vision_provider() -> OllamaVisionProvider | None:
    settings = get_photo_settings()
    if not settings.vision_features_enabled:
        return None
    try:
        return OllamaVisionProvider(
            model=settings.vision_model_id,
            base_url=settings.model_base_url,
            timeout_seconds=settings.vision_timeout_seconds,
            failure_threshold=settings.model_circuit_failure_threshold,
            recovery_seconds=settings.model_circuit_recovery_seconds,
        )
    except Exception:
        return None


def _service(settings: Settings, store: EntityStore) -> PhotoActivityService:
    return PhotoActivityService(
        store=store,
        asset_store=PhotoAssetStore(
            settings.assets_dir,
            max_file_bytes=settings.photo_max_file_bytes,
        ),
        text_provider=get_photo_text_provider(),
        vision_provider=get_photo_vision_provider(),
        max_images=settings.photo_max_images_per_record,
    )


def _decode_uploads(request: PhotoDraftRequest, settings: Settings) -> list[PhotoUpload]:
    if len(request.files) > settings.photo_max_images_per_record:
        raise HTTPException(status_code=422, detail="too_many_photos")
    uploads: list[PhotoUpload] = []
    total = 0
    for item in request.files:
        try:
            data = base64.b64decode(item.data_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=422, detail="invalid_photo_base64") from exc
        total += len(data)
        if len(data) > settings.photo_max_file_bytes:
            raise HTTPException(status_code=413, detail="photo_too_large")
        if total > settings.photo_max_total_bytes:
            raise HTTPException(status_code=413, detail="photo_batch_too_large")
        uploads.append(
            PhotoUpload(
                filename=item.filename,
                mime_type=item.mime_type,
                data=data,
            )
        )
    return uploads


@router.post("/children/{child_id}/photo-records")
def create_photo_record(
    child_id: UUID,
    request: PhotoDraftRequest,
    settings: Annotated[Settings, Depends(get_photo_settings)],
    store: Annotated[EntityStore, Depends(get_photo_store)],
) -> dict[str, object]:
    uploads = _decode_uploads(request, settings)
    try:
        record, assets = _service(settings, store).create_draft(
            child_id=str(child_id),
            uploads=uploads,
            user_context=request.user_context,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    except PhotoValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "record": record.model_dump(mode="json"),
        "assets": [asset.model_dump(mode="json") for asset in assets],
    }


@router.get("/children/{child_id}/photo-records")
def list_photo_records(
    child_id: UUID,
    settings: Annotated[Settings, Depends(get_photo_settings)],
    store: Annotated[EntityStore, Depends(get_photo_store)],
) -> list[dict[str, object]]:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return [
        record.model_dump(mode="json")
        for record in _service(settings, store).list_for_child(str(child_id))
    ]


@router.post("/photo-records/{record_id}/commit")
def commit_photo_record(
    record_id: UUID,
    request: PhotoCommitRequest,
    settings: Annotated[Settings, Depends(get_photo_settings)],
    store: Annotated[EntityStore, Depends(get_photo_store)],
) -> dict[str, object]:
    try:
        log = _service(settings, store).commit(
            record_id=str(record_id),
            observation=request.observation,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    except PhotoValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return log.model_dump(mode="json")


@router.get("/children/{child_id}/photo-assets/{asset_id}")
def get_photo_asset(
    child_id: UUID,
    asset_id: UUID,
    settings: Annotated[Settings, Depends(get_photo_settings)],
    store: Annotated[EntityStore, Depends(get_photo_store)],
) -> dict[str, object]:
    try:
        asset, data = _service(settings, store).get_asset(str(asset_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    except (PhotoValidationError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if asset.child_id != child_id:
        raise HTTPException(status_code=404, detail="photo_asset_not_found")
    typed_asset = PhotoAsset.model_validate(asset)
    return {
        "asset": typed_asset.model_dump(mode="json"),
        "data_base64": base64.b64encode(data).decode("ascii"),
    }
