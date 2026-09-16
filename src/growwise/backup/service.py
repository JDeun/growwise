from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import frontmatter
from pydantic import BaseModel

from growwise.storage.schema import CURRENT_SCHEMA_VERSION, validate_schema_version
from growwise.storage.sqlite import SQLiteProjection


class InvalidBackup(ValueError):
    pass


class BackupManifest(BaseModel):
    format_version: int = 1
    schema_version: int = CURRENT_SCHEMA_VERSION
    created_at: datetime
    record_count: int


class BackupService:
    """Portable backup/restore for the authoritative Markdown record set."""

    MANIFEST_NAME = "manifest.json"
    MAX_ARCHIVE_MEMBERS = 100_001
    MAX_SINGLE_FILE_BYTES = 16 * 1024 * 1024
    MAX_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024

    def create(self, *, records_root: Path, destination: Path) -> BackupManifest:
        destination.parent.mkdir(parents=True, exist_ok=True)
        records = sorted(path for path in records_root.rglob("*.md") if path.is_file())
        manifest = BackupManifest(
            created_at=datetime.now(UTC),
            record_count=len(records),
        )

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        os.close(fd)
        Path(tmp_name).unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(tmp_name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    self.MANIFEST_NAME,
                    json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
                )
                for path in records:
                    relative = path.relative_to(records_root).as_posix()
                    archive.write(path, f"records/{relative}")
            Path(tmp_name).replace(destination)
        finally:
            Path(tmp_name).unlink(missing_ok=True)
        return manifest

    def restore(
        self,
        *,
        archive_path: Path,
        records_root: Path,
        index_path: Path,
    ) -> BackupManifest:
        if not archive_path.is_file():
            raise FileNotFoundError(archive_path)

        staging_parent = records_root.parent
        staging_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="growwise-restore-",
            dir=staging_parent,
        ) as temp_dir:
            staging = Path(temp_dir)
            try:
                with zipfile.ZipFile(archive_path, "r") as archive:
                    manifest = self._read_manifest(archive)
                    self._validate_members(archive)
                    archive.extractall(staging)
            except zipfile.BadZipFile as exc:
                raise InvalidBackup("backup archive is not a valid ZIP file") from exc

            staged_records = staging / "records"
            actual_count = self._validate_records(staged_records)
            if actual_count != manifest.record_count:
                raise InvalidBackup(
                    "manifest record count does not match archive contents: "
                    f"expected {manifest.record_count}, got {actual_count}"
                )

            restore_source = staging / "records-ready"
            if staged_records.exists():
                shutil.copytree(staged_records, restore_source)
            else:
                restore_source.mkdir(parents=True)

            # Keep the rollback copy INSIDE the temporary restore directory. It exists only for
            # the duration of this transaction and is therefore removed automatically after a
            # successful restore instead of leaving sensitive records.pre-restore-* directories.
            previous = staging / "previous-records"
            moved_previous = False
            try:
                if records_root.exists():
                    records_root.replace(previous)
                    moved_previous = True
                restore_source.replace(records_root)
                SQLiteProjection(index_path).rebuild(records_root)
            except Exception:
                if records_root.exists():
                    shutil.rmtree(records_root, ignore_errors=True)
                if moved_previous and previous.exists():
                    previous.replace(records_root)
                    SQLiteProjection(index_path).rebuild(records_root)
                raise

        return manifest

    def _read_manifest(self, archive: zipfile.ZipFile) -> BackupManifest:
        try:
            payload = json.loads(archive.read(self.MANIFEST_NAME))
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidBackup("missing or invalid backup manifest") from exc
        manifest = BackupManifest.model_validate(payload)
        if manifest.format_version != 1:
            raise InvalidBackup(f"unsupported backup format_version={manifest.format_version}")
        validate_schema_version({"schema_version": manifest.schema_version})
        return manifest

    @classmethod
    def _validate_members(cls, archive: zipfile.ZipFile) -> None:
        members = archive.infolist()
        if len(members) > cls.MAX_ARCHIVE_MEMBERS:
            raise InvalidBackup("backup archive contains too many members")

        total_size = 0
        for info in members:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise InvalidBackup(f"unsafe archive member: {info.filename}")
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if unix_mode and stat.S_ISLNK(unix_mode):
                raise InvalidBackup(f"symlink archive member is not allowed: {info.filename}")
            if info.file_size > cls.MAX_SINGLE_FILE_BYTES:
                raise InvalidBackup(f"backup member is too large: {info.filename}")
            total_size += info.file_size
            if total_size > cls.MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise InvalidBackup("backup archive expands beyond the allowed size")
            if info.filename == cls.MANIFEST_NAME:
                continue
            if not path.parts or path.parts[0] != "records":
                raise InvalidBackup(f"unexpected archive member: {info.filename}")

    @staticmethod
    def _validate_records(records_root: Path) -> int:
        count = 0
        if not records_root.exists():
            return count
        for path in records_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix != ".md":
                raise InvalidBackup(f"unexpected record file: {path.name}")
            try:
                post = frontmatter.load(path)
                payload = dict(post.metadata)
                required = {"id", "entity_type", "schema_version", "created_at", "updated_at"}
                if not required.issubset(payload):
                    raise InvalidBackup(f"record metadata incomplete: {path.name}")
                validate_schema_version(payload)
            except InvalidBackup:
                raise
            except Exception as exc:
                raise InvalidBackup(f"invalid Markdown record: {path.name}") from exc
            count += 1
        return count
