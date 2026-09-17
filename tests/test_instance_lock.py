from pathlib import Path

import pytest

from growwise.api.instance_lock import DataDirInstanceLock, DataDirInUse


def test_data_dir_lock_is_exclusive_and_reusable(tmp_path: Path) -> None:
    first = DataDirInstanceLock(tmp_path)
    second = DataDirInstanceLock(tmp_path)

    first.acquire()
    try:
        with pytest.raises(DataDirInUse, match="already using this data directory"):
            second.acquire()
    finally:
        first.release()

    with second:
        assert second.path.is_file()

    # The persistent lock file is not ownership state. Once the OS lock is released, a new Core
    # can immediately reuse the same data directory without stale-lock cleanup.
    with DataDirInstanceLock(tmp_path):
        pass


def test_data_dir_lock_release_is_idempotent(tmp_path: Path) -> None:
    lock = DataDirInstanceLock(tmp_path)
    lock.acquire()
    lock.acquire()
    lock.release()
    lock.release()

    with DataDirInstanceLock(tmp_path):
        pass
