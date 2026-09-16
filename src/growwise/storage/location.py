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


def _is_nested(a: Path, b: Path) -> bool:
    """True when either resolved path is contained within the other."""
    return a.is_relative_to(b) or b.is_relative_to(a)


def _nearest_existing_ancestor(path: Path) -> Path:
    ancestor = path
    while not ancestor.exists():
        parent = ancestor.parent
        if parent == ancestor:  # reached filesystem root
            return ancestor
        ancestor = parent
    return ancestor


def _validate_relocation_paths(
    *,
    source_root: Path,
    source_index: Path,
    dest_root: Path,
    dest_index: Path,
) -> None:
    if dest_root == source_root or _is_nested(dest_root, source_root):
        raise StorageLocationError(
            "destination and source root must not be the same or nested within each other"
        )

    if source_index == dest_index:
        raise StorageLocationError("source and destination index paths must be different")

    # Index files are disposable projections but they must never live in a tree that the relocate
    # commit phase will delete. Without these guards a successfully rebuilt destination index could
    # be removed by source cleanup, or a source index could be mistaken for destination content.
    if dest_index.is_relative_to(source_root):
        raise StorageLocationError("destination index must not be inside the source record tree")
    if source_index.is_relative_to(dest_root):
        raise StorageLocationError("source index must not be inside the destination record tree")

    # Keep record trees pure Markdown SoT directories. SQLite files inside either record root are
    # otherwise copied as opaque files by relocation and can be deleted/reopened at surprising
    # times.
    if source_index.is_relative_to(source_root):
        raise StorageLocationError("source index must not be inside the source record tree")
    if dest_index.is_relative_to(dest_root):
        raise StorageLocationError(
            "destination index must not be inside the destination record tree"
        )


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

        _validate_relocation_paths(
            source_root=source_root_path,
            source_index=source_index_path,
            dest_root=dest_root_path,
            dest_index=dest_index_path,
        )

        # Validate the directory that will contain the destination index before copying anything.
        StorageLocation.validate(dest_index_path.parent)

        source_records = _markdown_records(source_root_path)

        existing = _markdown_records(dest_root_path)
        if existing and not overwrite:
            raise StorageLocationError(
                f"destination {dest_root_path} already holds {len(existing)} record(s); "
                "pass overwrite=True to merge"
            )

        dest_root_path.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []
        backups: list[tuple[Path, Path]] = []  # (target, backup of pre-existing content)
        try:
            for src in _all_files(source_root_path):
                rel = src.relative_to(source_root_path)
                target = dest_root_path / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    backup = target.with_name(target.name + ".relocate-bak")
                    shutil.copy2(target, backup)  # so a partial failure can restore it (I2)
                    backups.append((target, backup))
                else:
                    created.append(target)
                shutil.copy2(src, target)

            _verify_copy(source_records, source_root_path, dest_root_path)

            projection = SQLiteProjection(dest_index_path)
            projection.rebuild(dest_root_path)
        except Exception:
            # Destination-only undo — the source has NOT been touched yet, so no records lost.
            for target in reversed(created):
                target.unlink(missing_ok=True)
            for target, backup in reversed(backups):
                shutil.copy2(backup, target)  # restore the overwritten original
                backup.unlink(missing_ok=True)
            raise

        for _target, backup in backups:  # commit: discard the overwrite backups
            backup.unlink(missing_ok=True)

        # Source removal happens ONLY after the destination is proven durable, and its own
        # failure must never trigger the destination rollback above (C1): a leftover source
        # duplicates records but loses none.
        try:
            if source_root_path.exists():
                shutil.rmtree(source_root_path)
            if source_index_path.exists():
                source_index_path.unlink()
        except OSError:
            pass

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
