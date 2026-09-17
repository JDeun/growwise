from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def exclusive_data_dir_lock(data_dir: Path) -> Iterator[None]:
    """Hold a process-scoped exclusive lock for one GrowWise data directory.

    The desktop normally starts one private Core process. If the desktop is launched twice (or a
    Core is started manually against the same data directory), process-local Markdown locks are not
    sufficient to protect source files. SQLite's OS-backed locking gives us a small cross-platform
    guard whose lock is automatically released if the owning process exits or crashes.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".growwise-core-instance.sqlite3"
    connection = sqlite3.connect(lock_path, timeout=0.0, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 0")
        try:
            connection.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                raise RuntimeError(
                    "이 GrowWise 데이터 폴더를 사용하는 Core가 이미 실행 중입니다. "
                    "기존 GrowWise 창을 사용하거나 기존 Core를 종료한 뒤 다시 시도하세요."
                ) from exc
            raise
        yield
    finally:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass
        connection.close()
