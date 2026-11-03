"""The experience happened at occurred_at; created_at is the legacy fallback."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def record_time(payload: dict[str, Any]) -> datetime | None:
    for field in ("occurred_at", "created_at"):
        value = payload.get(field)
        try:
            parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            continue
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return None
