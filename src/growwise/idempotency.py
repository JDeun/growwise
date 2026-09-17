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


class IdempotencyConflict(ValueError):
    pass


class IdempotencyStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


DEFAULT_LEASE_SECONDS = 120


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: str
    request_hash: str
    resource_type: str
    resource_id: str
    created_at: str
    status: IdempotencyStatus = IdempotencyStatus.COMPLETED
    updated_at: str | None = None
    lease_expires_at: str | None = None


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


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class SQLiteIdempotencyStore:
    """Durable registry for retry-safe and concurrency-safe create operations.

    Claims use a renewable lease instead of deleting the reservation after a failed attempt. This
    deliberately preserves the originally reserved resource ID across crashes and partial writes:
    if Markdown was committed but a downstream projection update failed, a retry reuses the same
    ID rather than creating a second authoritative record. An abandoned PENDING claim becomes
    reclaimable after its lease expires.
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
                    updated_at TEXT,
                    lease_expires_at TEXT
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
                connection.execute("ALTER TABLE idempotency_records ADD COLUMN updated_at TEXT")
            if "lease_expires_at" not in columns:
                connection.execute(
                    "ALTER TABLE idempotency_records ADD COLUMN lease_expires_at TEXT"
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
                "status, updated_at, lease_expires_at FROM idempotency_records WHERE key = ?",
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
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> IdempotencyClaim:
        if not key.strip():
            raise ValueError("idempotency key must not be empty")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")

        now_dt = datetime.now(UTC)
        now = now_dt.isoformat()
        lease_expires_at = (now_dt + timedelta(seconds=lease_seconds)).isoformat()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_row = connection.execute(
                "SELECT key, request_hash, resource_type, resource_id, created_at, "
                "status, updated_at, lease_expires_at FROM idempotency_records WHERE key = ?",
                (key,),
            ).fetchone()
            if existing_row is not None:
                existing = self._row_to_record(existing_row)
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "idempotency key was already used for a different request"
                    )
                if existing.resource_type != resource_type:
                    raise IdempotencyConflict(
                        "idempotency key was already used for a different resource type"
                    )
                if existing.status is IdempotencyStatus.COMPLETED:
                    connection.commit()
                    return IdempotencyClaim(record=existing, acquired=False)

                lease = _parse_timestamp(existing.lease_expires_at)
                if lease is not None and lease > now_dt:
                    connection.commit()
                    return IdempotencyClaim(record=existing, acquired=False)

                # Stale/abandoned PENDING claim: reacquire the SAME reserved resource ID.
                connection.execute(
                    "UPDATE idempotency_records "
                    "SET status = ?, updated_at = ?, lease_expires_at = ? WHERE key = ?",
                    (IdempotencyStatus.PENDING, now, lease_expires_at, key),
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
                        updated_at=now,
                        lease_expires_at=lease_expires_at,
                    ),
                    acquired=True,
                )

            connection.execute(
                "INSERT INTO idempotency_records "
                "(key, request_hash, resource_type, resource_id, created_at, status, updated_at, "
                "lease_expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    request_hash,
                    resource_type,
                    resource_id,
                    now,
                    IdempotencyStatus.PENDING,
                    now,
                    lease_expires_at,
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
                lease_expires_at=lease_expires_at,
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
                "status, updated_at, lease_expires_at FROM idempotency_records WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                raise KeyError(f"idempotency key is not claimed: {key}")
            existing = self._row_to_record(row)
            if existing.request_hash != request_hash or existing.resource_id != resource_id:
                raise IdempotencyConflict("idempotency completion does not match the claim")
            connection.execute(
                "UPDATE idempotency_records "
                "SET status = ?, updated_at = ?, lease_expires_at = NULL WHERE key = ?",
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
            lease_expires_at=None,
        )

    def release(
        self,
        *,
        key: str,
        request_hash: str,
        resource_id: str,
    ) -> bool:
        """Abandon a live claim without forgetting its reserved resource ID.

        The lease is expired immediately. A later retry can therefore reacquire the claim while
        preserving the same resource ID, which makes partial Markdown commits retry-safe.
        """
        now = datetime.now(UTC).isoformat()
        connection = self._connect()
        try:
            cursor = connection.execute(
                "UPDATE idempotency_records SET updated_at = ?, lease_expires_at = ? "
                "WHERE key = ? AND request_hash = ? AND resource_id = ? AND status = ?",
                (
                    now,
                    now,
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

    def delete_resources(self, resource_ids: set[str]) -> int:
        """Remove idempotency metadata for resources that were deliberately purged."""
        if not resource_ids:
            return 0
        placeholders = ",".join("?" for _ in resource_ids)
        connection = self._connect()
        try:
            cursor = connection.execute(
                f"DELETE FROM idempotency_records WHERE resource_id IN ({placeholders})",
                tuple(sorted(resource_ids)),
            )
            connection.commit()
            return cursor.rowcount
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
