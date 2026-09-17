from __future__ import annotations

from pathlib import Path

import pytest

from growwise.api.data_dir_lock import exclusive_data_dir_lock


def test_data_dir_lock_rejects_concurrent_core(tmp_path: Path) -> None:
    data_dir = tmp_path / "growwise-data"

    with exclusive_data_dir_lock(data_dir):
        with pytest.raises(RuntimeError, match="이미 실행 중"):
            with exclusive_data_dir_lock(data_dir):
                pytest.fail("a second Core must never acquire the same data directory")


def test_data_dir_lock_is_released_after_owner_exits(tmp_path: Path) -> None:
    data_dir = tmp_path / "growwise-data"

    with exclusive_data_dir_lock(data_dir):
        pass

    with exclusive_data_dir_lock(data_dir):
        assert data_dir.is_dir()
