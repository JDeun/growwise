"""Middle/high study-tracking routes with deterministic, child-scoped behavior."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from uuid6 import uuid7

from growwise.api.background_write_routes import router as background_write_router
from growwise.api.child_profile_routes import router as child_profile_router
from growwise.api.curriculum_routes import router as curriculum_router
from growwise.api.discovery_routes import router as discovery_router
from growwise.api.learning_record_routes import router as learning_record_router
from growwise.api.learning_wiki_routes import router as learning_wiki_router
from growwise.api.link_routes import router as link_router
from growwise.api.material_result_routes import router as material_result_router
from growwise.api.photo_routes import router as photo_router
from growwise.api.privacy_routes import router as privacy_router
from growwise.api.resource_routes import router as resource_router
from growwise.config import Settings
from growwise.domain.models import ChildProfile, EntityBase, SourceRef, Stage
from growwise.domain.study import (
    MistakeRecord,
    MistakeType,
    PlanItemStatus,
    SelfExplanationLog,
    StudyPlan,
    StudyPlanItem,
    StudyProgressState,
    StudyReflection,
    StudyUnitProgress,
)
from growwise.idempotency import (
    IdempotencyConflict,
    IdempotencyStatus,
    SQLiteIdempotencyStore,
    request_fingerprint,
)
from growwise.services.study import StudyTrackingService
from growwise.storage import EntityStore

router = APIRouter(prefix="/v1", tags=["study-tracking"])


class StudyProgressRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=240)
    state: StudyProgressState = StudyProgressState.IN_PROGRESS
    note: str | None = Field(default=None, max_length=4000)
    last_studied_at: datetime | None = None


class MistakeRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=240)
    mistake_type: MistakeType = MistakeType.OTHER
    prompt: str | None = Field(default=None, max_length=4000)
    learner_response: str | None = Field(default=None, max_length=4000)
    corrected_understanding: str | None = Field(default=None, max_length=4000)
    evidence_ref: str | None = Field(default=None, max_length=500)


class ReflectionRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=240)
    worked_well: str | None = Field(default=None, max_length=4000)
    difficult_point: str | None = Field(default=None, max_length=4000)
    next_step: str | None = Field(default=None, max_length=4000)


class SelfExplanationRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=240)
    explanation: str = Field(min_length=1, max_length=8000)
    evidence_refs: list[SourceRef] = Field(default_factory=list, max_length=30)
    open_question: str | None = Field(default=None, max_length=4000)


class StudyPlanRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    target_date: date | None = None
    parent_note: str | None = Field(default=None, max_length=4000)
    max_items: int = Field(default=6, ge=1, le=20)


class StudyPlanItemStatusRequest(BaseModel):
    status: PlanItemStatus


@lru_cache
def get_study_settings() -> Settings:
    return Settings()


def get_study_store(
    settings: Annotated[Settings, Depends(get_study_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


def _study_child(store: EntityStore, child_id: UUID) -> ChildProfile:
    payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(payload)
    if child.stage not in {Stage.MIDDLE, Stage.HIGH}:
        raise HTTPException(status_code=409, detail="study_tracking_requires_middle_or_high_stage")
    return child


def _idempotent_study_create[TStudyEntity: EntityBase](
    *,
    child_id: UUID,
    request_payload: dict[str, object],
    resource_type: str,
    model: type[TStudyEntity],
    build: Callable[[UUID], TStudyEntity],
    store: EntityStore,
    idempotency_key: str | None,
) -> TStudyEntity:
    reserved_id: UUID = uuid7()
    if idempotency_key is None:
        entity = build(reserved_id)
        store.save(entity)
        return entity

    claim = None
    idempotency_store = SQLiteIdempotencyStore(get_study_settings().idempotency_path)
    request_hash = request_fingerprint(
        {"child_id": str(child_id), "resource_type": resource_type, **request_payload}
    )
    if idempotency_key is not None:
        try:
            claim = idempotency_store.claim(
                key=idempotency_key,
                request_hash=request_hash,
                resource_type=resource_type,
                resource_id=str(reserved_id),
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        reserved_id = UUID(claim.record.resource_id)
        if not claim.acquired:
            existing = store.index.get_entity(claim.record.resource_id, entity_type=resource_type)
            if existing is not None:
                if claim.record.status is IdempotencyStatus.PENDING:
                    idempotency_store.complete(
                        key=claim.record.key,
                        request_hash=claim.record.request_hash,
                        resource_id=claim.record.resource_id,
                    )
                return model.model_validate(existing)
            if claim.record.status is IdempotencyStatus.COMPLETED:
                raise HTTPException(status_code=409, detail="idempotency_resource_missing")
            raise HTTPException(status_code=409, detail="idempotency_in_progress")

    entity = build(reserved_id)
    try:
        store.save(entity)
        if claim is not None and claim.acquired:
            idempotency_store.complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        return entity
    except Exception:
        if claim is not None and claim.acquired:
            existing = store.index.get_entity(claim.record.resource_id, entity_type=resource_type)
            if existing is None:
                idempotency_store.release(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
            else:
                idempotency_store.complete(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
        raise


@router.post("/children/{child_id}/study/progress", response_model=StudyUnitProgress)
def record_progress(
    child_id: UUID,
    request: StudyProgressRequest,
    store: Annotated[EntityStore, Depends(get_study_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> StudyUnitProgress:
    _study_child(store, child_id)
    payload = request.model_dump(mode="json")
    return _idempotent_study_create(
        child_id=child_id,
        request_payload=payload,
        resource_type="study_unit_progress",
        model=StudyUnitProgress,
        build=lambda entity_id: StudyUnitProgress(
            id=entity_id, child_id=child_id, **request.model_dump()
        ),
        store=store,
        idempotency_key=idempotency_key,
    )


@router.get("/children/{child_id}/study/progress")
def list_progress(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_study_store)],
) -> list[dict]:
    _study_child(store, child_id)
    return store.index.list_entities(entity_type="study_unit_progress", child_id=str(child_id))


@router.post("/children/{child_id}/study/mistakes", response_model=MistakeRecord)
def record_mistake(
    child_id: UUID,
    request: MistakeRequest,
    store: Annotated[EntityStore, Depends(get_study_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> MistakeRecord:
    _study_child(store, child_id)
    payload = request.model_dump(mode="json")
    return _idempotent_study_create(
        child_id=child_id,
        request_payload=payload,
        resource_type="mistake_record",
        model=MistakeRecord,
        build=lambda entity_id: MistakeRecord(
            id=entity_id, child_id=child_id, **request.model_dump()
        ),
        store=store,
        idempotency_key=idempotency_key,
    )


@router.get("/children/{child_id}/study/mistakes")
def list_mistakes(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_study_store)],
) -> list[dict]:
    _study_child(store, child_id)
    return store.index.list_entities(entity_type="mistake_record", child_id=str(child_id))


@router.post("/children/{child_id}/study/reflections", response_model=StudyReflection)
def record_reflection(
    child_id: UUID,
    request: ReflectionRequest,
    store: Annotated[EntityStore, Depends(get_study_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> StudyReflection:
    _study_child(store, child_id)
    payload = request.model_dump(mode="json")
    return _idempotent_study_create(
        child_id=child_id,
        request_payload=payload,
        resource_type="study_reflection",
        model=StudyReflection,
        build=lambda entity_id: StudyReflection(
            id=entity_id, child_id=child_id, **request.model_dump()
        ),
        store=store,
        idempotency_key=idempotency_key,
    )


@router.get("/children/{child_id}/study/reflections")
def list_reflections(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_study_store)],
) -> list[dict]:
    _study_child(store, child_id)
    return store.index.list_entities(entity_type="study_reflection", child_id=str(child_id))


@router.post(
    "/children/{child_id}/study/self-explanations",
    response_model=SelfExplanationLog,
)
def record_self_explanation(
    child_id: UUID,
    request: SelfExplanationRequest,
    store: Annotated[EntityStore, Depends(get_study_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> SelfExplanationLog:
    _study_child(store, child_id)
    payload = request.model_dump(mode="json")
    return _idempotent_study_create(
        child_id=child_id,
        request_payload=payload,
        resource_type="self_explanation_log",
        model=SelfExplanationLog,
        build=lambda entity_id: SelfExplanationLog(
            id=entity_id, child_id=child_id, **request.model_dump()
        ),
        store=store,
        idempotency_key=idempotency_key,
    )


@router.get("/children/{child_id}/study/self-explanations")
def list_self_explanations(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_study_store)],
) -> list[dict]:
    _study_child(store, child_id)
    return store.index.list_entities(entity_type="self_explanation_log", child_id=str(child_id))


@router.get("/children/{child_id}/study/weak-map")
def get_weak_map(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_study_store)],
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> dict:
    _study_child(store, child_id)
    return StudyTrackingService(store.index).weak_map(
        child_id=str(child_id),
        limit=limit,
    ).model_dump(mode="json")


@router.get("/children/{child_id}/study/resources")
def recommend_study_resources(
    child_id: UUID,
    subject: Annotated[str, Query(min_length=1, max_length=120)],
    unit: Annotated[str, Query(min_length=1, max_length=240)],
    store: Annotated[EntityStore, Depends(get_study_store)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[dict]:
    _study_child(store, child_id)
    result = StudyTrackingService(store.index).recommend_resources(
        child_id=str(child_id),
        subject=subject,
        unit=unit,
        limit=limit,
    )
    return [item.model_dump(mode="json") for item in result]


@router.post("/children/{child_id}/study/plans", response_model=StudyPlan)
def create_study_plan(
    child_id: UUID,
    request: StudyPlanRequest,
    store: Annotated[EntityStore, Depends(get_study_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> StudyPlan:
    _study_child(store, child_id)
    weak_map = StudyTrackingService(store.index).weak_map(
        child_id=str(child_id),
        limit=request.max_items,
    )
    items = [
        StudyPlanItem(
            subject=entry.subject,
            unit=entry.unit,
            focus=(
                entry.recent_difficulties[0]
                if entry.recent_difficulties
                else "최근 기록을 바탕으로 이해 과정을 다시 설명하고 필요한 부분만 복습한다."
            ),
        )
        for entry in weak_map.entries
    ]
    payload = request.model_dump(mode="json")
    return _idempotent_study_create(
        child_id=child_id,
        request_payload=payload,
        resource_type="study_plan",
        model=StudyPlan,
        build=lambda entity_id: StudyPlan(
            id=entity_id,
            child_id=child_id,
            title=request.title,
            target_date=request.target_date,
            items=items,
            parent_note=request.parent_note,
        ),
        store=store,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/children/{child_id}/study/plans/{plan_id}/items/{item_index}/status",
    response_model=StudyPlan,
)
def update_study_plan_item_status(
    child_id: UUID,
    plan_id: UUID,
    item_index: int,
    request: StudyPlanItemStatusRequest,
    store: Annotated[EntityStore, Depends(get_study_store)],
) -> StudyPlan:
    _study_child(store, child_id)
    payload = store.index.get_entity(str(plan_id), entity_type="study_plan")
    if payload is None:
        raise HTTPException(status_code=404, detail="study_plan_not_found")
    plan = StudyPlan.model_validate(payload)
    if plan.child_id != child_id:
        raise HTTPException(status_code=404, detail="study_plan_not_found")
    if item_index < 0 or item_index >= len(plan.items):
        raise HTTPException(status_code=404, detail="study_plan_item_not_found")

    items = list(plan.items)
    items[item_index] = items[item_index].model_copy(update={"status": request.status})
    updated = plan.model_copy(
        update={
            "items": items,
            "updated_at": datetime.now(UTC),
        }
    )
    store.save(updated)
    return updated


@router.get("/children/{child_id}/study/plans")
def list_study_plans(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_study_store)],
) -> list[dict]:
    _study_child(store, child_id)
    return store.index.list_entities(entity_type="study_plan", child_id=str(child_id))


router.include_router(background_write_router)
router.include_router(learning_record_router)
router.include_router(learning_wiki_router)
router.include_router(curriculum_router)
router.include_router(discovery_router)
router.include_router(resource_router)
router.include_router(child_profile_router)
router.include_router(privacy_router)
router.include_router(photo_router)
router.include_router(link_router)
router.include_router(material_result_router)
