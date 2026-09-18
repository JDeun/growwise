import threading
from contextlib import ExitStack
from pathlib import Path

import pytest

from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.idempotency import SQLiteIdempotencyStore, request_fingerprint
from growwise.maintenance import (
    DATA_MAINTENANCE,
    DataMaintenanceCoordinator,
    MaintenanceAwareJobQueue,
    MaintenanceInProgress,
    StaleDataGeneration,
)
from growwise.services import ConversationSession, SQLiteConversationStore
from growwise.storage import EntityStore


def _child(nickname: str) -> ChildProfile:
    return ChildProfile(nickname=nickname, stage=Stage.INFANT_0_2, age_months=10)


def test_ordinary_mutation_waits_for_non_destructive_maintenance() -> None:
    coordinator = DataMaintenanceCoordinator()
    started = threading.Event()
    finished = threading.Event()

    def mutate() -> None:
        started.set()
        with coordinator.mutation():
            pass
        finished.set()

    worker = threading.Thread(target=mutate)
    with coordinator.maintenance():
        worker.start()
        assert started.wait(timeout=1)
        assert not finished.wait(timeout=0.05)

    worker.join(timeout=1)
    assert finished.is_set()


def test_concurrent_maintenance_is_retryable_503() -> None:
    coordinator = DataMaintenanceCoordinator()
    with coordinator.maintenance(), ExitStack() as stack:
        error = stack.enter_context(pytest.raises(MaintenanceInProgress))
        stack.enter_context(coordinator.maintenance())

    assert error.value.status_code == 503
    assert error.value.detail == "data_maintenance_in_progress"


def test_destructive_maintenance_fences_old_store_generation(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    old_store = EntityStore(settings.records_dir, settings.index_path)
    old_store.save(_child("before"))

    with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
        pass

    with pytest.raises(StaleDataGeneration) as error:
        old_store.save(_child("stale"))
    assert error.value.status_code == 503

    fresh_store = EntityStore(settings.records_dir, settings.index_path)
    fresh_store.save(_child("fresh"))
    nicknames = {
        payload["nickname"]
        for payload in fresh_store.index.list_entities(entity_type="child_profile")
    }
    assert "fresh" in nicknames
    assert "stale" not in nicknames


def test_maintenance_aware_job_heartbeat_fences_new_store_on_same_worker_thread(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path)
    queue = MaintenanceAwareJobQueue(settings.jobs_path)
    queue.enqueue("generation-test", {"child_id": "child"})
    claim = queue.claim_next(job_types=("generation-test",), lease_seconds=60, max_attempts=2)
    assert claim is not None
    assert claim.claim_token is not None

    try:
        assert queue.heartbeat(claim.id, claim.claim_token, lease_seconds=60)
        with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
            pass

        fresh_store = EntityStore(settings.records_dir, settings.index_path)
        with pytest.raises(StaleDataGeneration):
            fresh_store.save(_child("late-worker-write"))
    finally:
        DATA_MAINTENANCE.clear_bound_generation()

    retry_store = EntityStore(settings.records_dir, settings.index_path)
    retry_store.save(_child("after-clear"))



def test_destructive_maintenance_fences_old_conversation_store_generation(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    old_store = SQLiteConversationStore(settings.conversations_path)
    old_session = ConversationSession(child_id="child-before")
    old_store.save(old_session)

    with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
        pass

    with pytest.raises(StaleDataGeneration):
        old_store.get(old_session.id)
    with pytest.raises(StaleDataGeneration):
        old_store.save(ConversationSession(child_id="stale-child"))

    fresh_store = SQLiteConversationStore(settings.conversations_path)
    fresh_session = ConversationSession(child_id="child-after")
    fresh_store.save(fresh_session)
    assert fresh_store.get(fresh_session.id) is not None


def test_destructive_maintenance_fences_old_idempotency_store_generation(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    old_store = SQLiteIdempotencyStore(settings.idempotency_path)
    fingerprint = request_fingerprint({"value": "before"})
    old_store.record(
        key="before",
        request_hash=fingerprint,
        resource_type="learning_log",
        resource_id="log-before",
    )

    with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
        old_store.reset()

    with pytest.raises(StaleDataGeneration):
        old_store.get("before")
    with pytest.raises(StaleDataGeneration):
        old_store.claim(
            key="stale",
            request_hash=request_fingerprint({"value": "stale"}),
            resource_type="learning_log",
            resource_id="log-stale",
        )

    fresh_store = SQLiteIdempotencyStore(settings.idempotency_path)
    fresh = fresh_store.record(
        key="after",
        request_hash=request_fingerprint({"value": "after"}),
        resource_type="learning_log",
        resource_id="log-after",
    )
    assert fresh.resource_id == "log-after"
