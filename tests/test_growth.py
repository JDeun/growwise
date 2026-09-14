from datetime import UTC, datetime, timedelta

from uuid6 import uuid7

from growwise.domain import ChildProfile, ExperienceAxis, LearningLog, Stage
from growwise.services import CoverageState, DiversityState, GrowthMapService
from growwise.storage import EntityStore


def _save_log(
    store: EntityStore,
    *,
    child_id,
    axes: list[ExperienceAxis],
    created_at: datetime,
    label: str,
) -> None:
    store.save(
        LearningLog(
            child_id=child_id,
            parent_observation=label,
            experience_axes=axes,
            created_at=created_at,
            updated_at=created_at,
        )
    )


def test_growth_map_uses_explicit_axes_without_llm(tmp_path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)

    now = datetime.now(UTC)
    for index in range(3):
        _save_log(
            store,
            child_id=child.id,
            axes=[ExperienceAxis.READING, ExperienceAxis.EXPLORATION],
            created_at=now - timedelta(days=index),
            label=f"책을 살펴본 기록 {index}",
        )

    projection = GrowthMapService(store.index).project(
        child_id=str(child.id),
        period_days=30,
        stage=child.stage,
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

    _save_log(
        store,
        child_id=child_id,
        axes=[ExperienceAxis.PHYSICAL],
        created_at=now,
        label="최근 신체 활동",
    )
    _save_log(
        store,
        child_id=child_id,
        axes=[ExperienceAxis.PHYSICAL],
        created_at=now - timedelta(days=90),
        label="오래된 신체 활동",
    )
    _save_log(
        store,
        child_id=other_child_id,
        axes=[ExperienceAxis.PHYSICAL],
        created_at=now,
        label="다른 아이 기록",
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


def test_growth_map_exposes_three_non_diagnostic_layers_for_stage(tmp_path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="초등", stage=Stage.ELEMENTARY, age_months=108)
    store.save(child)
    projection = GrowthMapService(store.index).project(
        child_id=str(child.id),
        stage=child.stage,
    )

    assert projection.stage is Stage.ELEMENTARY
    assert [layer.key for layer in projection.layers] == [
        "whole_person",
        "learning",
        "stage_focus",
    ]
    stage_layer = projection.layers[-1]
    assert stage_layer.label == "초등 학습 렌즈"
    assert {item.axis for item in stage_layer.axes} == {
        ExperienceAxis.READING,
        ExperienceAxis.SPEAKING,
        ExperienceAxis.WRITING,
        ExperienceAxis.MATH,
        ExperienceAxis.EXPLORATION,
        ExperienceAxis.SOCIAL,
    }


def test_diversity_does_not_label_sparse_history_as_concentrated(tmp_path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="초등", stage=Stage.ELEMENTARY, age_months=108)
    store.save(child)
    now = datetime.now(UTC)
    for index in range(4):
        _save_log(
            store,
            child_id=child.id,
            axes=[ExperienceAxis.READING],
            created_at=now - timedelta(days=index),
            label=f"읽기 {index}",
        )

    projection = GrowthMapService(store.index).project(
        child_id=str(child.id),
        stage=child.stage,
        now=now,
    )
    assert projection.diversity.state is DiversityState.INSUFFICIENT_DATA
    assert projection.diversity.focus_axes == []
    assert "능력" in projection.diversity.note


def test_diversity_marks_repeated_focus_without_scoring_child(tmp_path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="초등", stage=Stage.ELEMENTARY, age_months=108)
    store.save(child)
    now = datetime.now(UTC)
    for index in range(6):
        axis = ExperienceAxis.READING if index < 5 else ExperienceAxis.SOCIAL
        _save_log(
            store,
            child_id=child.id,
            axes=[axis],
            created_at=now - timedelta(days=index),
            label=f"경험 {index}",
        )

    projection = GrowthMapService(store.index).project(
        child_id=str(child.id),
        stage=child.stage,
        now=now,
    )
    assert projection.diversity.state is DiversityState.CONCENTRATED
    assert projection.diversity.focus_axes == [ExperienceAxis.READING]
    assert "능력 평가가 아닙니다" in projection.diversity.note


def test_diversity_recognizes_varied_recent_experiences(tmp_path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="초등", stage=Stage.ELEMENTARY, age_months=108)
    store.save(child)
    now = datetime.now(UTC)
    axes = [
        ExperienceAxis.READING,
        ExperienceAxis.SPEAKING,
        ExperienceAxis.WRITING,
        ExperienceAxis.MATH,
        ExperienceAxis.EXPLORATION,
        ExperienceAxis.SOCIAL,
    ]
    for index, axis in enumerate(axes):
        _save_log(
            store,
            child_id=child.id,
            axes=[axis],
            created_at=now - timedelta(days=index),
            label=f"경험 {index}",
        )

    projection = GrowthMapService(store.index).project(
        child_id=str(child.id),
        stage=child.stage,
        now=now,
    )
    assert projection.diversity.state is DiversityState.VARIED
    assert projection.diversity.observed_axis_count == 6
