from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class IdempotencyConflict(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: str
    request_hash: str
    resource_type: str
    resource_id: str
    created_at: str


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
    """Durable key registry for retry-safe create operations."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
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
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def get(self, key: str) -> IdempotencyRecord | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT key, request_hash, resource_type, resource_id, created_at "
                "FROM idempotency_records WHERE key = ?",
                (key,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        return IdempotencyRecord(**dict(row))

    def record(
        self,
        *,
        key: str,
        request_hash: str,
        resource_type: str,
        resource_id: str,
    ) -> IdempotencyRecord:
        if not key.strip():
            raise ValueError("idempotency key must not be empty")
        created_at = datetime.now(UTC).isoformat()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_row = connection.execute(
                "SELECT key, request_hash, resource_type, resource_id, created_at "
                "FROM idempotency_records WHERE key = ?",
                (key,),
            ).fetchone()
            if existing_row is not None:
                existing = IdempotencyRecord(**dict(existing_row))
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "idempotency key was already used for a different request"
                    )
                connection.commit()
                return existing

            connection.execute(
                "INSERT INTO idempotency_records "
                "(key, request_hash, resource_type, resource_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, request_hash, resource_type, resource_id, created_at),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return IdempotencyRecord(
            key=key,
            request_hash=request_hash,
            resource_type=resource_type,
            resource_id=resource_id,
            created_at=created_at,
        )
