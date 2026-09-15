from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from .models import EntityBase


class StudyProgressState(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    REVISIT = "revisit"
    COMFORTABLE = "comfortable"


class MistakeType(StrEnum):
    CONCEPT = "concept"
    PROCESS = "process"
    READING = "reading"
    CALCULATION = "calculation"
    ATTENTION = "attention"
    COMMUNICATION = "communication"
    OTHER = "other"


class PlanItemStatus(StrEnum):
    PLANNED = "planned"
    DONE = "done"
    SKIPPED = "skipped"


class StudyUnitProgress(EntityBase):
    entity_type: str = "study_unit_progress"
    child_id: UUID
    subject: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=240)
    state: StudyProgressState = StudyProgressState.IN_PROGRESS
    note: str | None = Field(default=None, max_length=4000)
    last_studied_at: datetime | None = None


class MistakeRecord(EntityBase):
    entity_type: str = "mistake_record"
    child_id: UUID
    subject: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=240)
    mistake_type: MistakeType = MistakeType.OTHER
    prompt: str | None = Field(default=None, max_length=4000)
    learner_response: str | None = Field(default=None, max_length=4000)
    corrected_understanding: str | None = Field(default=None, max_length=4000)
    evidence_ref: str | None = Field(default=None, max_length=500)


class StudyReflection(EntityBase):
    entity_type: str = "study_reflection"
    child_id: UUID
    subject: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=240)
    worked_well: str | None = Field(default=None, max_length=4000)
    difficult_point: str | None = Field(default=None, max_length=4000)
    next_step: str | None = Field(default=None, max_length=4000)


class SelfExplanationLog(EntityBase):
    entity_type: str = "self_explanation_log"
    child_id: UUID
    subject: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=240)
    explanation: str = Field(min_length=1, max_length=8000)
    evidence_refs: list[str] = Field(default_factory=list)
    open_question: str | None = Field(default=None, max_length=4000)


class StudyPlanItem(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=240)
    focus: str = Field(min_length=1, max_length=1000)
    status: PlanItemStatus = PlanItemStatus.PLANNED


class StudyPlan(EntityBase):
    entity_type: str = "study_plan"
    child_id: UUID
    title: str = Field(min_length=1, max_length=240)
    target_date: date | None = None
    items: list[StudyPlanItem] = Field(default_factory=list, max_length=100)
    parent_note: str | None = Field(default=None, max_length=4000)
