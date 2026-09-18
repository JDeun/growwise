import json
import sqlite3
from uuid import uuid4

import pytest

from growwise.jobs import SQLiteJobQueue


def test_delete_for_child_matches_structured_owner_only(tmp_path) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    target_child_id = str(uuid4())
    other_child_id = str(uuid4())

    owned = queue.enqueue(
        "photo_activity_analysis",
        {"child_id": target_child_id, "record_id": "owned-record"},
    )
    incidental = queue.enqueue(
        "background_note",
        {
            "child_id": other_child_id,
            "note": f"parent text happens to mention {target_child_id}",
        },
    )
    unrelated = queue.enqueue(
        "background_note",
        {"child_id": other_child_id, "note": "unrelated"},
    )

    assert queue.delete_for_child(target_child_id) == 1
    assert queue.get(owned.id) is None
    assert queue.get(incidental.id) is not None
    assert queue.get(unrelated.id) is not None



def test_delete_for_child_uses_single_indexed_delete_without_payload_scan(tmp_path) -> None:
    statements: list[str] = []

    class TracedJobQueue(SQLiteJobQueue):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.set_trace_callback(statements.append)
            return connection

    path = tmp_path / "jobs.sqlite3"
    queue = TracedJobQueue(path)
    target_child_id = str(uuid4())
    other_child_id = str(uuid4())

    with sqlite3.connect(path) as connection:
        connection.executemany(
            """
            INSERT INTO jobs (
                id, job_type, child_id, payload_json, status, attempts, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(uuid4()),
                    "background_note",
                    target_child_id,
                    "{malformed-but-ownership-is-indexed",
                    "pending",
                    0,
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                )
                for _ in range(1_200)
            ]
            + [
                (
                    str(uuid4()),
                    "background_note",
                    other_child_id,
                    json.dumps({"child_id": other_child_id}),
                    "pending",
                    0,
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                )
            ],
        )

    statements.clear()
    assert queue.delete_for_child(target_child_id) == 1_200

    deletes = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("DELETE FROM JOBS WHERE CHILD_ID")
    ]
    assert len(deletes) == 1
    with sqlite3.connect(path) as connection:
        remaining = connection.execute(
            "SELECT child_id FROM jobs"
        ).fetchall()
    assert remaining == [(other_child_id,)]


def test_existing_job_table_backfills_indexed_child_owner(tmp_path) -> None:
    path = tmp_path / "legacy-jobs.sqlite3"
    target_child_id = str(uuid4())
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE jobs (
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
            """
            INSERT INTO jobs (
                id, job_type, payload_json, status, attempts, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                "background_note",
                json.dumps({"child_id": target_child_id}),
                "pending",
                0,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )

    queue = SQLiteJobQueue(path)

    with sqlite3.connect(path) as connection:
        child_id = connection.execute("SELECT child_id FROM jobs").fetchone()[0]
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(jobs)").fetchall()
        }
    assert child_id == target_child_id
    assert "idx_jobs_child_id" in indexes
    assert queue.delete_for_child(target_child_id) == 1



def test_job_owner_backfill_is_not_repeated_for_global_jobs(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "jobs.sqlite3"
    queue = SQLiteJobQueue(path)
    queue.enqueue("global-job", {"resource_id": "resource-1"})

    def forbid_payload_parse(_value: str) -> object:
        raise AssertionError("existing child_id column must skip legacy payload backfill")

    monkeypatch.setattr("growwise.jobs.json.loads", forbid_payload_parse)

    SQLiteJobQueue(path)
