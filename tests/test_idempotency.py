import sqlite3

import pytest

from growwise.idempotency import (
    IdempotencyConflict,
    IdempotencyStatus,
    SQLiteIdempotencyStore,
    request_fingerprint,
)


def test_same_idempotency_key_and_payload_returns_original_resource(tmp_path):
    store = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    fingerprint = request_fingerprint({"child_id": "child-1", "observation": "같은 요청"})

    first = store.record(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-1",
    )
    second = store.record(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-2",
    )

    assert first.resource_id == "log-1"
    assert first.status is IdempotencyStatus.COMPLETED
    assert second.resource_id == "log-1"
    assert second.status is IdempotencyStatus.COMPLETED


def test_reusing_key_for_different_request_is_rejected(tmp_path):
    store = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    store.record(
        key="request-1",
        request_hash=request_fingerprint({"value": 1}),
        resource_type="learning_log",
        resource_id="log-1",
    )

    with pytest.raises(IdempotencyConflict):
        store.record(
            key="request-1",
            request_hash=request_fingerprint({"value": 2}),
            resource_type="learning_log",
            resource_id="log-2",
        )


def test_concurrent_claim_observes_pending_owner(tmp_path):
    store = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    fingerprint = request_fingerprint({"value": 1})

    owner = store.claim(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-1",
    )
    duplicate = store.claim(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-2",
    )

    assert owner.acquired is True
    assert owner.record.status is IdempotencyStatus.PENDING
    assert duplicate.acquired is False
    assert duplicate.record.resource_id == "log-1"
    assert duplicate.record.status is IdempotencyStatus.PENDING


def test_failed_owner_can_release_and_retry_same_resource_key(tmp_path):
    store = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    fingerprint = request_fingerprint({"value": 1})
    first = store.claim(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-1",
    )

    assert store.release(
        key=first.record.key,
        request_hash=first.record.request_hash,
        resource_id=first.record.resource_id,
    )
    retry = store.claim(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-2",
    )
    assert retry.acquired is True
    assert retry.record.resource_id == "log-2"


def test_existing_v1_table_is_migrated_without_losing_completed_record(tmp_path):
    path = tmp_path / "idempotency.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE idempotency_records (
                key TEXT PRIMARY KEY,
                request_hash TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?)",
            ("legacy", "hash", "learning_log", "log-1", "2026-01-01T00:00:00+00:00"),
        )

    store = SQLiteIdempotencyStore(path)
    record = store.get("legacy")

    assert record is not None
    assert record.resource_id == "log-1"
    assert record.status is IdempotencyStatus.COMPLETED
