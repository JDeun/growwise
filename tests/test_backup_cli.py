import sqlite3
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from growwise.backup import BackupService
from growwise.backup.cli import (
    create_backup,
    list_backups,
    managed_archive_path,
    rebuild_rag_projection,
    restore_backup,
    validate_archive_name,
)
from growwise.config import Settings
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.idempotency import SQLiteIdempotencyStore
from growwise.jobs import SQLiteJobQueue
from growwise.maintenance import StaleDataGeneration
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services import ConversationSession, ConversationTurn, SQLiteConversationStore
from growwise.services.background_ai import OBSERVATION_ENRICHMENT_JOB
from growwise.services.photo_jobs import PHOTO_ANALYSIS_JOB
from growwise.storage import EntityStore
from growwise.workflows import build_material_review_graph


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

    created = create_backup(settings, "baseline.zip")
    assert created["archive"] == "baseline.zip"
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

    idempotency = SQLiteIdempotencyStore(settings.idempotency_path)
    idempotency.record(
        key="pre-restore-key",
        request_hash="pre-restore-hash",
        resource_type="resource",
        resource_id=str(baseline_resource.id),
    )

    checkpoint_connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    checkpoint_saver = SqliteSaver(checkpoint_connection)
    checkpoint_saver.setup()
    checkpoint_graph = build_material_review_graph(checkpointer=checkpoint_saver)
    checkpoint_graph.invoke(
        {"material_id": "stale-material", "child_id": str(child.id), "title": "복원 전 상태"},
        config={"configurable": {"thread_id": "stale-review-thread"}},
    )
    checkpoint_connection.close()

    with pytest.raises(ValueError):
        restore_backup(settings, "baseline.zip", confirmed=False)

    restored = restore_backup(settings, "baseline.zip", confirmed=True)
    assert restored["restored"] is True
    assert restored["cancelled_jobs"] == 2
    assert restored["cleared_jobs"] == 3
    assert restored["cleared_idempotency"] == 1
    assert restored["cleared_checkpoint_threads"] == 1
    assert int(restored["rag_chunk_count"]) > 0

    assert queue.get(pending_job.id) is None
    assert queue.get(running_job.id) is None
    assert queue.get(unrelated_job.id) is None

    # The owner created before restore is generation-bound and must not inspect or mutate the new
    # operational registry. A fresh post-restore owner sees that the disposable registry was reset.
    with pytest.raises(StaleDataGeneration):
        idempotency.get("pre-restore-key")
    assert SQLiteIdempotencyStore(settings.idempotency_path).get("pre-restore-key") is None

    checkpoint_connection = sqlite3.connect(settings.checkpoint_path)
    try:
        checkpoint_count = checkpoint_connection.execute(
            "SELECT COUNT(*) FROM checkpoints"
        ).fetchone()
        assert checkpoint_count is not None
        assert checkpoint_count[0] == 0
    finally:
        checkpoint_connection.close()

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



def test_managed_backup_roundtrips_conversations_at_snapshot_boundary(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="대화아이", stage=Stage.ELEMENTARY)
    store.save(child)

    conversations = SQLiteConversationStore(settings.conversations_path)
    baseline = ConversationSession(child_id=str(child.id), title="백업 시점")
    baseline.turns.append(ConversationTurn(role="user", content="백업 전 질문"))
    conversations.save(baseline)

    created = create_backup(settings, "conversation-baseline.zip")
    assert created["manifest"]["format_version"] == 2
    assert created["manifest"]["conversation_count"] == 1

    later = ConversationSession(child_id=str(child.id), title="백업 이후")
    later.turns.append(ConversationTurn(role="user", content="백업 후 질문"))
    conversations.save(later)
    assert conversations.get(later.id) is not None

    restored = restore_backup(settings, "conversation-baseline.zip", confirmed=True)
    assert restored["restored"] is True

    reopened = SQLiteConversationStore(settings.conversations_path)
    restored_baseline = reopened.get(baseline.id)
    assert restored_baseline is not None
    assert [turn.content for turn in restored_baseline.turns] == ["백업 전 질문"]
    assert reopened.get(later.id) is None



def test_restore_rag_rehydrates_embeddings_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeEmbeddingProvider:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, float(index + 1)] for index, _text in enumerate(texts)]

        def embed_query(self, text: str) -> list[float]:
            del text
            return [1.0, 1.0]

    settings = Settings(data_dir=tmp_path, embedding_features_enabled=True)
    store = EntityStore(settings.records_dir, settings.index_path)
    resource = ResourceRecord(
        kind=ResourceKind.NOTE,
        title="임베딩 복원",
        content="고양이 관찰 기록",
    )
    store.save(resource)
    monkeypatch.setattr(
        "growwise.backup.cli.OllamaEmbeddingProvider",
        FakeEmbeddingProvider,
    )

    assert rebuild_rag_projection(settings) > 0

    with sqlite3.connect(settings.rag_index_path) as connection:
        rows = connection.execute(
            "SELECT embedding_json FROM rag_chunks WHERE resource_id = ?",
            (str(resource.id),),
        ).fetchall()
    assert rows
    assert all(row[0] is not None for row in rows)


