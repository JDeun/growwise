from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import zipfile
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

from growwise.backup.record_validation import InvalidRecordTree, validate_record_tree
from growwise.storage.schema import CURRENT_SCHEMA_VERSION, validate_schema_version
from growwise.storage.sqlite import SQLiteProjection


class InvalidBackup(ValueError):
    pass


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class BackupManifest(BaseModel):
    # format_version remains 1 because assets/ is a backwards-readable extension to the archive
    # layout. Old archives omit asset_count and continue to validate with the default of zero.
    format_version: int = 1
    schema_version: int = CURRENT_SCHEMA_VERSION
    created_at: datetime
    record_count: int
    asset_count: int = 0


class BackupService:
    """Portable backup/restore for authoritative Markdown and managed local assets."""

    MANIFEST_NAME = "manifest.json"
    MAX_ARCHIVE_MEMBERS = 100_001
    MAX_MANIFEST_BYTES = 256 * 1024
    MAX_SINGLE_FILE_BYTES = 16 * 1024 * 1024
    MAX_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024

    def create(
        self,
        *,
        records_root: Path,
        destination: Path,
        assets_root: Path | None = None,
    ) -> BackupManifest:
        destination.parent.mkdir(parents=True, exist_ok=True)

        # A backup that GrowWise creates must also satisfy the semantic rules enforced during
        # restore. Validate the authoritative tree before publication instead of creating an
        # archive that will only be rejected later when the user needs it most.
        actual_record_count = self._validate_records(records_root)
        records = sorted(path for path in records_root.rglob("*.md") if path.is_file())
        if actual_record_count != len(records):
            raise InvalidBackup(
                "validated record count does not match backup source files: "
                f"expected {actual_record_count}, got {len(records)}"
            )

        if assets_root is not None:
            self._validate_assets(assets_root)
        assets = (
            sorted(
                path
                for path in assets_root.rglob("*")
                if path.is_file() and not path.is_symlink()
            )
            if assets_root is not None and assets_root.exists()
            else []
        )
        manifest = BackupManifest(
            created_at=datetime.now(UTC),
            record_count=len(records),
            asset_count=len(assets),
        )
        manifest_bytes = json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        self._validate_create_inputs(
            files=[*records, *assets],
            manifest_size=len(manifest_bytes),
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
                archive.writestr(self.MANIFEST_NAME, manifest_bytes)
                for path in records:
                    relative = path.relative_to(records_root).as_posix()
                    archive.write(path, f"records/{relative}")
                if assets_root is not None:
                    for path in assets:
                        relative = path.relative_to(assets_root).as_posix()
                        archive.write(path, f"assets/{relative}")
            with Path(tmp_name).open("r+b") as handle:
                os.fsync(handle.fileno())
            Path(tmp_name).replace(destination)
            _fsync_directory(destination.parent)
        finally:
            Path(tmp_name).unlink(missing_ok=True)
        return manifest

    def restore(
        self,
        *,
        archive_path: Path,
        records_root: Path,
        index_path: Path,
        assets_root: Path | None = None,
    ) -> BackupManifest:
        if not archive_path.is_file():
            raise FileNotFoundError(archive_path)

        records_staging_parent = records_root.parent
        records_staging_parent.mkdir(parents=True, exist_ok=True)
        if assets_root is not None:
            assets_root.parent.mkdir(parents=True, exist_ok=True)

        with ExitStack() as stack:
            records_temp_dir = stack.enter_context(
                tempfile.TemporaryDirectory(
                    prefix="growwise-restore-",
                    dir=records_staging_parent,
                )
            )
            staging = Path(records_temp_dir)
            assets_transaction: Path | None = None
            if assets_root is not None:
                assets_temp_dir = stack.enter_context(
                    tempfile.TemporaryDirectory(
                        prefix="growwise-assets-restore-",
                        dir=assets_root.parent,
                    )
                )
                assets_transaction = Path(assets_temp_dir)

            try:
                with zipfile.ZipFile(archive_path, "r") as archive:
                    # Validate metadata before inflating any member. The manifest itself has a much
                    # smaller hard limit so a hostile ZIP cannot consume memory before validation.
                    self._validate_members(archive)
                    manifest = self._read_manifest(archive)
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

            staged_assets = staging / "assets"
            actual_asset_count = self._validate_assets(staged_assets)
            if actual_asset_count != manifest.asset_count:
                raise InvalidBackup(
                    "manifest asset count does not match archive contents: "
                    f"expected {manifest.asset_count}, got {actual_asset_count}"
                )
            if manifest.asset_count and assets_root is None:
                raise InvalidBackup(
                    "backup contains assets but no managed asset destination was provided"
                )

            records_ready = staging / "records-ready"
            if staged_records.exists():
                shutil.copytree(staged_records, records_ready)
            else:
                records_ready.mkdir(parents=True)

            assets_ready: Path | None = None
            previous_assets: Path | None = None
            if assets_root is not None:
                assert assets_transaction is not None
                assets_ready = assets_transaction / "assets-ready"
                previous_assets = assets_transaction / "previous-assets"
                if staged_assets.exists():
                    # Copy across filesystems before any authoritative state is swapped. The later
                    # replace operations then stay within the assets filesystem and remain atomic.
                    shutil.copytree(staged_assets, assets_ready)
                else:
                    assets_ready.mkdir(parents=True)

            # Each rollback directory lives on the same filesystem as the state it protects. This
            # keeps Path.replace() atomic even when records and managed assets live on different
            # volumes (for example, local storage plus an external SSD).
            previous_records = staging / "previous-records"
            moved_records = False
            moved_assets = False
            try:
                if records_root.exists():
                    records_root.replace(previous_records)
                    moved_records = True
                records_ready.replace(records_root)

                if assets_root is not None:
                    assert assets_ready is not None
                    assert previous_assets is not None
                    if assets_root.exists():
                        assets_root.replace(previous_assets)
                        moved_assets = True
                    assets_ready.replace(assets_root)

                SQLiteProjection(index_path).rebuild(records_root)
            except Exception:
                if records_root.exists():
                    shutil.rmtree(records_root, ignore_errors=True)
                if moved_records and previous_records.exists():
                    previous_records.replace(records_root)

                if assets_root is not None:
                    assert previous_assets is not None
                    if assets_root.exists():
                        shutil.rmtree(assets_root, ignore_errors=True)
                    if moved_assets and previous_assets.exists():
                        previous_assets.replace(assets_root)

                SQLiteProjection(index_path).rebuild(records_root)
                raise

        return manifest

    def _read_manifest(self, archive: zipfile.ZipFile) -> BackupManifest:
        try:
            with archive.open(self.MANIFEST_NAME, "r") as handle:
                raw = handle.read(self.MAX_MANIFEST_BYTES + 1)
            if len(raw) > self.MAX_MANIFEST_BYTES:
                raise InvalidBackup("backup manifest is too large")
            payload = json.loads(raw)
        except InvalidBackup:
            raise
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidBackup("missing or invalid backup manifest") from exc
        manifest = BackupManifest.model_validate(payload)
        if manifest.format_version != 1:
            raise InvalidBackup(f"unsupported format_version={manifest.format_version}")
        validate_schema_version({"schema_version": manifest.schema_version})
        return manifest

    @classmethod
    def _validate_create_inputs(
        cls,
        *,
        files: list[Path],
        manifest_size: int,
    ) -> None:
        """Apply restore-time archive limits before publishing a GrowWise backup."""

        member_count = 1 + len(files)
        if member_count > cls.MAX_ARCHIVE_MEMBERS:
            raise InvalidBackup("backup source contains too many members")
        if manifest_size > cls.MAX_MANIFEST_BYTES:
            raise InvalidBackup("backup manifest is too large")

        total_size = manifest_size
        if total_size > cls.MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise InvalidBackup("backup source expands beyond the allowed size")
        for path in files:
            size = path.stat().st_size
            if size > cls.MAX_SINGLE_FILE_BYTES:
                raise InvalidBackup(f"backup source file is too large: {path.name}")
            total_size += size
            if total_size > cls.MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise InvalidBackup("backup source expands beyond the allowed size")

    @classmethod
    def _validate_members(cls, archive: zipfile.ZipFile) -> None:
        members = archive.infolist()
        if len(members) > cls.MAX_ARCHIVE_MEMBERS:
            raise InvalidBackup("backup archive contains too many members")

        total_size = 0
        seen_names: set[str] = set()
        manifest_count = 0
        for info in members:
            if info.filename in seen_names:
                raise InvalidBackup(f"duplicate archive member: {info.filename}")
            seen_names.add(info.filename)
            if "\\" in info.filename or "\x00" in info.filename:
                raise InvalidBackup(f"unsafe archive member: {info.filename}")

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
                manifest_count += 1
                if info.file_size > cls.MAX_MANIFEST_BYTES:
                    raise InvalidBackup("backup manifest is too large")
                continue
            if not path.parts or path.parts[0] not in {"records", "assets"}:
                raise InvalidBackup(f"unexpected archive member: {info.filename}")

        if manifest_count != 1:
            raise InvalidBackup("backup archive must contain exactly one manifest.json")

    @staticmethod
    def _validate_records(records_root: Path) -> int:
        try:
            return validate_record_tree(records_root)
        except InvalidRecordTree as exc:
            raise InvalidBackup(str(exc)) from exc

    @staticmethod
    def _validate_assets(assets_root: Path) -> int:
        if not assets_root.exists():
            return 0
        count = 0
        for path in assets_root.rglob("*"):
            if path.is_symlink():
                raise InvalidBackup(f"symlink asset is not allowed: {path.name}")
            if path.is_file():
                count += 1
        return count
