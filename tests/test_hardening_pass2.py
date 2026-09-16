from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.types import Command

from growwise.api import resource_routes
from growwise.api.secure_main import CoreTokenMiddleware
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.idempotency import SQLiteIdempotencyStore, request_fingerprint
from growwise.jobs import JobStatus, SQLiteJobQueue
from growwise.rag.ingestion import ResourceIngestor
from growwise.storage import EntityStore
from growwise.workflows.material_review import ResilientMaterialReviewGraph


def test_idempotency_release_preserves_reserved_resource_id(tmp_path: Path) -> None:
    registry = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    request_hash = request_fingerprint({"value": "same logical request"})
    original_id = str(uuid4())

    first = registry.claim(
        key="operation-1",
        request_hash=request_hash,
        resource_type="learning_log",
        resource_id=original_id,
        now=now,
    )
    assert first.acquired is True
    assert registry.release(
        key="operation-1",
        request_hash=request_hash,
        resource_id=original_id,
    )

    retry = registry.claim(
        key="operation-1",
        request_hash=request_hash,
        resource_type="learning_log",
        resource_id=str(uuid4()),
        now=now,
    )
    assert retry.acquired is True
    assert retry.record.resource_id == original_id


def test_stale_running_job_is_reclaimed_after_lease_expiry(tmp_path: Path) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    enqueued = queue.enqueue("projection-rebuild", {"resource_id": "r1"})
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

    first = queue.claim_next(lease_seconds=30, now=start)
    assert first is not None
    assert first.id == enqueued.id
    assert first.status is JobStatus.RUNNING
    assert first.attempts == 1

    retry = queue.claim_next(lease_seconds=30, now=start + timedelta(seconds=31))
    assert retry is not None
    assert retry.id == enqueued.id
    assert retry.status is JobStatus.RUNNING
    assert retry.attempts == 2


def test_entity_store_rebuilds_projection_after_incremental_upsert_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(name="projection-child", stage=Stage.ELEMENTARY, age_months=96)
    original_upsert = store.index.upsert
    calls = 0

    def fail_once(entity, path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected projection failure")
        return original_upsert(entity, path)

    monkeypatch.setattr(store.index, "upsert", fail_once)
    path = store.save(child)

    assert path.is_file()
    indexed = store.index.get_entity(str(child.id), entity_type="child_profile")
    assert indexed is not None
    assert indexed["id"] == str(child.id)


def test_rag_projection_failure_does_not_invalidate_resource_source() -> None:
    class BrokenIndex:
        def replace_resource(self, chunks):
            raise RuntimeError("injected rag outage")

    resource = ResourceRecord(kind=ResourceKind.NOTE, title="source survives", content="body")
    assert ResourceIngestor(BrokenIndex()).ingest(resource) == 0  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="injected rag outage"):
        ResourceIngestor(BrokenIndex()).ingest(resource, strict=True)  # type: ignore[arg-type]


def test_core_token_middleware_rejects_unauthenticated_local_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inner = FastAPI()

    @inner.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    monkeypatch.setenv("GROWWISE_API_TOKEN", "test-session-secret")
    client = TestClient(CoreTokenMiddleware(inner))

    unauthorized = client.get("/health")
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"detail": "unauthorized_core_client"}

    authorized = client.get(
        "/health",
        headers={"Authorization": "Bearer test-session-secret"},
    )
    assert authorized.status_code == 200
    assert authorized.json() == {"status": "ok"}


def test_resource_create_validates_child_and_replays_same_idempotent_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "growwise"
    monkeypatch.setenv("GROWWISE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("GROWWISE_EMBEDDING_FEATURES_ENABLED", "false")
    resource_routes.get_resource_settings.cache_clear()
    resource_routes.get_resource_rag_index.cache_clear()
    resource_routes.get_resource_idempotency_store.cache_clear()

    store = EntityStore(data_dir / "records", data_dir / "index.sqlite3")
    child = ChildProfile(name="resource-child", stage=Stage.ELEMENTARY, age_months=96)
    store.save(child)

    app = FastAPI()
    app.include_router(resource_routes.router, prefix="/v1")
    app.dependency_overrides[resource_routes.get_resource_store] = lambda: store
    client = TestClient(app)
    payload = {
        "kind": "note",
        "title": "same resource",
        "child_id": str(child.id),
        "summary": None,
        "content": "body",
        "source_url": None,
        "source_name": None,
        "author": None,
        "tags": [],
        "stage_tags": [],
        "provenance": {},
    }

    first = client.post(
        "/v1/resources",
        json=payload,
        headers={"Idempotency-Key": "resource-create-1"},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/v1/resources",
        json=payload,
        headers={"Idempotency-Key": "resource-create-1"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert len(store.index.list_entities(entity_type="resource")) == 1

    missing_child = client.post(
        "/v1/resources",
        json={**payload, "child_id": str(uuid4()), "title": "orphan"},
        headers={"Idempotency-Key": "resource-create-orphan"},
    )
    assert missing_child.status_code == 404
    assert missing_child.json()["detail"] == "child_not_found"

    app.dependency_overrides.clear()
    resource_routes.get_resource_settings.cache_clear()
    resource_routes.get_resource_rag_index.cache_clear()
    resource_routes.get_resource_idempotency_store.cache_clear()


def test_material_review_checkpoint_failure_degrades_to_domain_transition() -> None:
    class BrokenGraph:
        def invoke(self, input, *args, **kwargs):
            raise RuntimeError("checkpoint unavailable")

    graph = ResilientMaterialReviewGraph(BrokenGraph())
    initial = graph.invoke(
        {"material_id": "m1", "child_id": "c1", "title": "material"}
    )
    assert initial["projection_degraded"] is True

    resumed = graph.invoke(
        Command(resume={"status": "approved", "note": "ok"}),
        config={"configurable": {"thread_id": "material-review:m1"}},
    )
    assert resumed["decision_status"] == "approved"
    assert resumed["decision_note"] == "ok"
    assert resumed["projection_degraded"] is True
