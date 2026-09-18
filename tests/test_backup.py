from __future__ import annotations

import json
import stat
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from growwise.backup import BackupService, InvalidBackup
from growwise.domain import ChildProfile, Stage
from growwise.services import ConversationSession, SQLiteConversationStore
from growwise.storage import EntityStore, SQLiteProjection


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



def test_v1_restore_clears_post_backup_conversation_state(tmp_path: Path) -> None:
    records = tmp_path / "records"
    index = tmp_path / "index.sqlite3"
    conversations_path = tmp_path / "conversations.sqlite3"
    store = EntityStore(records, index)
    child = ChildProfile(nickname="v1아이", stage=Stage.ELEMENTARY)
    store.save(child)

    archive = tmp_path / "legacy-v1.zip"
    manifest = BackupService().create(records_root=records, destination=archive)
    assert manifest.format_version == 1

    conversations = SQLiteConversationStore(conversations_path)
    stale = ConversationSession(child_id=str(child.id), title="백업 이후 대화")
    conversations.save(stale)
    assert conversations.get(stale.id) is not None

    BackupService().restore(
        archive_path=archive,
        records_root=records,
        index_path=index,
        conversations_path=conversations_path,
    )

    reopened = SQLiteConversationStore(conversations_path)
    assert reopened.get(stale.id) is None



def test_restore_rolls_back_records_assets_and_conversations_on_projection_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = BackupService()

    source_records = tmp_path / "source" / "records"
    source_assets = tmp_path / "source" / "assets"
    source_assets.mkdir(parents=True)
    (source_assets / "photo.jpg").write_bytes(b"new-photo")
    source_store = EntityStore(source_records, tmp_path / "source" / "index.sqlite3")
    source_child = ChildProfile(nickname="복원본", stage=Stage.INFANT_0_2, age_months=8)
    source_store.save(source_child)
    source_conversations_path = tmp_path / "source" / "conversations.sqlite3"
    source_conversations = SQLiteConversationStore(source_conversations_path)
    source_session = ConversationSession(child_id=str(source_child.id), title="복원 대화")
    source_conversations.save(source_session)

    archive = tmp_path / "backup.zip"
    service.create(
        records_root=source_records,
        assets_root=source_assets,
        conversations_path=source_conversations_path,
        destination=archive,
    )

    target_records = tmp_path / "target" / "records"
    target_assets = tmp_path / "target" / "assets"
    target_assets.mkdir(parents=True)
    (target_assets / "photo.jpg").write_bytes(b"old-photo")
    target_index = tmp_path / "target" / "index.sqlite3"
    target_store = EntityStore(target_records, target_index)
    target_child = ChildProfile(nickname="이전본", stage=Stage.INFANT_0_2, age_months=7)
    target_store.save(target_child)
    target_conversations_path = tmp_path / "target" / "conversations.sqlite3"
    target_conversations = SQLiteConversationStore(target_conversations_path)
    target_session = ConversationSession(child_id=str(target_child.id), title="이전 대화")
    target_conversations.save(target_session)

    original_rebuild = SQLiteProjection.rebuild
    rebuild_calls = 0

    def fail_first_rebuild(self: SQLiteProjection, records_root: Path) -> int:
        nonlocal rebuild_calls
        rebuild_calls += 1
        if rebuild_calls == 1:
            raise RuntimeError("simulated projection rebuild failure")
        return original_rebuild(self, records_root)

    monkeypatch.setattr(SQLiteProjection, "rebuild", fail_first_rebuild)

    with pytest.raises(RuntimeError, match="simulated projection rebuild failure"):
        service.restore(
            archive_path=archive,
            records_root=target_records,
            assets_root=target_assets,
            conversations_path=target_conversations_path,
            index_path=target_index,
        )

    assert rebuild_calls == 2
    restored_target = EntityStore(target_records, target_index)
    assert (
        restored_target.index.get_entity(str(target_child.id), entity_type="child_profile")
        is not None
    )
    assert (
        restored_target.index.get_entity(str(source_child.id), entity_type="child_profile")
        is None
    )
    assert (target_assets / "photo.jpg").read_bytes() == b"old-photo"

    reopened_conversations = SQLiteConversationStore(target_conversations_path)
    assert reopened_conversations.get(target_session.id) is not None
    assert reopened_conversations.get(source_session.id) is None
