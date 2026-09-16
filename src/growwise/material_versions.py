from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from threading import Lock
from typing import Concatenate
from uuid import UUID

_LOCK_STRIPES = 128
_material_locks: tuple[Lock, ...] = tuple(Lock() for _ in range(_LOCK_STRIPES))


def _lock_for(material_id: UUID) -> Lock:
    # Bounded lock striping avoids an unbounded process-lifetime dictionary keyed by every
    # material ever edited. A hash collision only serializes two unrelated successor operations.
    return _material_locks[hash(str(material_id)) % _LOCK_STRIPES]


def serialize_material_successor[**P, R](
    func: Callable[Concatenate[UUID, P], R],
) -> Callable[Concatenate[UUID, P], R]:
    """Serialize successor creation for one material inside the Core sidecar process.

    GrowWise starts Uvicorn as a single-process local sidecar. FastAPI executes synchronous
    endpoints in a thread pool, so two edit/revision requests can otherwise both observe that
    no successor exists and create sibling versions. The bounded striped locks preserve the
    linear-history invariant without retaining one lock per material forever.
    """

    @wraps(func)
    def wrapped(material_id: UUID, *args: P.args, **kwargs: P.kwargs) -> R:
        with _lock_for(material_id):
            return func(material_id, *args, **kwargs)

    return wrapped
