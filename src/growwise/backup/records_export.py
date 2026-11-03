"""Portable, selected raw originals; deliberately not a whole-app restore archive."""

from __future__ import annotations

import hashlib
import json
import stat
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import frontmatter

from growwise.backup.record_validation import _RECORD_MODELS, _REQUIRED_RECORD_KEYS
from growwise.backup.service import BackupService, _make_private_file
from growwise.maintenance import DATA_MAINTENANCE
from growwise.services.record_time import record_time
from growwise.storage import EntityStore
from growwise.storage.markdown import _decode_metadata
from growwise.storage.schema import validate_schema_version

MANIFEST_NAME = "growwise-record-export.json"
MAX_MEMBERS = 10_000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_BYTES = 600 * 1024 * 1024
MAX_SECONDS = 120
_EXPORTABLE = set(_RECORD_MODELS) - {
    "child_profile", "photo_asset", "entity_link", "learning_wiki", "workflow_run",
}
_REFERENCE_FIELDS = {
    "id", "entity_type", "child_id", "created_at", "occurred_at", "relation", "source_id",
    "target_id", "book_id", "activity_plan_id", "parent_material_id", "source_refs",
    "photo_asset_ids", "avatar_asset_id", "learning_log_id", "relative_path", "sha256", "byte_size",
}


class RecordsExportUnavailable(ValueError):
    pass


class RecordsExportTooLarge(ValueError):
    pass


@dataclass
class _Record:
    metadata: dict
    path: Path


def _safe_file(root: Path, path: Path) -> Path:
    """Accept only regular managed files, with no symbolic links/junctions in their path."""
    try:
        relative = path.relative_to(root)
        if not relative.parts or any(part in {".", ".."} for part in relative.parts):
            raise RecordsExportUnavailable("unsafe source")
        current = root
        for part in ("", *relative.parts):
            current = current / part
            if current.is_symlink() or current.is_junction():
                raise RecordsExportUnavailable("linked source")
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
        if not stat.S_ISREG(resolved.stat().st_mode):
            raise RecordsExportUnavailable("non-regular source")
        return resolved
    except (OSError, ValueError) as exc:
        raise RecordsExportUnavailable("managed source unavailable") from exc


