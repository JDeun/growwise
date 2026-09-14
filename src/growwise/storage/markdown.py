from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TypeVar

import frontmatter
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class MarkdownRepository:
    """Atomic Markdown Source-of-Truth repository.

    SQLite projections are intentionally downstream of this repository. A failed index write must
    never invalidate the source Markdown document.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, entity: BaseModel) -> Path:
        entity_type = str(getattr(entity, "entity_type"))
        entity_id = str(getattr(entity, "id"))
        return self.root / entity_type / f"{entity_id}.md"

    def save(self, entity: BaseModel, body: str = "") -> Path:
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
