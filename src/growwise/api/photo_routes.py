from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from growwise.config import Settings
from growwise.domain.photo import PhotoAsset, PhotoRecordStatus
from growwise.jobs import SQLiteJobQueue
from growwise.model.factory import create_model_provider
from growwise.model.ollama import OllamaProvider
from growwise.model.provider import ModelProvider
from growwise.model.vision import OllamaVisionProvider
from growwise.services.entity_links import EntityLinkError, EntityLinkService
from growwise.services.photo_activity import (
    PhotoActivityService,
    PhotoAssetStore,
    PhotoUpload,
    PhotoValidationError,
)
from growwise.services.photo_image_validation import (
    PhotoImageValidationError,
    validate_image_dimensions,
)
from growwise.services.photo_jobs import PhotoJobRunner
from growwise.storage import EntityStore

# This router is mounted under study_routes, whose prefix is already /v1.
router = APIRouter(tags=["photo-activity"])

# 15 MiB expands to just under 21 MiB in base64. Bound the encoded representation as well as the
# decoded bytes so an authenticated local caller cannot send an unbounded string into validation.
_MAX_ENCODED_PHOTO_CHARS = 21_000_000


class PhotoUploadInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    data_base64: str = Field(min_length=4, max_length=_MAX_ENCODED_PHOTO_CHARS)


class PhotoDraftRequest(BaseModel):
    files: list[PhotoUploadInput] = Field(min_length=1, max_length=12)
    user_context: str | None = Field(default=None, max_length=10_000)
    manual_observation: str | None = Field(default=None, max_length=10_000)
    ai_assist: bool = True
    shared_child_ids: list[UUID] = Field(default_factory=list, max_length=20)


class PhotoCommitRequest(BaseModel):
    observation: str | None = Field(default=None, max_length=10_000)


@lru_cache
def get_photo_settings() -> Settings:
    return Settings()