class RecordsExportService:
    def create(self, *, store: EntityStore, assets_root: Path, destination: Path,
               child_id: UUID, start_date: date | None, end_date: date | None) -> dict:
        if start_date and end_date and (
            start_date > end_date or (end_date - start_date).days > 36_600
        ):
            raise ValueError("invalid_export_period")
        deadline = time.monotonic() + MAX_SECONDS

        def budget() -> None:
            if time.monotonic() > deadline:
                raise RecordsExportTooLarge("export time budget exceeded")

        # Like full backup, take one quiescent source snapshot. Background inference can continue,
        # but no save, scope narrowing, child purge or restore can race the selected raw bytes.
        with DATA_MAINTENANCE.maintenance(), store.mutation_window():
            records: dict[str, _Record] = {}
            scanned = 0
            pending = [store.markdown.root]
            while pending:
                directory = pending.pop()
                if directory.is_symlink() or directory.is_junction():
                    raise RecordsExportUnavailable("linked record directory")
                for path in sorted(directory.iterdir()):
                    budget()
                    if path.is_symlink() or path.is_junction():
                        raise RecordsExportUnavailable("linked record source")
                    if path.is_dir():
                        if directory != store.markdown.root or path.name not in _RECORD_MODELS:
                            raise RecordsExportUnavailable("non-canonical record directory")
                        pending.append(path)
                        continue
                    if path.suffix != ".md":
                        continue  # Temporary files and .bak generations are not current originals.
                    source = _safe_file(store.markdown.root, path)
                    size = source.stat().st_size
                    scanned += size
                    if (size > MAX_FILE_BYTES or scanned > MAX_TOTAL_BYTES
                            or len(records) >= 100_000):
                        raise RecordsExportTooLarge("record scan budget exceeded")
                    try:
                        metadata = _decode_metadata(dict(frontmatter.loads(
                            source.read_text(encoding="utf-8")
                        ).metadata))
                        if not _REQUIRED_RECORD_KEYS.issubset(metadata):
                            raise ValueError("incomplete record")
                        validate_schema_version(metadata)
                        model = _RECORD_MODELS[path.parent.name].model_validate(metadata)
                        if model.entity_type != path.parent.name or str(model.id) != path.stem:
                            raise ValueError("record path mismatch")
                        if str(model.id) in records:
                            raise ValueError("duplicate source id")
                    except Exception as exc:
                        raise RecordsExportUnavailable("invalid original record") from exc
                    # Retain only reference/scope metadata, not every family's large content bodies.
                    records[str(model.id)] = _Record(
                        model.model_dump(mode="json", include=_REFERENCE_FIELDS), path,
                    )

            child = str(child_id)
            profile = records.get(child)
            if profile is None or profile.metadata["entity_type"] != "child_profile":
                raise KeyError("child_not_found")
            grants = {row.metadata["source_id"] for row in records.values()
                      if row.metadata["entity_type"] == "entity_link"
                      and row.metadata.get("relation") == "child_scope"
                      and row.metadata.get("target_id") == child}

            def visible(identifier: str) -> bool:
                row = records.get(identifier)
                return row is not None and (
                    row.metadata.get("child_id") == child or identifier in grants
                    or (row.metadata["entity_type"] == "resource"
                        and row.metadata.get("child_id") is None)
                )

            def in_period(row: _Record) -> bool:
                if start_date is None and end_date is None:
                    return True
                moment = record_time(row.metadata)
                if moment is None:
                    return False
                event = moment.astimezone().date()
                return (start_date is None or event >= start_date) and (
                    end_date is None or event <= end_date
                )

            selected = {identifier for identifier, row in records.items()
                        if row.metadata["entity_type"] in _EXPORTABLE
                        and visible(identifier) and in_period(row)}
            primary = set(selected)
            selected.add(child)  # A profile provides context even when created outside the period.
            photos_by_log: dict[str, set[str]] = {}
            for identifier, row in records.items():
                meta = row.metadata
                if meta["entity_type"] == "photo_activity_record" and meta.get("learning_log_id"):
                    photos_by_log.setdefault(meta["learning_log_id"], set()).add(identifier)
                elif meta["entity_type"] == "entity_link" and (
                    meta.get("relation") == "documents" and meta.get("source_id") in records
                    and records[meta["source_id"]].metadata["entity_type"]
                    == "photo_activity_record"
                ):
                    photos_by_log.setdefault(meta["target_id"], set()).add(meta["source_id"])
            pending_ids = list(selected)
            while pending_ids:
                budget()
                if len(selected) >= MAX_MEMBERS:
                    raise RecordsExportTooLarge("too many selected records")
                current_id = pending_ids.pop()
                metadata = records[current_id].metadata
                refs = [metadata.get(key) for key in (
                    "book_id", "activity_plan_id", "parent_material_id", "learning_log_id",
                )]
                refs.extend(ref.partition(":")[2] for ref in metadata.get("source_refs", []))
                refs.extend(photos_by_log.get(current_id, set()))
                for reference_id in refs:
                    if reference_id and reference_id not in selected and visible(reference_id) and (
                        records[reference_id].metadata["entity_type"] in _EXPORTABLE
                    ):
                        selected.add(reference_id)
                        pending_ids.append(reference_id)

            assets: dict[str, tuple[_Record, str]] = {}
            for identifier in list(selected):
                metadata = records[identifier].metadata
                ids = list(metadata.get("photo_asset_ids", []))
                if metadata.get("avatar_asset_id"):
                    ids.append(metadata["avatar_asset_id"])
                for asset_id in ids:
                    asset = records.get(asset_id)
                    if asset is None or asset.metadata["entity_type"] != "photo_asset" or (
                        asset.metadata.get("child_id") != metadata.get("child_id", child)
                    ):
                        raise RecordsExportUnavailable("asset ownership mismatch")
                    relative = asset.metadata["relative_path"]
                    BackupService._portable_member_key(f"assets/{relative}")
                    _safe_file(assets_root, assets_root / relative)
                    assets[asset_id] = (asset, relative)
                    selected.add(asset_id)
            for identifier, row in records.items():
                meta = row.metadata
                if meta["entity_type"] == "entity_link" and (
                    meta.get("source_id") in selected and meta.get("target_id") in selected
                ):
                    selected.add(identifier)

            files: list[tuple[str, Path, dict | None]] = [
                     (f"records/{records[i].path.relative_to(store.markdown.root).as_posix()}",
                      _safe_file(store.markdown.root, records[i].path), None)
                     for i in sorted(selected)]
            files.extend((f"assets/{relative}", _safe_file(assets_root, assets_root / relative),
                          asset.metadata) for asset, relative in assets.values())
            names = [MANIFEST_NAME, *(name for name, _, _ in files)]
            if len(names) > MAX_MEMBERS:
                raise RecordsExportTooLarge("too many archive members")
            BackupService._validate_portable_member_names(names)
            destination.touch(exist_ok=False)
            _make_private_file(destination)
            total = 0
            hashes = {}
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, source, asset_metadata in files:
                    budget()
                    if source.stat().st_size > MAX_FILE_BYTES:
                        raise RecordsExportTooLarge("source file too large")
                    digest = hashlib.sha256()
                    size = 0
                    with source.open("rb") as original, archive.open(name, "w") as output:
                        while block := original.read(64 * 1024):
                            budget()
                            size += len(block)
                            total += len(block)
                            if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                                raise RecordsExportTooLarge("export size budget exceeded")
                            digest.update(block)
                            output.write(block)
                    if asset_metadata and (size != asset_metadata["byte_size"]
                                           or digest.hexdigest() != asset_metadata["sha256"]):
                        raise RecordsExportUnavailable("asset integrity mismatch")
                    hashes[name] = digest.hexdigest()
                manifest = {"format": "growwise-selected-records", "format_version": 1,
                            "full_backup": False, "restorable_by_app": False, "child_id": child,
                            "start_date": str(start_date) if start_date else None,
                            "end_date": str(end_date) if end_date else None,
                            "created_at": datetime.now(UTC).isoformat(),
                            "record_count": len(selected), "asset_count": len(assets),
                            "supporting_record_ids": sorted(selected - primary - {child}),
                            "sha256": hashes}
                data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
                if len(data) > 4 * 1024 * 1024 or total + len(data) > MAX_TOTAL_BYTES:
                    raise RecordsExportTooLarge("manifest budget exceeded")
                archive.writestr(MANIFEST_NAME, data)
            if destination.stat().st_size > MAX_ARCHIVE_BYTES:
                raise RecordsExportTooLarge("archive budget exceeded")
            return manifest
