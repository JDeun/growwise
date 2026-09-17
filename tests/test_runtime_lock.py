from __future__ import annotations

from pathlib import Path

import pytest

from growwise.runtime_lock import DataDirectoryLock, DataDirectoryLockError


def test_data_directory_lock_rejects_second_owner(tmp_path: Path) -> None:
    first = DataDirectoryLock(tmp_path).acquire()
    try:
        with pytest.raises(DataDirectoryLockError, match="already using"):
            DataDirectoryLock(tmp_path).acquire()
    finally:
        first.release()


def test_data_directory_lock_can_be_reacquired_after_release(tmp_path: Path) -> None:
    with DataDirectoryLock(tmp_path):
        assert (tmp_path / ".core.lock").exists()

    with DataDirectoryLock(tmp_path):
        pass


def test_data_directory_lock_release_is_idempotent(tmp_path: Path) -> None:
    lock = DataDirectoryLock(tmp_path).acquire()
    lock.release()
    lock.release()
