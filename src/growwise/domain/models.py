from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from uuid6 import uuid7


def utc_now() -> datetime:
    return datetime.now(UTC)


def age_in_months(birth_date: date, *, on_date: date | None = None) -> int:
    """Return completed chronological months without rounding partial months up."""
    # Use the local calendar date (the user's "today"), not UTC — otherwise a birth date
    # entered as "today" is wrongly rejected as future during the KST 00:00–09:00 window.
    reference = on_date or date.today()
    if birth_date > reference:
        raise ValueError("birth_date cannot be in the future")
    months = (reference.year - birth_date.year) * 12 + reference.month - birth_date.month
    if reference.day < birth_date.day:
        months -= 1
    return max(0, months)


class Stage(StrEnum):
    INFANT_0_2 = "infant_0_2"
    PRESCHOOL_3_5 = "preschool_3_5"
    ELEMENTARY = "elementary"
    MIDDLE = "middle"
    HIGH = "high"


class ChildSex(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNSPECIFIED = "unspecified"


class EducationSystem(StrEnum):
    KR = "KR"


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
    name: str = Field(min_length=1, max_length=120)
    nickname: str | None = Field(default=None, max_length=120)
    stage: Stage
    birth_date: date | None = None
    sex: ChildSex = ChildSex.UNSPECIFIED
    age_months: Annotated[int | None, Field(default=None, ge=0, le=240)]
    grade: Annotated[int | None, Field(default=None, ge=1, le=12)] = None
    school_entry_year: Annotated[int | None, Field(default=None, ge=1900, le=2200)] = None
    education_system: EducationSystem = EducationSystem.KR
    grade_override: Annotated[int | None, Field(default=None, ge=1, le=12)] = None
    grade_override_reason: str | None = Field(default=None, max_length=500)
    primary_language: str = Field(default="ko-KR", min_length=2, max_length=35)
    additional_languages: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    preferences: dict[str, list[str]] = Field(default_factory=dict)
    learning_goals: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=10_000)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            migrated = dict(data)
            if not migrated.get("name") and migrated.get("nickname"):
                migrated["name"] = migrated["nickname"]
            return migrated
        return data

    @model_validator(mode="after")
    def derive_age_from_birth_date(self) -> Self:
        if self.birth_date is not None:
            self.age_months = age_in_months(self.birth_date)
        if self.grade_override is not None:
            self.grade = self.grade_override
        return self

    def age_months_on(self, on_date: date) -> int | None:
        if self.birth_date is not None:
            return age_in_months(self.birth_date, on_date=on_date)
        return self.age_months

    def grade_on(self, on_date: date) -> int | None:
        if self.grade_override is not None:
            return self.grade_override
        if self.birth_date is None or self.education_system != EducationSystem.KR:
            return self.grade
        school_year = on_date.year if on_date.month >= 3 else on_date.year - 1
        grade = school_year - (self.birth_date.year + 6)
        return grade if 1 <= grade <= 12 else None

    def stage_on(self, on_date: date) -> Stage:
        grade = self.grade_on(on_date)
        if grade is None:
            months = self.age_months_on(on_date)
            if months is not None and months <= 35:
                return Stage.INFANT_0_2
            if months is not None and months <= 83:
                return Stage.PRESCHOOL_3_5
            return self.stage
        if grade <= 6:
            return Stage.ELEMENTARY
        if grade <= 9:
            return Stage.MIDDLE
        return Stage.HIGH


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
