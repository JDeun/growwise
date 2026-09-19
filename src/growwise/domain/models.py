from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from uuid6 import uuid7

ShortText = Annotated[str, Field(min_length=1, max_length=200)]
TagText = Annotated[str, Field(min_length=1, max_length=200)]
LanguageCode = Annotated[str, Field(min_length=2, max_length=35)]
SourceRef = Annotated[str, Field(min_length=1, max_length=500)]


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


class LearningRecordKind(StrEnum):
    OBSERVATION = "observation"
    PHOTO_ACTIVITY = "photo_activity"
    MATERIAL_USE = "material_use"
    READING_REFLECTION = "reading_reflection"
    DIARY = "diary"
    INSTITUTION = "institution"
    SELF_STUDY = "self_study"
    ASSIGNMENT = "assignment"
    OTHER = "other"


class AiEnhancementStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


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
    primary_language: LanguageCode = "ko-KR"
    additional_languages: list[LanguageCode] = Field(default_factory=list, max_length=20)
    interests: list[TagText] = Field(default_factory=list, max_length=100)
    preferences: dict[str, list[str]] = Field(default_factory=dict, max_length=100)
    learning_goals: list[ShortText] = Field(default_factory=list, max_length=100)
    notes: str | None = Field(default=None, max_length=10_000)
    avatar_asset_id: UUID | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            migrated = dict(data)
            if not migrated.get("name") and migrated.get("nickname"):
                migrated["name"] = migrated["nickname"]
            if not migrated.get("nickname") and migrated.get("name"):
                migrated["nickname"] = migrated["name"]
            return migrated
        return data

    @model_validator(mode="after")
    def derive_age_from_birth_date(self) -> Self:
        if self.birth_date is not None:
            self.age_months = age_in_months(self.birth_date)
        if self.grade_override is not None:
            self.grade = self.grade_override
        for key, values in self.preferences.items():
            if not key or len(key) > 120 or len(values) > 100:
                raise ValueError("preference keys must be 1..120 chars with at most 100 values")
            if any(not value or len(value) > 200 for value in values):
                raise ValueError("preference values must be 1..200 chars")
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
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    status: ActivityStatus = ActivityStatus.SUGGESTED
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=100)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list, max_length=20)
    parent_note: str | None = Field(default=None, max_length=10_000)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    skipped_at: datetime | None = None


class LearningLog(EntityBase):
    entity_type: str = "learning_log"
    child_id: UUID
    activity_plan_id: UUID | None = None
    record_kind: LearningRecordKind = LearningRecordKind.OBSERVATION
    title: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None
    subject: str | None = Field(default=None, max_length=200)
    institution: str | None = Field(default=None, max_length=500)
    learner_work: str | None = Field(default=None, max_length=20_000)
    # Legacy Markdown may contain an empty observation. API create requests remain min_length=1;
    # the domain model keeps read compatibility while still bounding pathological persisted input.
    parent_observation: str = Field(max_length=10_000)
    process: str | None = Field(default=None, max_length=10_000)
    child_question: str | None = Field(default=None, max_length=4_000)
    interest: str | None = Field(default=None, max_length=2_000)
    difficulty_note: str | None = Field(default=None, max_length=4_000)
    next_activity: str | None = Field(default=None, max_length=4_000)
    tags: list[TagText] = Field(default_factory=list, max_length=100)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list, max_length=20)
    ai_status: AiEnhancementStatus = AiEnhancementStatus.NOT_REQUESTED
    ai_job_id: UUID | None = None


class ResourceRecord(EntityBase):
    entity_type: str = "resource"
    child_id: UUID | None = None
    kind: ResourceKind
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = Field(default=None, max_length=20_000)
    content: str | None = Field(default=None, max_length=500_000)
    source_url: str | None = Field(default=None, max_length=2_048)
    source_name: str | None = Field(default=None, max_length=500)
    author: str | None = Field(default=None, max_length=500)
    published_at: datetime | None = None
    tags: list[TagText] = Field(default_factory=list, max_length=100)
    stage_tags: list[Stage] = Field(default_factory=list, max_length=10)
    provenance: dict[str, str] = Field(default_factory=dict, max_length=100)

    @model_validator(mode="after")
    def validate_provenance_bounds(self) -> Self:
        if any(not key or len(key) > 200 for key in self.provenance):
            raise ValueError("provenance keys must be 1..200 chars")
        if any(len(value) > 4_000 for value in self.provenance.values()):
            raise ValueError("provenance values must be at most 4000 chars")
        return self


