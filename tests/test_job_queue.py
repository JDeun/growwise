import json
import sqlite3
from uuid import uuid4

from growwise.jobs import JobStatus, SQLiteJobQueue


def test_sqlite_job_queue_round_trip(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")

    created = queue.enqueue("reindex", {"child_id": "child-1"})
    assert created.status is JobStatus.PENDING

    claimed = queue.claim_next()
    assert claimed is not None
    assert claimed.id == created.id
    assert claimed.status is JobStatus.RUNNING
    assert claimed.attempts == 1
    assert claimed.payload["child_id"] == "child-1"
    assert claimed.claim_token is not None

    assert queue.complete(claimed.id, claimed.claim_token) is True
    assert queue.claim_next() is None


def test_failed_job_is_not_reclaimed(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    queue.enqueue("embed", {"resource_id": "r1"})

    claimed = queue.claim_next()
    assert claimed is not None
    assert claimed.claim_token is not None
    assert queue.fail(claimed.id, claimed.claim_token, "boom") is True

    assert queue.claim_next() is None



def test_delete_for_child_scales_beyond_sqlite_variable_limit(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    queue = SQLiteJobQueue(path)
    child_id = "child-many-jobs"

    with sqlite3.connect(path) as connection:
        connection.executemany(
            """
            INSERT INTO jobs (
                id, job_type, payload_json, status, attempts, created_at, updated_at,
                started_at, finished_at, last_error, lease_expires_at, claim_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(uuid4()),
                    "bulk-test",
                    json.dumps({"child_id": child_id, "index": index}),
                    "pending",
                    0,
                    "2026-09-18T00:00:00+00:00",
                    "2026-09-18T00:00:00+00:00",
                    None,
                    None,
                    None,
                    None,
                    None,
                )
                for index in range(1_200)
            ],
        )

    assert queue.delete_for_child(child_id) == 1_200
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
