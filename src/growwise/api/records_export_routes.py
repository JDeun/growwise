from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import FileResponse

from growwise.api.dependencies import get_settings, get_store
from growwise.backup.records_export import (
    RecordsExportService,
    RecordsExportTooLarge,
    RecordsExportUnavailable,
)
from growwise.backup.service import InvalidBackup
from growwise.config import Settings
from growwise.storage import EntityStore

router = APIRouter(prefix="/v1", tags=["selected-record-export"])


class _ExportResponse(FileResponse):
    def __init__(self, path: Path, temporary: tempfile.TemporaryDirectory, filename: str) -> None:
        super().__init__(path, media_type="application/zip", filename=filename)
        self.temporary = temporary

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.temporary.cleanup()  # Also remove sensitive temporary bytes after disconnects.


@router.get("/children/{child_id}/records/export")
def export_child_records(
    child_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[EntityStore, Depends(get_store)],
    start_date: date | None = None,
    end_date: date | None = None,
) -> FileResponse:
    temporary = tempfile.TemporaryDirectory(prefix="growwise-record-export-")
    filename = f"growwise-records-{date.today().isoformat()}.zip"
    path = Path(temporary.name) / filename
    try:
        RecordsExportService().create(store=store, assets_root=settings.assets_dir,
                                      destination=path, child_id=child_id,
                                      start_date=start_date, end_date=end_date)
        return _ExportResponse(path, temporary, filename)
    except Exception as exc:
        temporary.cleanup()
        if isinstance(exc, KeyError):
            raise HTTPException(status_code=404, detail="child_not_found") from exc
        if isinstance(exc, RecordsExportTooLarge):
            raise HTTPException(status_code=413, detail="records_export_too_large") from exc
        if isinstance(exc, ValueError) and str(exc) == "invalid_export_period":
            raise HTTPException(status_code=400, detail="invalid_export_period") from exc
        if isinstance(exc, (RecordsExportUnavailable, InvalidBackup, OSError)):
            raise HTTPException(status_code=409, detail="records_export_unavailable") from exc
        raise
