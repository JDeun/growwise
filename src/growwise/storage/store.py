from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import ClassVar

from growwise.domain.models import EntityBase
from growwise.maintenance import DATA_MAINTENANCE

from .markdown import MarkdownRepository
from .sqlite import SQLiteProjection


def _fsync_directory(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(path, os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


class EntityStore:
    """Write-through store: Markdown is authoritative, SQLite is disposable projection.

    Projection writes are serialized process-wide. If an incremental projection write fails after
    the authoritative Markdown commit, GrowWise rebuilds the disposable SQLite projection from the
    source documents instead of rolling source data back to match a failed cache/index write.
    """

    _projection_lock: ClassVar[threading.RLock] = threading.RLock()
    _dirty_lock: ClassVar[threading.RLock] = threading.RLock()
    _dirty_counts: ClassVar[dict[str, int]] = {}
    _recovery_required: ClassVar[set[str]] = set()

    def __init__(self, records_root: Path, index_path: Path) -> None:
        self.markdown = MarkdownRepository(records_root)
        self.index = SQLiteProjection(index_path)
        self._projection_dirty_path = index_path.with_name(f"{index_path.name}.dirty")
        # A long-running worker may retain this store across a restore. Such a worker must never
        # write its pre-restore view into the newly restored source set.
        self._data_generation = DATA_MAINTENANCE.generation
        self._recover_projection_if_dirty()

    def _dirty_key(self) -> str:
        return str(self._projection_dirty_path.expanduser().resolve())

    def _mark_projection_dirty(self) -> None:
        key = self._dirty_key()
        with self._dirty_lock:
            count = self._dirty_counts.get(key, 0)
            if count == 0:
                self._projection_dirty_path.parent.mkdir(parents=True, exist_ok=True)
                with self._projection_dirty_path.open("wb") as handle:
                    handle.write(b"dirty\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                _fsync_directory(self._projection_dirty_path.parent)
            self._dirty_counts[key] = count + 1

    def _clear_projection_dirty(self) -> None:
        key = self._dirty_key()
        with self._dirty_lock:
            count = self._dirty_counts.get(key, 0)
            if count > 1:
                self._dirty_counts[key] = count - 1
                return
            self._dirty_counts.pop(key, None)
            if key in self._recovery_required:
                return
            try:
                self._projection_dirty_path.unlink()
            except FileNotFoundError:
                return
            _fsync_directory(self._projection_dirty_path.parent)

    def _abandon_projection_dirty(self) -> None:
        """Release this process-local mutation lease but preserve restart recovery state."""

        key = self._dirty_key()
        with self._dirty_lock:
            self._recovery_required.add(key)
            count = self._dirty_counts.get(key, 0)
            if count > 1:
                self._dirty_counts[key] = count - 1
            else:
                self._dirty_counts.pop(key, None)

    def _recover_projection_if_dirty(self) -> None:
        if not self._projection_dirty_path.exists():
            return
        key = self._dirty_key()
        with self._dirty_lock:
            if self._dirty_counts.get(key, 0) > 0:
                return
            with self._projection_lock:
                self.index.rebuild(self.markdown.root)
                self._recovery_required.discard(key)
                try:
                    self._projection_dirty_path.unlink()
                except FileNotFoundError:
                    pass
                else:
                    _fsync_directory(self._projection_dirty_path.parent)

    @contextmanager
    def mutation_window(self) -> Iterator[None]:
        """Hold one maintenance mutation lease across a multi-step domain operation."""
        self._recover_projection_if_dirty()
        with DATA_MAINTENANCE.mutation(expected_generation=self._data_generation):
            yield

    def save(self, entity: EntityBase, body: str = "") -> Path:
        entity = type(entity).model_validate(entity.model_dump(mode="python"))
        with self.mutation_window():
            self._mark_projection_dirty()
            path = self.markdown.path_for(entity)
            try:
                with self.markdown.lock_for(path):
                    self.markdown._write_locked(path, self.markdown.render(entity, body=body))
                    with self._projection_lock:
                        try:
                            self.index.upsert(entity, path)
                        except Exception:
                            self.index.rebuild(self.markdown.root)
            except Exception:
                self._abandon_projection_dirty()
                raise
            else:
                self._clear_projection_dirty()
            return path

    def delete(self, entity: EntityBase) -> bool:
        """Delete one authoritative record and its disposable projection entry."""
        with self.mutation_window():
            self._mark_projection_dirty()
            path = self.markdown.path_for(entity)
            backup = self.markdown.backup_path(path)
            try:
                with self.markdown.lock_for(path):
                    if not path.exists():
                        with self._projection_lock:
                            self.index.delete_entity(str(entity.id), entity_type=entity.entity_type)
                        deleted = False
                    else:
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
                        with suppress(OSError):
                            backup.unlink(missing_ok=True)
                        deleted = True
            except Exception:
                self._abandon_projection_dirty()
                raise
            else:
                self._clear_projection_dirty()
                return deleted

    def purge_child(self, child_id: str) -> int:
        """Permanently remove one child's Markdown records and rebuild the disposable index."""
        with self.mutation_window():
            self._mark_projection_dirty()
            try:
                with self._projection_lock:
                    deleted_files = self.markdown.purge_child(child_id)
                    self.index.rebuild(self.markdown.root)
            except Exception:
                self._abandon_projection_dirty()
                raise
            else:
                self._clear_projection_dirty()
                return deleted_files
