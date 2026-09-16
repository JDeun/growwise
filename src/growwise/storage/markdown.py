from __future__ import annotations

import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import ClassVar, TypeVar

import frontmatter
from pydantic import BaseModel

from growwise.domain.models import EntityBase

from .schema import validate_schema_version

T = TypeVar("T", bound=BaseModel)


def _fsync_dir(directory: Path) -> None:
    """Best-effort fsync of a directory so a preceding rename is durable across power loss.
    No-op where directory fsync is unsupported (e.g. Windows) or not permitted."""
    if not hasattr(os, "O_DIRECTORY"):  # Windows
        return
    try:
        dir_fd = os.open(directory, os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


_RESERVED_METADATA_KEYS = {
    "content": "__growwise_content",
    "handler": "__growwise_handler",
}
_REVERSE_RESERVED_METADATA_KEYS = {
    encoded: original for original, encoded in _RESERVED_METADATA_KEYS.items()
}


def _encode_metadata(payload: dict) -> dict:
    return {_RESERVED_METADATA_KEYS.get(key, key): value for key, value in payload.items()}


def _decode_metadata(payload: dict) -> dict:
    return {
        _REVERSE_RESERVED_METADATA_KEYS.get(key, key): value for key, value in payload.items()
    }


class MarkdownRepository:
    """Atomic Markdown Source-of-Truth repository with one-generation recovery.

    SQLite projections are intentionally downstream of this repository. A failed index write must
    never invalidate the source Markdown document. Before replacing an existing source document,
    GrowWise keeps the previous valid generation as ``.bak`` so corruption can be explicitly
    recovered without making SQLite the source of truth.

    Saves for the same entity path are serialized across repository instances in this process. A
    bounded striped lock table is used instead of a per-path dictionary so a long-lived desktop
    process cannot accumulate one lock object for every record ever observed. Hash collisions only
    serialize unrelated records temporarily; they do not affect correctness.
    """

    _LOCK_STRIPES: ClassVar[int] = 256
    _path_locks: ClassVar[tuple[threading.Lock, ...]] = tuple(
        threading.Lock() for _ in range(_LOCK_STRIPES)
    )

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, entity: EntityBase) -> Path:
        return self.root / entity.entity_type / f"{entity.id}.md"

    def path_for(self, entity: EntityBase) -> Path:
        """Public: the Markdown path an entity will be written to."""
        return self._path_for(entity)

    def path_for_id(self, entity_type: str, entity_id: str) -> Path:
        """Return the canonical source path for a previously reserved entity ID."""
        return self.root / entity_type / f"{entity_id}.md"

    @classmethod
    def _lock_for(cls, path: Path) -> threading.Lock:
        key = str(path.expanduser().resolve())
        return cls._path_locks[hash(key) % cls._LOCK_STRIPES]

    @classmethod
    def lock_for(cls, path: Path) -> threading.Lock:
        """Public: the striped write lock for a Markdown source path."""
        return cls._lock_for(path)

    @staticmethod
    def backup_path(path: Path) -> Path:
        return path.with_suffix(path.suffix + ".bak")

    def render(self, entity: EntityBase, body: str = "") -> str:
        """Serialize an entity to its Markdown (frontmatter + body) form."""
        raw_payload = entity.model_dump(mode="json")
        validate_schema_version(raw_payload)
        payload = _encode_metadata(raw_payload)
        post = frontmatter.Post(body)
        post.metadata.update(payload)
        return frontmatter.dumps(post)

    def save(self, entity: EntityBase, body: str = "") -> Path:
        target = self._path_for(entity)
        rendered = self.render(entity, body=body)
        with self._lock_for(target):
            self._write_locked(target, rendered)
        return target

    def _write_locked(self, target: Path, rendered: str) -> None:
        """Atomically write ``rendered`` to ``target``. Caller must hold ``lock_for(target)``.

        Durability: the temp file is fsynced before rename, the previous generation is backed
        up atomically (temp+rename), and the parent directory is fsynced so the renames survive
        power loss (best-effort; directory fsync is a no-op where unsupported, e.g. Windows)."""
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())

            if target.exists():
                self._atomic_backup(target)

            os.replace(tmp_name, target)
            _fsync_dir(target.parent)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def _atomic_backup(self, target: Path) -> None:
        """Write the current generation to ``.bak`` atomically (temp+rename), not a bare copy,
        so a crash cannot leave a torn backup adjacent to the new document."""
        backup = self.backup_path(target)
        data = target.read_bytes()
        bfd, btmp = tempfile.mkstemp(prefix=f".{backup.name}.", dir=target.parent)
        try:
            with os.fdopen(bfd, "wb") as bh:
                bh.write(data)
                bh.flush()
                os.fsync(bh.fileno())
            os.replace(btmp, backup)
            _fsync_dir(target.parent)
        finally:
            if os.path.exists(btmp):
                os.unlink(btmp)

    def load(self, path: Path, model: type[T]) -> T:
        post = frontmatter.load(path)
        payload = _decode_metadata(dict(post.metadata))
        validate_schema_version(payload)
        return model.model_validate(payload)

    def recover(self, path: Path, model: type[T]) -> T:
        """Restore the previous saved generation after validating the backup first.

        Recovery uses the same fsync-before-rename durability rule as a normal save so a power loss
        cannot acknowledge recovery while leaving only an unflushed replacement on disk.
        """
        backup = self.backup_path(path)
        if not backup.exists():
            raise FileNotFoundError(f"no backup exists for {path}")

        with self._lock_for(path):
            recovered = self.load(backup, model)
            fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.recover.", dir=path.parent)
            os.close(fd)
            try:
                shutil.copy2(backup, tmp_name)
                with open(tmp_name, "rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(tmp_name, path)
                _fsync_dir(path.parent)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
        return recovered
