from pathlib import Path

import pytest
from fastapi import HTTPException

import growwise.api.main as api
from growwise.domain import ChildProfile, Stage
from growwise.idempotency import IdempotencyStatus, SQLiteIdempotencyStore
from growwise.storage import EntityStore


class _ObservationGraph:
    def invoke(self, state: dict, config: dict) -> dict:
        del config
        return {
            "child_id": state["child_id"],
            "observation": state["observation"],
            "normalized_observation": " ".join(state["observation"].split()),
            "safety_flags": [],
        }


def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[EntityStore, ChildProfile]:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    idempotency = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")

    monkeypatch.setattr(api, "get_observation_graph", lambda: _ObservationGraph())
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_idempotency_store", lambda: idempotency)
    return store, child


def test_same_key_returns_same_learning_log_without_duplicate_side_effect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, child = _setup(monkeypatch, tmp_path)
    request = api.ObservationRequest(child_id=child.id, observation="고양이  그림을 오래 봄")

    first = api.create_observation(request, store, "observation-1")
    second = api.create_observation(request, store, "observation-1")

    assert second.id == first.id
    logs = store.index.list_entities(entity_type="learning_log", child_id=str(child.id))
    assert len(logs) == 1
    assert logs[0]["id"] == str(first.id)


def test_same_key_with_different_payload_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, child = _setup(monkeypatch, tmp_path)
    api.create_observation(
        api.ObservationRequest(child_id=child.id, observation="첫 관찰"),
        store,
        "observation-1",
    )

    with pytest.raises(HTTPException) as exc_info:
        api.create_observation(
            api.ObservationRequest(child_id=child.id, observation="다른 관찰"),
            store,
            "observation-1",
        )

    assert exc_info.value.status_code == 409


def test_failed_work_expires_pending_key_and_reuses_reserved_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, child = _setup(monkeypatch, tmp_path)
    idempotency = api.get_idempotency_store()

    class _FailingGraph:
        def invoke(self, state: dict, config: dict) -> dict:
            del state, config
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(api, "get_observation_graph", lambda: _FailingGraph())
    request = api.ObservationRequest(child_id=child.id, observation="재시도 가능한 관찰")

    with pytest.raises(RuntimeError):
        api.create_observation(request, store, "observation-retry")

    pending = idempotency.get("observation-retry")
    assert pending is not None
    assert pending.status is IdempotencyStatus.PENDING
    reserved_id = pending.resource_id

    monkeypatch.setattr(api, "get_observation_graph", lambda: _ObservationGraph())
    recovered = api.create_observation(request, store, "observation-retry")
    assert recovered.parent_observation == "재시도 가능한 관찰"
    assert str(recovered.id) == reserved_id
