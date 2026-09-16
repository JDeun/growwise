from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any


DEFAULT_IDEMPOTENCY_LEASE_SECONDS = 300


class IdempotencyConflict(ValueError):
    pass


class IdempotencyStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: str
    request_hash: str
    resource_type: str
    resource_id: str
    created_at: str
    status: IdempotencyStatus = IdempotencyStatus.COMPLETED
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    record: IdempotencyRecord
    acquired: bool


def request_fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class SQLiteIdempotencyStore:
    """Durable registry for retry-safe and concurrency-safe create operations.

    A create request first claims a key with a deterministic resource ID. Concurrent callers using
    the same key and payload observe the existing pending claim instead of repeating side effects.
    A pending claim is a lease, not a permanent lock: after its lease expires a later retry may
    reacquire *the same resource ID*. This closes the crash window where a process dies after
    reserving an ID (or even after writing its source record) but before marking the claim complete.

    Reacquisition intentionally never allocates a new resource ID for an existing key. Callers can
    therefore safely replay source writes without creating duplicate logical records.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_records (
                    key TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'completed',
                    updated_at TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(idempotency_records)").fetchall()
            }
            if "status" not in columns:
                connection.execute(
                    "ALTER TABLE idempotency_records "
                    "ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'"
                )
            if "updated_at" not in columns:
                connection.execute(
                    "ALTER TABLE idempotency_records ADD COLUMN updated_at TEXT"
                )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> IdempotencyRecord:
        payload = dict(row)
        payload["status"] = IdempotencyStatus(payload.get("status") or "completed")
        return IdempotencyRecord(**payload)

    def get(self, key: str) -> IdempotencyRecord | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT key, request_hash, resource_type, resource_id, created_at, "
                "status, updated_at FROM idempotency_records WHERE key = ?",
                (key,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        return self._row_to_record(row)

    def claim(
        self,
        *,
        key: str,
        request_hash: str,
        resource_type: str,
        resource_id: str,
        lease_seconds: int = DEFAULT_IDEMPOTENCY_LEASE_SECONDS,
        now: datetime | None = None,
    ) -> IdempotencyClaim:
        if not key.strip():
            raise ValueError("idempotency key must not be empty")
        if lease_seconds <= 0:
            raise ValueError("idempotency lease must be positive")

        current = _utc_now(now)
        current_iso = current.isoformat()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_row = connection.execute(
                "SELECT key, request_hash, resource_type, resource_id, created_at, "
                "status, updated_at FROM idempotency_records WHERE key = ?",
                (key,),
            ).fetchone()
            if existing_row is not None:
                existing = self._row_to_record(existing_row)
                if existing.request_hash != request_hash or existing.resource_type != resource_type:
                    raise IdempotencyConflict(
                        "idempotency key was already used for a different request"
                    )

                if existing.status is IdempotencyStatus.PENDING:
                    lease_anchor = _parse_utc(existing.updated_at or existing.created_at)
                    if current >= lease_anchor + timedelta(seconds=lease_seconds):
                        connection.execute(
                            "UPDATE idempotency_records SET updated_at = ? WHERE key = ?",
                            (current_iso, key),
                        )
                        connection.commit()
                        return IdempotencyClaim(
                            record=IdempotencyRecord(
                                key=existing.key,
                                request_hash=existing.request_hash,
                                resource_type=existing.resource_type,
                                resource_id=existing.resource_id,
                                created_at=existing.created_at,
                                status=IdempotencyStatus.PENDING,
                                updated_at=current_iso,
                            ),
                            acquired=True,
                        )

                connection.commit()
                return IdempotencyClaim(record=existing, acquired=False)

            connection.execute(
                "INSERT INTO idempotency_records "
                "(key, request_hash, resource_type, resource_id, created_at, status, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    request_hash,
                    resource_type,
                    resource_id,
                    current_iso,
                    IdempotencyStatus.PENDING,
                    current_iso,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return IdempotencyClaim(
            record=IdempotencyRecord(
                key=key,
                request_hash=request_hash,
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=current_iso,
                status=IdempotencyStatus.PENDING,
                updated_at=current_iso,
            ),
            acquired=True,
        )

    def renew(
        self,
        *,
        key: str,
        request_hash: str,
        resource_id: str,
        now: datetime | None = None,
    ) -> bool:
        """Extend a pending claim lease without changing its reserved resource ID."""
        current_iso = _utc_now(now).isoformat()
        connection = self._connect()
        try:
            cursor = connection.execute(
                "UPDATE idempotency_records SET updated_at = ? "
                "WHERE key = ? AND request_hash = ? AND resource_id = ? AND status = ?",
                (
                    current_iso,
                    key,
                    request_hash,
                    resource_id,
                    IdempotencyStatus.PENDING,
                ),
            )
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()

    def complete(
        self,
        *,
        key: str,
        request_hash: str,
        resource_id: str,
        now: datetime | None = None,
    ) -> IdempotencyRecord:
        current_iso = _utc_now(now).isoformat()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT key, request_hash, resource_type, resource_id, created_at, "
                "status, updated_at FROM idempotency_records WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                raise KeyError(f"idempotency key is not claimed: {key}")
            existing = self._row_to_record(row)
            if existing.request_hash != request_hash or existing.resource_id != resource_id:
                raise IdempotencyConflict("idempotency completion does not match the claim")
            connection.execute(
                "UPDATE idempotency_records SET status = ?, updated_at = ? WHERE key = ?",
                (IdempotencyStatus.COMPLETED, current_iso, key),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return IdempotencyRecord(
            key=existing.key,
            request_hash=existing.request_hash,
            resource_type=existing.resource_type,
            resource_id=existing.resource_id,
            created_at=existing.created_at,
            status=IdempotencyStatus.COMPLETED,
            updated_at=current_iso,
        )

    def release(
        self,
        *,
        key: str,
        request_hash: str,
        resource_id: str,
    ) -> bool:
        connection = self._connect()
        try:
            cursor = connection.execute(
                "DELETE FROM idempotency_records "
                "WHERE key = ? AND request_hash = ? AND resource_id = ? AND status = ?",
                (key, request_hash, resource_id, IdempotencyStatus.PENDING),
            )
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()

    def record(
        self,
        *,
        key: str,
        request_hash: str,
        resource_type: str,
        resource_id: str,
    ) -> IdempotencyRecord:
        """Compatibility helper for callers that already completed their side effect."""
        claim = self.claim(
            key=key,
            request_hash=request_hash,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if not claim.acquired:
            return claim.record
        return self.complete(
            key=key,
            request_hash=request_hash,
            resource_id=claim.record.resource_id,
        )
