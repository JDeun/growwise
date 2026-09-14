import pytest
from uuid6 import uuid7

from growwise.domain import ActivityPlan, ActivityStatus
from growwise.services import ActivityPlanService, InvalidActivityTransition


def test_activity_can_be_skipped_without_failure_and_resumed() -> None:
    activity = ActivityPlan(child_id=uuid7(), title="책 함께 보기")
    service = ActivityPlanService()

    service.transition(activity, ActivityStatus.SKIPPED, parent_note="오늘은 관심이 없었음")
    assert activity.status is ActivityStatus.SKIPPED
    assert activity.completed_at is None

    service.transition(activity, ActivityStatus.ACTIVE)
    assert activity.status is ActivityStatus.ACTIVE


def test_activity_completion_sets_timestamp() -> None:
    activity = ActivityPlan(child_id=uuid7(), title="촉감 탐색")
    service = ActivityPlanService()

    service.transition(activity, ActivityStatus.ACTIVE)
    service.transition(activity, ActivityStatus.COMPLETED)

    assert activity.status is ActivityStatus.COMPLETED
    assert activity.completed_at is not None


def test_completed_activity_cannot_be_marked_skipped() -> None:
    activity = ActivityPlan(child_id=uuid7(), title="소리 놀이")
    service = ActivityPlanService()
    service.transition(activity, ActivityStatus.ACTIVE)
    service.transition(activity, ActivityStatus.COMPLETED)

    with pytest.raises(InvalidActivityTransition):
        service.transition(activity, ActivityStatus.SKIPPED)
