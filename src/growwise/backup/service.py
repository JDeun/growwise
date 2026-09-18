from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from collections.abc import Mapping
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
    # v2 adds portable SQLite state snapshots. v1 archives remain readable; they simply have no
    # state_files and callers must apply their legacy-state policy after restore.
    format_version: int = 2
    schema_version: int = CURRENT_SCHEMA_VERSION
    created_at: datetime
    record_count: int
    asset_count: int = 0
    state_files: tuple[str, ...] = ()


class BackupService:
    """Portable backup/restore for authoritative Markdown and managed local assets."""

    MANIFEST_NAME = "manifest.json"
    MAX_ARCHIVE_MEMBERS = 100_001
    MAX_MANIFEST_BYTES = 256 * 1024
    MAX_SINGLE_FILE_BYTES = 16 * 1024 * 1024
    MAX_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
    MAX_STATE_FILE_BYTES = MAX_TOTAL_UNCOMPRESSED_BYTES

    def create(
        self,
        *,
        records_root: Path,
        destination: Path,
        assets_root: Path | None = None,
        sqlite_state: Mapping[str, Path] | None = None,
    ) -> BackupManifest:
        destination.parent.mkdir(parents=True, exist_ok=True)

        # A backup that GrowWise creates must also satisfy the semantic rules enforced during
        # restore. Local .bak/temp recovery artifacts are not archived, but every current Markdown
        # Source-of-Truth record is validated before publication.
        actual_record_count = self._validate_records(records_root, strict_extras=False)
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

        with tempfile.TemporaryDirectory(
            prefix="growwise-backup-state-",
            dir=destination.parent,
        ) as state_temp_name:
            state_temp = Path(state_temp_name)
            state_snapshots: list[tuple[str, Path]] = []
            for name, source in sorted((sqlite_state or {}).items()):
                self._validate_state_name(name)
                snapshot = state_temp / name
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                self._snapshot_sqlite(source, snapshot)
                self._validate_sqlite_snapshot(snapshot)
                state_snapshots.append((name, snapshot))

            manifest = BackupManifest(
                created_at=datetime.now(UTC),
                record_count=len(records),
                asset_count=len(assets),
                state_files=tuple(name for name, _ in state_snapshots),
            )
            manifest_bytes = json.dumps(
                manifest.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self._validate_create_inputs(
                files=[*records, *assets],
                state_files=[path for _, path in state_snapshots],
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
                    for name, path in state_snapshots:
                        archive.write(path, f"state/{name}")
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
        sqlite_state: Mapping[str, Path] | None = None,
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

            state_destinations = dict(sqlite_state or {})
            expected_state = set(manifest.state_files)
            staged_state = staging / "state"
            actual_state = (
                {path.name for path in staged_state.iterdir() if path.is_file()}
                if staged_state.exists()
                else set()
            )
            if actual_state != expected_state:
                raise InvalidBackup(
                    "manifest state files do not match archive contents: "
                    f"expected {sorted(expected_state)}, got {sorted(actual_state)}"
                )
            missing_destinations = expected_state - set(state_destinations)
            if missing_destinations:
                raise InvalidBackup(
                    "backup contains portable state without a restore destination: "
                    + ", ".join(sorted(missing_destinations))
                )
            for name in expected_state:
                self._validate_state_name(name)
                self._validate_sqlite_snapshot(staged_state / name)

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
                    shutil.copytree(staged_assets, assets_ready)
                else:
                    assets_ready.mkdir(parents=True)

            previous_state_dir = staging / "previous-state"
            previous_state_dir.mkdir(parents=True, exist_ok=True)
            previous_state: dict[str, Path | None] = {}
            for name in expected_state:
                destination = state_destinations[name]
                if destination.exists():
                    snapshot = previous_state_dir / name
                    self._snapshot_sqlite(destination, snapshot)
                    previous_state[name] = snapshot
                else:
                    previous_state[name] = None

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

                for name in sorted(expected_state):
                    self._restore_sqlite_snapshot(
                        staged_state / name,
                        state_destinations[name],
                    )

                SQLiteProjection(index_path).rebuild(records_root)
            except Exception:
                for name, previous in previous_state.items():
                    destination = state_destinations[name]
                    if previous is None:
                        self._remove_sqlite_files(destination)
                    else:
                        self._restore_sqlite_snapshot(previous, destination)

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
        if manifest.format_version not in {1, 2}:
            raise InvalidBackup(f"unsupported format_version={manifest.format_version}")
        if manifest.format_version == 1 and manifest.state_files:
            raise InvalidBackup("format_version=1 cannot declare portable state files")
        validate_schema_version({"schema_version": manifest.schema_version})
        return manifest

    @classmethod
    def _validate_create_inputs(
        cls,
        *,
        files: list[Path],
        state_files: list[Path],
        manifest_size: int,
    ) -> None:
        """Apply restore-time archive limits before publishing a GrowWise backup."""

        member_count = 1 + len(files) + len(state_files)
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
        for path in state_files:
            size = path.stat().st_size
            if size > cls.MAX_STATE_FILE_BYTES:
                raise InvalidBackup(f"backup state file is too large: {path.name}")
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
            is_state = bool(path.parts and path.parts[0] == "state")
            member_limit = cls.MAX_STATE_FILE_BYTES if is_state else cls.MAX_SINGLE_FILE_BYTES
            if info.file_size > member_limit:
                raise InvalidBackup(f"backup member is too large: {info.filename}")
            total_size += info.file_size
            if total_size > cls.MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise InvalidBackup("backup archive expands beyond the allowed size")

            if info.filename == cls.MANIFEST_NAME:
                manifest_count += 1
                if info.file_size > cls.MAX_MANIFEST_BYTES:
                    raise InvalidBackup("backup manifest is too large")
                continue
            if not path.parts or path.parts[0] not in {"records", "assets", "state"}:
                raise InvalidBackup(f"unexpected archive member: {info.filename}")
            if path.parts[0] == "state" and len(path.parts) != 2:
                raise InvalidBackup(f"invalid state archive member: {info.filename}")

        if manifest_count != 1:
            raise InvalidBackup("backup archive must contain exactly one manifest.json")

    @staticmethod
    def _validate_state_name(name: str) -> None:
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or "\x00" in name
            or path.is_absolute()
            or len(path.parts) != 1
            or path.name != name
            or path.suffix != ".sqlite3"
        ):
            raise InvalidBackup(f"invalid portable state filename: {name!r}")

    @staticmethod
    def _snapshot_sqlite(source: Path, destination: Path) -> None:
        source.parent.mkdir(parents=True, exist_ok=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(source, timeout=30.0) as source_connection:
            with sqlite3.connect(destination, timeout=30.0) as destination_connection:
                source_connection.backup(destination_connection)

    @staticmethod
    def _restore_sqlite_snapshot(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(source, timeout=30.0) as source_connection:
            with sqlite3.connect(destination, timeout=30.0) as destination_connection:
                source_connection.backup(destination_connection)

    @staticmethod
    def _validate_sqlite_snapshot(path: Path) -> None:
        try:
            uri = f"{path.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=30.0) as connection:
                row = connection.execute("PRAGMA quick_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise InvalidBackup(f"portable state is not a valid SQLite database: {path.name}") from exc
        if row is None or row[0] != "ok":
            raise InvalidBackup(f"portable state failed SQLite integrity check: {path.name}")

    @staticmethod
    def _remove_sqlite_files(path: Path) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{path}{suffix}").unlink(missing_ok=True)

    @staticmethod
    def _validate_records(records_root: Path, *, strict_extras: bool = True) -> int:
        try:
            return validate_record_tree(records_root, strict_extras=strict_extras)
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
