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
        # Hold the per-path write lock across BOTH the Markdown write and the index upsert so
        # concurrent saves of the same entity commit last-writer-wins consistently to both
        # stores. Otherwise two threads could interleave such that the disposable SQLite index
        # permanently reflects an older generation than the authoritative Markdown (reads would
        # then silently return a stale record until a rebuild).
        path = self.markdown.path_for(entity)
        with self.markdown.lock_for(path):
            self.markdown._write_locked(path, self.markdown.render(entity, body=body))
            self.index.upsert(entity, path)
        return path
