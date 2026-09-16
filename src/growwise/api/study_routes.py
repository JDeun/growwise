"""Middle/high study-tracking routes with deterministic, child-scoped behavior."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from growwise.api.curriculum_routes import router as curriculum_router
from growwise.api.photo_routes import router as photo_router
from growwise.api.privacy_routes import router as privacy_router
from growwise.api.resource_routes import router as resource_router
from growwise.config import Settings
from growwise.domain.models import ChildProfile, Stage
from growwise.domain.study import (
    MistakeRecord,
    MistakeType,
    SelfExplanationLog,
    StudyPlan,
    StudyPlanItem,
    StudyProgressState,
    StudyReflection,
    StudyUnitProgress,
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
    evidence_refs: list[str] = Field(default_factory=list, max_length=30)
    open_question: str | None = Field(default=None, max_length=4000)


class StudyPlanRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    target_date: date | None = None
    parent_note: str | None = Field(default=None, max_length=4000)
    max_items: int = Field(default=6, ge=1, le=20)


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


@router.post("/children/{child_id}/study/progress", response_model=StudyUnitProgress)
def record_progress(
    child_id: UUID,
    request: StudyProgressRequest,
    store: Annotated[EntityStore, Depends(get_study_store)],
) -> StudyUnitProgress:
    _study_child(store, child_id)
    record = StudyUnitProgress(child_id=child_id, **request.model_dump())
    store.save(record)
    return record


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
) -> MistakeRecord:
    _study_child(store, child_id)
    record = MistakeRecord(child_id=child_id, **request.model_dump())
    store.save(record)
    return record


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
) -> StudyReflection:
    _study_child(store, child_id)
    record = StudyReflection(child_id=child_id, **request.model_dump())
    store.save(record)
    return record


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
) -> SelfExplanationLog:
    _study_child(store, child_id)
    record = SelfExplanationLog(child_id=child_id, **request.model_dump())
    store.save(record)
    return record


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
    plan = StudyPlan(
        child_id=child_id,
        title=request.title,
        target_date=request.target_date,
        items=items,
        parent_note=request.parent_note,
    )
    store.save(plan)
    return plan


@router.get("/children/{child_id}/study/plans")
def list_study_plans(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_study_store)],
) -> list[dict]:
    _study_child(store, child_id)
    return store.index.list_entities(entity_type="study_plan", child_id=str(child_id))


router.include_router(curriculum_router)
router.include_router(resource_router)
router.include_router(privacy_router)
router.include_router(photo_router)
