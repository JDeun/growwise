from __future__ import annotations

import random
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from growwise.idempotency import (
    IdempotencyConflict,
    IdempotencyStatus,
    SQLiteIdempotencyStore,
    request_fingerprint,
)
from growwise.jobs import JobStatus, SQLiteJobQueue

_SEED = 0x1D3A_BA5E


def test_idempotency_state_machine_randomized_fencing(tmp_path) -> None:
    rng = random.Random(_SEED)
    path = tmp_path / "idempotency.sqlite3"
    store = SQLiteIdempotencyStore(path)

    for index in range(250):
        key = f"request-{index}"
        fingerprint = request_fingerprint({"index": index, "salt": rng.randint(0, 1_000_000)})
        first = store.claim(
            key=key,
            request_hash=fingerprint,
            resource_type="learning_log",
            resource_id=f"log-{index}",
            lease_seconds=60,
        )
        assert first.acquired is True
        assert first.record.claim_token is not None

        scenario = rng.choice(("complete", "release", "expire", "conflict"))
        if scenario == "complete":
            completed = store.complete(
                key=key,
                request_hash=fingerprint,
                resource_id=first.record.resource_id,
                claim_token=first.record.claim_token,
            )
            assert completed.status is IdempotencyStatus.COMPLETED
            duplicate = store.claim(
                key=key,
                request_hash=fingerprint,
                resource_type="learning_log",
                resource_id=f"other-{index}",
            )
            assert duplicate.acquired is False
            assert duplicate.record.resource_id == first.record.resource_id
            continue

        if scenario == "conflict":
            with pytest.raises(IdempotencyConflict):
                store.claim(
                    key=key,
                    request_hash=request_fingerprint({"different": index}),
                    resource_type="learning_log",
                    resource_id=f"other-{index}",
                )

        if scenario == "release":
            assert store.release(
                key=key,
                request_hash=fingerprint,
                resource_id=first.record.resource_id,
                claim_token=first.record.claim_token,
            )
        else:
            with sqlite3.connect(path) as connection:
                connection.execute(
                    "UPDATE idempotency_records SET lease_expires_at = ? WHERE key = ?",
                    ("2000-01-01T00:00:00+00:00", key),
                )

        second = store.claim(
            key=key,
            request_hash=fingerprint,
            resource_type="learning_log",
            resource_id=f"replacement-{index}",
            lease_seconds=60,
        )
        assert second.acquired is True
        assert second.record.resource_id == first.record.resource_id
        assert second.record.claim_token is not None
        assert second.record.claim_token != first.record.claim_token

        stale = store.complete(
            key=key,
            request_hash=fingerprint,
            resource_id=first.record.resource_id,
            claim_token=first.record.claim_token,
        )
        assert stale.status is IdempotencyStatus.PENDING
        assert stale.claim_token == second.record.claim_token
        assert (
            store.release(
                key=key,
                request_hash=fingerprint,
                resource_id=first.record.resource_id,
                claim_token=first.record.claim_token,
            )
            is False
        )

        current = store.get(key)
        assert current is not None
        assert current.status is IdempotencyStatus.PENDING
        assert current.claim_token == second.record.claim_token

        completed = store.complete(
            key=key,
            request_hash=fingerprint,
            resource_id=second.record.resource_id,
            claim_token=second.record.claim_token,
        )
        assert completed.status is IdempotencyStatus.COMPLETED
        assert completed.claim_token is None


def test_job_queue_state_machine_randomized_lease_fencing(tmp_path) -> None:
    rng = random.Random(_SEED + 1)
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    base = datetime(2026, 9, 18, 0, 0, tzinfo=UTC)

    for index in range(200):
        created = queue.enqueue("fuzz-job", {"child_id": f"child-{index}", "index": index})
        start = base + timedelta(minutes=index * 2)
        first = queue.claim_next(
            job_types=("fuzz-job",),
            lease_seconds=30,
            max_attempts=5,
            now=start,
        )
        assert first is not None
        assert first.id == created.id
        assert first.claim_token is not None

        scenario = rng.choice(("complete", "retry", "expire"))
        if scenario == "complete":
            assert queue.complete(first.id, first.claim_token) is True
            current = queue.get(first.id)
            assert current is not None
            assert current.status is JobStatus.COMPLETED
            continue

        if scenario == "retry":
            assert queue.retry(first.id, first.claim_token, "retry requested") is True
            second = queue.claim_next(
                job_types=("fuzz-job",),
                lease_seconds=30,
                max_attempts=5,
                now=start + timedelta(seconds=1),
            )
        else:
            second = queue.claim_next(
                job_types=("fuzz-job",),
                lease_seconds=30,
                max_attempts=5,
                now=start + timedelta(seconds=31),
            )

        assert second is not None
        assert second.id == first.id
        assert second.claim_token is not None
        assert second.claim_token != first.claim_token

        assert queue.heartbeat(
            first.id,
            first.claim_token,
            lease_seconds=30,
            now=start + timedelta(seconds=32),
        ) is False
        assert queue.retry(first.id, first.claim_token, "stale retry") is False
        assert queue.fail(first.id, first.claim_token, "stale fail") is False
        assert queue.complete(first.id, first.claim_token) is False

        current = queue.get(second.id)
        assert current is not None
        assert current.status is JobStatus.RUNNING
        assert current.claim_token == second.claim_token

        terminal = rng.choice(("complete", "fail"))
        if terminal == "complete":
            assert queue.complete(second.id, second.claim_token) is True
            expected = JobStatus.COMPLETED
        else:
            assert queue.fail(second.id, second.claim_token, "terminal") is True
            expected = JobStatus.FAILED

        final = queue.get(second.id)
        assert final is not None
        assert final.status is expected
        assert final.claim_token is None
