from __future__ import annotations

from pathlib import Path

from growwise.backup import BackupService
from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore


def test_successful_restore_does_not_leave_pre_restore_record_copy(tmp_path: Path) -> None:
    service = BackupService()

    source_root = tmp_path / "source-records"
    source_store = EntityStore(source_root, tmp_path / "source.sqlite3")
    source_store.save(ChildProfile(nickname="복원본", stage=Stage.INFANT_0_2, age_months=8))
    archive = tmp_path / "backup.zip"
    service.create(records_root=source_root, destination=archive)

    target_root = tmp_path / "records"
    target_store = EntityStore(target_root, tmp_path / "target.sqlite3")
    target_store.save(ChildProfile(nickname="이전본", stage=Stage.INFANT_0_2, age_months=7))

    service.restore(
        archive_path=archive,
        records_root=target_root,
        index_path=tmp_path / "target.sqlite3",
    )

    assert not list(tmp_path.glob("records.pre-restore-*"))
    assert not list(tmp_path.glob("growwise-restore-*"))
