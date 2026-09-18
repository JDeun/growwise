from __future__ import annotations

import json
import sqlite3
import stat
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from growwise.backup import BackupService, InvalidBackup
from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore


def _manifest(*, record_count: int = 0) -> dict[str, object]:
    return {
        "format_version": 1,
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "record_count": record_count,
    }


def test_backup_restores_markdown_and_rebuilds_projection(tmp_path: Path) -> None:
    source_root = tmp_path / "source-records"
    source_index = tmp_path / "source.sqlite3"
    source_store = EntityStore(source_root, source_index)
    child = ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9)
    source_store.save(child)

    archive = tmp_path / "growwise-backup.zip"
    service = BackupService()
    manifest = service.create(records_root=source_root, destination=archive)
    assert manifest.record_count == 1

    restored_root = tmp_path / "restored-records"
    restored_index = tmp_path / "restored.sqlite3"
    service.restore(
        archive_path=archive,
        records_root=restored_root,
        index_path=restored_index,
    )

    restored_store = EntityStore(restored_root, restored_index)
    payload = restored_store.index.get_entity(str(child.id), entity_type="child_profile")
    assert payload is not None
    assert payload["nickname"] == "샘플아이"




def _write_state_value(path: Path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS state_value (value TEXT NOT NULL)")
        connection.execute("DELETE FROM state_value")
        connection.execute("INSERT INTO state_value (value) VALUES (?)", (value,))


def _read_state_value(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT value FROM state_value").fetchone()
    assert row is not None
    return str(row[0])


def test_backup_v2_roundtrips_portable_sqlite_state(tmp_path: Path) -> None:
    records = tmp_path / "records"
    store = EntityStore(records, tmp_path / "index.sqlite3")
    store.save(ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9))

    source_state = tmp_path / "source-conversations.sqlite3"
    target_state = tmp_path / "target-conversations.sqlite3"
    _write_state_value(source_state, "backup-state")
    _write_state_value(target_state, "newer-live-state")

    archive = tmp_path / "portable-v2.zip"
    service = BackupService()
    manifest = service.create(
        records_root=records,
        destination=archive,
        sqlite_state={"conversations.sqlite3": source_state},
    )

    assert manifest.format_version == 2
    assert manifest.state_files == ("conversations.sqlite3",)

    service.restore(
        archive_path=archive,
        records_root=tmp_path / "restored-records",
        index_path=tmp_path / "restored-index.sqlite3",
        sqlite_state={"conversations.sqlite3": target_state},
    )

    assert _read_state_value(target_state) == "backup-state"


def test_backup_v2_rolls_back_portable_state_when_late_restore_step_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = tmp_path / "records"
    store = EntityStore(records, tmp_path / "index.sqlite3")
    store.save(ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9))

    source_state = tmp_path / "source-conversations.sqlite3"
    target_state = tmp_path / "target-conversations.sqlite3"
    _write_state_value(source_state, "backup-state")
    _write_state_value(target_state, "pre-restore-live-state")

    archive = tmp_path / "portable-v2.zip"
    service = BackupService()
    service.create(
        records_root=records,
        destination=archive,
        sqlite_state={"conversations.sqlite3": source_state},
    )

    from growwise.backup import service as backup_service_module

    original_rebuild = backup_service_module.SQLiteProjection.rebuild
    calls = 0

    def fail_first_rebuild(self, records_root):  # noqa: ANN001, ANN202
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated projection rebuild failure")
        return original_rebuild(self, records_root)

    monkeypatch.setattr(backup_service_module.SQLiteProjection, "rebuild", fail_first_rebuild)

    with pytest.raises(RuntimeError, match="simulated projection rebuild failure"):
        service.restore(
            archive_path=archive,
            records_root=tmp_path / "restored-records",
            index_path=tmp_path / "restored-index.sqlite3",
            sqlite_state={"conversations.sqlite3": target_state},
        )

    assert _read_state_value(target_state) == "pre-restore-live-state"

def test_backup_create_rejects_semantically_invalid_record_tree(tmp_path: Path) -> None:
    records = tmp_path / "records"
    records.mkdir()
    (records / "orphan.md").write_text(
        "---\nschema_version: 1\nid: not-a-uuid\nentity_type: child_profile\n---\n",
        encoding="utf-8",
    )
    archive = tmp_path / "invalid-source.zip"

    with pytest.raises(InvalidBackup):
        BackupService().create(records_root=records, destination=archive)

    assert not archive.exists()


def test_backup_create_enforces_restore_size_limit_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = tmp_path / "records"
    index = tmp_path / "index.sqlite3"
    store = EntityStore(records, index)
    store.save(ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9))
    archive = tmp_path / "oversized-source.zip"

    monkeypatch.setattr(BackupService, "MAX_TOTAL_UNCOMPRESSED_BYTES", 32)
    with pytest.raises(InvalidBackup, match="backup source expands beyond the allowed size"):
        BackupService().create(records_root=records, destination=archive)

    assert not archive.exists()

def test_backup_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(_manifest()))
        output.writestr("../escape.txt", "nope")

    with pytest.raises(InvalidBackup, match="unsafe archive member"):
        BackupService().restore(
            archive_path=archive,
            records_root=tmp_path / "records",
            index_path=tmp_path / "index.sqlite3",
        )


def test_backup_rejects_symlink_member(tmp_path: Path) -> None:
    archive = tmp_path / "symlink.zip"
    symlink = zipfile.ZipInfo("records/link.md")
    symlink.create_system = 3
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16

    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(_manifest(record_count=1)))
        output.writestr(symlink, "../../outside")

    with pytest.raises(InvalidBackup, match="symlink archive member"):
        BackupService().restore(
            archive_path=archive,
            records_root=tmp_path / "records",
            index_path=tmp_path / "index.sqlite3",
        )


def test_backup_rejects_oversized_member_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "oversized.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("manifest.json", json.dumps(_manifest(record_count=1)))
        output.writestr("records/large.md", "x" * 64)

    monkeypatch.setattr(BackupService, "MAX_SINGLE_FILE_BYTES", 32)
    with pytest.raises(InvalidBackup, match="member is too large"):
        BackupService().restore(
            archive_path=archive,
            records_root=tmp_path / "records",
            index_path=tmp_path / "index.sqlite3",
        )


def test_backup_rejects_too_many_members_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "many.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(_manifest(record_count=2)))
        output.writestr("records/a.md", "a")
        output.writestr("records/b.md", "b")

    monkeypatch.setattr(BackupService, "MAX_ARCHIVE_MEMBERS", 2)
    with pytest.raises(InvalidBackup, match="too many members"):
        BackupService().restore(
            archive_path=archive,
            records_root=tmp_path / "records",
            index_path=tmp_path / "index.sqlite3",
        )


def test_restore_rejects_non_zip_as_invalid_backup(tmp_path) -> None:
    from growwise.backup import InvalidBackup

    archive = tmp_path / "not-a-backup.zip"
    archive.write_text("not a zip", encoding="utf-8")
    with pytest.raises(InvalidBackup, match="valid ZIP"):
        BackupService().restore(
            archive_path=archive,
            records_root=tmp_path / "records",
            index_path=tmp_path / "index.sqlite3",
        )


def test_backup_fsyncs_archive_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def record_fsync(descriptor: int) -> None:
        calls.append(descriptor)

    monkeypatch.setattr("growwise.backup.service.os.fsync", record_fsync)
    archive = tmp_path / "durable.zip"

    BackupService().create(records_root=tmp_path / "records", destination=archive)

    assert archive.is_file()
    assert calls
    with zipfile.ZipFile(archive) as created:
        assert "manifest.json" in created.namelist()
