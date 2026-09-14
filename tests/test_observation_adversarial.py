from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import growwise.api.main as api
from growwise.api.main import ObservationRequest
from growwise.domain import ChildProfile, ExperienceAxis, Stage
from growwise.idempotency import SQLiteIdempotencyStore
from growwise.services.observation import ObservationEnricher
from growwise.storage import EntityStore
from growwise.workflows import build_observation_graph


class HostileProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        return schema.model_validate(
            {
                "tags": ["독서", "ADHD 의심"],
                "experience_axes": ["reading"],
                "interest": "또래보다 발달이 빠름",
                "difficulty_note": "자폐 진단이 필요함",
                "next_activity": "그림책을 함께 천천히 살펴보기",
            }
        )


class FailingProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        raise TimeoutError("model timeout")

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        raise TimeoutError("model timeout")


def _store_with_child(tmp_path: Path) -> tuple[EntityStore, ChildProfile]:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="수아", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    return store, child


def test_observation_graph_derives_normalized_text_without_mutating_input() -> None:
    source = "  책을  보고\n다시 손을 뻗었다.\n---\ncontent: 그대로  "
    state = build_observation_graph().invoke(
        {"child_id": "child-1", "observation": source}
    )

    assert state["observation"] == source
    assert state["normalized_observation"] == "책을 보고 다시 손을 뻗었다. --- content: 그대로"
    assert state["safety_flags"] == []


def test_whitespace_only_observation_is_rejected_by_workflow_safety() -> None:
    state = build_observation_graph().invoke(
        {"child_id": "child-1", "observation": " \n\t  "}
    )
    assert state["safety_flags"] == ["empty_observation"]


def test_observation_enrichment_filters_diagnosis_and_peer_ranking() -> None:
    enrichment = ObservationEnricher(HostileProvider()).enrich("그림책을 오래 바라봤다.")

    assert enrichment.tags == ["독서"]
    assert enrichment.experience_axes == [ExperienceAxis.READING]
    assert enrichment.interest is None
    assert enrichment.difficulty_note is None
    assert enrichment.next_activity == "그림책을 함께 천천히 살펴보기"


def test_observation_request_enforces_text_size_boundary() -> None:
    child = ChildProfile(nickname="수아", stage=Stage.INFANT_0_2, age_months=9)
    accepted = ObservationRequest(child_id=child.id, observation="가" * 10_000)
    assert len(accepted.observation) == 10_000

    with pytest.raises(ValidationError):
        ObservationRequest(child_id=child.id, observation="가" * 10_001)


def test_duplicate_submit_is_idempotent_and_preserves_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    idempotency = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    monkeypatch.setattr(api, "get_idempotency_store", lambda: idempotency)
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_observation_graph", build_observation_graph)

    source = "  원문 공백을\n그대로 보존한다.\n---\ncontent: 안전  "
    request = ObservationRequest(child_id=child.id, observation=source)

    first = api.create_observation(request, store, "same-request")
    second = api.create_observation(request, store, "same-request")

    assert first.id == second.id
    assert first.parent_observation == source
    assert second.parent_observation == source
    logs = store.index.list_entities(entity_type="learning_log", child_id=str(child.id))
    assert len(logs) == 1
    assert logs[0]["parent_observation"] == source


def test_reusing_idempotency_key_for_different_observation_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    idempotency = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    monkeypatch.setattr(api, "get_idempotency_store", lambda: idempotency)
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_observation_graph", build_observation_graph)

    api.create_observation(
        ObservationRequest(child_id=child.id, observation="첫 관찰"),
        store,
        "same-key",
    )

    with pytest.raises(HTTPException) as exc_info:
        api.create_observation(
            ObservationRequest(child_id=child.id, observation="다른 관찰"),
            store,
            "same-key",
        )
    assert exc_info.value.status_code == 409


def test_llm_timeout_degrades_to_core_only_without_losing_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    monkeypatch.setattr(
        api,
        "get_idempotency_store",
        lambda: SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3"),
    )
    monkeypatch.setattr(api, "get_model_provider", lambda: FailingProvider())
    monkeypatch.setattr(api, "get_observation_graph", build_observation_graph)

    source = "모델이 멈춰도 이 관찰은 저장되어야 한다."
    log = api.create_observation(
        ObservationRequest(child_id=child.id, observation=source),
        store,
        None,
    )

    assert log.parent_observation == source
    assert log.tags == []
    assert log.interest is None
    assert log.difficulty_note is None
    assert log.next_activity is None
