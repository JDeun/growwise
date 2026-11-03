from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from growwise.jobs import JobStatus, SQLiteJobQueue


def test_expired_worker_cannot_mutate_reclaimed_job(tmp_path: Path) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    queue.enqueue("projection-rebuild", {"resource_id": "r1"})
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

    first = queue.claim_next(lease_seconds=30, now=start)
    assert first is not None
    assert first.claim_token is not None

    second = queue.claim_next(lease_seconds=30, now=start + timedelta(seconds=31))
    assert second is not None
    assert second.id == first.id
    assert second.claim_token is not None
    assert second.claim_token != first.claim_token

    assert queue.heartbeat(
        first.id,
        first.claim_token,
        now=start + timedelta(seconds=32),
    ) is False
    assert queue.retry(first.id, first.claim_token, "stale retry") is False
    assert queue.fail(first.id, first.claim_token, "stale failure") is False
    assert queue.complete(first.id, first.claim_token) is False

    current = queue.get(second.id)
    assert current is not None
    assert current.status is JobStatus.RUNNING
    assert current.claim_token == second.claim_token
    assert queue.complete(second.id, second.claim_token) is True


@pytest.mark.parametrize("other_limit", [1, 10])
def test_expiry_recovery_uses_only_the_claiming_workers_job_types(
    tmp_path: Path, other_limit: int,
) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    submitted = queue.enqueue("photo_activity_analysis", {"child_id": "synthetic"})
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    photo = queue.claim_next(job_types=("photo_activity_analysis",), lease_seconds=60,
                             max_attempts=5, now=start)
    assert photo is not None and photo.attempts == 1

    # A lower unrelated budget must not fail the photo, and a higher budget must not requeue it.
    assert queue.claim_next(job_types=("material_enhancement", "observation_enrichment"),
                            max_attempts=other_limit, now=start + timedelta(seconds=61)) is None
    unchanged = queue.get(submitted.id)
    assert unchanged is not None and unchanged.status is JobStatus.RUNNING
    assert unchanged.claim_token == photo.claim_token
    own_retry = queue.claim_next(job_types=("photo_activity_analysis",), lease_seconds=60,
                                 max_attempts=5, now=start + timedelta(seconds=61))
    assert own_retry is not None and own_retry.attempts == 2
    assert own_retry.claim_token != photo.claim_token
