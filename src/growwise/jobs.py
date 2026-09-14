from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
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


class JobQueue(Protocol):
    def enqueue(self, job_type: str, payload: dict) -> Job: ...

    def claim_next(self) -> Job | None: ...

    def complete(self, job_id: UUID) -> None: ...

    def fail(self, job_id: UUID, error: str) -> None: ...

    def cancel(self, job_id: UUID) -> None: ...


class SQLiteJobQueue:
    """Local durable queue for background work without requiring Redis."""

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
                    last_error TEXT
                )
                """
            )
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

    def claim_next(self) -> Job | None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
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
                SET status = ?, attempts = attempts + 1, started_at = ?, updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    JobStatus.RUNNING,
                    now,
                    now,
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

    def complete(self, job_id: UUID) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = ?, finished_at = ?, updated_at = ?, last_error = NULL
                WHERE id = ?
                """,
                (JobStatus.COMPLETED, now, now, str(job_id)),
            )

    def fail(self, job_id: UUID, error: str) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = ?, finished_at = ?, updated_at = ?, last_error = ?
                WHERE id = ?
                """,
                (JobStatus.FAILED, now, now, error[:2000], str(job_id)),
            )

    def cancel(self, job_id: UUID) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = ?, finished_at = ?, updated_at = ?
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
