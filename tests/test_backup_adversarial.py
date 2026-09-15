from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from growwise.backup import BackupService, InvalidBackup


def _manifest(*, record_count: int = 0, padding: str = "") -> dict[str, object]:
    return {
        "format_version": 1,
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "record_count": record_count,
        "padding": padding,
    }


def test_restore_validates_manifest_size_before_reading_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "manifest-bomb.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("manifest.json", json.dumps(_manifest(padding="x" * 256)))

    service = BackupService()
    monkeypatch.setattr(service, "MAX_SINGLE_FILE_BYTES", 64)

    def fail_if_read(_: zipfile.ZipFile) -> None:
        pytest.fail("manifest was read before central-directory size validation")

    monkeypatch.setattr(service, "_read_manifest", fail_if_read)
    with pytest.raises(InvalidBackup, match="member is too large"):
        service.restore(
            archive_path=archive,
            records_root=tmp_path / "records",
            index_path=tmp_path / "index.sqlite3",
        )


def test_restore_rejects_duplicate_archive_member_names(tmp_path: Path) -> None:
    archive = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(_manifest()))
        output.writestr("records/a.md", "first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            output.writestr("records/a.md", "second")

    with pytest.raises(InvalidBackup, match="duplicate archive member"):
        BackupService().restore(
            archive_path=archive,
            records_root=tmp_path / "records",
            index_path=tmp_path / "index.sqlite3",
        )


def test_restore_rejects_windows_style_archive_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "windows-traversal.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(_manifest(record_count=1)))
        output.writestr(r"records\..\escape.md", "nope")

    with pytest.raises(InvalidBackup, match="unsafe archive member"):
        BackupService().restore(
            archive_path=archive,
            records_root=tmp_path / "records",
            index_path=tmp_path / "index.sqlite3",
        )


def test_create_rejects_backup_that_restore_size_policy_would_reject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = tmp_path / "records"
    records.mkdir()
    (records / "large.md").write_text("x" * 128, encoding="utf-8")
    destination = tmp_path / "backup.zip"

    monkeypatch.setattr(BackupService, "MAX_SINGLE_FILE_BYTES", 64)
    with pytest.raises(InvalidBackup, match="source record is too large"):
        BackupService().create(records_root=records, destination=destination)
    assert not destination.exists()


def test_create_rejects_backup_that_restore_member_policy_would_reject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = tmp_path / "records"
    records.mkdir()
    (records / "a.md").write_text("a", encoding="utf-8")
    (records / "b.md").write_text("b", encoding="utf-8")

    # One manifest plus two records would require three archive members.
    monkeypatch.setattr(BackupService, "MAX_ARCHIVE_MEMBERS", 2)
    with pytest.raises(InvalidBackup, match="too many members"):
        BackupService().create(
            records_root=records,
            destination=tmp_path / "backup.zip",
        )
