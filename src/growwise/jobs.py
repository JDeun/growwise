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


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


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

    def claim_next(
        self,
        *,
        job_types: tuple[str, ...] | None = None,
        lease_seconds: int = 3600,
    ) -> Job | None: ...

    def complete(self, job_id: UUID) -> None: ...

    def fail(self, job_id: UUID, error: str) -> None: ...

    def cancel(self, job_id: UUID) -> None: ...


class SQLiteJobQueue:
    """Local durable queue for background work without requiring Redis.

    GrowWise runs one local Core process, so jobs can be processed serially without an external
    broker. A lease protects against a worker disappearing while the process is still alive, and
    ``recover_running`` lets a fresh Core process reclaim jobs that were interrupted by shutdown.
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
                str(row[1])
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "lease_expires_at" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN lease_expires_at TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_created "
                "ON jobs(status, created_at)"
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
                    id, job_type, payload_json, status, attempts, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
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

    def _requeue_expired(self, connection: sqlite3.Connection, *, max_attempts: int) -> None:
        now = utc_now_iso()
        connection.execute(
            """
            UPDATE jobs
            SET status = ?, started_at = NULL, updated_at = ?, lease_expires_at = NULL
            WHERE status = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
              AND attempts < ?
            """,
            (JobStatus.PENDING, now, JobStatus.RUNNING, now, max_attempts),
        )
        connection.execute(
            """
            UPDATE jobs
            SET status = ?, finished_at = ?, updated_at = ?, lease_expires_at = NULL,
                last_error = COALESCE(last_error, 'job lease expired after maximum attempts')
            WHERE status = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
              AND attempts >= ?
            """,
            (JobStatus.FAILED, now, now, JobStatus.RUNNING, now, max_attempts),
        )

    def claim_next(
        self,
        *,
        job_types: tuple[str, ...] | None = None,
        lease_seconds: int = 3600,
        max_attempts: int = 3,
    ) -> Job | None:
        now = datetime.now(UTC)
        now_iso = now.isoformat()
        lease_expires_at = (now + timedelta(seconds=max(1, lease_seconds))).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._requeue_expired(connection, max_attempts=max_attempts)
            if job_types:
                placeholders = ",".join("?" for _ in job_types)
                row = connection.execute(
                    f"SELECT * FROM jobs WHERE status = ? AND job_type IN ({placeholders}) "
                    "ORDER BY created_at ASC LIMIT 1",
                    (JobStatus.PENDING, *job_types),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1",
                    (JobStatus.PENDING,),
                ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, attempts = attempts + 1, started_at = ?, updated_at = ?,
                    lease_expires_at = ?, finished_at = NULL
                WHERE id = ? AND status = ?
                """,
                (
                    JobStatus.RUNNING,
                    now_iso,
                    now_iso,
                    lease_expires_at,
                    row["id"],
                    JobStatus.PENDING,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (row["id"],),
            ).fetchone()
            connection.commit()
        if updated is None:
            return None
        return self._row_to_job(updated)

    def recover_running(
        self,
        *,
        job_type: str | None = None,
        max_attempts: int = 3,
    ) -> int:
        """Recover jobs orphaned by a previous Core process.

        This should be called once by the owning worker during application startup, not by every
        queue instance. Jobs that already exhausted their retry budget become failed instead of
        looping forever.
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
                    last_error = COALESCE(last_error, 'job interrupted before completion')
                WHERE {where} AND attempts >= ?
                """,
                (JobStatus.FAILED, now, now, *params, max_attempts),
            ).rowcount
            recovered = connection.execute(
                f"""
                UPDATE jobs
                SET status = ?, started_at = NULL, updated_at = ?, lease_expires_at = NULL
                WHERE {where} AND attempts < ?
                """,
                (JobStatus.PENDING, now, *params, max_attempts),
            ).rowcount
        return recovered + failed

    def heartbeat(self, job_id: UUID, *, lease_seconds: int = 3600) -> None:
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET updated_at = ?, lease_expires_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    now.isoformat(),
                    (now + timedelta(seconds=max(1, lease_seconds))).isoformat(),
                    str(job_id),
                    JobStatus.RUNNING,
                ),
            )

    def complete(self, job_id: UUID) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, updated_at = ?, last_error = NULL,
                    lease_expires_at = NULL
                WHERE id = ?
                """,
                (JobStatus.COMPLETED, now, now, str(job_id)),
            )

    def fail(self, job_id: UUID, error: str) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, updated_at = ?, last_error = ?,
                    lease_expires_at = NULL
                WHERE id = ?
                """,
                (JobStatus.FAILED, now, now, error[:2000], str(job_id)),
            )

    def cancel(self, job_id: UUID) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, updated_at = ?, lease_expires_at = NULL
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
        """Remove queued or completed jobs whose structured payload references one child UUID."""
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM jobs WHERE payload_json LIKE ?",
                (f"%{child_id}%",),
            )
        return cursor.rowcount
