import json
import sqlite3
from uuid import UUID, uuid4

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



def test_delete_for_child_chunks_large_job_set_below_sqlite_limit(tmp_path) -> None:
    class LowVariableJobQueue(SQLiteJobQueue):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 512)
            return connection

    path = tmp_path / "jobs.sqlite3"
    queue = LowVariableJobQueue(path)
    child_id = str(uuid4())
    survivor_id = str(uuid4())
    rows = [
        (
            str(uuid4()),
            "bulk-test",
            json.dumps({"child_id": child_id}),
            "pending",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        )
        for _ in range(1_200)
    ]
    rows.append(
        (
            survivor_id,
            "bulk-test",
            json.dumps({"child_id": str(uuid4())}),
            "pending",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        )
    )
    with sqlite3.connect(path) as connection:
        connection.executemany(
            """
            INSERT INTO jobs (
                id, job_type, payload_json, status, attempts, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    assert queue.delete_for_child(child_id) == 1_200
    assert queue.get(UUID(survivor_id)) is not None
