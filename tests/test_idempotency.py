import sqlite3

import pytest

from growwise.idempotency import (
    IdempotencyConflict,
    IdempotencyStatus,
    SQLiteIdempotencyStore,
    request_fingerprint,
)
from growwise.maintenance import DATA_MAINTENANCE, StaleDataGeneration


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
    assert owner.record.claim_token is not None
    assert duplicate.acquired is False
    assert duplicate.record.resource_id == "log-1"
    assert duplicate.record.status is IdempotencyStatus.PENDING


def test_failed_owner_release_reuses_same_reserved_resource_id(tmp_path):
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
    assert retry.record.resource_id == "log-1"
    assert retry.record.claim_token != first.record.claim_token


def test_stale_pending_claim_is_reacquired_after_crash(tmp_path):
    path = tmp_path / "idempotency.sqlite3"
    store = SQLiteIdempotencyStore(path)
    fingerprint = request_fingerprint({"value": 1})
    first = store.claim(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-1",
    )

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE idempotency_records SET lease_expires_at = ? WHERE key = ?",
            ("2000-01-01T00:00:00+00:00", "request-1"),
        )

    retry = store.claim(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-2",
    )

    assert first.record.resource_id == "log-1"
    assert retry.acquired is True
    assert retry.record.resource_id == "log-1"
    assert retry.record.lease_expires_at is not None
    assert retry.record.claim_token != first.record.claim_token


def test_stale_owner_cannot_complete_or_release_reacquired_claim(tmp_path):
    path = tmp_path / "idempotency.sqlite3"
    store = SQLiteIdempotencyStore(path)
    fingerprint = request_fingerprint({"value": 1})
    first = store.claim(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-1",
    )
    assert first.record.claim_token is not None

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE idempotency_records SET lease_expires_at = ? WHERE key = ?",
            ("2000-01-01T00:00:00+00:00", "request-1"),
        )

    second = store.claim(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-2",
    )
    assert second.acquired is True
    assert second.record.claim_token is not None
    assert second.record.claim_token != first.record.claim_token

    stale_completion = store.complete(
        key=first.record.key,
        request_hash=first.record.request_hash,
        resource_id=first.record.resource_id,
        claim_token=first.record.claim_token,
    )
    assert stale_completion.status is IdempotencyStatus.PENDING
    assert stale_completion.claim_token == second.record.claim_token
    assert (
        store.release(
            key=first.record.key,
            request_hash=first.record.request_hash,
            resource_id=first.record.resource_id,
            claim_token=first.record.claim_token,
        )
        is False
    )

    current = store.get("request-1")
    assert current is not None
    assert current.status is IdempotencyStatus.PENDING
    assert current.claim_token == second.record.claim_token

    completed = store.complete(
        key=second.record.key,
        request_hash=second.record.request_hash,
        resource_id=second.record.resource_id,
        claim_token=second.record.claim_token,
    )
    assert completed.status is IdempotencyStatus.COMPLETED
    assert completed.claim_token is None


def test_resource_type_mismatch_is_rejected(tmp_path):
    store = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    fingerprint = request_fingerprint({"value": 1})
    store.claim(
        key="request-1",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-1",
    )

    with pytest.raises(IdempotencyConflict, match="resource type"):
        store.claim(
            key="request-1",
            request_hash=fingerprint,
            resource_type="activity_plan",
            resource_id="activity-1",
        )


def test_delete_resources_removes_only_purged_resource_metadata(tmp_path):
    store = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    for key, resource_id in (("one", "log-1"), ("two", "log-2")):
        store.record(
            key=key,
            request_hash=request_fingerprint({"key": key}),
            resource_type="learning_log",
            resource_id=resource_id,
        )

    assert store.delete_resources({"log-1"}) == 1
    assert store.get("one") is None
    assert store.get("two") is not None


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
    assert record.lease_expires_at is None
    assert record.claim_token is None


def test_pre_restore_idempotency_owner_cannot_write_new_generation(tmp_path) -> None:
    path = tmp_path / "idempotency.sqlite3"
    old_store = SQLiteIdempotencyStore(path)
    fingerprint = request_fingerprint({"value": "before-restore"})
    claim = old_store.claim(
        key="restore-fence",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-before",
    )

    with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
        old_store.reset()

    with pytest.raises(StaleDataGeneration):
        old_store.complete(
            key=claim.record.key,
            request_hash=claim.record.request_hash,
            resource_id=claim.record.resource_id,
            claim_token=claim.record.claim_token,
        )

    fresh_store = SQLiteIdempotencyStore(path)
    fresh = fresh_store.claim(
        key="restore-fence",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-after",
    )
    assert fresh.acquired is True
    assert fresh.record.resource_id == "log-after"



def test_delete_resources_chunks_below_sqlite_variable_ceiling(tmp_path) -> None:
    class LowVariableIdempotencyStore(SQLiteIdempotencyStore):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 512)
            return connection

    path = tmp_path / "idempotency.sqlite3"
    store = LowVariableIdempotencyStore(path)
    resource_ids = {f"resource-{index}" for index in range(600)}
    connection = sqlite3.connect(path)
    try:
        connection.executemany(
            """
            INSERT INTO idempotency_records (
                key, request_hash, resource_type, resource_id, created_at, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"key-{index}",
                    f"hash-{index}",
                    "learning_log",
                    f"resource-{index}",
                    "2026-01-01T00:00:00+00:00",
                    "completed",
                    "2026-01-01T00:00:00+00:00",
                )
                for index in range(600)
            ],
        )
        connection.commit()
    finally:
        connection.close()

    assert store.delete_resources(resource_ids) == 600
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM idempotency_records").fetchone()[0] == 0
    finally:
        connection.close()



def test_idempotency_resource_purge_index_is_present(tmp_path) -> None:
    path = tmp_path / "idempotency.sqlite3"
    SQLiteIdempotencyStore(path)

    with sqlite3.connect(path) as connection:
        indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(idempotency_records)"
            ).fetchall()
        }

    assert "idx_idempotency_resource_id" in indexes
