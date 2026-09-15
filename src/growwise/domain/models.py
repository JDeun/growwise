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


class ExperienceAxis(StrEnum):
    PHYSICAL = "physical"
    EMOTIONAL_CHARACTER = "emotional_character"
    EXPRESSION_ART = "expression_art"
    THINKING_INQUIRY = "thinking_inquiry"
    SOCIAL = "social"
    READING = "reading"
    SPEAKING = "speaking"
    WRITING = "writing"
    MATH = "math"
    EXPLORATION = "exploration"


class ActivityStatus(StrEnum):
    SUGGESTED = "suggested"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    ARCHIVED = "archived"


class MaterialKind(StrEnum):
    ACTIVITY_GUIDE = "activity_guide"
    READING_ACTIVITY = "reading_activity"
    ENGLISH_CARD = "english_card"
    MATH_ACTIVITY = "math_activity"
    SCIENCE_INQUIRY = "science_inquiry"
    WRITING_PROMPT = "writing_prompt"
    FIELD_TRIP = "field_trip"


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


class ResourceKind(StrEnum):
    BOOK = "book"
    CURRICULUM = "curriculum"
    WEB = "web"
    NOTE = "note"
    FILE = "file"


class EntityBase(BaseModel):
    entity_type: str
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
    description: str | None = None
    status: ActivityStatus = ActivityStatus.SUGGESTED
    source_refs: list[str] = Field(default_factory=list)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list)
    parent_note: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    skipped_at: datetime | None = None


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
    experience_axes: list[ExperienceAxis] = Field(default_factory=list)


class ResourceRecord(EntityBase):
    entity_type: str = "resource"
    child_id: UUID | None = None
    kind: ResourceKind
    title: str
    summary: str | None = None
    content: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    stage_tags: list[Stage] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)


class GeneratedMaterial(EntityBase):
    entity_type: str = "generated_material"
    child_id: UUID
    kind: MaterialKind
    title: str
    content_markdown: str
    status: MaterialStatus = MaterialStatus.DRAFT
    source_refs: list[str] = Field(default_factory=list)
    generator_mode: str = "template"
    review_note: str | None = None
    request_topic: str | None = None
    request_goal: str | None = None
    version: int = Field(default=1, ge=1)
    parent_material_id: UUID | None = None
    version_note: str | None = None


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
