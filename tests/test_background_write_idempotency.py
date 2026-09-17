from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

import growwise.api.background_write_routes as routes
from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.idempotency import SQLiteIdempotencyStore
from growwise.storage import EntityStore


def _setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[EntityStore, ChildProfile]:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    idempotency = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    monkeypatch.setattr(routes, "get_background_idempotency_store", lambda: idempotency)
    monkeypatch.setattr(routes, "queue_learning_log_enrichment", lambda **_: None)
    monkeypatch.setattr(routes, "queue_material_enhancement", lambda **_: None)
    monkeypatch.setattr(routes, "_init_review", lambda material: None)
    return store, child


def test_background_observation_same_key_returns_same_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, child = _setup(monkeypatch, tmp_path)
    request = routes.BackgroundObservationRequest(
        child_id=child.id,
        observation="고양이 그림을 오래 살펴봤다.",
    )

    first = routes.create_observation_background(request, store, "observation-background-1")
    second = routes.create_observation_background(request, store, "observation-background-1")

    assert second.id == first.id
    logs = store.index.list_entities(entity_type="learning_log", child_id=str(child.id))
    assert [payload["id"] for payload in logs] == [str(first.id)]


def test_background_observation_rejects_key_reuse_for_different_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, child = _setup(monkeypatch, tmp_path)
    routes.create_observation_background(
        routes.BackgroundObservationRequest(child_id=child.id, observation="첫 기록"),
        store,
        "observation-background-1",
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.create_observation_background(
            routes.BackgroundObservationRequest(child_id=child.id, observation="다른 기록"),
            store,
            "observation-background-1",
        )

    assert exc_info.value.status_code == 409


def test_background_material_same_key_returns_same_material(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, child = _setup(monkeypatch, tmp_path)
    request = routes.BackgroundMaterialRequest(
        kind=MaterialKind.ACTIVITY_GUIDE,
        topic="동네에서 가을 찾기",
        goal="계절 변화를 관찰한다",
    )

    first = routes.generate_material_background(child.id, request, store, "material-background-1")
    second = routes.generate_material_background(child.id, request, store, "material-background-1")

    assert second.id == first.id
    materials = store.index.list_entities(
        entity_type="generated_material",
        child_id=str(child.id),
    )
    assert [payload["id"] for payload in materials] == [str(first.id)]


def test_checkpoint_failure_after_material_commit_is_non_fatal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, child = _setup(monkeypatch, tmp_path)

    class FailingGraph:
        def invoke(self, state: dict, config: dict) -> None:
            del state, config
            raise RuntimeError("checkpoint unavailable")

    monkeypatch.setattr(routes, "get_background_material_review_graph", lambda: FailingGraph())
    monkeypatch.setattr(routes, "_init_review", routes._init_review)

    material = routes.generate_material_background(
        child.id,
        routes.BackgroundMaterialRequest(topic="식물 관찰"),
        store,
        "material-background-checkpoint",
    )

    persisted = store.index.get_entity(str(material.id), entity_type="generated_material")
    assert persisted is not None
    assert persisted["id"] == str(material.id)
