import sqlite3
from pathlib import Path

import pytest

from growwise.backup.cli import (
    create_backup,
    list_backups,
    managed_archive_path,
    restore_backup,
    validate_archive_name,
)
from growwise.config import Settings
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.idempotency import SQLiteIdempotencyStore, request_fingerprint
from growwise.jobs import JobStatus, SQLiteJobQueue
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services import ConversationSession, ConversationTurn, SQLiteConversationStore
from growwise.services.background_ai import OBSERVATION_ENRICHMENT_JOB
from growwise.services.photo_jobs import PHOTO_ANALYSIS_JOB
from growwise.storage import EntityStore


def test_backup_name_rejects_path_traversal(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)

    for unsafe in ("../escape.zip", "nested/escape.zip", "\\escape.zip", "not-a-zip.txt"):
        with pytest.raises(ValueError):
            managed_archive_path(settings, unsafe)

    assert validate_archive_name("family-20260914.zip") == "family-20260914.zip"


def test_cli_helpers_create_list_and_restore_managed_backup(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    baseline_resource = ResourceRecord(
        child_id=child.id,
        kind=ResourceKind.NOTE,
        title="고양이 관찰 메모",
        content="고양이 그림을 오래 바라보았다.",
    )
    store.save(baseline_resource)
    ResourceIngestor(HybridRagIndex(settings.rag_index_path)).ingest(baseline_resource)

    conversation_store = SQLiteConversationStore(settings.conversations_path)
    baseline_conversation = ConversationSession(child_id=str(child.id), title="백업 시점 대화")
    baseline_conversation.turns.append(ConversationTurn(role="user", content="백업 질문"))
    conversation_store.save(baseline_conversation)

    created = create_backup(settings, "baseline.zip")
    assert created["archive"] == "baseline.zip"
    assert created["manifest"]["format_version"] == 2
    assert created["manifest"]["state_files"] == ["conversations.sqlite3"]
    assert (settings.backups_dir / "baseline.zip").is_file()
    assert [item["archive"] for item in list_backups(settings)] == ["baseline.zip"]

    # Backup creation is read-only maintenance. The store opened before backup must remain usable.
    replacement = ChildProfile(nickname="다른 아이", stage=Stage.INFANT_0_2, age_months=8)
    store.save(replacement)
    stale_resource = ResourceRecord(
        child_id=child.id,
        kind=ResourceKind.NOTE,
        title="복원 후 없어져야 할 메모",
        content="공룡 탐색 기록",
    )
    store.save(stale_resource)
    ResourceIngestor(HybridRagIndex(settings.rag_index_path)).ingest(stale_resource)

    queue = SQLiteJobQueue(settings.jobs_path)
    pending_job = queue.enqueue(
        OBSERVATION_ENRICHMENT_JOB,
        {"child_id": str(child.id), "log_id": "stale-log"},
    )
    running_job = queue.enqueue(
        PHOTO_ANALYSIS_JOB,
        {"child_id": str(child.id), "record_id": "stale-photo"},
    )
    running_claim = queue.claim_next(
        job_types=(PHOTO_ANALYSIS_JOB,),
        lease_seconds=3600,
        max_attempts=3,
    )
    assert running_claim is not None
    unrelated_job = queue.enqueue("unrelated-maintenance-test", {"child_id": str(child.id)})

    late_conversation = ConversationSession(child_id=str(child.id), title="복원 후 없어져야 할 대화")
    late_conversation.turns.append(ConversationTurn(role="user", content="백업 이후 질문"))
    conversation_store.save(late_conversation)

    idempotency = SQLiteIdempotencyStore(settings.idempotency_path)
    idempotency.record(
        key="post-backup-key",
        request_hash=request_fingerprint({"value": "post-backup"}),
        resource_type="test-resource",
        resource_id="post-backup-resource",
    )

    with sqlite3.connect(settings.checkpoint_path) as checkpoint_connection:
        checkpoint_connection.execute(
            "CREATE TABLE IF NOT EXISTS checkpoints (thread_id TEXT PRIMARY KEY)"
        )
        checkpoint_connection.execute(
            "INSERT INTO checkpoints (thread_id) VALUES (?)",
            ("post-backup-thread",),
        )

    with pytest.raises(ValueError):
        restore_backup(settings, "baseline.zip", confirmed=False)

    restored = restore_backup(settings, "baseline.zip", confirmed=True)
    assert restored["restored"] is True
    assert restored["cancelled_jobs"] == 2
    assert restored["purged_jobs"] == 2
    assert restored["checkpoint_rows_deleted"] == 1
    assert restored["idempotency_records_deleted"] == 1
    assert int(restored["rag_chunk_count"]) > 0

    pending_after = queue.get(pending_job.id)
    running_after = queue.get(running_job.id)
    unrelated_after = queue.get(unrelated_job.id)
    assert pending_after is None
    assert running_after is None
    assert unrelated_after is not None
    assert unrelated_after.status is JobStatus.PENDING

    restored_conversation = conversation_store.get(baseline_conversation.id)
    assert restored_conversation is not None
    assert [turn.content for turn in restored_conversation.turns] == ["백업 질문"]
    assert conversation_store.get(late_conversation.id) is None
    assert idempotency.get("post-backup-key") is None
    with sqlite3.connect(settings.checkpoint_path) as checkpoint_connection:
        checkpoint_count = checkpoint_connection.execute(
            "SELECT COUNT(*) FROM checkpoints"
        ).fetchone()
    assert checkpoint_count == (0,)

    rebuilt = EntityStore(settings.records_dir, settings.index_path)
    children = rebuilt.index.list_entities(entity_type="child_profile")
    assert [item["nickname"] for item in children] == ["샘플아이"]

    restored_rag = HybridRagIndex(settings.rag_index_path)
    assert restored_rag.search(query="고양이", child_id=str(child.id))
    assert restored_rag.search(query="공룡", child_id=str(child.id)) == []


def test_default_archive_names_do_not_collide_in_same_second() -> None:
    from growwise.backup.cli import default_archive_name

    first = default_archive_name()
    second = default_archive_name()
    assert first != second
    assert first.startswith("growwise-") and first.endswith(".zip")



def test_restore_reports_rag_degraded_after_authoritative_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="백업아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    create_backup(settings, "baseline.zip")

    replacement = ChildProfile(nickname="복원전아이", stage=Stage.INFANT_0_2, age_months=8)
    store.save(replacement)

    def fail_rag(_settings: Settings) -> int:
        raise RuntimeError("simulated rag rebuild failure")

    monkeypatch.setattr("growwise.backup.cli.rebuild_rag_projection", fail_rag)

    restored = restore_backup(settings, "baseline.zip", confirmed=True)

    assert restored["restored"] is True
    assert restored["rag_status"] == "degraded"
    assert restored["rag_chunk_count"] == 0

    rebuilt = EntityStore(settings.records_dir, settings.index_path)
    children = rebuilt.index.list_entities(entity_type="child_profile")
    assert [item["nickname"] for item in children] == ["백업아이"]
