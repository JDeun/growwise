from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from threading import Lock
from typing import Concatenate
from uuid import UUID

_LOCK_STRIPES = 128
_material_locks: tuple[Lock, ...] = tuple(Lock() for _ in range(_LOCK_STRIPES))


def _lock_for(material_id: UUID) -> Lock:
    # Bounded striping avoids retaining one process-lifetime lock for every material ever edited.
    # A hash collision only serializes two unrelated successor operations temporarily.
    return _material_locks[hash(str(material_id)) % _LOCK_STRIPES]


def serialize_material_successor[**P, R](
    func: Callable[Concatenate[UUID, P], R],
) -> Callable[Concatenate[UUID, P], R]:
    """Serialize successor creation for one material inside the local Core sidecar.

    FastAPI executes synchronous endpoints in a thread pool, so two edit/revision requests can
    otherwise both observe that no successor exists and create sibling versions. Bounded striped
    locks preserve the linear-history invariant without unbounded lock-registry growth.
    """

    @wraps(func)
    def wrapped(material_id: UUID, *args: P.args, **kwargs: P.kwargs) -> R:
        with _lock_for(material_id):
            return func(material_id, *args, **kwargs)

    return wrapped
