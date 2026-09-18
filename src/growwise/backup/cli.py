from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from growwise.backup import BackupService
from growwise.backup.naming import unique_backup_token
from growwise.backup.restore_journal import RestoreJournalManager
from growwise.config import Settings
from growwise.domain import ResourceRecord
from growwise.idempotency import SQLiteIdempotencyStore
from growwise.maintenance import DATA_MAINTENANCE, MaintenanceAwareJobQueue
from growwise.rag import HybridRagIndex, OllamaEmbeddingProvider, ResourceIngestor
from growwise.runtime_lock import DataDirectoryLock
from growwise.services.background_ai import MATERIAL_ENHANCEMENT_JOB, OBSERVATION_ENRICHMENT_JOB
from growwise.services.photo_jobs import PHOTO_ANALYSIS_JOB
from growwise.storage import EntityStore

logger = logging.getLogger(__name__)

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.zip$")
_AI_JOB_TYPES = (OBSERVATION_ENRICHMENT_JOB, MATERIAL_ENHANCEMENT_JOB, PHOTO_ANALYSIS_JOB)
_RAG_REBUILD_MARKER = ".growwise-rag-rebuild-required"


def _fsync_directory(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(path, os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _rag_rebuild_marker(settings: Settings) -> Path:
    return settings.data_dir / _RAG_REBUILD_MARKER


def mark_rag_rebuild_required(settings: Settings) -> None:
    marker = _rag_rebuild_marker(settings)
    marker.parent.mkdir(parents=True, exist_ok=True)
    with marker.open("wb") as handle:
        handle.write(b"rebuild\n")
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(marker.parent)


def clear_rag_rebuild_required(settings: Settings) -> None:
    marker = _rag_rebuild_marker(settings)
    marker.unlink(missing_ok=True)
    _fsync_directory(marker.parent)


def recover_startup_state(settings: Settings) -> dict[str, object]:
    """Recover an interrupted restore before workers or API traffic can observe mixed state."""

    restore_recovered = RestoreJournalManager(
        records_root=settings.records_dir,
        index_path=settings.index_path,
        assets_root=settings.assets_dir,
        conversations_path=settings.conversations_path,
    ).recover_if_needed()

    rag_rebuilt = False
    rag_degraded = False
    if _rag_rebuild_marker(settings).exists():
        try:
            rebuild_rag_projection(settings)
        except Exception:
            rag_degraded = True
            logger.exception("RAG rebuild retry failed during startup recovery")
        else:
            clear_rag_rebuild_required(settings)
            rag_rebuilt = True

    return {
        "restore_recovered": restore_recovered,
        "rag_rebuilt": rag_rebuilt,
        "rag_degraded": rag_degraded,
    }


def validate_archive_name(name: str) -> str:
    if not _SAFE_NAME.fullmatch(name):
        raise ValueError(
            "backup name must be a simple .zip filename using letters, digits, '.', '_' or '-'"
        )
    return name


def default_archive_name() -> str:
    return f"growwise-{unique_backup_token()}.zip"


def managed_archive_path(settings: Settings, name: str) -> Path:
    safe_name = validate_archive_name(name)
    settings.backups_dir.mkdir(parents=True, exist_ok=True)
    return settings.backups_dir / safe_name


def create_backup(settings: Settings, name: str | None = None) -> dict[str, object]:
    archive = managed_archive_path(settings, name or default_archive_name())
    # A backup must observe one coherent authoritative snapshot. This waits for source mutations
    # that already started and blocks new ones until the archive has closed. Read-only maintenance
    # does not advance the data generation because the active source set is unchanged.
    with DATA_MAINTENANCE.maintenance():
        manifest = BackupService().create(
            records_root=settings.records_dir,
            assets_root=settings.assets_dir,
            conversations_path=settings.conversations_path,
            destination=archive,
        )
    return {
        "archive": archive.name,
        "path": str(archive),
        "manifest": manifest.model_dump(mode="json"),
    }


def list_backups(settings: Settings) -> list[dict[str, object]]:
    settings.backups_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for archive in sorted(settings.backups_dir.glob("*.zip"), reverse=True):
        stat = archive.stat()
        results.append(
            {
                "archive": archive.name,
                "path": str(archive),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            }
        )
    return results


def reset_checkpoint_projection(path: Path) -> int:
    """Delete every LangGraph thread from the pre-restore data generation."""

    if not path.exists():
        return 0
    connection = sqlite3.connect(path, check_same_thread=False)
    try:
        saver = SqliteSaver(connection)
        saver.setup()
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        thread_ids: set[str] = set()
        for table in ("checkpoints", "checkpoint_writes", "checkpoint_blobs"):
            if table not in tables:
                continue
            columns = {
                str(row[1])
                for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if "thread_id" not in columns:
                continue
            thread_ids.update(
                str(row[0])
                for row in connection.execute(
                    f"SELECT DISTINCT thread_id FROM {table} WHERE thread_id IS NOT NULL"
                ).fetchall()
            )
        for thread_id in sorted(thread_ids):
            saver.delete_thread(thread_id)
        return len(thread_ids)
    finally:
        connection.close()


def rebuild_rag_projection(settings: Settings) -> int:
    """Rebuild RAG from restored resources, rehydrating embeddings when configured.

    Embedding failures remain non-fatal inside HybridRagIndex.replace_resource(), so lexical
    retrieval is always rebuilt even when the local embedding runtime is temporarily unavailable.
    """
    store = EntityStore(settings.records_dir, settings.index_path)
    embedding = None
    if settings.embedding_features_enabled:
        try:
            embedding = OllamaEmbeddingProvider(
                model=settings.embedding_model_id,
                base_url=settings.model_base_url,
            )
        except Exception:
            logger.exception(
                "embedding provider unavailable during restore; rebuilding lexical RAG only"
            )
    index = HybridRagIndex(settings.rag_index_path, embedding=embedding)
    index.reset()
    ingestor = ResourceIngestor(index)
    count = 0
    for payload in store.index.list_entities(entity_type="resource"):
        count += ingestor.ingest(ResourceRecord.model_validate(payload))
    return count


def restore_backup(settings: Settings, name: str, *, confirmed: bool) -> dict[str, object]:
    if not confirmed:
        raise ValueError("restore requires --yes because it replaces the active record set")
    archive = managed_archive_path(settings, name)
    if not archive.is_file():
        raise FileNotFoundError(archive)

    backup_service = BackupService()

    # Copy the selected archive once and validate/restore that immutable snapshot. This removes the
    # preflight-to-restore TOCTOU window if the managed backup file is replaced externally while a
    # restore is in progress. Copy/preflight happen before the exclusive maintenance window so a
    # corrupt archive never blocks or mutates live application state.
    with tempfile.TemporaryDirectory(
        prefix="growwise-restore-snapshot-",
        dir=settings.backups_dir,
    ) as temp_dir:
        restore_archive = Path(temp_dir) / archive.name
        shutil.copyfile(archive, restore_archive)
        backup_service.validate_archive(restore_archive)

        # The exclusive maintenance window first drains any in-flight SoT mutation. Queue claims
        # are then cancelled before files are replaced, fencing model work started from the old
        # record set. The generation advances on exit, so a stale worker cannot persist afterward.
        with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
            # RAG is disposable but must never silently remain on the pre-restore generation if the
            # process dies after authoritative swap and before rebuild completes.
            mark_rag_rebuild_required(settings)

            queue = MaintenanceAwareJobQueue(settings.jobs_path)
            cancelled_jobs = queue.cancel_active(job_types=_AI_JOB_TYPES)

            # Clear disposable execution state before replacing authoritative data. The archive was
            # fully validated above and restore() validates the same immutable snapshot again.
            cleared_jobs = queue.reset()
            cleared_idempotency = SQLiteIdempotencyStore(settings.idempotency_path).reset()
            cleared_checkpoint_threads = reset_checkpoint_projection(settings.checkpoint_path)

            manifest = backup_service.restore(
                archive_path=restore_archive,
                records_root=settings.records_dir,
                assets_root=settings.assets_dir,
                conversations_path=settings.conversations_path,
                index_path=settings.index_path,
            )
            try:
                rag_chunk_count = rebuild_rag_projection(settings)
                clear_rag_rebuild_required(settings)
                rag_status = "ready"
            except Exception:
                # Markdown/assets/index have already been restored successfully. RAG is disposable
                # and must not turn that authoritative success into an ambiguous restore failure.
                # Keep the durable marker so the next Core startup retries automatically.
                logger.exception("RAG projection rebuild failed after authoritative restore")
                rag_chunk_count = 0
                rag_status = "degraded"

    return {
        "archive": archive.name,
        "restored": True,
        "cancelled_jobs": cancelled_jobs,
        "cleared_jobs": cleared_jobs,
        "cleared_idempotency": cleared_idempotency,
        "cleared_checkpoint_threads": cleared_checkpoint_threads,
        "rag_chunk_count": rag_chunk_count,
        "rag_status": rag_status,
        "manifest": manifest.model_dump(mode="json"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage GrowWise portable backups")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="create a portable GrowWise backup")
    create_parser.add_argument("--name", help="managed .zip filename")

    subparsers.add_parser("list", help="list managed backups")

    restore_parser = subparsers.add_parser("restore", help="restore a managed backup")
    restore_parser.add_argument("name", help="managed .zip filename")
    restore_parser.add_argument(
        "--yes",
        action="store_true",
        help="confirm replacement of the active record set",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings()
    result: dict[str, object] | list[dict[str, object]]

    if args.command == "create":
        # The standalone CLI is a separate process from Core. Reuse the same OS ownership lock so
        # a shell backup cannot bypass the in-process maintenance barrier of a running application.
        with DataDirectoryLock(settings.data_dir):
            recover_startup_state(settings)
            result = create_backup(settings, args.name)
    elif args.command == "list":
        result = list_backups(settings)
    elif args.command == "restore":
        with DataDirectoryLock(settings.data_dir):
            recover_startup_state(settings)
            result = restore_backup(settings, args.name, confirmed=args.yes)
    else:  # pragma: no cover - argparse prevents this branch
        raise SystemExit(2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
