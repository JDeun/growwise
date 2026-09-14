from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable

import frontmatter
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_RESERVED_METADATA_KEYS = {
    "content": "__growwise_content",
    "handler": "__growwise_handler",
}
_REVERSE_RESERVED_METADATA_KEYS = {
    encoded: original for original, encoded in _RESERVED_METADATA_KEYS.items()
}


@runtime_checkable
class StoredEntity(Protocol):
    entity_type: str
    id: object

    def model_dump(self, *, mode: str = "python") -> dict: ...


def _encode_metadata(payload: dict) -> dict:
    return {
        _RESERVED_METADATA_KEYS.get(key, key): value
        for key, value in payload.items()
    }


def _decode_metadata(payload: dict) -> dict:
    return {
        _REVERSE_RESERVED_METADATA_KEYS.get(key, key): value
        for key, value in payload.items()
    }


class MarkdownRepository:
    """Atomic Markdown Source-of-Truth repository with one-generation recovery.

    SQLite projections are intentionally downstream of this repository. A failed index write must
    never invalidate the source Markdown document. Before replacing an existing source document,
    GrowWise keeps the previous valid generation as ``.bak`` so corruption can be explicitly
    recovered without making SQLite the source of truth.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, entity: StoredEntity) -> Path:
        return self.root / entity.entity_type / f"{entity.id}.md"

    @staticmethod
    def backup_path(path: Path) -> Path:
        return path.with_suffix(path.suffix + ".bak")

    def save(self, entity: StoredEntity, body: str = "") -> Path:
        target = self._path_for(entity)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = _encode_metadata(entity.model_dump(mode="json"))

        # python-frontmatter reserves `content` and `handler` as Post constructor
        # parameters. GrowWise escapes those domain field names at the persistence
        # boundary and restores them on load/rebuild.
        post = frontmatter.Post(body)
        post.metadata.update(payload)
        rendered = frontmatter.dumps(post)

        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())

            if target.exists():
                backup = self.backup_path(target)
                shutil.copy2(target, backup)
                with backup.open("rb") as handle:
                    os.fsync(handle.fileno())

            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return target

    def load(self, path: Path, model: type[T]) -> T:
        post = frontmatter.load(path)
        payload = _decode_metadata(dict(post.metadata))
        return model.model_validate(payload)

    def recover(self, path: Path, model: type[T]) -> T:
        """Restore the previous saved generation after validating the backup first."""
        backup = self.backup_path(path)
        if not backup.exists():
            raise FileNotFoundError(f"no backup exists for {path}")

        recovered = self.load(backup, model)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.recover.", dir=path.parent)
        os.close(fd)
        try:
            shutil.copy2(backup, tmp_name)
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return recovered
