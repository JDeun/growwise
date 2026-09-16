from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from growwise.config import Settings
from growwise.domain.links import EntityLinkRelation
from growwise.domain.models import (
    ActivityPlan,
    ActivityStatus,
    ExperienceAxis,
    GeneratedMaterial,
    LearningLog,
    MaterialStatus,
)
from growwise.services.activity import ActivityPlanService, InvalidActivityTransition
from growwise.services.child_lock import child_operation_lock
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore

router = APIRouter(tags=["material-results"])


class MaterialUseOutcome(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class MaterialResultRequest(BaseModel):
    outcome: MaterialUseOutcome = MaterialUseOutcome.COMPLETED
    observation: str = Field(min_length=1, max_length=10_000)
    process: str | None = Field(default=None, max_length=10_000)
    child_question: str | None = Field(default=None, max_length=4_000)
    interest: str | None = Field(default=None, max_length=2_000)
    difficulty_note: str | None = Field(default=None, max_length=4_000)
    next_activity: str | None = Field(default=None, max_length=4_000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list, max_length=20)
    activity_plan_id: UUID | None = None


class MaterialResultResponse(BaseModel):
    activity: ActivityPlan
    learning_log: LearningLog


class MaterialUseHistoryItem(BaseModel):
    activity: ActivityPlan
    learning_logs: list[LearningLog] = Field(default_factory=list)


@lru_cache
def get_material_result_settings() -> Settings:
    return Settings()


def get_material_result_store(
    settings: Annotated[Settings, Depends(get_material_result_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


def _approved_material(store: EntityStore, material_id: UUID) -> GeneratedMaterial:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    material = GeneratedMaterial.model_validate(payload)
    if material.status is not MaterialStatus.APPROVED:
        raise HTTPException(status_code=409, detail="material_must_be_approved_before_use")
    return material


def _material_ref(material_id: UUID) -> str:
    return f"material:{material_id}"


def _load_activity_for_material(
    *,
    store: EntityStore,
    material: GeneratedMaterial,
    activity_plan_id: UUID,
) -> ActivityPlan:
    payload = store.index.get_entity(str(activity_plan_id), entity_type="activity_plan")
    if payload is None:
        raise HTTPException(status_code=404, detail="activity_not_found")
    activity = ActivityPlan.model_validate(payload)
    if activity.child_id != material.child_id:
        raise HTTPException(status_code=409, detail="activity_child_mismatch")
    if _material_ref(material.id) not in activity.source_refs:
        raise HTTPException(status_code=409, detail="activity_material_mismatch")
    return activity


def _transition_for_outcome(
    activity: ActivityPlan,
    *,
    outcome: MaterialUseOutcome,
) -> None:
    if activity.status is ActivityStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="material_activity_archived")

    service = ActivityPlanService()
    try:
        if outcome is MaterialUseOutcome.PARTIAL:
            if activity.status in {ActivityStatus.SUGGESTED, ActivityStatus.SKIPPED}:
                service.transition(activity, ActivityStatus.ACTIVE)
            return

        if outcome is MaterialUseOutcome.COMPLETED:
            if activity.status in {ActivityStatus.SUGGESTED, ActivityStatus.SKIPPED}:
                service.transition(activity, ActivityStatus.ACTIVE)
            if activity.status is ActivityStatus.ACTIVE:
                service.transition(activity, ActivityStatus.COMPLETED)
            return

        if activity.status is ActivityStatus.COMPLETED:
            raise HTTPException(status_code=409, detail="completed_activity_cannot_be_skipped")
        if activity.status in {ActivityStatus.SUGGESTED, ActivityStatus.ACTIVE}:
            service.transition(activity, ActivityStatus.SKIPPED)
    except InvalidActivityTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _activity_for_result(
    *,
    store: EntityStore,
    material: GeneratedMaterial,
    request: MaterialResultRequest,
) -> ActivityPlan:
    if request.activity_plan_id is not None:
        activity = _load_activity_for_material(
            store=store,
            material=material,
            activity_plan_id=request.activity_plan_id,
        )
    else:
        activity = ActivityPlan(
            child_id=material.child_id,
            title=material.title,
            description="GrowWise에서 승인한 교육자료를 사용한 실제 활동",
            source_refs=[_material_ref(material.id)],
            experience_axes=list(request.experience_axes),
        )
        store.save(activity)

    activity.experience_axes = list(
        dict.fromkeys([*activity.experience_axes, *request.experience_axes])
    )
    _transition_for_outcome(activity, outcome=request.outcome)
    store.save(activity)
    return activity


@router.post(
    "/materials/{material_id}/results",
    response_model=MaterialResultResponse,
)
def record_material_result(
    material_id: UUID,
    request: MaterialResultRequest,
    store: Annotated[EntityStore, Depends(get_material_result_store)],
) -> MaterialResultResponse:
    material = _approved_material(store, material_id)

    with child_operation_lock(str(material.child_id)):
        if store.index.get_entity(str(material.child_id), entity_type="child_profile") is None:
            raise HTTPException(status_code=404, detail="child_not_found")
        material = _approved_material(store, material_id)
        activity = _activity_for_result(store=store, material=material, request=request)

        tags = list(dict.fromkeys(["material-use", material.kind.value, *request.tags]))
        log = LearningLog(
            child_id=material.child_id,
            activity_plan_id=activity.id,
            parent_observation=request.observation,
            process=request.process,
            child_question=request.child_question,
            interest=request.interest,
            difficulty_note=request.difficulty_note,
            next_activity=request.next_activity,
            tags=tags,
            experience_axes=list(request.experience_axes),
        )
        store.save(log)

        links = EntityLinkService(store)
        links.create(
            source_id=material.id,
            target_id=activity.id,
            relation=EntityLinkRelation.SUPPORTS,
            label="이 생성 자료로 수행한 활동",
        )
        links.create(
            source_id=log.id,
            target_id=activity.id,
            relation=EntityLinkRelation.DOCUMENTS,
            label="활동 결과 기록",
        )
        links.create(
            source_id=log.id,
            target_id=material.id,
            relation=EntityLinkRelation.DERIVED_FROM,
            label="이 생성 자료를 사용한 결과",
        )

    return MaterialResultResponse(activity=activity, learning_log=log)


@router.get(
    "/materials/{material_id}/results",
    response_model=list[MaterialUseHistoryItem],
)
def list_material_results(
    material_id: UUID,
    store: Annotated[EntityStore, Depends(get_material_result_store)],
) -> list[MaterialUseHistoryItem]:
    material = _approved_material(store, material_id)
    material_ref = _material_ref(material.id)
    activities = [
        ActivityPlan.model_validate(payload)
        for payload in store.index.list_entities(
            entity_type="activity_plan",
            child_id=str(material.child_id),
        )
        if material_ref in payload.get("source_refs", [])
    ]
    logs = [
        LearningLog.model_validate(payload)
        for payload in store.index.list_entities(
            entity_type="learning_log",
            child_id=str(material.child_id),
        )
    ]
    by_activity: dict[UUID, list[LearningLog]] = {}
    for log in logs:
        if log.activity_plan_id is not None:
            by_activity.setdefault(log.activity_plan_id, []).append(log)

    activities.sort(key=lambda item: item.created_at, reverse=True)
    return [
        MaterialUseHistoryItem(
            activity=activity,
            learning_logs=sorted(
                by_activity.get(activity.id, []),
                key=lambda item: item.created_at,
                reverse=True,
            ),
        )
        for activity in activities
    ]
