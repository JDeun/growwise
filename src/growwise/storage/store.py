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

    Projection writes are serialized process-wide. If the incremental upsert fails after the
    authoritative Markdown commit, GrowWise immediately attempts a full projection rebuild from
    Markdown before surfacing an error. This closes the common partial-commit window without ever
    rolling the source document back to match a disposable index.
    """

    _projection_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self, records_root: Path, index_path: Path) -> None:
        self.markdown = MarkdownRepository(records_root)
        self.index = SQLiteProjection(index_path)

    def save(self, entity: EntityBase, body: str = "") -> Path:
        # Hold the per-path write lock across BOTH the Markdown write and the projection sync so
        # concurrent saves of the same entity commit last-writer-wins consistently. Projection
        # operations also share a process-wide lock so an emergency rebuild cannot race another
        # incremental upsert and erase a just-committed projection row.
        path = self.markdown.path_for(entity)
        with self.markdown.lock_for(path):
            self.markdown._write_locked(path, self.markdown.render(entity, body=body))
            with self._projection_lock:
                try:
                    self.index.upsert(entity, path)
                except Exception:
                    # Markdown has already committed and remains authoritative. Rebuild the
                    # disposable index from source rather than deleting/re-writing the source.
                    self.index.rebuild(self.markdown.root)
        return path

    def delete(self, entity: EntityBase) -> bool:
        """Delete one authoritative record and its disposable projection entry.

        The same per-path lock used by ``save`` prevents a concurrent update from interleaving with
        deletion. Projection operations share the rebuild lock so a concurrent recovery cannot
        resurrect a projection row from a source file being deleted.
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
