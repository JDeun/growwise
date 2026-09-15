from __future__ import annotations

import filecmp
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .sqlite import SQLiteProjection


class StorageLocationError(RuntimeError):
    """Raised when a storage location is invalid or a relocation would be unsafe."""


@dataclass(frozen=True)
class RelocationReport:
    """Small result summary returned by a successful relocation."""

    moved_count: int
    dest_root: Path
    dest_index: Path


def _markdown_records(root: Path) -> list[Path]:
    """Return every Markdown record under ``root`` (``.bak`` backups excluded)."""
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def _all_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _nearest_existing_ancestor(path: Path) -> Path:
    ancestor = path
    while not ancestor.exists():
        parent = ancestor.parent
        if parent == ancestor:  # reached filesystem root
            return ancestor
        ancestor = parent
    return ancestor


class StorageLocation:
    """Helpers to validate a data directory and safely relocate records + index.

    Markdown is the source of truth; the SQLite index is a disposable projection.
    Relocation copies the Markdown first, verifies it, rebuilds the index at the
    destination, and only then removes the source. Any failure leaves the source
    intact so records can never be lost by a partial move.
    """

    @staticmethod
    def validate(path: Path | str) -> Path:
        """Normalize ``path`` to an absolute, writable directory (or a creatable one).

        Returns the resolved absolute path. Raises :class:`StorageLocationError`
        when the target is a file or cannot be written to / created.
        """
        resolved = Path(path).expanduser().resolve()
        if resolved.exists():
            if not resolved.is_dir():
                raise StorageLocationError(f"{resolved} exists and is not a directory")
            if not os.access(resolved, os.W_OK):
                raise StorageLocationError(f"{resolved} is not a writable directory")
            return resolved

        ancestor = _nearest_existing_ancestor(resolved)
        if not ancestor.is_dir():
            raise StorageLocationError(f"cannot create {resolved}: {ancestor} is not a directory")
        if not os.access(ancestor, os.W_OK):
            raise StorageLocationError(f"cannot create {resolved}: {ancestor} is not writable")
        return resolved

    @staticmethod
    def relocate(
        *,
        source_root: Path | str,
        source_index: Path | str,
        dest_root: Path | str,
        dest_index: Path | str,
        overwrite: bool = False,
    ) -> RelocationReport:
        """Relocate Markdown records + index from source to destination, safely.

        The move is copy-then-verify-then-swap: the source is only removed after
        the copy is byte-verified and the index has been rebuilt at the
        destination. On any failure the source stays intact and freshly copied
        destination files are rolled back. Refuses a destination that already
        holds records unless ``overwrite=True``.
        """
        source_root_path = Path(source_root).expanduser().resolve()
        source_index_path = Path(source_index).expanduser().resolve()
        dest_root_path = StorageLocation.validate(dest_root)
        dest_index_path = Path(dest_index).expanduser().resolve()

        if dest_root_path == source_root_path:
            raise StorageLocationError("destination root is the same as the source root")

        source_records = _markdown_records(source_root_path)

        existing = _markdown_records(dest_root_path)
        if existing and not overwrite:
            raise StorageLocationError(
                f"destination {dest_root_path} already holds {len(existing)} record(s); "
                "pass overwrite=True to merge"
            )

        dest_root_path.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []
        try:
            for src in _all_files(source_root_path):
                rel = src.relative_to(source_root_path)
                target = dest_root_path / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                preexisted = target.exists()
                shutil.copy2(src, target)
                if not preexisted:
                    created.append(target)

            _verify_copy(source_records, source_root_path, dest_root_path)

            projection = SQLiteProjection(dest_index_path)
            projection.rebuild(dest_root_path)

            # Swap: source is only removed once the destination is proven good.
            if source_root_path.exists():
                shutil.rmtree(source_root_path)
            if source_index_path.exists():
                source_index_path.unlink()
        except Exception:
            for target in reversed(created):
                target.unlink(missing_ok=True)
            raise

        return RelocationReport(
            moved_count=len(source_records),
            dest_root=dest_root_path,
            dest_index=dest_index_path,
        )


def _verify_copy(sources: list[Path], source_root: Path, dest_root: Path) -> None:
    for src in sources:
        rel = src.relative_to(source_root)
        target = dest_root / rel
        if not target.exists():
            raise StorageLocationError(f"copy verification failed: missing {target}")
        if not filecmp.cmp(src, target, shallow=False):
            raise StorageLocationError(f"copy verification failed: content mismatch {target}")
