from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import growwise.api.main as api
from growwise.api.main import ActivityCreateRequest
from growwise.domain import ActivityPlan, ActivityStatus, ChildProfile, Stage
from growwise.idempotency import SQLiteIdempotencyStore
from growwise.services import ActivityPlanService, InvalidActivityTransition
from growwise.storage import EntityStore


def _store_with_child(tmp_path: Path) -> tuple[EntityStore, ChildProfile]:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="수아", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    return store, child


def test_duplicate_activity_submit_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    idempotency = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    monkeypatch.setattr(api, "get_idempotency_store", lambda: idempotency)
    request = ActivityCreateRequest(
        title="그림 함께 보기",
        source_refs=["resource:book-1"],
        parent_note="오늘 관심이 있으면 해보기",
    )

    first = api.create_activity(child.id, request, store, "activity-1")
    second = api.create_activity(child.id, request, store, "activity-1")

    assert first.id == second.id
    assert first.status is ActivityStatus.SUGGESTED
    activities = store.index.list_entities(entity_type="activity_plan", child_id=str(child.id))
    assert len(activities) == 1
    assert activities[0]["source_refs"] == ["resource:book-1"]


def test_activity_idempotency_key_cannot_be_reused_for_different_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    idempotency = SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3")
    monkeypatch.setattr(api, "get_idempotency_store", lambda: idempotency)

    api.create_activity(
        child.id,
        ActivityCreateRequest(title="첫 활동"),
        store,
        "same-key",
    )
    with pytest.raises(HTTPException) as exc_info:
        api.create_activity(
            child.id,
            ActivityCreateRequest(title="다른 활동"),
            store,
            "same-key",
        )
    assert exc_info.value.status_code == 409


def test_activity_cannot_skip_directly_to_completed() -> None:
    activity = ActivityPlan(child_id=ChildProfile(
        nickname="수아", stage=Stage.INFANT_0_2, age_months=9
    ).id, title="촉감 놀이")

    with pytest.raises(InvalidActivityTransition):
        ActivityPlanService().transition(activity, ActivityStatus.COMPLETED)


def test_archived_activity_is_terminal() -> None:
    child = ChildProfile(nickname="수아", stage=Stage.INFANT_0_2, age_months=9)
    activity = ActivityPlan(child_id=child.id, title="소리 놀이")
    service = ActivityPlanService()
    service.transition(activity, ActivityStatus.ARCHIVED)

    with pytest.raises(InvalidActivityTransition):
        service.transition(activity, ActivityStatus.ACTIVE)


def test_skipped_activity_remains_reversible_and_non_failure() -> None:
    child = ChildProfile(nickname="수아", stage=Stage.INFANT_0_2, age_months=9)
    activity = ActivityPlan(child_id=child.id, title="책 보기")
    service = ActivityPlanService()

    service.transition(activity, ActivityStatus.SKIPPED, parent_note="오늘은 다른 놀이를 선택함")
    skipped_at = activity.skipped_at
    assert skipped_at is not None
    assert activity.completed_at is None

    service.transition(activity, ActivityStatus.ACTIVE)
    assert activity.status is ActivityStatus.ACTIVE
    assert activity.started_at is not None
    assert activity.completed_at is None


def test_activity_request_bounds_parent_authored_fields() -> None:
    accepted = ActivityCreateRequest(title="가" * 500, parent_note="나" * 2000)
    assert len(accepted.title) == 500
    assert len(accepted.parent_note or "") == 2000

    with pytest.raises(ValidationError):
        ActivityCreateRequest(title="가" * 501)
    with pytest.raises(ValidationError):
        ActivityCreateRequest(title="활동", parent_note="나" * 2001)
