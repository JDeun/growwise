from __future__ import annotations

import json
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
    child = ChildProfile(nickname="수아", stage=Stage.INFANT_0_2, age_months=9)
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
    assert payload["nickname"] == "수아"


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
