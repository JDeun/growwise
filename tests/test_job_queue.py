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

    queue.complete(claimed.id)
    assert queue.claim_next() is None


def test_failed_job_is_not_reclaimed(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    created = queue.enqueue("embed", {"resource_id": "r1"})

    claimed = queue.claim_next()
    assert claimed is not None
    queue.fail(created.id, "boom")

    assert queue.claim_next() is None
