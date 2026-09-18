from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from functools import wraps
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Concatenate, ParamSpec, Protocol, TypeVar


class IdempotencyConflict(ValueError):
    pass


class IdempotencyStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


DEFAULT_LEASE_SECONDS = 120

_P = ParamSpec("_P")
_R = TypeVar("_R")
_S = TypeVar("_S", bound="_GenerationBound")


class _GenerationBound(Protocol):
    _data_generation: int


def _generation_fenced(
    method: Callable[Concatenate[_S, _P], _R],
) -> Callable[Concatenate[_S, _P], _R]:
    """Fence one registry operation to the data generation that created its store."""

    @wraps(method)
    def wrapped(self: _S, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        from growwise.maintenance import DATA_MAINTENANCE

        with DATA_MAINTENANCE.mutation(expected_generation=self._data_generation):
            return method(self, *args, **kwargs)

    return wrapped


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
    claim_token: str | None = None


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    record: IdempotencyRecord
    acquired: bool


@dataclass(frozen=True, slots=True)
class _ClaimContext:
    token: str | None = None
    can_reconcile: bool = False


_ACTIVE_CLAIMS: ContextVar[dict[tuple[str, str], _ClaimContext] | None] = ContextVar(
    "growwise_idempotency_active_claims",
    default=None,
)


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

    Every acquired lease also receives a fencing token. Completion and release operations from the
    current owner are conditional on that token, so an expired owner cannot mutate a newer claim
    after the same idempotency key has been reacquired (the classic ABA race). Existing route code
    can omit the token because the claim is retained in the current execution context; lower-level
    callers may pass ``claim_token`` explicitly.
    """

    def __init__(self, path: Path) -> None:
        from growwise.maintenance import DATA_MAINTENANCE

        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._context_path = str(self.path.absolute())
        self._data_generation = DATA_MAINTENANCE.generation
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _context_key(self, key: str) -> tuple[str, str]:
        return self._context_path, key

    def _set_claim_context(
        self, key: str, *, token: str | None = None, can_reconcile: bool = False
    ) -> None:
        claims = dict(_ACTIVE_CLAIMS.get() or {})
        claims[self._context_key(key)] = _ClaimContext(
            token=token,
            can_reconcile=can_reconcile,
        )
        _ACTIVE_CLAIMS.set(claims)

    def _clear_claim_context(self, key: str) -> None:
        claims = dict(_ACTIVE_CLAIMS.get() or {})
        claims.pop(self._context_key(key), None)
        _ACTIVE_CLAIMS.set(claims or None)

    def _claim_context(self, key: str) -> _ClaimContext:
        claims = _ACTIVE_CLAIMS.get() or {}
        return claims.get(self._context_key(key), _ClaimContext())

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
                    lease_expires_at TEXT,
                    claim_token TEXT
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
            if "claim_token" not in columns:
                connection.execute("ALTER TABLE idempotency_records ADD COLUMN claim_token TEXT")
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> IdempotencyRecord:
        payload = dict(row)
        payload["status"] = IdempotencyStatus(payload.get("status") or "completed")
        return IdempotencyRecord(**payload)

    @staticmethod
    def _select_record(connection: sqlite3.Connection, key: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT key, request_hash, resource_type, resource_id, created_at, "
            "status, updated_at, lease_expires_at, claim_token "
            "FROM idempotency_records WHERE key = ?",
            (key,),
        ).fetchone()

    @_generation_fenced
    def get(self, key: str) -> IdempotencyRecord | None:
        connection = self._connect()
        try:
            row = self._select_record(connection, key)
        finally:
            connection.close()
        if row is None:
            return None
        return self._row_to_record(row)

    @_generation_fenced
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

        self._clear_claim_context(key)
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat()
        lease_expires_at = (now_dt + timedelta(seconds=lease_seconds)).isoformat()
        claim_token = secrets.token_hex(16)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing_row = self._select_record(connection, key)
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
                    self._set_claim_context(key, can_reconcile=True)
                    return IdempotencyClaim(record=existing, acquired=False)

                connection.execute(
                    "UPDATE idempotency_records "
                    "SET status = ?, updated_at = ?, lease_expires_at = ?, claim_token = ? "
                    "WHERE key = ?",
                    (
                        IdempotencyStatus.PENDING,
                        now,
                        lease_expires_at,
                        claim_token,
                        key,
                    ),
                )
                connection.commit()
                record = IdempotencyRecord(
                    key=existing.key,
                    request_hash=existing.request_hash,
                    resource_type=existing.resource_type,
                    resource_id=existing.resource_id,
                    created_at=existing.created_at,
                    status=IdempotencyStatus.PENDING,
                    updated_at=now,
                    lease_expires_at=lease_expires_at,
                    claim_token=claim_token,
                )
                self._set_claim_context(key, token=claim_token)
                return IdempotencyClaim(record=record, acquired=True)

            connection.execute(
                "INSERT INTO idempotency_records "
                "(key, request_hash, resource_type, resource_id, created_at, status, updated_at, "
                "lease_expires_at, claim_token) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    request_hash,
                    resource_type,
                    resource_id,
                    now,
                    IdempotencyStatus.PENDING,
                    now,
                    lease_expires_at,
                    claim_token,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            self._clear_claim_context(key)
            raise
        finally:
            connection.close()
        record = IdempotencyRecord(
            key=key,
            request_hash=request_hash,
            resource_type=resource_type,
            resource_id=resource_id,
            created_at=now,
            status=IdempotencyStatus.PENDING,
            updated_at=now,
            lease_expires_at=lease_expires_at,
            claim_token=claim_token,
        )
        self._set_claim_context(key, token=claim_token)
        return IdempotencyClaim(record=record, acquired=True)

    @_generation_fenced
    def complete(
        self,
        *,
        key: str,
        request_hash: str,
        resource_id: str,
        claim_token: str | None = None,
    ) -> IdempotencyRecord:
        now = datetime.now(UTC).isoformat()
        context = self._claim_context(key)
        owner_token = claim_token or context.token
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = self._select_record(connection, key)
            if row is None:
                raise KeyError(f"idempotency key is not claimed: {key}")
            existing = self._row_to_record(row)
            if existing.request_hash != request_hash or existing.resource_id != resource_id:
                raise IdempotencyConflict("idempotency completion does not match the claim")
            if existing.status is IdempotencyStatus.COMPLETED:
                connection.commit()
                return existing

            if owner_token is not None:
                cursor = connection.execute(
                    "UPDATE idempotency_records "
                    "SET status = ?, updated_at = ?, lease_expires_at = NULL, claim_token = NULL "
                    "WHERE key = ? AND request_hash = ? AND resource_id = ? AND status = ? "
                    "AND claim_token = ?",
                    (
                        IdempotencyStatus.COMPLETED,
                        now,
                        key,
                        request_hash,
                        resource_id,
                        IdempotencyStatus.PENDING,
                        owner_token,
                    ),
                )
                if cursor.rowcount == 0:
                    connection.commit()
                    current = self._select_record(connection, key)
                    if current is None:
                        raise KeyError(f"idempotency key is not claimed: {key}")
                    return self._row_to_record(current)
            elif context.can_reconcile:
                connection.execute(
                    "UPDATE idempotency_records "
                    "SET status = ?, updated_at = ?, lease_expires_at = NULL, claim_token = NULL "
                    "WHERE key = ? AND request_hash = ? AND resource_id = ? AND status = ?",
                    (
                        IdempotencyStatus.COMPLETED,
                        now,
                        key,
                        request_hash,
                        resource_id,
                        IdempotencyStatus.PENDING,
                    ),
                )
            else:
                raise IdempotencyConflict("idempotency completion requires the current claim token")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
            self._clear_claim_context(key)
        return IdempotencyRecord(
            key=existing.key,
            request_hash=existing.request_hash,
            resource_type=existing.resource_type,
            resource_id=existing.resource_id,
            created_at=existing.created_at,
            status=IdempotencyStatus.COMPLETED,
            updated_at=now,
            lease_expires_at=None,
            claim_token=None,
        )

    @_generation_fenced
    def release(
        self,
        *,
        key: str,
        request_hash: str,
        resource_id: str,
        claim_token: str | None = None,
    ) -> bool:
        """Abandon a live claim without forgetting its reserved resource ID.

        The lease is expired immediately. A later retry can therefore reacquire the claim while
        preserving the same resource ID, which makes partial Markdown commits retry-safe. The
        update is fenced by the current claim token; a stale owner becomes a harmless no-op.
        """
        context = self._claim_context(key)
        owner_token = claim_token or context.token
        if owner_token is None:
            return False
        now = datetime.now(UTC).isoformat()
        connection = self._connect()
        try:
            cursor = connection.execute(
                "UPDATE idempotency_records SET updated_at = ?, lease_expires_at = ? "
                "WHERE key = ? AND request_hash = ? AND resource_id = ? AND status = ? "
                "AND claim_token = ?",
                (
                    now,
                    now,
                    key,
                    request_hash,
                    resource_id,
                    IdempotencyStatus.PENDING,
                    owner_token,
                ),
            )
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()
            self._clear_claim_context(key)

    @_generation_fenced
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

    @_generation_fenced
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
            claim_token=claim.record.claim_token,
        )


    def reset(self) -> int:
        """Delete retry metadata that belongs to the pre-restore data generation."""

        connection = self._connect()
        try:
            cursor = connection.execute("DELETE FROM idempotency_records")
            connection.commit()
            return cursor.rowcount
        finally:
            connection.close()