def test_restore_rag_keeps_lexical_projection_when_embedding_runtime_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingEmbeddingProvider:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            del texts
            raise RuntimeError("embedding runtime unavailable")

        def embed_query(self, text: str) -> list[float]:
            del text
            raise RuntimeError("embedding runtime unavailable")

    settings = Settings(data_dir=tmp_path, embedding_features_enabled=True)
    store = EntityStore(settings.records_dir, settings.index_path)
    resource = ResourceRecord(
        kind=ResourceKind.NOTE,
        title="lexical fallback",
        content="공룡 탐색 기록",
    )
    store.save(resource)
    monkeypatch.setattr(
        "growwise.backup.cli.OllamaEmbeddingProvider",
        FailingEmbeddingProvider,
    )

    assert rebuild_rag_projection(settings) > 0

    restored = HybridRagIndex(settings.rag_index_path)
    hits = restored.search(query="공룡", child_id=None)
    assert [item["resource_id"] for item in hits] == [str(resource.id)]



def test_invalid_restore_preflight_preserves_operational_state(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="보존아이", stage=Stage.ELEMENTARY)
    store.save(child)

    create_backup(settings, "corrupt.zip")

    queue = SQLiteJobQueue(settings.jobs_path)
    job = queue.enqueue(
        OBSERVATION_ENRICHMENT_JOB,
        {"child_id": str(child.id), "log_id": "keep-log"},
    )

    idempotency = SQLiteIdempotencyStore(settings.idempotency_path)
    idempotency.record(
        key="keep-key",
        request_hash="keep-hash",
        resource_type="resource",
        resource_id="keep-resource",
    )

    checkpoint_connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    checkpoint_saver = SqliteSaver(checkpoint_connection)
    checkpoint_saver.setup()
    checkpoint_graph = build_material_review_graph(checkpointer=checkpoint_saver)
    checkpoint_graph.invoke(
        {"material_id": "keep-material", "child_id": str(child.id), "title": "보존 상태"},
        config={"configurable": {"thread_id": "keep-review-thread"}},
    )
    checkpoint_connection.close()

    (settings.backups_dir / "corrupt.zip").write_bytes(b"not-a-valid-zip")

    with pytest.raises(ValueError, match="valid ZIP"):
        restore_backup(settings, "corrupt.zip", confirmed=True)

    fresh_store = EntityStore(settings.records_dir, settings.index_path)
    assert fresh_store.index.get_entity(str(child.id), entity_type="child_profile") is not None

    fresh_queue = SQLiteJobQueue(settings.jobs_path)
    assert fresh_queue.get(job.id) is not None

    fresh_idempotency = SQLiteIdempotencyStore(settings.idempotency_path)
    assert fresh_idempotency.get("keep-key") is not None

    checkpoint_connection = sqlite3.connect(settings.checkpoint_path)
    try:
        checkpoint_count = checkpoint_connection.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?",
            ("keep-review-thread",),
        ).fetchone()
        assert checkpoint_count is not None
        assert checkpoint_count[0] > 0
    finally:
        checkpoint_connection.close()



def test_restore_uses_same_immutable_archive_after_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(data_dir=tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    baseline = ChildProfile(nickname="백업시점", stage=Stage.ELEMENTARY)
    store.save(baseline)
    create_backup(settings, "stable.zip")

    later = ChildProfile(nickname="복원전추가", stage=Stage.ELEMENTARY)
    store.save(later)

    original_validate = BackupService.validate_archive
    original_archive = settings.backups_dir / "stable.zip"

    def validate_then_replace_source(
        self: BackupService,
        archive_path: Path,
    ):
        manifest = original_validate(self, archive_path)
        original_archive.write_bytes(b"changed-after-snapshot")
        return manifest

    monkeypatch.setattr(BackupService, "validate_archive", validate_then_replace_source)

    restored = restore_backup(settings, "stable.zip", confirmed=True)

    assert restored["restored"] is True
    rebuilt = EntityStore(settings.records_dir, settings.index_path)
    children = rebuilt.index.list_entities(entity_type="child_profile")
    assert [item["nickname"] for item in children] == ["백업시점"]
