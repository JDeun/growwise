import json
import sqlite3
from uuid import uuid4

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



def test_delete_for_child_chunks_below_sqlite_variable_ceiling(tmp_path) -> None:
    class LowVariableJobQueue(SQLiteJobQueue):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 512)
            return connection

    path = tmp_path / "jobs.sqlite3"
    queue = LowVariableJobQueue(path)
    target_child_id = str(uuid4())
    other_child_id = str(uuid4())
    connection = sqlite3.connect(path)
    try:
        rows = [
            (
                str(uuid4()),
                "background_note",
                json.dumps({"child_id": target_child_id}),
                "pending",
                0,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            )
            for _ in range(600)
        ]
        rows.append(
            (
                str(uuid4()),
                "background_note",
                json.dumps({"child_id": other_child_id}),
                "pending",
                0,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            )
        )
        connection.executemany(
            """
            INSERT INTO jobs (
                id, job_type, payload_json, status, attempts, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
    finally:
        connection.close()

    assert queue.delete_for_child(target_child_id) == 600
    connection = sqlite3.connect(path)
    try:
        remaining = connection.execute("SELECT payload_json FROM jobs").fetchall()
    finally:
        connection.close()
    assert len(remaining) == 1
    assert json.loads(remaining[0][0])["child_id"] == other_child_id
