"""Regression tests for adversarially-found storage data-loss defects (C1, C2, I1, I2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.storage import EntityStore, SQLiteProjection
from growwise.storage import location as location_mod
from growwise.storage.location import StorageLocation, StorageLocationError


def _seed(root: Path, index: Path) -> int:
    store = EntityStore(root, index)
    child = ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    store.save(LearningLog(child_id=child.id, parent_observation="책 표지를 오래 바라봄"))
    store.save(LearningLog(child_id=child.id, parent_observation="블록을 두드림"))
    return 3


def _md_count(root: Path) -> int:
    return len(list(root.rglob("*.md"))) if root.exists() else 0


def test_c2_rejects_destination_nested_in_source(tmp_path) -> None:
    src_root, src_index = tmp_path / "data", tmp_path / "data.sqlite3"
    n = _seed(src_root, src_index)
    with pytest.raises(StorageLocationError):
        StorageLocation.relocate(
            source_root=src_root, source_index=src_index,
            dest_root=src_root / "v2", dest_index=src_root / "v2.sqlite3",
        )
    assert _md_count(src_root) == n  # source fully intact


def test_c2_rejects_source_nested_in_destination(tmp_path) -> None:
    dest_root = tmp_path / "data"
    src_root, src_index = dest_root / "inner", tmp_path / "inner.sqlite3"
    n = _seed(src_root, src_index)
    with pytest.raises(StorageLocationError):
        StorageLocation.relocate(
            source_root=src_root, source_index=src_index,
            dest_root=dest_root, dest_index=tmp_path / "d.sqlite3",
        )
    assert _md_count(src_root) == n


def test_c1_partial_source_removal_loses_no_records(tmp_path, monkeypatch) -> None:
    src_root, src_index = tmp_path / "data", tmp_path / "data.sqlite3"
    n = _seed(src_root, src_index)
    dest_root, dest_index = tmp_path / "moved", tmp_path / "moved.sqlite3"

    def flaky_rmtree(path, *a, **k):  # delete part of the source, then crash
        for child in sorted(Path(path).rglob("*.md"))[:1]:
            child.unlink()
        raise OSError("interrupted during source removal")

    monkeypatch.setattr(location_mod.shutil, "rmtree", flaky_rmtree)
    report = StorageLocation.relocate(
        source_root=src_root, source_index=src_index,
        dest_root=dest_root, dest_index=dest_index,
    )
    assert report.moved_count == n
    assert _md_count(dest_root) == n  # every record survived at the destination


def test_i2_overwrite_restores_original_on_failure(tmp_path, monkeypatch) -> None:
    src_root, src_index = tmp_path / "data", tmp_path / "data.sqlite3"
    _seed(src_root, src_index)
    dest_root, dest_index = tmp_path / "dest", tmp_path / "dest.sqlite3"
    # Pre-existing destination record at a colliding relative path, with distinct content.
    one = sorted(src_root.rglob("*.md"))[0]
    rel = one.relative_to(src_root)
    (dest_root / rel).parent.mkdir(parents=True, exist_ok=True)
    (dest_root / rel).write_text("ORIGINAL-DEST-CONTENT", encoding="utf-8")

    def boom_rebuild(self, records_root):  # fail after files were copied/overwritten
        raise OSError("rebuild failed")

    monkeypatch.setattr(SQLiteProjection, "rebuild", boom_rebuild)
    with pytest.raises(OSError):
        StorageLocation.relocate(
            source_root=src_root, source_index=src_index,
            dest_root=dest_root, dest_index=dest_index, overwrite=True,
        )
    assert (dest_root / rel).read_text(encoding="utf-8") == "ORIGINAL-DEST-CONTENT"
    assert _md_count(src_root) == 3  # source untouched


def test_i1_operational_error_does_not_delete_index(tmp_path, monkeypatch) -> None:
    index = tmp_path / "i.sqlite3"
    SQLiteProjection(index)  # create a valid index file first
    assert index.exists()

    def locked(self) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(SQLiteProjection, "_create_schema", locked)
    with pytest.raises(sqlite3.OperationalError):
        SQLiteProjection(index)
    assert index.exists()  # transient error must NOT wipe a recoverable index
