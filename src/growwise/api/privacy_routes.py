from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from growwise.config import Settings
from growwise.services.privacy import ChildPurgeService

router = APIRouter(tags=["privacy"])


@router.delete("/children/{child_id}")
def purge_child(child_id: UUID) -> dict[str, object]:
    """Permanently delete one child's live data across authoritative and derived stores."""
    try:
        return ChildPurgeService(Settings()).purge(str(child_id)).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="child_not_found") from exc
