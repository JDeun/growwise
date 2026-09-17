from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from growwise.backup import BackupService
from growwise.backup.naming import unique_backup_token
from growwise.config import Settings
from growwise.domain import ResourceRecord
from growwise.maintenance import DATA_MAINTENANCE, MaintenanceAwareJobQueue
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.runtime_lock import DataDirectoryLock
from growwise.services.background_ai import MATERIAL_ENHANCEMENT_JOB, OBSERVATION_ENRICHMENT_JOB
from growwise.services.photo_jobs import PHOTO_ANALYSIS_JOB
from growwise.storage import EntityStore

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.zip$")
_AI_JOB_TYPES = (OBSERVATION_ENRICHMENT_JOB, MATERIAL_ENHANCEMENT_JOB, PHOTO_ANALYSIS_JOB)


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
    # that already started and rejects new ones until the archive has closed. Read-only maintenance
    # does not advance the data generation because the active source set is unchanged.
    with DATA_MAINTENANCE.maintenance():
        manifest = BackupService().create(
            records_root=settings.records_dir,
            assets_root=settings.assets_dir,
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


def rebuild_rag_projection(settings: Settings) -> int:
    """Rebuild the lexical RAG projection from restored ResourceRecord source documents."""
    store = EntityStore(settings.records_dir, settings.index_path)
    index = HybridRagIndex(settings.rag_index_path, embedding=None)
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

    # The exclusive maintenance window first drains any in-flight SoT mutation. Queue claims are
    # then cancelled before files are replaced, fencing model work that was started from the old
    # record set. The generation advances on exit, so even a worker still returning from inference
    # cannot persist through an old EntityStore or a generation-bound worker thread.
    with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
        cancelled_jobs = MaintenanceAwareJobQueue(settings.jobs_path).cancel_active(
            job_types=_AI_JOB_TYPES
        )
        manifest = BackupService().restore(
            archive_path=archive,
            records_root=settings.records_dir,
            assets_root=settings.assets_dir,
            index_path=settings.index_path,
        )
        rag_chunk_count = rebuild_rag_projection(settings)

    return {
        "archive": archive.name,
        "restored": True,
        "cancelled_jobs": cancelled_jobs,
        "rag_chunk_count": rag_chunk_count,
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
            result = create_backup(settings, args.name)
    elif args.command == "list":
        result = list_backups(settings)
    elif args.command == "restore":
        with DataDirectoryLock(settings.data_dir):
            result = restore_backup(settings, args.name, confirmed=args.yes)
    else:  # pragma: no cover - argparse prevents this branch
        raise SystemExit(2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
