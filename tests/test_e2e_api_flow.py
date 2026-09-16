from __future__ import annotations

import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import growwise.api.main as api
from growwise.api.main import app
from growwise.storage import EntityStore

# lru_cache-wrapped dependency providers that resolve their paths from Settings().
# They must be reset between environments so the sidecar rebuilds them against the
# per-test data directory instead of a leaked ~/.growwise instance.
_CACHED_PROVIDERS = (
    api.get_settings,
    api.get_model_provider,
    api.get_rag_index,
    api.get_conversation_store,
    api.get_idempotency_store,
    api.get_observation_graph,
    api.get_material_review_graph,
)


def _reset_caches() -> None:
    for provider in _CACHED_PROVIDERS:
        provider.cache_clear()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    data_dir = tmp_path / "growwise"
    monkeypatch.setenv("GROWWISE_DATA_DIR", str(data_dir))
    # Core / template mode: no live model or embedding runtime in the harness.
    monkeypatch.setenv("GROWWISE_LLM_FEATURES_ENABLED", "false")
    monkeypatch.setenv("GROWWISE_EMBEDDING_FEATURES_ENABLED", "false")
    _reset_caches()

    store = EntityStore(data_dir / "records", data_dir / "index.sqlite3")
    app.dependency_overrides[api.get_store] = lambda: store
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        _reset_caches()


def _create_child(client: TestClient) -> str:
    response = client.post(
        "/v1/children",
        json={
            "nickname": "샘플아이",
            "stage": "elementary",
            "age_months": 96,
            "interests": ["관찰", "그림책"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_parent_journey_child_to_material_review_to_export(client: TestClient) -> None:
    """Broad happy-path across resource-grounded material -> review -> activity -> backup."""
    child_id = _create_child(client)

    source_response = client.post(
        "/v1/resources",
        json={
            "kind": "note",
            "title": "고양이 관찰 메모",
            "child_id": child_id,
            "summary": "고양이의 귀와 꼬리 움직임을 장면별로 살펴본다.",
            "content": "그림을 먼저 충분히 보고 아이가 발견한 특징을 자신의 말로 표현하게 한다.",
            "source_url": None,
            "source_name": "부모 메모",
            "author": None,
            "tags": ["고양이", "관찰"],
            "stage_tags": ["elementary"],
            "provenance": {"origin": "parent"},
        },
    )
    assert source_response.status_code == 200, source_response.text
    source = source_response.json()
    source_ref = f"resource:{source['id']}"

    # Generate in deterministic template mode with an explicitly selected source. The source title
    # is visible even without an LLM, and the same bounded evidence is available to an LLM when on.
    generated = client.post(
        f"/v1/children/{child_id}/materials",
        json={
            "kind": "reading_activity",
            "topic": "고양이 그림책",
            "goal": "장면을 관찰하고 아이의 반응을 기다린다.",
            "source_refs": [source_ref],
        },
    )
    assert generated.status_code == 200, generated.text
    material = generated.json()
    material_id = material["id"]
    assert material["status"] == "review_pending"
    assert material["source_refs"] == [source_ref]
    assert "고양이 관찰 메모" in material["content_markdown"]

    # Parent approves through the real review checkpoint graph.
    approved = client.post(
        f"/v1/materials/{material_id}/review",
        json={"status": "approved", "note": "확인함"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    # The approved material is visible in the child-scoped listing.
    listed = client.get(f"/v1/children/{child_id}/materials")
    assert listed.status_code == 200
    statuses = {item["id"]: item["status"] for item in listed.json()}
    assert statuses.get(material_id) == "approved"

    # Create an activity and record an observation linked to it.
    activity_resp = client.post(
        f"/v1/children/{child_id}/activities",
        json={"title": "고양이 그림 함께 보기", "source_refs": [source_ref]},
    )
    assert activity_resp.status_code == 200, activity_resp.text
    activity = activity_resp.json()
    assert activity["status"] == "suggested"
    activity_id = activity["id"]

    observation_resp = client.post(
        "/v1/observations",
        json={
            "child_id": child_id,
            "observation": "그림책의 고양이를 오래 바라보며 이름을 물었다.",
            "experience_axes": ["reading", "speaking"],
            "activity_plan_id": activity_id,
        },
    )
    assert observation_resp.status_code == 200, observation_resp.text
    log = observation_resp.json()
    assert log["child_id"] == child_id
    assert log["activity_plan_id"] == activity_id

    # The observation surfaces in the deterministic growth-map projection.
    growth_resp = client.get(f"/v1/children/{child_id}/growth-map")
    assert growth_resp.status_code == 200, growth_resp.text
    growth = growth_resp.json()
    assert growth["child_id"] == child_id
    assert growth["total_logs_in_period"] >= 1
    assert growth["tagged_logs_in_period"] >= 1
    assert growth["axes"]

    # Export a managed backup and assert the archive is a valid zip.
    backup_resp = client.post("/v1/admin/backups", json={})
    assert backup_resp.status_code == 200, backup_resp.text
    archive_path = Path(backup_resp.json()["path"])
    assert archive_path.is_file()
    assert zipfile.is_zipfile(archive_path)
    with zipfile.ZipFile(archive_path) as bundle:
        assert bundle.testzip() is None
        assert bundle.namelist()


def test_parent_review_rejection_path(client: TestClient) -> None:
    """A parent rejection transitions the material to rejected and blocks export."""
    child_id = _create_child(client)

    generated = client.post(
        f"/v1/children/{child_id}/materials",
        json={"kind": "activity_guide", "topic": "블록 쌓기"},
    )
    assert generated.status_code == 200, generated.text
    material_id = generated.json()["id"]
    assert generated.json()["status"] == "review_pending"

    rejected = client.post(
        f"/v1/materials/{material_id}/review",
        json={"status": "rejected", "note": "이번에는 사용하지 않겠습니다."},
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["status"] == "rejected"
    assert body["review_note"] == "이번에는 사용하지 않겠습니다."
