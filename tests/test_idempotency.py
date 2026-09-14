import pytest

from growwise.idempotency import (
    IdempotencyConflict,
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
    assert second.resource_id == "log-1"


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
