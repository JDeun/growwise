from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from growwise.backup.cli import create_backup, list_backups, restore_backup
from growwise.config import Settings

router = APIRouter(prefix="/v1/admin/backups", tags=["backup"])


class BackupCreateRequest(BaseModel):
    name: str | None = None


class BackupRestoreRequest(BaseModel):
    confirmed: bool = False


@router.get("")
def list_managed_backups() -> list[dict[str, object]]:
    return list_backups(Settings())


@router.post("")
def create_managed_backup(request: BackupCreateRequest) -> dict[str, object]:
    try:
        return create_backup(Settings(), request.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{archive_name}/restore")
def restore_managed_backup(
    archive_name: str,
    request: BackupRestoreRequest,
) -> dict[str, object]:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="restore_confirmation_required")
    try:
        return restore_backup(Settings(), archive_name, confirmed=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="backup_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
