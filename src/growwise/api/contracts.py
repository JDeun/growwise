from __future__ import annotations

from typing import Annotated
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
from growwise.domain.models import SourceRef, TagText

ProvenanceKey = Annotated[str, Field(min_length=1, max_length=200)]
ProvenanceValue = Annotated[str, Field(max_length=4_000)]


class ChildCreateRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=120)
    stage: Stage
    age_months: int | None = Field(default=None, ge=0, le=240)
    interests: list[TagText] = Field(default_factory=list, max_length=100)


class ObservationRequest(BaseModel):
    child_id: UUID
    observation: str = Field(min_length=1, max_length=10_000)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list, max_length=20)
    activity_plan_id: UUID | None = None


class ActivityCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=100)
    parent_note: str | None = Field(default=None, max_length=2_000)


class ActivityTransitionRequest(BaseModel):
    status: ActivityStatus
    parent_note: str | None = Field(default=None, max_length=2_000)


class ResourceCreateRequest(BaseModel):
    kind: ResourceKind
    title: str = Field(min_length=1, max_length=500)
    child_id: UUID | None = None
    summary: str | None = Field(default=None, max_length=20_000)
    content: str | None = Field(default=None, max_length=500_000)
    source_url: str | None = Field(default=None, max_length=2_048)
    source_name: str | None = Field(default=None, max_length=500)
    author: str | None = Field(default=None, max_length=500)
    tags: list[TagText] = Field(default_factory=list, max_length=100)
    stage_tags: list[Stage] = Field(default_factory=list, max_length=10)
    provenance: dict[ProvenanceKey, ProvenanceValue] = Field(
        default_factory=dict,
        max_length=100,
    )


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
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=100)


class MaterialReviewRequest(BaseModel):
    status: MaterialStatus
    note: str | None = Field(default=None, max_length=2000)


class MaterialRevisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class MaterialEditRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content_markdown: str = Field(min_length=1, max_length=100_000)
    note: str | None = Field(default=None, max_length=2000)
