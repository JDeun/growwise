from datetime import UTC, datetime, timedelta
from pathlib import Path

from growwise.jobs import SQLiteJobQueue


def test_expired_worker_cannot_complete_reclaimed_job(tmp_path: Path) -> None:
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

    assert queue.heartbeat(first.id, first.claim_token, now=start + timedelta(seconds=32)) is False
    assert queue.complete(first.id, first.claim_token) is False
    assert queue.complete(second.id, second.claim_token) is True
