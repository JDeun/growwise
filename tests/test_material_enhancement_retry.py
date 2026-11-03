from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import growwise.api.background_write_routes as routes
from growwise.api.dependencies import get_store
from growwise.api.main import app
from growwise.domain import AiEnhancementStatus, ChildProfile, MaterialKind, MaterialStatus, Stage
from growwise.generators import MaterialGenerationService
from growwise.storage import EntityStore


@pytest.fixture
def material_store(tmp_path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="가상재시도검증", stage=Stage.ELEMENTARY, age_months=96)
    store.save(child)
    material = MaterialGenerationService(None).generate(
        child=child, kind=MaterialKind.ACTIVITY_GUIDE, topic="씨앗 관찰"
    )
    material.ai_status = AiEnhancementStatus.FAILED
    store.save(material)
    app.dependency_overrides[get_store] = lambda: store
    try:
        yield store, material, TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_retry_enqueues_once_preserving_original_material(monkeypatch, material_store):
    store, material, client = material_store
    before = material.content_markdown
    calls = []

    def enqueue(*, material, store):
        calls.append(material.id)
        material.ai_status = AiEnhancementStatus.QUEUED
        store.save(material)
        return object()

    monkeypatch.setattr(routes, "queue_material_enhancement", enqueue)
    for _ in range(2):
        response = client.post(f"/v1/materials/{material.id}/retry-enhancement")
        assert response.status_code == 200, response.text
        assert response.json()["ai_status"] == "queued"
        assert response.json()["content_markdown"] == before
    assert calls == [material.id]
    assert store.index.get_entity(str(material.id))["status"] == "review_pending"


@pytest.mark.parametrize(
    "status", [MaterialStatus.APPROVED, MaterialStatus.REJECTED, MaterialStatus.ARCHIVED]
)
def test_retry_cannot_rewrite_reviewed_material(monkeypatch, material_store, status):
    store, material, client = material_store
    material.status = status
    store.save(material)
    enqueue = Mock()
    monkeypatch.setattr(routes, "queue_material_enhancement", enqueue)
    assert client.post(f"/v1/materials/{material.id}/retry-enhancement").status_code == 409
    enqueue.assert_not_called()
    assert store.index.get_entity(str(material.id))["status"] == status


def test_retry_reports_model_unavailable_without_success(monkeypatch, material_store):
    store, material, client = material_store

    def unavailable(*, material, store):
        material.ai_status = AiEnhancementStatus.NOT_REQUESTED
        store.save(material)
        return None

    monkeypatch.setattr(routes, "queue_material_enhancement", unavailable)
    assert client.post(f"/v1/materials/{material.id}/retry-enhancement").status_code == 503
    assert store.index.get_entity(str(material.id))["ai_status"] == "failed"
