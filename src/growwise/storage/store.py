from __future__ import annotations

from contextlib import suppress
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

    def delete(self, entity: EntityBase) -> bool:
        """Delete one authoritative record and its disposable projection entry.

        The same per-path lock used by ``save`` prevents a concurrent update from interleaving with
        deletion. The projection is removed first; if the authoritative Markdown unlink fails, the
        projection is restored from the still-valid entity so callers never observe a successful
        index deletion for a record that remains authoritative on disk.
        """
        path = self.markdown.path_for(entity)
        backup = self.markdown.backup_path(path)
        with self.markdown.lock_for(path):
            if not path.exists():
                # Markdown is authoritative. If it is already gone, remove any stale disposable
                # projection entry rather than preserving a ghost record in list/search results.
                self.index.delete_entity(str(entity.id), entity_type=entity.entity_type)
                return False
            deleted_from_index = self.index.delete_entity(
                str(entity.id), entity_type=entity.entity_type
            )
            try:
                path.unlink()
            except Exception:
                if deleted_from_index:
                    self.index.upsert(entity, path)
                raise
            # A stale previous-generation backup is not authoritative and rebuild ignores *.md.bak.
            # Best-effort cleanup avoids turning an already-successful delete into data ambiguity.
            with suppress(OSError):
                backup.unlink(missing_ok=True)
        return True
