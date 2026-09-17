from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from growwise.domain import (
    ActivityStatus,
    ExperienceAxis,
    MaterialKind,
    MaterialStatus,
    ResourceKind,
    Stage,
)

class ChildCreateRequest(BaseModel):
    nickname: str
    stage: Stage
    age_months: int | None = None
    interests: list[str] = Field(default_factory=list)


class ObservationRequest(BaseModel):
    child_id: UUID
    observation: str = Field(min_length=1, max_length=10_000)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list)
    activity_plan_id: UUID | None = None


class ActivityCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    source_refs: list[str] = Field(default_factory=list)
    parent_note: str | None = Field(default=None, max_length=2000)


class ActivityTransitionRequest(BaseModel):
    status: ActivityStatus
    parent_note: str | None = Field(default=None, max_length=2000)


class ResourceCreateRequest(BaseModel):
    kind: ResourceKind
    title: str = Field(min_length=1, max_length=500)
    child_id: UUID | None = None
    summary: str | None = None
    content: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    stage_tags: list[Stage] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)


class RagQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    child_id: UUID | None = None
    limit: int = Field(default=8, ge=1, le=20)


class ChildQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationTurnRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)


class MaterialGenerateRequest(BaseModel):
    kind: MaterialKind = MaterialKind.ACTIVITY_GUIDE
    topic: str = Field(min_length=1, max_length=500)
    goal: str | None = Field(default=None, max_length=1000)
    source_refs: list[str] = Field(default_factory=list)


class MaterialReviewRequest(BaseModel):
    status: MaterialStatus
    note: str | None = Field(default=None, max_length=2000)


class MaterialRevisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class MaterialEditRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content_markdown: str = Field(min_length=1, max_length=100_000)
    note: str | None = Field(default=None, max_length=2000)
