from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from growwise.config import Settings
from growwise.idempotency import SQLiteIdempotencyStore
from growwise.jobs import SQLiteJobQueue
from growwise.maintenance import DATA_MAINTENANCE
from growwise.rag import HybridRagIndex
from growwise.services.child_lock import child_operation_lock
from growwise.services.conversation_store import SQLiteConversationStore
from growwise.services.entity_links import EntityLinkService
from growwise.services.photo_activity import PhotoAssetStore
from growwise.storage import EntityStore


@dataclass(frozen=True, slots=True)
class ChildPurgeResult:
    child_id: str
    markdown_files_deleted: int
    photo_files_deleted: int
    rag_chunks_deleted: int
    conversations_deleted: int
    jobs_deleted: int
    idempotency_records_deleted: int
    checkpoint_threads_deleted: int
    links_deleted: int
    backups_may_contain_deleted_child: bool = True

    def model_dump(self) -> dict[str, object]:
        return asdict(self)


class ChildPurgeService:
    """Permanently delete one child's live data while preserving unrelated family data.

    Derived stores are cleaned first. Managed photo binaries are deleted before the authoritative
    Markdown records; the child profile remains available until the final step so an interrupted
    purge is retryable. Existing backup ZIPs are intentionally not rewritten, so callers must
    disclose that historical backups can still contain deleted data.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = EntityStore(settings.records_dir, settings.index_path)

    def purge(self, child_id: str) -> ChildPurgeResult:
        # Privacy purge is a destructive data-generation boundary, not an ordinary mutation.
        # Drain every in-flight authoritative writer first, block new writers for the duration, and
        # advance the generation on exit. Any worker/store created before the purge therefore becomes
        # stale and cannot resurrect child-scoped records after deletion, even if that writer never
        # participates in the per-child lock.
        with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
            with child_operation_lock(child_id):
                return self._purge_locked(child_id)

    def _purge_locked(self, child_id: str) -> ChildPurgeResult:
        profile = self.store.index.get_entity(child_id, entity_type="child_profile")
        if profile is None:
            raise KeyError("child_not_found")

        # Important: entity_type=None intentionally returns only directly-owned entities. Shared
        # documents linked into this child's scope must not be mistaken for owned deletion targets.
        child_entities = self.store.index.list_entities(child_id=child_id)
        resource_ids = {str(payload["id"]) for payload in child_entities if payload.get("id")}
        resource_ids.add(child_id)

        checkpoint_threads: set[str] = set()
        for payload in child_entities:
            if payload.get("entity_type") == "workflow_run" and payload.get("thread_id"):
                checkpoint_threads.add(str(payload["thread_id"]))
            if payload.get("entity_type") == "generated_material" and payload.get("id"):
                checkpoint_threads.add(f"material-review:{payload['id']}")

        # Remove both links scoped to this child and sibling-scoped backlinks whose source document
        # is about to disappear. This prevents dangling Obsidian-style backlinks after a purge.
        links_deleted = EntityLinkService(self.store).delete_for_entities(resource_ids)
        checkpoint_deleted = self._delete_checkpoint_threads(checkpoint_threads)
        rag_deleted = HybridRagIndex(self.settings.rag_index_path).delete_child(child_id)
        conversations_deleted = SQLiteConversationStore(
            self.settings.conversations_path
        ).delete_for_child(child_id)
        jobs_deleted = SQLiteJobQueue(self.settings.jobs_path).delete_for_child(child_id)
        idempotency_deleted = SQLiteIdempotencyStore(
            self.settings.idempotency_path
        ).delete_resources(resource_ids)
        photo_files_deleted = PhotoAssetStore(
            self.settings.assets_dir,
            max_file_bytes=self.settings.photo_max_file_bytes,
        ).delete_child(child_id)
        markdown_deleted = self.store.purge_child(child_id)

        if self.store.index.get_entity(child_id, entity_type="child_profile") is not None:
            raise RuntimeError("child purge verification failed: profile still indexed")
        if self.store.index.list_entities(child_id=child_id):
            raise RuntimeError("child purge verification failed: child records still indexed")
        if (self.settings.photo_assets_dir / child_id).exists():
            raise RuntimeError("child purge verification failed: photo assets still exist")

        return ChildPurgeResult(
            child_id=child_id,
            markdown_files_deleted=markdown_deleted,
            photo_files_deleted=photo_files_deleted,
            rag_chunks_deleted=rag_deleted,
            conversations_deleted=conversations_deleted,
            jobs_deleted=jobs_deleted,
            idempotency_records_deleted=idempotency_deleted,
            checkpoint_threads_deleted=checkpoint_deleted,
            links_deleted=links_deleted,
        )

    def _delete_checkpoint_threads(self, thread_ids: set[str]) -> int:
        if not thread_ids or not self.settings.checkpoint_path.exists():
            return 0
        connection = sqlite3.connect(self.settings.checkpoint_path, check_same_thread=False)
        try:
            saver = SqliteSaver(connection)
            saver.setup()
            for thread_id in sorted(thread_ids):
                saver.delete_thread(thread_id)
        finally:
            connection.close()
        return len(thread_ids)


def checkpoint_thread_ids_for_child(index_path: Path, child_id: str) -> set[str]:
    """Audit helper used by privacy tests without opening the LangGraph checkpoint database."""
    store = EntityStore(index_path.parent / "records", index_path)
    thread_ids: set[str] = set()
    for payload in store.index.list_entities(child_id=child_id):
        if payload.get("entity_type") == "workflow_run" and payload.get("thread_id"):
            thread_ids.add(str(payload["thread_id"]))
        if payload.get("entity_type") == "generated_material" and payload.get("id"):
            thread_ids.add(f"material-review:{payload['id']}")
    return thread_ids
