from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from growwise.api import learning_record_routes, material_result_routes
from growwise.api.main import app
from growwise.config import Settings
from growwise.domain import (
    ChildProfile,
    GeneratedMaterial,
    LearningLog,
    MaterialKind,
    MaterialStatus,
    ResourceKind,
    ResourceRecord,
    Stage,
)
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore


@pytest.fixture
def setup(tmp_path: Path, monkeypatch):
    settings = Settings(data_dir=tmp_path, llm_features_enabled=False,
                        embedding_features_enabled=False, vision_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(nickname="다른 합성아이", stage=Stage.ELEMENTARY)
    store.save(child)
    store.save(sibling)
    book = ResourceRecord(child_id=child.id, kind=ResourceKind.BOOK, title="합성 도서")
    store.save(book)
    material = GeneratedMaterial(child_id=child.id, kind=MaterialKind.READING_ACTIVITY,
                                 title="읽기 활동", content_markdown="# 읽기 활동",
                                 status=MaterialStatus.APPROVED)
    store.save(material)
    monkeypatch.setattr(learning_record_routes, "queue_learning_log_enrichment", lambda **_kw: None)
    overrides = (learning_record_routes.get_learning_record_store,
                 material_result_routes.get_material_result_store)
    for dependency in overrides:
        app.dependency_overrides[dependency] = lambda: store
    try:
        yield TestClient(app), store, child, sibling, book, material
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)


def _post(client, child, material, flow, fields):
    if flow == "independent":
        return client.post(f"/v1/children/{child.id}/learning-records", json={
            "kind": "reading_reflection", "title": "독서 회고", "summary": "함께 읽고 설명했다.",
            **fields,
        })
    return client.post(f"/v1/materials/{material.id}/results", json={
        "observation": "활동 뒤 자기 말로 설명했다.", **fields,
    })


@pytest.mark.parametrize("flow", ["independent", "material"])
@pytest.mark.parametrize("checked", [True, False, None])
def test_optional_learning_evidence_round_trips_through_http_markdown_and_history(
    setup, flow, checked,
):
    client, store, child, _sibling, book, material = setup
    fields = {"book_id": str(book.id), "ai_hint": "조건을 하나 바꾸어 보라는 힌트",
              "evidence_checked": checked,
              "child_reexplanation": "책의 앞 장면과 비교해서\n설명했어요."}
    response = _post(client, child, material, flow, fields)
    assert response.status_code == 200, response.text
    record = response.json() if flow == "independent" else response.json()["learning_log"]
    assert {key: record[key] for key in fields} == fields
    saved = store.index.get_entity(record["id"], entity_type="learning_log")
    assert saved is not None
    assert {key: saved[key] for key in fields} == fields
    # Rebuild from authoritative Markdown, rather than merely reading back the same SQLite row.
    store.index.rebuild(store.markdown.root)
    rebuilt = store.index.get_entity(record["id"], entity_type="learning_log")
    assert rebuilt is not None
    assert {key: rebuilt[key] for key in fields} == fields
    route = (f"/v1/children/{child.id}/learning-records" if flow == "independent"
             else f"/v1/materials/{material.id}/results")
    history = client.get(route)
    assert history.status_code == 200
    records = history.json() if flow == "independent" else history.json()[0]["learning_logs"]
    assert {key: records[0][key] for key in fields} == fields


@pytest.mark.parametrize("flow", ["independent", "material"])
@pytest.mark.parametrize("case", ["foreign", "missing", "not_book", "invalid_uuid"])
def test_book_reference_is_validated_before_any_record_or_activity_write(setup, flow, case):
    client, store, child, sibling, _book, material = setup
    invalid = ResourceRecord(child_id=sibling.id if case == "foreign" else child.id,
                             kind=ResourceKind.NOTE if case == "not_book" else ResourceKind.BOOK,
                             title="참조 검증용 자료")
    store.save(invalid)
    book_id = "책 제목을 ID로 넣을 수 없음" if case == "invalid_uuid" else str(
        uuid4() if case == "missing" else invalid.id
    )
    response = _post(client, child, material, flow, {"book_id": book_id})
    assert response.status_code == (422 if case in {"not_book", "invalid_uuid"} else 404)
    assert store.index.list_entities(entity_type="learning_log") == []
    assert store.index.list_entities(entity_type="activity_plan") == []


@pytest.mark.parametrize("flow", ["independent", "material"])
def test_explicit_shared_book_is_allowed_but_revoked_share_is_not(setup, flow):
    client, store, child, sibling, _book, material = setup
    book = ResourceRecord(child_id=sibling.id, kind=ResourceKind.BOOK, title="함께 보는 책")
    store.save(book)
    links = EntityLinkService(store).share_with_children(source_id=book.id, child_ids=[child.id])
    response = _post(client, child, material, flow, {"book_id": str(book.id)})
    assert response.status_code == 200, response.text
    for link in links:
        store.delete(link)
    before = store.index.list_entities(entity_type="learning_log")
    denied = _post(client, child, material, flow, {"book_id": str(book.id)})
    assert denied.status_code == 404
    assert store.index.list_entities(entity_type="learning_log") == before


@pytest.mark.parametrize("field, limit", [("ai_hint", 4000), ("child_reexplanation", 10000)])
@pytest.mark.parametrize("flow", ["independent", "material"])
def test_optional_text_has_server_side_bounds(setup, flow, field, limit):
    client, store, child, _sibling, _book, material = setup
    response = _post(client, child, material, flow, {field: "가" * (limit + 1)})
    assert response.status_code == 422
    assert store.index.list_entities(entity_type="learning_log") == []


def test_legacy_learning_record_defaults_remain_unknown():
    log = LearningLog(child_id=uuid4(), parent_observation="예전 기록")
    assert log.book_id is None
    assert log.ai_hint is None
    assert log.evidence_checked is None
    assert log.child_reexplanation is None