class CurriculumTarget(BaseModel):
    """Machine-readable curriculum alignment without redistributing source text.

    ``mapping_id`` is a GrowWise identifier, not an official achievement-standard code.
    ``standard_codes`` is reserved for verified official codes supplied by curated data or an
    adapter. The description is GrowWise-authored and intentionally paraphrased.
    """

    mapping_id: str = Field(min_length=1, max_length=120)
    framework: str = Field(min_length=1, max_length=160)
    domain: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    source_ref: str = Field(min_length=1, max_length=160)
    revision: str | None = Field(default=None, max_length=120)
    effective_from: date | None = None
    effective_to: date | None = None
    grade: Annotated[int | None, Field(default=None, ge=1, le=12)] = None
    resolution_precision: str | None = Field(default=None, max_length=80)
    transition_note: str | None = Field(default=None, max_length=500)
    standard_codes: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(
        default_factory=list,
        max_length=50,
    )


class MaterialSourceCitation(BaseModel):
    """Immutable provenance snapshot captured when a material is generated."""

    source_ref: SourceRef
    title: str = Field(min_length=1, max_length=500)
    excerpt: str = Field(default="", max_length=4_000)
    source_name: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_048)
    author: str | None = Field(default=None, max_length=500)
    attribution: str | None = Field(default=None, max_length=2_000)
    license_note: str | None = Field(default=None, max_length=4_000)


class GeneratedMaterial(EntityBase):
    entity_type: str = "generated_material"
    child_id: UUID
    kind: MaterialKind
    title: str = Field(min_length=1, max_length=500)
    content_markdown: str = Field(min_length=1, max_length=100_000)
    parent_guide_markdown: str = Field(default="", max_length=50_000)
    status: MaterialStatus = MaterialStatus.DRAFT
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=100)
    source_citations: list[MaterialSourceCitation] = Field(
        default_factory=list,
        max_length=100,
    )
    curriculum_targets: list[CurriculumTarget] = Field(default_factory=list, max_length=100)
    generator_mode: str = Field(default="template", min_length=1, max_length=120)
    ai_status: AiEnhancementStatus = AiEnhancementStatus.NOT_REQUESTED
    ai_job_id: UUID | None = None
    review_note: str | None = Field(default=None, max_length=10_000)
    request_topic: str | None = Field(default=None, max_length=500)
    request_goal: str | None = Field(default=None, max_length=2_000)
    version: int = Field(default=1, ge=1)
    parent_material_id: UUID | None = None
    version_note: str | None = Field(default=None, max_length=10_000)

    @model_validator(mode="after")
    def validate_source_citations(self) -> Self:
        refs = set(self.source_refs)
        citation_refs = [citation.source_ref for citation in self.source_citations]
        if len(citation_refs) != len(set(citation_refs)):
            raise ValueError("source_citations must contain unique source_ref values")
        if any(ref not in refs for ref in citation_refs):
            raise ValueError("source_citations must reference source_refs")
        return self


class WorkflowRun(EntityBase):
    entity_type: str = "workflow_run"
    child_id: UUID
    workflow_type: str = Field(min_length=1, max_length=120)
    thread_id: str = Field(min_length=1, max_length=500)
    status: WorkflowStatus = WorkflowStatus.RUNNING
    attempt_count: int = Field(default=1, ge=1, le=10_000)
    input_ref: str | None = Field(default=None, max_length=500)
    output_ref: str | None = Field(default=None, max_length=500)
    last_error_code: str | None = Field(default=None, max_length=500)
