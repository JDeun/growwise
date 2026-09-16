from __future__ import annotations

import threading
from contextlib import suppress
from pathlib import Path
from typing import ClassVar

from growwise.domain.models import EntityBase

from .markdown import MarkdownRepository
from .sqlite import SQLiteProjection


class EntityStore:
    """Write-through store: Markdown is authoritative, SQLite is disposable projection.

    Projection writes are serialized process-wide. If an incremental projection write fails after
    the authoritative Markdown commit, GrowWise rebuilds the disposable SQLite projection from the
    source documents instead of rolling source data back to match a failed cache/index write.
    """

    _projection_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self, records_root: Path, index_path: Path) -> None:
        self.markdown = MarkdownRepository(records_root)
        self.index = SQLiteProjection(index_path)

    def save(self, entity: EntityBase, body: str = "") -> Path:
        # Hold the per-path write lock across source commit and projection sync. Projection changes
        # additionally share one process-wide lock so an emergency rebuild cannot race an unrelated
        # upsert and erase a row that was committed while the rebuild was scanning Markdown.
        path = self.markdown.path_for(entity)
        with self.markdown.lock_for(path):
            self.markdown._write_locked(path, self.markdown.render(entity, body=body))
            with self._projection_lock:
                try:
                    self.index.upsert(entity, path)
                except Exception:
                    # Source has already committed and remains authoritative. A rebuild either
                    # repairs the projection or raises, leaving the durable Markdown intact for a
                    # later recovery rather than creating source/index split-brain deliberately.
                    self.index.rebuild(self.markdown.root)
        return path

    def delete(self, entity: EntityBase) -> bool:
        """Delete one authoritative record and its disposable projection entry.

        The same per-path lock used by ``save`` prevents a concurrent update from interleaving with
        deletion. Projection operations share the rebuild lock so recovery cannot resurrect a row
        from a source file while that file is being deleted.
        """
        path = self.markdown.path_for(entity)
        backup = self.markdown.backup_path(path)
        with self.markdown.lock_for(path):
            if not path.exists():
                # Markdown is authoritative. If it is already gone, remove any stale disposable
                # projection entry rather than preserving a ghost record in list/search results.
                with self._projection_lock:
                    self.index.delete_entity(str(entity.id), entity_type=entity.entity_type)
                return False
            with self._projection_lock:
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

    def purge_child(self, child_id: str) -> int:
        """Permanently remove one child's Markdown records and rebuild the disposable index."""
        with self._projection_lock:
            deleted_files = self.markdown.purge_child(child_id)
            self.index.rebuild(self.markdown.root)
        return deleted_files
