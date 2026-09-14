from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


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


class SQLiteIdempotencyStore:
    """Durable registry for retry-safe and concurrency-safe create operations.

    A create request first claims a key with a deterministic resource ID. Concurrent callers using
    the same key and payload observe the existing pending claim instead of repeating side effects.
    The owner marks the claim completed only after the resource is durably stored. If work fails,
    the pending claim can be released so a later retry may safely acquire it again.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
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
    ) -> IdempotencyClaim:
        if not key.strip():
            raise ValueError("idempotency key must not be empty")
        now = datetime.now(UTC).isoformat()
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
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "idempotency key was already used for a different request"
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
                    now,
                    IdempotencyStatus.PENDING,
                    now,
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
                created_at=now,
                status=IdempotencyStatus.PENDING,
                updated_at=now,
            ),
            acquired=True,
        )

    def complete(
        self,
        *,
        key: str,
        request_hash: str,
        resource_id: str,
    ) -> IdempotencyRecord:
        now = datetime.now(UTC).isoformat()
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
                (IdempotencyStatus.COMPLETED, now, key),
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
            updated_at=now,
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
            resource_id=resource_id,
        )
