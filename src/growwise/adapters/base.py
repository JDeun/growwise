from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExternalAdapterError(RuntimeError):
    """Base exception for optional external-enrichment failures."""


class ExternalUnavailable(ExternalAdapterError):
    """Raised when neither a live response nor an allowed cached response exists."""


class AdapterResult(BaseModel):
    source: str
    records: list[dict[str, Any]] = Field(default_factory=list)
    attribution: str
    license_note: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cache_status: Literal["live", "fresh", "stale"] = "live"

    @property
    def from_cache(self) -> bool:
        return self.cache_status != "live"
