from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from threading import Lock
from typing import Concatenate
from uuid import UUID

_registry_lock = Lock()
_material_locks: dict[str, Lock] = {}


def _lock_for(material_id: UUID) -> Lock:
    key = str(material_id)
    with _registry_lock:
        lock = _material_locks.get(key)
        if lock is None:
            lock = Lock()
            _material_locks[key] = lock
        return lock


def serialize_material_successor[**P, R](
    func: Callable[Concatenate[UUID, P], R],
) -> Callable[Concatenate[UUID, P], R]:
    """Serialize successor creation for one material inside the Core sidecar process.

    GrowWise starts Uvicorn as a single-process local sidecar. FastAPI executes synchronous
    endpoints in a thread pool, so two edit/revision requests can otherwise both observe that
    no successor exists and create sibling versions. The per-material lock preserves unrelated
    material concurrency while making the supported sidecar topology linearizable here.
    """

    @wraps(func)
    def wrapped(material_id: UUID, *args: P.args, **kwargs: P.kwargs) -> R:
        with _lock_for(material_id):
            return func(material_id, *args, **kwargs)

    return wrapped
