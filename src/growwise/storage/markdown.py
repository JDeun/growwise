from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable

import frontmatter
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class StoredEntity(Protocol):
    entity_type: str
    id: object

    def model_dump(self, *, mode: str = "python") -> dict: ...


class MarkdownRepository:
    """Atomic Markdown Source-of-Truth repository.

    SQLite projections are intentionally downstream of this repository. A failed index write must
    never invalidate the source Markdown document.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, entity: StoredEntity) -> Path:
        return self.root / entity.entity_type / f"{entity.id}.md"

    def save(self, entity: StoredEntity, body: str = "") -> Path:
        target = self._path_for(entity)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = entity.model_dump(mode="json")
        post = frontmatter.Post(body, **payload)
        rendered = frontmatter.dumps(post)

        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return target

    def load(self, path: Path, model: type[T]) -> T:
        post = frontmatter.load(path)
        return model.model_validate(dict(post.metadata))
