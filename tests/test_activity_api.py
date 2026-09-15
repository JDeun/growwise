from pathlib import Path

from growwise.api.main import (
    ActivityCreateRequest,
    ActivityTransitionRequest,
    create_activity,
    list_activities,
    transition_activity,
)
from growwise.domain import ActivityStatus, ChildProfile, Stage
from growwise.storage import EntityStore


def test_activity_api_flow_persists_low_pressure_states(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)

    activity = create_activity(
        child.id,
        ActivityCreateRequest(
            title="고양이 그림 함께 보기",
            source_refs=["resource:book-1"],
        ),
        store,
    )
    assert activity.status is ActivityStatus.SUGGESTED

    skipped = transition_activity(
        activity.id,
        ActivityTransitionRequest(
            status=ActivityStatus.SKIPPED,
            parent_note="오늘은 관심이 적었음",
        ),
        store,
    )
    assert skipped.status is ActivityStatus.SKIPPED

    resumed = transition_activity(
        activity.id,
        ActivityTransitionRequest(status=ActivityStatus.ACTIVE),
        store,
    )
    assert resumed.status is ActivityStatus.ACTIVE

    stored = list_activities(child.id, store)
    assert len(stored) == 1
    assert stored[0]["status"] == ActivityStatus.ACTIVE.value
    assert stored[0]["source_refs"] == ["resource:book-1"]
