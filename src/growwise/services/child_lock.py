from __future__ import annotations

import threading

_CHILD_LOCKS: dict[str, threading.RLock] = {}
_CHILD_LOCKS_GUARD = threading.Lock()


def child_operation_lock(child_id: str) -> threading.RLock:
    """Return the in-process serialization lock for one child's destructive/write operations.

    Long model inference must stay outside this lock. Callers should acquire it only around
    authoritative reads/writes so privacy deletion cannot race with a late background save and
    resurrect child-scoped data.
    """
    with _CHILD_LOCKS_GUARD:
        return _CHILD_LOCKS.setdefault(child_id, threading.RLock())
