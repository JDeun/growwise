from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import unicodedata
import zipfile
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

from growwise.backup.record_validation import InvalidRecordTree, validate_record_tree
from growwise.services.conversation_store import SQLiteConversationStore
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
    # v2 adds portable conversation state. v1 archives remain readable and are restored with an
    # empty conversation store so post-backup conversations cannot leak across the time boundary.
    format_version: int = 1
    schema_version: int = CURRENT_SCHEMA_VERSION
    created_at: datetime
    record_count: int
    asset_count: int = 0
    conversation_count: int = 0


class BackupService:
    """Portable backup/restore for Markdown, managed assets, and durable conversation state."""

    MANIFEST_NAME = "manifest.json"
    CONVERSATIONS_STATE_NAME = "state/conversations.sqlite3"
    MAX_ARCHIVE_MEMBERS = 100_001
    MAX_MANIFEST_BYTES = 256 * 1024
    MAX_SINGLE_FILE_BYTES = 16 * 1024 * 1024
    MAX_STATE_FILE_BYTES = 256 * 1024 * 1024
    MAX_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
    _WINDOWS_INVALID_CHARS = frozenset('<>:"|?*')
    _WINDOWS_RESERVED_NAMES = frozenset(
        {"con", "prn", "aux", "nul"}
        | {f"com{index}" for index in range(1, 10)}
        | {f"lpt{index}" for index in range(1, 10)}
    )

    def create(
        self,
        *,
        records_root: Path,
        destination: Path,
        assets_root: Path | None = None,
        conversations_path: Path | None = None,
    ) -> BackupManifest:
        destination.parent.mkdir(parents=True, exist_ok=True)

        # A backup that GrowWise creates must also satisfy the semantic rules enforced during
        # restore. Validate the authoritative tree before publication instead of creating an
        # archive that will only be rejected later when the user needs it most.
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
        conversation_snapshot: Path | None = None
        conversation_count = 0
        if conversations_path is not None:
            state_fd, state_name = tempfile.mkstemp(
                prefix=".growwise-conversations-",
                suffix=".sqlite3",
                dir=destination.parent,
            )
            os.close(state_fd)
            conversation_snapshot = Path(state_name)
            conversation_snapshot.unlink(missing_ok=True)
            try:
                if conversations_path.exists():
                    conversation_count = SQLiteConversationStore(conversations_path).snapshot_to(
                        conversation_snapshot
                    )
                else:
                    empty_store = SQLiteConversationStore(conversation_snapshot)
                    conversation_count = empty_store.validate_snapshot(conversation_snapshot)
            except Exception:
                conversation_snapshot.unlink(missing_ok=True)
                raise

        manifest = BackupManifest(
            format_version=2 if conversations_path is not None else 1,
            created_at=datetime.now(UTC),
            record_count=len(records),
            asset_count=len(assets),
            conversation_count=conversation_count,
        )
        manifest_bytes = json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        member_names = [
            self.MANIFEST_NAME,
            *(f"records/{path.relative_to(records_root).as_posix()}" for path in records),
            *(
                f"assets/{path.relative_to(assets_root).as_posix()}"
                for path in assets
                if assets_root is not None
            ),
        ]
        if conversation_snapshot is not None:
            member_names.append(self.CONVERSATIONS_STATE_NAME)
        try:
            self._validate_create_inputs(
                files=[*records, *assets],
                state_files=[conversation_snapshot] if conversation_snapshot is not None else [],
                member_names=member_names,
                manifest_size=len(manifest_bytes),
            )
        except Exception:
            if conversation_snapshot is not None:
                conversation_snapshot.unlink(missing_ok=True)
            raise

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
                if conversation_snapshot is not None:
                    archive.write(conversation_snapshot, self.CONVERSATIONS_STATE_NAME)
            with Path(tmp_name).open("r+b") as handle:
                os.fsync(handle.fileno())
            Path(tmp_name).replace(destination)
            _fsync_directory(destination.parent)
        finally:
            Path(tmp_name).unlink(missing_ok=True)
            if conversation_snapshot is not None:
                conversation_snapshot.unlink(missing_ok=True)
        return manifest

    def validate_archive(self, archive_path: Path) -> BackupManifest:
        """Fully validate a backup archive without mutating active application state."""

        if not archive_path.is_file():
            raise FileNotFoundError(archive_path)

        with tempfile.TemporaryDirectory(prefix="growwise-backup-preflight-") as temp_dir:
            staging = Path(temp_dir)
            try:
                with zipfile.ZipFile(archive_path, "r") as archive:
                    self._validate_members(archive)
                    manifest = self._read_manifest(archive)
                    archive.extractall(staging)
            except zipfile.BadZipFile as exc:
                raise InvalidBackup("backup archive is not a valid ZIP file") from exc

            staged_records = staging / "records"
            actual_record_count = self._validate_records(staged_records)
            if actual_record_count != manifest.record_count:
                raise InvalidBackup(
                    "manifest record count does not match archive contents: "
                    f"expected {manifest.record_count}, got {actual_record_count}"
                )

            staged_assets = staging / "assets"
            actual_asset_count = self._validate_assets(staged_assets)
            if actual_asset_count != manifest.asset_count:
                raise InvalidBackup(
                    "manifest asset count does not match archive contents: "
                    f"expected {manifest.asset_count}, got {actual_asset_count}"
                )

            staged_conversations = staging / self.CONVERSATIONS_STATE_NAME
            if manifest.format_version == 2:
                if not staged_conversations.is_file():
                    raise InvalidBackup("backup v2 is missing conversation state")
                try:
                    actual_conversation_count = SQLiteConversationStore.validate_snapshot(
                        staged_conversations
                    )
                except ValueError as exc:
                    raise InvalidBackup(str(exc)) from exc
                if actual_conversation_count != manifest.conversation_count:
                    raise InvalidBackup(
                        "manifest conversation count does not match archive contents: "
                        f"expected {manifest.conversation_count}, got {actual_conversation_count}"
                    )
            elif staged_conversations.exists():
                raise InvalidBackup("backup v1 must not contain conversation state")

            return manifest

    def restore(
        self,
        *,
        archive_path: Path,
        records_root: Path,
        index_path: Path,
        assets_root: Path | None = None,
        conversations_path: Path | None = None,
    ) -> BackupManifest:
        if not archive_path.is_file():
            raise FileNotFoundError(archive_path)

        records_staging_parent = records_root.parent
        records_staging_parent.mkdir(parents=True, exist_ok=True)
        if assets_root is not None:
            assets_root.parent.mkdir(parents=True, exist_ok=True)
        if conversations_path is not None:
            conversations_path.parent.mkdir(parents=True, exist_ok=True)

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

            staged_conversations = staging / self.CONVERSATIONS_STATE_NAME
            if manifest.format_version == 2:
                if not staged_conversations.is_file():
                    raise InvalidBackup("backup v2 is missing conversation state")
                try:
                    actual_conversation_count = SQLiteConversationStore.validate_snapshot(
                        staged_conversations
                    )
                except ValueError as exc:
                    raise InvalidBackup(str(exc)) from exc
                if actual_conversation_count != manifest.conversation_count:
                    raise InvalidBackup(
                        "manifest conversation count does not match archive contents: "
                        f"expected {manifest.conversation_count}, got {actual_conversation_count}"
                    )
                if conversations_path is None:
                    raise InvalidBackup(
                        "backup contains conversation state but no conversation "
                        "destination was provided"
                    )
            elif staged_conversations.exists():
                raise InvalidBackup("backup v1 must not contain conversation state")

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

            conversations_ready: Path | None = None
            previous_conversations: Path | None = None
            conversations_transaction: Path | None = None
            if conversations_path is not None:
                conversations_temp_dir = stack.enter_context(
                    tempfile.TemporaryDirectory(
                        prefix="growwise-conversations-restore-",
                        dir=conversations_path.parent,
                    )
                )
                conversations_transaction = Path(conversations_temp_dir)
                conversations_ready = conversations_transaction / "conversations-ready.sqlite3"
                previous_conversations = (
                    conversations_transaction / "previous-conversations.sqlite3"
                )
                if manifest.format_version == 2:
                    shutil.copy2(staged_conversations, conversations_ready)
                else:
                    SQLiteConversationStore(conversations_ready)
                try:
                    ready_count = SQLiteConversationStore.validate_snapshot(conversations_ready)
                except ValueError as exc:
                    raise InvalidBackup(str(exc)) from exc
                if ready_count != manifest.conversation_count:
                    raise InvalidBackup(
                        "prepared conversation count does not match manifest: "
                        f"expected {manifest.conversation_count}, got {ready_count}"
                    )

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
            moved_conversations = False
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

                if conversations_path is not None:
                    assert conversations_ready is not None
                    assert previous_conversations is not None
                    if conversations_path.exists():
                        conversations_path.replace(previous_conversations)
                        moved_conversations = True
                    conversations_ready.replace(conversations_path)

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

                if conversations_path is not None:
                    assert previous_conversations is not None
                    conversations_path.unlink(missing_ok=True)
                    if moved_conversations and previous_conversations.exists():
                        previous_conversations.replace(conversations_path)

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
        validate_schema_version({"schema_version": manifest.schema_version})
        return manifest

    @classmethod
    def _validate_create_inputs(
        cls,
        *,
        files: list[Path],
        state_files: list[Path],
        member_names: list[str],
        manifest_size: int,
    ) -> None:
        """Apply restore-time archive limits before publishing a GrowWise backup."""

        cls._validate_portable_member_names(member_names)
        member_count = len(member_names)
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
    def _portable_member_key(cls, filename: str) -> str:
        if "\\" in filename or "\x00" in filename:
            raise InvalidBackup(f"unsafe archive member: {filename}")

        raw = filename[:-1] if filename.endswith("/") else filename
        raw_parts = raw.split("/")
        if not raw or any(part in {"", ".", ".."} for part in raw_parts):
            raise InvalidBackup(f"unsafe archive member: {filename}")

        path = PurePosixPath(filename)
        if path.is_absolute() or ".." in path.parts:
            raise InvalidBackup(f"unsafe archive member: {filename}")

        normalized_parts: list[str] = []
        for part in path.parts:
            normalized = unicodedata.normalize("NFC", part)
            if normalized != normalized.rstrip(" ."):
                raise InvalidBackup(f"non-portable archive member: {filename}")
            if any(ord(char) < 32 or char in cls._WINDOWS_INVALID_CHARS for char in normalized):
                raise InvalidBackup(f"non-portable archive member: {filename}")
            device_name = normalized.split(".", 1)[0].casefold()
            if device_name in cls._WINDOWS_RESERVED_NAMES:
                raise InvalidBackup(f"non-portable archive member: {filename}")
            normalized_parts.append(normalized.casefold())
        return "/".join(normalized_parts)

    @classmethod
    def _validate_portable_member_names(cls, member_names: list[str]) -> None:
        seen: dict[str, str] = {}
        for filename in member_names:
            key = cls._portable_member_key(filename)
            previous = seen.get(key)
            if previous is not None:
                if previous == filename:
                    raise InvalidBackup(f"duplicate archive member: {filename}")
                raise InvalidBackup(
                    "archive members collide on a portable filesystem: "
                    f"{previous!r} and {filename!r}"
                )
            seen[key] = filename

    @classmethod
    def _validate_members(cls, archive: zipfile.ZipFile) -> None:
        members = archive.infolist()
        if len(members) > cls.MAX_ARCHIVE_MEMBERS:
            raise InvalidBackup("backup archive contains too many members")

        total_size = 0
        cls._validate_portable_member_names([info.filename for info in members])
        manifest_count = 0
        for info in members:
            path = PurePosixPath(info.filename)
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if unix_mode and stat.S_ISLNK(unix_mode):
                raise InvalidBackup(f"symlink archive member is not allowed: {info.filename}")
            size_limit = (
                cls.MAX_STATE_FILE_BYTES
                if info.filename == cls.CONVERSATIONS_STATE_NAME
                else cls.MAX_SINGLE_FILE_BYTES
            )
            if info.file_size > size_limit:
                raise InvalidBackup(f"backup member is too large: {info.filename}")
            total_size += info.file_size
            if total_size > cls.MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise InvalidBackup("backup archive expands beyond the allowed size")

            if info.filename == cls.MANIFEST_NAME:
                manifest_count += 1
                if info.file_size > cls.MAX_MANIFEST_BYTES:
                    raise InvalidBackup("backup manifest is too large")
                continue
            if info.filename == cls.CONVERSATIONS_STATE_NAME:
                continue
            if not path.parts or path.parts[0] not in {"records", "assets"}:
                raise InvalidBackup(f"unexpected archive member: {info.filename}")

        if manifest_count != 1:
            raise InvalidBackup("backup archive must contain exactly one manifest.json")

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