def get_photo_store(
    settings: Annotated[Settings, Depends(get_photo_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


def _model_endpoint_is_loopback(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname
    except ValueError:
        return False
    if host is None:
        return False
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@lru_cache
def get_photo_text_provider() -> ModelProvider | None:
    settings = get_photo_settings()
    if not settings.llm_features_enabled:
        return None
    if settings.model_provider.casefold() == "ollama":
        if (
            not _model_endpoint_is_loopback(settings.model_base_url)
            and not settings.photo_remote_text_allowed
        ):
            return None
        try:
            return OllamaProvider(
                model=settings.model_id,
                base_url=settings.model_base_url,
                temperature=settings.model_temperature,
                timeout_seconds=settings.photo_text_timeout_seconds,
                failure_threshold=settings.model_circuit_failure_threshold,
                recovery_seconds=settings.model_circuit_recovery_seconds,
            )
        except Exception:
            return None
    if not settings.photo_remote_text_allowed:
        return None
    try:
        return create_model_provider(settings)
    except Exception:
        return None


@lru_cache
def get_photo_vision_provider() -> OllamaVisionProvider | None:
    settings = get_photo_settings()
    if not settings.vision_features_enabled or settings.vision_provider.casefold() != "ollama":
        return None
    if (
        not _model_endpoint_is_loopback(settings.vision_base_url)
        and not settings.photo_remote_vision_allowed
    ):
        return None
    try:
        return OllamaVisionProvider(
            model=settings.vision_model_id,
            base_url=settings.vision_base_url,
            timeout_seconds=settings.vision_timeout_seconds,
            failure_threshold=settings.model_circuit_failure_threshold,
            recovery_seconds=settings.model_circuit_recovery_seconds,
        )
    except Exception:
        return None


def _service(
    settings: Settings,
    store: EntityStore,
    *,
    ai_enabled: bool = True,
) -> PhotoActivityService:
    return PhotoActivityService(
        store=store,
        asset_store=PhotoAssetStore(
            settings.assets_dir,
            max_file_bytes=settings.photo_max_file_bytes,
        ),
        text_provider=get_photo_text_provider() if ai_enabled else None,
        vision_provider=get_photo_vision_provider() if ai_enabled else None,
        max_images=settings.photo_max_images_per_record,
    )


@lru_cache
def get_photo_job_runner() -> PhotoJobRunner:
    settings = get_photo_settings()

    def service_factory() -> PhotoActivityService:
        store = EntityStore(settings.records_dir, settings.index_path)
        return _service(settings, store)

    return PhotoJobRunner(
        queue=SQLiteJobQueue(settings.jobs_path),
        service_factory=service_factory,
        lease_seconds=settings.photo_job_lease_seconds,
        max_attempts=settings.photo_job_max_attempts,
        poll_interval_seconds=settings.photo_job_poll_interval_seconds,
    )


def start_photo_job_runner() -> None:
    get_photo_job_runner().start()


def stop_photo_job_runner() -> None:
    get_photo_job_runner().stop()


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
        uploads.append(
            PhotoUpload(
                filename=item.filename,
                mime_type=item.mime_type,
                data=data,
            )
        )
    return uploads


def _shared_children(
    *,
    primary_child_id: UUID,
    requested: list[UUID],
    store: EntityStore,
) -> list[UUID]:
    shared: list[UUID] = []
    for child_id in dict.fromkeys(requested):
        if child_id == primary_child_id:
            continue
        if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
            raise HTTPException(status_code=404, detail="shared_child_not_found")
        shared.append(child_id)
    return shared


@router.post(
    "/children/{child_id}/photo-records",
    status_code=status.HTTP_202_ACCEPTED,
)
def create_photo_record(
    child_id: UUID,
    request: PhotoDraftRequest,
    settings: Annotated[Settings, Depends(get_photo_settings)],
    store: Annotated[EntityStore, Depends(get_photo_store)],
) -> dict[str, object]:
    shared_child_ids = _shared_children(
        primary_child_id=child_id,
        requested=request.shared_child_ids,
        store=store,
    )
    uploads = _decode_uploads(request, settings)

    manual_text = (request.manual_observation or "").strip()
    context_text = (request.user_context or "").strip()
    ai_service = _service(settings, store, ai_enabled=request.ai_assist)
    can_assist = request.ai_assist and (
        ai_service.text_provider is not None or ai_service.vision_provider is not None
    )
    # In manual mode the parent's text is the record. If they only supplied a context note, keep
    # that as the editable draft. No model is required to reach the parent-review state.
    effective_context = context_text
    if not can_assist and manual_text:
        effective_context = manual_text

    try:
        record, assets = ai_service.prepare_draft(
            child_id=str(child_id),
            uploads=uploads,
            user_context=effective_context or None,
        )
        if shared_child_ids:
            EntityLinkService(store).share_with_children(
                source_id=record.id,
                child_ids=shared_child_ids,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    except (PhotoValidationError, EntityLinkError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not can_assist:
        manual_service = _service(settings, store, ai_enabled=False)
        record = manual_service.process_draft(str(record.id))
        if manual_text and record.generated_observation != manual_text:
            # Deterministic processing can append metadata-only fallback text. Parent-authored text
            # wins in manual diary mode and is stored verbatim until the parent edits it again.
            record.generated_observation = manual_text[:10_000]
            record.generation_mode = "manual_photo_diary"
            store.save(record)
        else:
            record.generation_mode = "manual_photo_diary"
            store.save(record)
        return {
            "record": record.model_dump(mode="json"),
            "assets": [asset.model_dump(mode="json") for asset in assets],
            "job": None,
        }

    runner = get_photo_job_runner()
    try:
        with store.mutation_window():
            runner.start()
            job = runner.submit(child_id=str(child_id), record_id=str(record.id))
            record = ai_service.attach_job(record_id=str(record.id), job_id=job.id)
    except HTTPException:
        raise
    except Exception as exc:
        # Queue failure must not make a locally-saved diary unusable. Convert immediately to a
        # deterministic parent-editable draft rather than returning a hard dependency on AI.
        fallback_service = _service(settings, store, ai_enabled=False)
        fallback_service.mark_queued(str(record.id), error=f"background_queue_error: {exc}")
        record = fallback_service.process_draft(str(record.id))
        return {
            "record": record.model_dump(mode="json"),
            "assets": [asset.model_dump(mode="json") for asset in assets],
            "job": None,
        }

    return {
        "record": record.model_dump(mode="json"),
        "assets": [asset.model_dump(mode="json") for asset in assets],
        "job": {
            "id": str(job.id),
            "status": job.status,
            "attempts": job.attempts,
        },
    }


@router.get("/children/{child_id}/photo-records")
def list_photo_records(
    child_id: UUID,
    settings: Annotated[Settings, Depends(get_photo_settings)],
    store: Annotated[EntityStore, Depends(get_photo_store)],
) -> list[dict[str, object]]:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    # Opening the photo workspace after an app restart wakes the durable worker and reclaims any
    # analysis that was interrupted while Core was shutting down.
    get_photo_job_runner().start()
    return [
        record.model_dump(mode="json")
        for record in _service(settings, store).list_for_child(str(child_id))
    ]


@router.get("/children/{child_id}/photo-records/{record_id}")
def get_photo_record(
    child_id: UUID,
    record_id: UUID,
    settings: Annotated[Settings, Depends(get_photo_settings)],
    store: Annotated[EntityStore, Depends(get_photo_store)],
) -> dict[str, object]:
    service = _service(settings, store)
    try:
        record = service.get_record(str(record_id))
        shared_children = EntityLinkService(store).child_scope_targets(record.id)
        if record.child_id != child_id and child_id not in shared_children:
            raise KeyError("photo_record_not_found")
        assets = service.get_assets_for_record(str(record_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    return {
        "record": record.model_dump(mode="json"),
        "assets": [asset.model_dump(mode="json") for asset in assets],
    }


@router.post("/photo-records/{record_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_photo_record(
    record_id: UUID,
    settings: Annotated[Settings, Depends(get_photo_settings)],
    store: Annotated[EntityStore, Depends(get_photo_store)],
) -> dict[str, object]:
    service = _service(settings, store)
    try:
        record = service.get_record(str(record_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    if record.status is not PhotoRecordStatus.FAILED:
        raise HTTPException(status_code=409, detail="photo_record_not_failed")

    runner = get_photo_job_runner()
    with store.mutation_window():
        service.mark_queued(str(record_id))
        runner.start()
        job = runner.submit(child_id=str(record.child_id), record_id=str(record.id))
        record = service.attach_job(record_id=str(record.id), job_id=job.id)
    return {
        "record": record.model_dump(mode="json"),
        "job": {"id": str(job.id), "status": job.status, "attempts": job.attempts},
    }


@router.post("/photo-records/{record_id}/commit")
def commit_photo_record(
    record_id: UUID,
    request: PhotoCommitRequest,
    settings: Annotated[Settings, Depends(get_photo_settings)],
    store: Annotated[EntityStore, Depends(get_photo_store)],
) -> dict[str, object]:
    try:
        service = _service(settings, store)
        record = service.get_record(str(record_id))
        shared_child_ids = EntityLinkService(store).child_scope_targets(record.id)
        log = service.commit(
            record_id=str(record_id),
            observation=request.observation,
        )
        if shared_child_ids:
            EntityLinkService(store).share_with_children(
                source_id=log.id,
                child_ids=shared_child_ids,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    except (PhotoValidationError, EntityLinkError) as exc:
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
