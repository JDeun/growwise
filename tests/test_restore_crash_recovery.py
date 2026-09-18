from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from growwise.backup import BackupService
from growwise.backup.cli import (
    clear_rag_rebuild_required,
    mark_rag_rebuild_required,
    recover_startup_state,
)
from growwise.backup.restore_journal import RESTORE_JOURNAL_NAME, RestoreJournalManager
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.services import ConversationSession, SQLiteConversationStore
from growwise.storage import EntityStore


def test_restore_journal_rolls_back_all_authoritative_state_after_hard_exit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source_records = source / "records"
    source_assets = source / "assets"
    source_assets.mkdir(parents=True)
    (source_assets / "photo.txt").write_text("new-asset", encoding="utf-8")
    source_store = EntityStore(source_records, source / "index.sqlite3")
    new_child = ChildProfile(nickname="new-generation", stage=Stage.ELEMENTARY)
    source_store.save(new_child)
    source_conversations = source / "conversations.sqlite3"
    new_session = ConversationSession(child_id=str(new_child.id), title="new-conversation")
    SQLiteConversationStore(source_conversations).save(new_session)

    archive = tmp_path / "backup.zip"
    BackupService().create(
        records_root=source_records,
        assets_root=source_assets,
        conversations_path=source_conversations,
        destination=archive,
    )

    target = tmp_path / "target"
    target_records = target / "records"
    target_assets = target / "assets"
    target_assets.mkdir(parents=True)
    (target_assets / "photo.txt").write_text("old-asset", encoding="utf-8")
    target_index = target / "index.sqlite3"
    target_store = EntityStore(target_records, target_index)
    old_child = ChildProfile(nickname="old-generation", stage=Stage.ELEMENTARY)
    target_store.save(old_child)
    target_conversations = target / "conversations.sqlite3"
    old_session = ConversationSession(child_id=str(old_child.id), title="old-conversation")
    SQLiteConversationStore(target_conversations).save(old_session)

    script = r"""
import os
from pathlib import Path

from growwise.backup import BackupService
from growwise.storage.sqlite import SQLiteProjection

def hard_exit(_self, _records_root):
    os._exit(87)

SQLiteProjection.rebuild = hard_exit
BackupService().restore(
    archive_path=Path(os.environ["GW_ARCHIVE"]),
    records_root=Path(os.environ["GW_RECORDS"]),
    assets_root=Path(os.environ["GW_ASSETS"]),
    conversations_path=Path(os.environ["GW_CONVERSATIONS"]),
    index_path=Path(os.environ["GW_INDEX"]),
)
"""
    env = dict(os.environ)
    env.update(
        {
            "GW_ARCHIVE": str(archive),
            "GW_RECORDS": str(target_records),
            "GW_ASSETS": str(target_assets),
            "GW_CONVERSATIONS": str(target_conversations),
            "GW_INDEX": str(target_index),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        env=env,
        check=False,
        timeout=30,
    )
    assert result.returncode == 87

    journal_path = target / RESTORE_JOURNAL_NAME
    assert journal_path.is_file()
    # All three live paths had already crossed to the new generation before projection rebuild.
    assert (target_assets / "photo.txt").read_text(encoding="utf-8") == "new-asset"
    assert SQLiteConversationStore(target_conversations).get(new_session.id) is not None

    recovered = RestoreJournalManager(
        records_root=target_records,
        index_path=target_index,
        assets_root=target_assets,
        conversations_path=target_conversations,
    ).recover_if_needed()

    assert recovered is True
    assert not journal_path.exists()
    rebuilt = EntityStore(target_records, target_index)
    assert rebuilt.index.get_entity(str(old_child.id), entity_type="child_profile") is not None
    assert rebuilt.index.get_entity(str(new_child.id), entity_type="child_profile") is None
    assert (target_assets / "photo.txt").read_text(encoding="utf-8") == "old-asset"

    conversations = SQLiteConversationStore(target_conversations)
    assert conversations.get(old_session.id) is not None
    assert conversations.get(new_session.id) is None


def test_committed_restore_journal_never_rolls_back_new_generation(tmp_path: Path) -> None:
    records = tmp_path / "records"
    index = tmp_path / "index.sqlite3"
    store = EntityStore(records, index)
    old_child = ChildProfile(nickname="old", stage=Stage.ELEMENTARY)
    store.save(old_child)

    transaction = Path(
        tempfile.mkdtemp(prefix="growwise-restore-", dir=records.parent)
    )
    manager = RestoreJournalManager(
        records_root=records,
        index_path=index,
        assets_root=None,
        conversations_path=None,
    )
    manager.begin(
        records_transaction=transaction,
        assets_transaction=None,
        conversations_transaction=None,
    )

    records.replace(transaction / "previous-records")
    new_records = transaction / "records-ready"
    new_store = EntityStore(new_records, tmp_path / "new-index.sqlite3")
    new_child = ChildProfile(nickname="new", stage=Stage.ELEMENTARY)
    new_store.save(new_child)
    new_records.replace(records)
    EntityStore(records, index).index.rebuild(records)

    manager.mark_committed()
    assert manager.recover_if_needed() is True

    current = EntityStore(records, index)
    assert current.index.get_entity(str(new_child.id), entity_type="child_profile") is not None
    assert current.index.get_entity(str(old_child.id), entity_type="child_profile") is None
    assert not manager.path.exists()
    assert not transaction.exists()


def test_startup_retries_rag_rebuild_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(data_dir=tmp_path)
    mark_rag_rebuild_required(settings)
    calls: list[Path] = []

    def fake_rebuild(received: Settings) -> int:
        calls.append(received.data_dir)
        return 3

    monkeypatch.setattr("growwise.backup.cli.rebuild_rag_projection", fake_rebuild)

    result = recover_startup_state(settings)

    assert result == {
        "restore_recovered": False,
        "rag_rebuilt": True,
        "rag_degraded": False,
    }
    assert calls == [tmp_path]
    assert not (tmp_path / ".growwise-rag-rebuild-required").exists()


def test_failed_startup_rag_rebuild_keeps_retry_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(data_dir=tmp_path)
    mark_rag_rebuild_required(settings)

    def fail_rebuild(_settings: Settings) -> int:
        raise RuntimeError("offline embedding/runtime")

    monkeypatch.setattr("growwise.backup.cli.rebuild_rag_projection", fail_rebuild)

    result = recover_startup_state(settings)

    assert result["rag_degraded"] is True
    assert (tmp_path / ".growwise-rag-rebuild-required").exists()
    clear_rag_rebuild_required(settings)
