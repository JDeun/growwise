from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from growwise.api.background_ai import queue_learning_log_enrichment
from growwise.config import Settings
from growwise.domain import ExperienceAxis, LearningLog, LearningRecordKind
from growwise.domain.models import TagText
from growwise.services.entity_links import EntityLinkError, EntityLinkService
from growwise.storage import EntityStore

router = APIRouter(tags=["learning-records"])

_INDEPENDENT_KINDS = {
    LearningRecordKind.READING_REFLECTION,
    LearningRecordKind.DIARY,
    LearningRecordKind.INSTITUTION,
    LearningRecordKind.SELF_STUDY,
    LearningRecordKind.ASSIGNMENT,
    LearningRecordKind.OTHER,
}


class LearningRecordRequest(BaseModel):
    kind: LearningRecordKind
    title: str = Field(min_length=1, max_length=500)
    occurred_at: datetime | None = None
    subject: str | None = Field(default=None, max_length=200)
    institution: str | None = Field(default=None, max_length=500)
    summary: str = Field(min_length=1, max_length=10_000)
    learner_work: str | None = Field(default=None, max_length=20_000)
    process: str | None = Field(default=None, max_length=10_000)
    interest: str | None = Field(default=None, max_length=2_000)
    difficulty_note: str | None = Field(default=None, max_length=4_000)
    next_activity: str | None = Field(default=None, max_length=4_000)
    tags: list[TagText] = Field(default_factory=list, max_length=100)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list, max_length=20)
    shared_child_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def independent_kind_only(self) -> Self:
        if self.kind not in _INDEPENDENT_KINDS:
            raise ValueError("record kind is reserved for another GrowWise capture flow")
        return self


@lru_cache
def get_learning_record_settings() -> Settings:
    return Settings()


def get_learning_record_store(
    settings: Annotated[Settings, Depends(get_learning_record_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


def _validate_shared_children(
    *, child_id: UUID, shared_child_ids: list[UUID], store: EntityStore
) -> list[UUID]:
    result: list[UUID] = []
    for target_id in dict.fromkeys(shared_child_ids):
        if target_id == child_id:
            continue
        if store.index.get_entity(str(target_id), entity_type="child_profile") is None:
            raise HTTPException(status_code=404, detail="shared_child_not_found")
        result.append(target_id)
    return result


@router.post("/children/{child_id}/learning-records", response_model=LearningLog)
def create_learning_record(
    child_id: UUID,
    request: LearningRecordRequest,
    store: Annotated[EntityStore, Depends(get_learning_record_store)],
) -> LearningLog:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    shared_child_ids = _validate_shared_children(
        child_id=child_id,
        shared_child_ids=request.shared_child_ids,
        store=store,
    )

    log = LearningLog(
        child_id=child_id,
        record_kind=request.kind,
        title=request.title,
        occurred_at=request.occurred_at,
        subject=request.subject,
        institution=request.institution,
        learner_work=request.learner_work,
        parent_observation=request.summary,
        process=request.process,
        interest=request.interest,
        difficulty_note=request.difficulty_note,
        next_activity=request.next_activity,
        tags=list(dict.fromkeys(request.tags)),
        experience_axes=list(dict.fromkeys(request.experience_axes)),
    )
    store.save(log)
    if shared_child_ids:
        try:
            EntityLinkService(store).share_with_children(
                source_id=log.id,
                child_ids=shared_child_ids,
            )
        except EntityLinkError as exc:
            store.delete(log)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    queue_learning_log_enrichment(log=log, store=store)
    return log


@router.get("/children/{child_id}/learning-records", response_model=list[LearningLog])
def list_learning_records(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_learning_record_store)],
) -> list[LearningLog]:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    records = [
        LearningLog.model_validate(payload)
        for payload in store.index.list_entities(
            entity_type="learning_log",
            child_id=str(child_id),
        )
    ]
    independent = [record for record in records if record.record_kind in _INDEPENDENT_KINDS]
    independent.sort(key=lambda record: record.occurred_at or record.created_at, reverse=True)
    return independent
