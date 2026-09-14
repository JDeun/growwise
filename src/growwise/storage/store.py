from __future__ import annotations

from pathlib import Path

from growwise.domain.models import EntityBase

from .markdown import MarkdownRepository
from .sqlite import SQLiteProjection


class EntityStore:
    """Write-through store: Markdown is authoritative, SQLite is disposable projection."""

    def __init__(self, records_root: Path, index_path: Path) -> None:
        self.markdown = MarkdownRepository(records_root)
        self.index = SQLiteProjection(index_path)

    def save(self, entity: EntityBase, body: str = "") -> Path:
        path = self.markdown.save(entity, body=body)
        self.index.upsert(entity, path)
        return path
