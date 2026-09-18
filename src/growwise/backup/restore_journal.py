from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from growwise.storage.sqlite import SQLiteProjection

RESTORE_JOURNAL_NAME = ".growwise-restore-journal.json"
_MAX_JOURNAL_BYTES = 64 * 1024


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


class RestoreJournal(BaseModel):
    version: int = 1
    phase: Literal["prepared", "committed"] = "prepared"
    records_root: str
    index_path: str
    records_transaction: str
    had_records: bool
    assets_root: str | None = None
    assets_transaction: str | None = None
    had_assets: bool = False
    conversations_path: str | None = None
    conversations_transaction: str | None = None
    had_conversations: bool = False


class RestoreJournalManager:
    """Crash-recovery journal for the multi-path authoritative restore swap.

    Recovery always rolls an interrupted restore back to the pre-restore generation. Temporary
    rollback directories intentionally live beside each state root so each individual replace stays
    on one filesystem.
    """

    def __init__(
        self,
        *,
        records_root: Path,
        index_path: Path,
        assets_root: Path | None,
        conversations_path: Path | None,
    ) -> None:
        self.records_root = records_root.absolute()
        self.index_path = index_path.absolute()
        self.assets_root = assets_root.absolute() if assets_root is not None else None
        self.conversations_path = (
            conversations_path.absolute() if conversations_path is not None else None
        )
        self.path = self.records_root.parent / RESTORE_JOURNAL_NAME

    def begin(
        self,
        *,
        records_transaction: Path,
        assets_transaction: Path | None,
        conversations_transaction: Path | None,
    ) -> None:
        journal = RestoreJournal(
            records_root=str(self.records_root),
            index_path=str(self.index_path),
            records_transaction=str(records_transaction.absolute()),
            had_records=self.records_root.exists(),
            assets_root=str(self.assets_root) if self.assets_root is not None else None,
            assets_transaction=(
                str(assets_transaction.absolute()) if assets_transaction is not None else None
            ),
            had_assets=self.assets_root.exists() if self.assets_root is not None else False,
            conversations_path=(
                str(self.conversations_path) if self.conversations_path is not None else None
            ),
            conversations_transaction=(
                str(conversations_transaction.absolute())
                if conversations_transaction is not None
                else None
            ),
            had_conversations=(
                self.conversations_path.exists() if self.conversations_path is not None else False
            ),
        )
        self._write(journal)

    def _write(self, journal: RestoreJournal) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = journal.model_dump_json(indent=2).encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
            _fsync_directory(self.path.parent)
        finally:
            Path(tmp_name).unlink(missing_ok=True)

    def mark_committed(self) -> None:
        journal = self._read()
        self._validate_targets(journal)
        self._write(journal.model_copy(update={"phase": "committed"}))

    def finalize(self) -> None:
        if not self.path.exists():
            return
        journal = self._read()
        self._validate_targets(journal)
        if journal.phase != "committed":
            raise RuntimeError("cannot finalize an uncommitted restore journal")
        self._cleanup_transactions(journal)
        try:
            self.path.unlink()
        except OSError:
            # The committed journal is safe to retry on next startup; never turn an already
            # committed authoritative restore into an ambiguous API failure because cleanup failed.
            return
        _fsync_directory(self.path.parent)

    def recover_if_needed(self) -> bool:
        if not self.path.exists():
            return False
        journal = self._read()
        self._validate_targets(journal)
        if journal.phase == "committed":
            self._cleanup_transactions(journal)
            try:
                self.path.unlink()
            except OSError:
                return True
            _fsync_directory(self.path.parent)
        else:
            self._rollback(journal)
        return True

    def rollback(self) -> None:
        if not self.path.exists():
            return
        journal = self._read()
        self._validate_targets(journal)
        if journal.phase == "committed":
            self.finalize()
            return
        self._rollback(journal)

    def _read(self) -> RestoreJournal:
        raw = self.path.read_bytes()
        if len(raw) > _MAX_JOURNAL_BYTES:
            raise RuntimeError("restore recovery journal is too large")
        try:
            payload = json.loads(raw)
            journal = RestoreJournal.model_validate(payload)
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("restore recovery journal is invalid") from exc
        if journal.version != 1:
            raise RuntimeError(f"unsupported restore recovery journal version={journal.version}")
        return journal

    @staticmethod
    def _validated_transaction(
        raw: str | None,
        *,
        parent: Path,
        prefix: str,
    ) -> Path | None:
        if raw is None:
            return None
        transaction = Path(raw)
        if transaction.parent.resolve() != parent.resolve():
            raise RuntimeError("restore recovery transaction escaped its expected parent")
        if not transaction.name.startswith(prefix):
            raise RuntimeError("restore recovery transaction has an unexpected name")
        if transaction.is_symlink():
            raise RuntimeError("restore recovery transaction must not be a symlink")
        return transaction

    def _validate_targets(self, journal: RestoreJournal) -> None:
        if Path(journal.records_root).absolute() != self.records_root:
            raise RuntimeError("restore recovery records target does not match current settings")
        if Path(journal.index_path).absolute() != self.index_path:
            raise RuntimeError("restore recovery index target does not match current settings")

        expected_assets = str(self.assets_root) if self.assets_root is not None else None
        if journal.assets_root != expected_assets:
            raise RuntimeError("restore recovery assets target does not match current settings")
        if self.assets_root is None:
            if journal.assets_transaction is not None or journal.had_assets:
                raise RuntimeError("restore recovery journal has unexpected asset state")
        elif journal.assets_transaction is None:
            raise RuntimeError("restore recovery journal is missing its asset transaction")

        expected_conversations = (
            str(self.conversations_path) if self.conversations_path is not None else None
        )
        if journal.conversations_path != expected_conversations:
            raise RuntimeError(
                "restore recovery conversation target does not match current settings"
            )
        if self.conversations_path is None:
            if journal.conversations_transaction is not None or journal.had_conversations:
                raise RuntimeError("restore recovery journal has unexpected conversation state")
        elif journal.conversations_transaction is None:
            raise RuntimeError("restore recovery journal is missing its conversation transaction")

        self._validated_transaction(
            journal.records_transaction,
            parent=self.records_root.parent,
            prefix="growwise-restore-",
        )
        if self.assets_root is not None:
            self._validated_transaction(
                journal.assets_transaction,
                parent=self.assets_root.parent,
                prefix="growwise-assets-restore-",
            )
        if self.conversations_path is not None:
            self._validated_transaction(
                journal.conversations_transaction,
                parent=self.conversations_path.parent,
                prefix="growwise-conversations-restore-",
            )

    @staticmethod
    def _rollback_directory(
        *,
        live: Path,
        transaction: Path,
        ready_name: str,
        previous_name: str,
        had_live: bool,
    ) -> None:
        ready = transaction / ready_name
        previous = transaction / previous_name
        if had_live:
            if previous.exists():
                if live.exists():
                    shutil.rmtree(live)
                previous.replace(live)
        elif not ready.exists() and live.exists():
            shutil.rmtree(live)

    @staticmethod
    def _unlink_sqlite_family(path: Path) -> None:
        for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
            candidate.unlink(missing_ok=True)

    @classmethod
    def _rollback_file(
        cls,
        *,
        live: Path,
        transaction: Path,
        ready_name: str,
        previous_name: str,
        had_live: bool,
    ) -> None:
        ready = transaction / ready_name
        previous = transaction / previous_name
        if had_live:
            if previous.exists():
                cls._unlink_sqlite_family(live)
                previous.replace(live)
        elif not ready.exists() and live.exists():
            cls._unlink_sqlite_family(live)

    def _cleanup_transactions(self, journal: RestoreJournal) -> None:
        transactions = [
            self._validated_transaction(
                journal.records_transaction,
                parent=self.records_root.parent,
                prefix="growwise-restore-",
            )
        ]
        if self.assets_root is not None:
            transactions.append(
                self._validated_transaction(
                    journal.assets_transaction,
                    parent=self.assets_root.parent,
                    prefix="growwise-assets-restore-",
                )
            )
        if self.conversations_path is not None:
            transactions.append(
                self._validated_transaction(
                    journal.conversations_transaction,
                    parent=self.conversations_path.parent,
                    prefix="growwise-conversations-restore-",
                )
            )
        for transaction in transactions:
            if transaction is not None:
                shutil.rmtree(transaction, ignore_errors=True)

    def _rollback(self, journal: RestoreJournal) -> None:
        records_transaction = self._validated_transaction(
            journal.records_transaction,
            parent=self.records_root.parent,
            prefix="growwise-restore-",
        )
        assert records_transaction is not None
        self._rollback_directory(
            live=self.records_root,
            transaction=records_transaction,
            ready_name="records-ready",
            previous_name="previous-records",
            had_live=journal.had_records,
        )

        transactions: list[Path] = [records_transaction]
        if self.assets_root is not None:
            assets_transaction = self._validated_transaction(
                journal.assets_transaction,
                parent=self.assets_root.parent,
                prefix="growwise-assets-restore-",
            )
            assert assets_transaction is not None
            self._rollback_directory(
                live=self.assets_root,
                transaction=assets_transaction,
                ready_name="assets-ready",
                previous_name="previous-assets",
                had_live=journal.had_assets,
            )
            transactions.append(assets_transaction)

        if self.conversations_path is not None:
            conversations_transaction = self._validated_transaction(
                journal.conversations_transaction,
                parent=self.conversations_path.parent,
                prefix="growwise-conversations-restore-",
            )
            assert conversations_transaction is not None
            self._rollback_file(
                live=self.conversations_path,
                transaction=conversations_transaction,
                ready_name="conversations-ready.sqlite3",
                previous_name="previous-conversations.sqlite3",
                had_live=journal.had_conversations,
            )
            transactions.append(conversations_transaction)

        SQLiteProjection(self.index_path).rebuild(self.records_root)

        for transaction in transactions:
            shutil.rmtree(transaction, ignore_errors=True)
        try:
            self.path.unlink()
        except FileNotFoundError:
            return
        _fsync_directory(self.path.parent)
