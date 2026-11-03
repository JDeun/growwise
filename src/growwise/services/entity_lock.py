"""Bounded in-process locks for source ownership and visibility changes."""

import threading
from uuid import UUID

_ENTITY_LOCKS = tuple(threading.RLock() for _ in range(64))


def entity_operation_lock(entity_id: UUID) -> threading.RLock:
    """Serialize scope checks with edits and sharing grants for the same source."""
    return _ENTITY_LOCKS[entity_id.int % len(_ENTITY_LOCKS)]
