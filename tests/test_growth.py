from datetime import UTC, datetime, timedelta

from uuid6 import uuid7

from growwise.domain import ChildProfile, ExperienceAxis, LearningLog, Stage
from growwise.services import CoverageState, GrowthMapService
from growwise.storage import EntityStore


def test_growth_map_uses_explicit_axes_without_llm(tmp_path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)

    now = datetime.now(UTC)
    for index in range(3):
        log = LearningLog(
            child_id=child.id,
            parent_observation=f"책을 살펴본 기록 {index}",
            experience_axes=[ExperienceAxis.READING, ExperienceAxis.EXPLORATION],
            created_at=now - timedelta(days=index),
            updated_at=now - timedelta(days=index),
        )
        store.save(log)

    projection = GrowthMapService(store.index).project(
        child_id=str(child.id),
        period_days=30,
        now=now,
    )

    by_axis = {item.axis: item for item in projection.axes}
    assert projection.total_logs_in_period == 3
    assert projection.tagged_logs_in_period == 3
    assert by_axis[ExperienceAxis.READING].observation_count == 3
    assert by_axis[ExperienceAxis.READING].state is CoverageState.REPEATED_EXPERIENCE
    assert by_axis[ExperienceAxis.MATH].state is CoverageState.NOT_OBSERVED


def test_growth_map_ignores_other_children_and_old_logs(tmp_path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child_id = uuid7()
    other_child_id = uuid7()
    now = datetime.now(UTC)

    store.save(
        LearningLog(
            child_id=child_id,
            parent_observation="최근 신체 활동",
            experience_axes=[ExperienceAxis.PHYSICAL],
            created_at=now,
            updated_at=now,
        )
    )
    store.save(
        LearningLog(
            child_id=child_id,
            parent_observation="오래된 신체 활동",
            experience_axes=[ExperienceAxis.PHYSICAL],
            created_at=now - timedelta(days=90),
            updated_at=now - timedelta(days=90),
        )
    )
    store.save(
        LearningLog(
            child_id=other_child_id,
            parent_observation="다른 아이 기록",
            experience_axes=[ExperienceAxis.PHYSICAL],
            created_at=now,
            updated_at=now,
        )
    )

    projection = GrowthMapService(store.index).project(
        child_id=str(child_id),
        period_days=30,
        now=now,
    )
    physical = next(item for item in projection.axes if item.axis is ExperienceAxis.PHYSICAL)
    assert projection.total_logs_in_period == 1
    assert physical.observation_count == 1
    assert physical.state is CoverageState.RECENTLY_OBSERVED
