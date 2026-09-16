from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from .models import EntityBase

Sha256Text = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
PhotoMimeType = Literal["image/jpeg", "image/png", "image/webp"]


class PhotoRecordStatus(StrEnum):
    DRAFT = "draft"
    COMMITTED = "committed"
    DISCARDED = "discarded"


class PhotoAsset(EntityBase):
    """Metadata record for a child-scoped photo stored in the local asset directory.

    The binary image is intentionally not embedded in Markdown/SQLite. ``relative_path`` points
    into GrowWise's managed asset root, while SHA-256 binds the metadata to the exact bytes.
    Exact GPS coordinates are not persisted by this model.
    """

    entity_type: str = "photo_asset"
    child_id: UUID
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: PhotoMimeType
    relative_path: str = Field(min_length=1, max_length=700)
    sha256: Sha256Text
    byte_size: int = Field(ge=1, le=100 * 1024 * 1024)
    width: int | None = Field(default=None, ge=1, le=100_000)
    height: int | None = Field(default=None, ge=1, le=100_000)
    captured_at: datetime | None = None
    metadata_summary: dict[str, str] = Field(default_factory=dict, max_length=30)
    caption: str | None = Field(default=None, max_length=4_000)
    caption_model: str | None = Field(default=None, max_length=240)


class PhotoActivityRecord(EntityBase):
    """Parent-reviewable draft synthesized from one or more activity photos."""

    entity_type: str = "photo_activity_record"
    child_id: UUID
    photo_asset_ids: list[UUID] = Field(min_length=1, max_length=12)
    user_context: str | None = Field(default=None, max_length=10_000)
    generated_observation: str = Field(min_length=1, max_length=10_000)
    generation_mode: str = Field(min_length=1, max_length=160)
    status: PhotoRecordStatus = PhotoRecordStatus.DRAFT
    learning_log_id: UUID | None = None
