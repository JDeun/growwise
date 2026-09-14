from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field
from uuid6 import uuid7


def utc_now() -> datetime:
    return datetime.now(UTC)


class Stage(StrEnum):
    INFANT_0_2 = "infant_0_2"
    PRESCHOOL_3_5 = "preschool_3_5"
    ELEMENTARY = "elementary"
    MIDDLE = "middle"
    HIGH = "high"


class MaterialStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_PENDING = "review_pending"
    REVISION_REQUESTED = "revision_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EntityBase(BaseModel):
    schema_version: int = 1
    id: UUID = Field(default_factory=uuid7)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ChildProfile(EntityBase):
    entity_type: str = "child_profile"
    nickname: str
    stage: Stage
    age_months: Annotated[int | None, Field(default=None, ge=0, le=240)]
    interests: list[str] = Field(default_factory=list)
    notes: str | None = None


class ActivityPlan(EntityBase):
    entity_type: str = "activity_plan"
    child_id: UUID
    title: str
    status: str = "suggested"
    source_refs: list[str] = Field(default_factory=list)


class LearningLog(EntityBase):
    entity_type: str = "learning_log"
    child_id: UUID
    activity_plan_id: UUID | None = None
    parent_observation: str
    process: str | None = None
    child_question: str | None = None
    interest: str | None = None
    difficulty_note: str | None = None
    next_activity: str | None = None
    tags: list[str] = Field(default_factory=list)


class WorkflowRun(EntityBase):
    entity_type: str = "workflow_run"
    child_id: UUID
    workflow_type: str
    thread_id: str
    status: WorkflowStatus = WorkflowStatus.RUNNING
    attempt_count: int = 1
    input_ref: str | None = None
    output_ref: str | None = None
    last_error_code: str | None = None
