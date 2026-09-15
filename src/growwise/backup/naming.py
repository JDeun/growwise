from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def unique_backup_token(*, now: datetime | None = None) -> str:
    """Return a human-readable token that does not depend on clock resolution for uniqueness."""
    stamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{stamp}-{uuid4().hex[:12]}"
