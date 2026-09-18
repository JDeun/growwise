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

_SQLITE_IN_CHUNK = 400


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
    claim_token: str | None = None


class JobQueue(Protocol):
    def enqueue(self, job_type: str, payload: dict) -> Job: ...

    def claim_next(
        self,
        *,
        job_types: tuple[str, ...] | None = None,
        lease_seconds: int = 3600,
        max_attempts: int = 3,
        now: datetime | None = None,
    ) -> Job | None: ...

    def heartbeat(
        self,
        job_id: UUID,
        claim_token: str,
        *,
        lease_seconds: int = 3600,
        now: datetime | None = None,
    ) -> bool: ...

    def complete(self, job_id: UUID, claim_token: str) -> bool: ...

    def retry(self, job_id: UUID, claim_token: str, error: str) -> bool: ...

    def fail(self, job_id: UUID, claim_token: str, error: str) -> bool: ...

    def cancel(self, job_id: UUID) -> None: ...


class SQLiteJobQueue:
    """Local durable queue with leased, fenced claims.

    Each RUNNING attempt owns a unique claim token. Expired work can therefore be reclaimed after
    process/worker failure without allowing the old worker to heartbeat, retry, complete, or fail a
    newer claim of the same durable job (the lease ABA problem).
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
                    lease_expires_at TEXT,
                    claim_token TEXT
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "lease_expires_at" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN lease_expires_at TEXT")
            if "claim_token" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN claim_token TEXT")
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
            claim_token=row["claim_token"],
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
                    lease_expires_at, claim_token
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
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

    def get(self, job_id: UUID | str) -> Job | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (str(job_id),),
            ).fetchone()
        return None if row is None else self._row_to_job(row)

    def _requeue_expired(
        self,
        connection: sqlite3.Connection,
        *,
        now_iso: str,
        max_attempts: int,
    ) -> None:
        connection.execute(
            """
            UPDATE jobs
            SET status = ?, started_at = NULL, updated_at = ?, lease_expires_at = NULL,
                claim_token = NULL,
                last_error = COALESCE(last_error, 'worker lease expired; job returned to pending')
            WHERE status = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
              AND attempts < ?
            """,
            (JobStatus.PENDING, now_iso, JobStatus.RUNNING, now_iso, max_attempts),
        )
        connection.execute(
            """
            UPDATE jobs
            SET status = ?, finished_at = ?, updated_at = ?, lease_expires_at = NULL,
                claim_token = NULL,
                last_error = COALESCE(last_error, 'job lease expired after maximum attempts')
            WHERE status = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
              AND attempts >= ?
            """,
            (JobStatus.FAILED, now_iso, now_iso, JobStatus.RUNNING, now_iso, max_attempts),
        )

    def claim_next(
        self,
        *,
        job_types: tuple[str, ...] | None = None,
        lease_seconds: int = 3600,
        max_attempts: int = 3,
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
        lease_expires_at = (current + timedelta(seconds=lease_seconds)).isoformat()
        claim_token = str(uuid7())

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._requeue_expired(
                connection,
                now_iso=now_iso,
                max_attempts=max_attempts,
            )
            if job_types:
                placeholders = ",".join("?" for _ in job_types)
                row = connection.execute(
                    f"SELECT * FROM jobs WHERE status = ? AND attempts < ? "
                    f"AND job_type IN ({placeholders}) ORDER BY created_at ASC LIMIT 1",
                    (JobStatus.PENDING, max_attempts, *job_types),
                ).fetchone()
            else:
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
                    lease_expires_at = ?, claim_token = ?, finished_at = NULL
                WHERE id = ? AND status = ?
                """,
                (
                    JobStatus.RUNNING,
                    now_iso,
                    now_iso,
                    lease_expires_at,
                    claim_token,
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
        return None if updated is None else self._row_to_job(updated)

    def recover_running(
        self,
        *,
        job_type: str | None = None,
        max_attempts: int = 3,
    ) -> int:
        """Recover jobs orphaned by a previous Core process.

        The owning worker calls this during application startup. The claim token is cleared before a
        recovered job can be claimed again, which also fences any surviving stale worker.
        """
        now = utc_now_iso()
        clauses = ["status = ?"]
        params: list[object] = [JobStatus.RUNNING]
        if job_type is not None:
            clauses.append("job_type = ?")
            params.append(job_type)
        where = " AND ".join(clauses)
        with self._connect() as connection:
            failed = connection.execute(
                f"""
                UPDATE jobs
                SET status = ?, finished_at = ?, updated_at = ?, lease_expires_at = NULL,
                    claim_token = NULL,
                    last_error = COALESCE(last_error, 'job interrupted before completion')
                WHERE {where} AND attempts >= ?
                """,
                (JobStatus.FAILED, now, now, *params, max_attempts),
            ).rowcount
            recovered = connection.execute(
                f"""
                UPDATE jobs
                SET status = ?, started_at = NULL, updated_at = ?, lease_expires_at = NULL,
                    claim_token = NULL
                WHERE {where} AND attempts < ?
                """,
                (JobStatus.PENDING, now, *params, max_attempts),
            ).rowcount
        return recovered + failed

    def heartbeat(
        self,
        job_id: UUID,
        claim_token: str,
        *,
        lease_seconds: int = 3600,
        now: datetime | None = None,
    ) -> bool:
        if lease_seconds <= 0:
            raise ValueError("job lease must be positive")
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        current = current.astimezone(UTC)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs SET updated_at = ?, lease_expires_at = ?
                WHERE id = ? AND status = ? AND claim_token = ?
                """,
                (
                    current.isoformat(),
                    (current + timedelta(seconds=lease_seconds)).isoformat(),
                    str(job_id),
                    JobStatus.RUNNING,
                    claim_token,
                ),
            )
            return cursor.rowcount == 1

    def complete(self, job_id: UUID, claim_token: str) -> bool:
        now = utc_now_iso()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, updated_at = ?, last_error = NULL,
                    lease_expires_at = NULL, claim_token = NULL
                WHERE id = ? AND status = ? AND claim_token = ?
                """,
                (
                    JobStatus.COMPLETED,
                    now,
                    now,
                    str(job_id),
                    JobStatus.RUNNING,
                    claim_token,
                ),
            )
            return cursor.rowcount == 1

    def retry(self, job_id: UUID, claim_token: str, error: str) -> bool:
        now = utc_now_iso()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, started_at = NULL, finished_at = NULL, updated_at = ?,
                    last_error = ?, lease_expires_at = NULL, claim_token = NULL
                WHERE id = ? AND status = ? AND claim_token = ?
                """,
                (
                    JobStatus.PENDING,
                    now,
                    error[:2000],
                    str(job_id),
                    JobStatus.RUNNING,
                    claim_token,
                ),
            )
            return cursor.rowcount == 1

    def fail(self, job_id: UUID, claim_token: str, error: str) -> bool:
        now = utc_now_iso()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, updated_at = ?, last_error = ?,
                    lease_expires_at = NULL, claim_token = NULL
                WHERE id = ? AND status = ? AND claim_token = ?
                """,
                (
                    JobStatus.FAILED,
                    now,
                    now,
                    error[:2000],
                    str(job_id),
                    JobStatus.RUNNING,
                    claim_token,
                ),
            )
            return cursor.rowcount == 1

    def cancel(self, job_id: UUID) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, updated_at = ?, lease_expires_at = NULL,
                    claim_token = NULL
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

    def delete_for_child(self, child_id: str) -> int:
        """Remove jobs explicitly owned by one child without matching arbitrary payload text."""
        with self._connect() as connection:
            rows = connection.execute("SELECT id, payload_json FROM jobs").fetchall()
            owned_job_ids: list[str] = []
            for row in rows:
                try:
                    payload = json.loads(row["payload_json"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("child_id") or "") == child_id:
                    owned_job_ids.append(str(row["id"]))

            if not owned_job_ids:
                return 0
            deleted = 0
            for offset in range(0, len(owned_job_ids), _SQLITE_IN_CHUNK):
                chunk = owned_job_ids[offset : offset + _SQLITE_IN_CHUNK]
                placeholders = ",".join("?" for _ in chunk)
                cursor = connection.execute(
                    f"DELETE FROM jobs WHERE id IN ({placeholders})",
                    tuple(chunk),
                )
                deleted += cursor.rowcount
        return deleted


    def reset(self) -> int:
        """Delete all operational jobs after a destructive data-generation restore."""

        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM jobs")
        return cursor.rowcount
