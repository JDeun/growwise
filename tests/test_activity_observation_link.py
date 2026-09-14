from pathlib import Path

import pytest
from fastapi import HTTPException

from growwise.api.main import list_activity_observations, validate_activity_link
from growwise.domain import ActivityPlan, ChildProfile, LearningLog, Stage
from growwise.storage import EntityStore


def test_activity_link_is_child_scoped(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    first = ChildProfile(nickname="수아", stage=Stage.INFANT_0_2, age_months=9)
    second = ChildProfile(nickname="다른 아이", stage=Stage.INFANT_0_2, age_months=10)
    store.save(first)
    store.save(second)
    activity = ActivityPlan(child_id=first.id, title="그림 함께 보기")
    store.save(activity)

    linked = validate_activity_link(
        store=store,
        child_id=first.id,
        activity_plan_id=activity.id,
    )
    assert linked is not None
    assert linked.id == activity.id

    with pytest.raises(HTTPException) as exc_info:
        validate_activity_link(
            store=store,
            child_id=second.id,
            activity_plan_id=activity.id,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "activity_child_mismatch"


def test_activity_observation_listing_uses_explicit_provenance(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="수아", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    activity = ActivityPlan(child_id=child.id, title="소리 탐색")
    store.save(activity)

    linked = LearningLog(
        child_id=child.id,
        activity_plan_id=activity.id,
        parent_observation="방울 소리를 듣고 여러 번 손을 뻗었다.",
    )
    unrelated = LearningLog(
        child_id=child.id,
        parent_observation="책장을 천천히 넘겼다.",
    )
    store.save(linked)
    store.save(unrelated)

    results = list_activity_observations(activity.id, store)
    assert len(results) == 1
    assert results[0]["id"] == str(linked.id)
    assert results[0]["activity_plan_id"] == str(activity.id)
