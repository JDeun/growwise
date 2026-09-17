from __future__ import annotations

from pathlib import Path

from growwise.api.learning_record_routes import (
    LearningRecordRequest,
    create_learning_record,
    list_learning_records,
)
from growwise.config import Settings
from growwise.domain import ChildProfile, LearningRecordKind, Stage
from growwise.storage import EntityStore


def _store(tmp_path: Path) -> EntityStore:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
    )
    return EntityStore(settings.records_dir, settings.index_path)


def test_independent_learning_record_does_not_require_activity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path)
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    monkeypatch.setattr(
        "growwise.api.learning_record_routes.queue_learning_log_enrichment",
        lambda **_kwargs: None,
    )

    record = create_learning_record(
        child.id,
        LearningRecordRequest(
            kind=LearningRecordKind.READING_REFLECTION,
            title="어린 왕자 독서감상",
            summary="별과 장미 이야기를 읽고 책임에 대해 이야기했다.",
            learner_work="가장 기억에 남는 것은 장미였다.",
            subject="국어",
        ),
        store,
    )

    assert record.activity_plan_id is None
    assert record.record_kind is LearningRecordKind.READING_REFLECTION
    assert record.title == "어린 왕자 독서감상"
    assert record.learner_work == "가장 기억에 남는 것은 장미였다."


def test_shared_learning_record_is_one_entity_visible_to_both_children(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path)
    first = ChildProfile(name="첫째", nickname="첫째", stage=Stage.ELEMENTARY)
    second = ChildProfile(name="둘째", nickname="둘째", stage=Stage.ELEMENTARY)
    store.save(first)
    store.save(second)
    monkeypatch.setattr(
        "growwise.api.learning_record_routes.queue_learning_log_enrichment",
        lambda **_kwargs: None,
    )

    created = create_learning_record(
        first.id,
        LearningRecordRequest(
            kind=LearningRecordKind.INSTITUTION,
            title="과학관 공동 수업",
            summary="두 아이가 자석 실험 수업에 함께 참여했다.",
            institution="어린이 과학관",
            shared_child_ids=[second.id],
        ),
        store,
    )

    first_records = list_learning_records(first.id, store)
    second_records = list_learning_records(second.id, store)

    assert [record.id for record in first_records] == [created.id]
    assert [record.id for record in second_records] == [created.id]
    assert second_records[0].child_id == first.id
