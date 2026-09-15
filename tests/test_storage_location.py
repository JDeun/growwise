from __future__ import annotations

import os

import pytest

from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.storage import EntityStore, SQLiteProjection
from growwise.storage.location import (
    RelocationReport,
    StorageLocation,
    StorageLocationError,
)


def _seed(root, index) -> tuple[ChildProfile, int]:
    store = EntityStore(root, index)
    child = ChildProfile(nickname="sample-child", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    store.save(LearningLog(child_id=child.id, parent_observation="책 표지를 오래 바라봄"))
    store.save(LearningLog(child_id=child.id, parent_observation="블록을 두드림"))
    return child, 3


def test_validate_accepts_existing_directory(tmp_path) -> None:
    resolved = StorageLocation.validate(tmp_path)
    assert resolved == tmp_path.resolve()
    assert resolved.is_absolute()


def test_validate_accepts_creatable_directory(tmp_path) -> None:
    target = tmp_path / "does" / "not" / "exist"
    resolved = StorageLocation.validate(target)
    assert resolved == target.resolve()


def test_validate_rejects_a_file(tmp_path) -> None:
    file_path = tmp_path / "index.sqlite3"
    file_path.write_text("not a dir", encoding="utf-8")
    with pytest.raises(StorageLocationError):
        StorageLocation.validate(file_path)


def test_validate_rejects_unwritable_directory(tmp_path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)
    if os.access(locked, os.W_OK):  # running as root or restrictive perms unsupported
        os.chmod(locked, 0o700)
        pytest.skip("cannot make directory unwritable in this environment")
    try:
        with pytest.raises(StorageLocationError):
            StorageLocation.validate(locked)
    finally:
        os.chmod(locked, 0o700)


def test_relocate_moves_records_and_rebuilds_index(tmp_path) -> None:
    src_root = tmp_path / "src" / "records"
    src_index = tmp_path / "src" / "index.sqlite3"
    child, count = _seed(src_root, src_index)

    dest_root = tmp_path / "dest" / "records"
    dest_index = tmp_path / "dest" / "index.sqlite3"

    report = StorageLocation.relocate(
        source_root=src_root,
        source_index=src_index,
        dest_root=dest_root,
        dest_index=dest_index,
    )

    assert isinstance(report, RelocationReport)
    assert report.moved_count == count
    assert not src_root.exists()
    assert not src_index.exists()

    projection = SQLiteProjection(dest_index)
    logs = projection.list_entities(entity_type="learning_log", child_id=str(child.id))
    assert len(logs) == 2
    profiles = projection.list_entities(entity_type="child_profile")
    assert len(profiles) == 1

    # The rebuilt index must match a fresh rebuild from the moved Markdown SoT.
    fresh = SQLiteProjection(tmp_path / "verify.sqlite3")
    assert fresh.rebuild(dest_root) == count


def test_relocate_refuses_to_clobber_non_empty_destination(tmp_path) -> None:
    src_root = tmp_path / "src" / "records"
    src_index = tmp_path / "src" / "index.sqlite3"
    _seed(src_root, src_index)

    dest_root = tmp_path / "dest" / "records"
    dest_index = tmp_path / "dest" / "index.sqlite3"
    _seed(dest_root, dest_index)  # destination already holds records

    with pytest.raises(StorageLocationError):
        StorageLocation.relocate(
            source_root=src_root,
            source_index=src_index,
            dest_root=dest_root,
            dest_index=dest_index,
        )

    # Both sides remain intact when the safe default refuses.
    assert src_root.exists()
    assert len(list(src_root.rglob("*.md"))) == 3
    assert len(list(dest_root.rglob("*.md"))) == 3


def test_relocate_failure_leaves_source_intact(tmp_path, monkeypatch) -> None:
    src_root = tmp_path / "src" / "records"
    src_index = tmp_path / "src" / "index.sqlite3"
    _seed(src_root, src_index)

    dest_root = tmp_path / "dest" / "records"
    dest_index = tmp_path / "dest" / "index.sqlite3"

    def boom(self, records_root):  # noqa: ANN001, ANN202 - test stub
        raise RuntimeError("simulated mid-relocate failure")

    monkeypatch.setattr(SQLiteProjection, "rebuild", boom)

    with pytest.raises(RuntimeError, match="simulated mid-relocate failure"):
        StorageLocation.relocate(
            source_root=src_root,
            source_index=src_index,
            dest_root=dest_root,
            dest_index=dest_index,
        )

    # Source Markdown + index survive an abort; copied dest records are rolled back.
    assert src_root.exists()
    assert src_index.exists()
    assert len(list(src_root.rglob("*.md"))) == 3
    assert list(dest_root.rglob("*.md")) == []
