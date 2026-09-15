from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CachedPayload:
    payload: dict[str, Any]
    source: str
    attribution: str
    license_note: str
    fetched_at: datetime
    expires_at: datetime
    stale: bool


class SQLiteExternalCache:
    """Small local cache for optional public API enrichment.

    Cache keys must describe the public query only. Credentials and child identifiers must never be
    embedded in a key or payload unless the upstream public data itself contains them.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._setup()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _setup(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS external_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    attribution TEXT NOT NULL,
                    license_note TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )

    def put(
        self,
        *,
        cache_key: str,
        payload: dict[str, Any],
        source: str,
        attribution: str,
        license_note: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> CachedPayload:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")
        fetched_at = self._normalize_time(now or datetime.now(UTC))
        expires_at = fetched_at + timedelta(seconds=ttl_seconds)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO external_cache (
                    cache_key,
                    payload_json,
                    source,
                    attribution,
                    license_note,
                    fetched_at,
                    expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    source=excluded.source,
                    attribution=excluded.attribution,
                    license_note=excluded.license_note,
                    fetched_at=excluded.fetched_at,
                    expires_at=excluded.expires_at
                """,
                (
                    cache_key,
                    encoded,
                    source,
                    attribution,
                    license_note,
                    fetched_at.isoformat(),
                    expires_at.isoformat(),
                ),
            )
        return CachedPayload(
            payload=payload,
            source=source,
            attribution=attribution,
            license_note=license_note,
            fetched_at=fetched_at,
            expires_at=expires_at,
            stale=False,
        )

    def get(
        self,
        cache_key: str,
        *,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> CachedPayload | None:
        reference = self._normalize_time(now or datetime.now(UTC))
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM external_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        fetched_at = self._parse_time(row["fetched_at"])
        expires_at = self._parse_time(row["expires_at"])
        stale = expires_at <= reference
        if stale and not allow_stale:
            return None
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            return None
        return CachedPayload(
            payload=payload,
            source=row["source"],
            attribution=row["attribution"],
            license_note=row["license_note"],
            fetched_at=fetched_at,
            expires_at=expires_at,
            stale=stale,
        )

    def delete_expired(self, *, now: datetime | None = None) -> int:
        reference = self._normalize_time(now or datetime.now(UTC))
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM external_cache WHERE expires_at <= ?",
                (reference.isoformat(),),
            )
            return int(cursor.rowcount)

    @staticmethod
    def _parse_time(value: str) -> datetime:
        return SQLiteExternalCache._normalize_time(datetime.fromisoformat(value))

    @staticmethod
    def _normalize_time(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
