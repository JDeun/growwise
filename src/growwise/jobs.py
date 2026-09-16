from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID

from uuid6 import uuid7


DEFAULT_JOB_LEASE_SECONDS = 300
DEFAULT_JOB_MAX_ATTEMPTS = 5


def utc_now_iso(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Job:
    id: UUID
    job_type: str
    payload: dict
    status: JobStatus
    attempts: int
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    last_error: str | None = None
    lease_expires_at: str | None = None


class JobQueue(Protocol):
    def enqueue(self, job_type: str, payload: dict) -> Job: ...

    def claim_next(self) -> Job | None: ...

    def heartbeat(self, job_id: UUID) -> bool: ...

    def complete(self, job_id: UUID) -> None: ...

    def fail(self, job_id: UUID, error: str) -> None: ...

    def cancel(self, job_id: UUID) -> None: ...


class SQLiteJobQueue:
    """Local durable queue for background work without requiring Redis.

    Running jobs carry a lease. A process crash therefore cannot strand a job in RUNNING forever:
    the next claimant first returns expired leases to PENDING, preserving the attempt counter and
    applying a bounded retry policy.
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
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    last_error TEXT,
                    lease_expires_at TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "lease_expires_at" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN lease_expires_at TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_created "
                "ON jobs(status, created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_lease "
                "ON jobs(status, lease_expires_at)"
            )

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=UUID(row["id"]),
            job_type=row["job_type"],
            payload=json.loads(row["payload_json"]),
            status=JobStatus(row["status"]),
            attempts=row["attempts"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            last_error=row["last_error"],
            lease_expires_at=row["lease_expires_at"],
        )

    def enqueue(self, job_type: str, payload: dict) -> Job:
        now = utc_now_iso()
        job = Job(
            id=uuid7(),
            job_type=job_type,
            payload=payload,
            status=JobStatus.PENDING,
            attempts=0,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, job_type, payload_json, status, attempts, created_at, updated_at,
                    lease_expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    str(job.id),
                    job.job_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    job.status,
                    job.attempts,
                    job.created_at,
                    job.updated_at,
                ),
            )
        return job

    def _requeue_stale_locked(
        self,
        connection: sqlite3.Connection,
        *,
        now_iso: str,
        max_attempts: int,
    ) -> None:
        # Expired work below the retry ceiling becomes claimable again. Work that already consumed
        # the retry budget is terminally failed so it cannot spin forever after repeated crashes.
        connection.execute(
            """
            UPDATE jobs
            SET status = ?, started_at = NULL, lease_expires_at = NULL,
                updated_at = ?, last_error = ?
            WHERE status = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
              AND attempts < ?
            """,
            (
                JobStatus.PENDING,
                now_iso,
                "worker lease expired; job returned to pending",
                JobStatus.RUNNING,
                now_iso,
                max_attempts,
            ),
        )
        connection.execute(
            """
            UPDATE jobs
            SET status = ?, finished_at = ?, lease_expires_at = NULL,
                updated_at = ?, last_error = ?
            WHERE status = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
              AND attempts >= ?
            """,
            (
                JobStatus.FAILED,
                now_iso,
                now_iso,
                "worker lease expired after maximum attempts",
                JobStatus.RUNNING,
                now_iso,
                max_attempts,
            ),
        )

    def claim_next(
        self,
        *,
        lease_seconds: int = DEFAULT_JOB_LEASE_SECONDS,
        max_attempts: int = DEFAULT_JOB_MAX_ATTEMPTS,
        now: datetime | None = None,
    ) -> Job | None:
        if lease_seconds <= 0:
            raise ValueError("job lease must be positive")
        if max_attempts <= 0:
            raise ValueError("job max_attempts must be positive")

        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        current = current.astimezone(UTC)
        now_iso = current.isoformat()
        lease_expires = (current + timedelta(seconds=lease_seconds)).isoformat()

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._requeue_stale_locked(
                connection,
                now_iso=now_iso,
                max_attempts=max_attempts,
            )
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = ? AND attempts < ? "
                "ORDER BY created_at ASC LIMIT 1",
                (JobStatus.PENDING, max_attempts),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, attempts = attempts + 1, started_at = ?, updated_at = ?,
                    finished_at = NULL, lease_expires_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    JobStatus.RUNNING,
                    now_iso,
                    now_iso,
                    lease_expires,
                    row["id"],
                    JobStatus.PENDING,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return None
            updated = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (row["id"],),
            ).fetchone()
            connection.commit()
        if updated is None:
            return None
        return self._row_to_job(updated)

    def heartbeat(
        self,
        job_id: UUID,
        *,
        lease_seconds: int = DEFAULT_JOB_LEASE_SECONDS,
        now: datetime | None = None,
    ) -> bool:
        if lease_seconds <= 0:
            raise ValueError("job lease must be positive")
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        current = current.astimezone(UTC)
        now_iso = current.isoformat()
        lease_expires = (current + timedelta(seconds=lease_seconds)).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs SET updated_at = ?, lease_expires_at = ?
                WHERE id = ? AND status = ?
                """,
                (now_iso, lease_expires, str(job_id), JobStatus.RUNNING),
            )
            return cursor.rowcount == 1

    def complete(self, job_id: UUID) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = ?, finished_at = ?, updated_at = ?,
                    last_error = NULL, lease_expires_at = NULL
                WHERE id = ? AND status = ?
                """,
                (JobStatus.COMPLETED, now, now, str(job_id), JobStatus.RUNNING),
            )

    def fail(self, job_id: UUID, error: str) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = ?, finished_at = ?, updated_at = ?, last_error = ?,
                    lease_expires_at = NULL
                WHERE id = ? AND status = ?
                """,
                (JobStatus.FAILED, now, now, error[:2000], str(job_id), JobStatus.RUNNING),
            )

    def cancel(self, job_id: UUID) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = ?, finished_at = ?, updated_at = ?,
                    lease_expires_at = NULL
                WHERE id = ? AND status IN (?, ?)
                """,
                (
                    JobStatus.CANCELLED,
                    now,
                    now,
                    str(job_id),
                    JobStatus.PENDING,
                    JobStatus.RUNNING,
                ),
            )
