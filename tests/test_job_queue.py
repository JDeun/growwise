from growwise.jobs import JobStatus, SQLiteJobQueue


def _token(job) -> str:
    assert job.claim_token is not None
    return job.claim_token


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

    assert queue.complete(claimed.id, _token(claimed)) is True
    assert queue.claim_next() is None


def test_failed_job_is_not_reclaimed(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    queue.enqueue("embed", {"resource_id": "r1"})

    claimed = queue.claim_next()
    assert claimed is not None
    assert queue.fail(claimed.id, _token(claimed), "boom") is True

    assert queue.claim_next() is None
