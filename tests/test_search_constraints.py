from datetime import UTC, date, datetime, timedelta

import pytest

from growwise.domain import ChildProfile, ExperienceAxis, LearningLog, LearningRecordKind, Stage
from growwise.services.context import ChildContextService, _entity_text
from growwise.services.search import NaturalLanguageSearch
from growwise.storage import EntityStore


def _fixture(tmp_path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="합성 검색", stage=Stage.ELEMENTARY, age_months=96)
    other = ChildProfile(nickname="다른 합성 검색", stage=Stage.ELEMENTARY, age_months=96)
    store.save(child)
    store.save(other)
    return store, child, other


def _log(store, child, *, event, created, axis=ExperienceAxis.PHYSICAL, text="공원에서 달리기"):
    log = LearningLog(
        child_id=child.id, parent_observation=text, experience_axes=[axis],
        occurred_at=event, created_at=created, updated_at=created,
    )
    store.save(log)
    return log


def test_documented_month_physical_query_filters_event_time_before_limit(tmp_path):
    store, child, other = _fixture(tmp_path)
    now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    old = now - timedelta(days=90)
    wanted = _log(store, child, event=now - timedelta(days=1), created=old)
    _log(store, child, event=old, created=now)  # Backfilled today is not a recent experience.
    _log(store, child, event=now, created=now, axis=ExperienceAxis.MATH)
    _log(store, other, event=now, created=now)
    result = NaturalLanguageSearch(store.index).search(
        child_id=str(child.id), query="최근 한 달 신체 활동 기록만 찾아줘",
        reference_date=date(2026, 11, 3), limit=1,
    )
    assert result.plan.start_date == date(2026, 10, 5)
    assert result.plan.end_date == date(2026, 11, 3)
    assert result.plan.experience_axes == ["physical"]
    assert [row["id"] for row in result.results] == [str(wanted.id)]
    evidence = _entity_text(result.results[0])
    assert "경험·기록 시각" in evidence
    assert wanted.occurred_at.astimezone().isoformat() in evidence


def test_last_measurement_query_orders_occurrence_instead_of_edit_time(tmp_path):
    store, child, _ = _fixture(tmp_path)
    now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    wanted = _log(store, child, event=now, created=now - timedelta(days=4),
                  axis=ExperienceAxis.MATH, text="측정: 물건 길이를 비교했다")
    _log(store, child, event=now - timedelta(days=20), created=now,
         axis=ExperienceAxis.MATH, text="측정: 블록 길이를 재었다")
    result = NaturalLanguageSearch(store.index).search(
        child_id=str(child.id), query="측정 관련 수학 활동을 마지막으로 한 게 언제야?",
    )
    assert result.plan.keywords == ["측정"]
    assert result.plan.order == "newest"
    assert result.plan.limit == 1
    assert [row["id"] for row in result.results] == [str(wanted.id)]


@pytest.mark.parametrize("provider_mode", ["failed", "drops_filters"])
def test_optional_rewrite_cannot_drop_explicit_filters(tmp_path, provider_mode):
    store, child, _ = _fixture(tmp_path)
    now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    wanted = _log(store, child, event=now, created=now)
    _log(store, child, event=now - timedelta(days=90), created=now)

    class Provider:
        def generate_structured(self, *, schema, **_):
            if provider_mode == "failed":
                raise RuntimeError("synthetic provider unavailable")
            return schema.model_validate({"keywords": ["invented"], "limit": 50})

    result = NaturalLanguageSearch(store.index, Provider()).search(
        child_id=str(child.id), query="최근 한 달 신체 활동 기록만 찾아줘",
        reference_date=date(2026, 11, 3),
    )
    assert [row["id"] for row in result.results] == [str(wanted.id)]


def test_explicit_calendar_range_legacy_fallback_and_literal_topic(tmp_path):
    store, child, _ = _fixture(tmp_path)
    legacy = _log(store, child, event=None, created=datetime(2026, 10, 15, 12, tzinfo=UTC),
                  text="북한 지역의 지형을 지도에서 살펴보았다")
    result = NaturalLanguageSearch(store.index).search(
        child_id=str(child.id), query="2026-10-01부터 2026-10-31까지 북한 기록 찾아줘",
    )
    assert result.plan.keywords == ["북한"]
    assert [row["id"] for row in result.results] == [str(legacy.id)]
    plan = NaturalLanguageSearch(store.index).plan(
        "지난달 기록", reference_date=date(2026, 3, 2),
    )
    assert (plan.start_date, plan.end_date) == (date(2026, 2, 1), date(2026, 2, 28))


def test_subject_and_reading_kind_do_not_require_duplicate_axis_tags(tmp_path):
    store, child, _ = _fixture(tmp_path)
    for subject, kind, query in [
        ("수학", LearningRecordKind.SELF_STUDY, "최근 수학 기록 찾아줘"),
        (None, LearningRecordKind.READING_REFLECTION, "최근 읽은 동물 주제 책을 정리해줘"),
    ]:
        record = LearningLog(
            child_id=child.id, subject=subject, record_kind=kind,
            parent_observation="동물의 생활을 탐색했다", experience_axes=[],
        )
        store.save(record)
        result = NaturalLanguageSearch(store.index).search(child_id=str(child.id), query=query)
        assert [row["id"] for row in result.results] == [str(record.id)]


@pytest.mark.parametrize("query,start,end", [
    ("오늘 기록", date(2026, 11, 3), date(2026, 11, 3)),
    ("어제 기록", date(2026, 11, 2), date(2026, 11, 2)),
    ("지난주 기록", date(2026, 10, 26), date(2026, 11, 1)),
    ("이번 주 기록", date(2026, 11, 2), date(2026, 11, 3)),
])
def test_calendar_words_have_explicit_local_date_boundaries(query, start, end):
    plan = NaturalLanguageSearch.explicit_plan(query, 8, date(2026, 11, 3))
    assert (plan.start_date, plan.end_date) == (start, end)
    assert plan.keywords == []


def test_conversation_uses_same_filters_without_adding_unfiltered_neighbors(tmp_path):
    store, child, other = _fixture(tmp_path)
    now = datetime.now(UTC)
    wanted = _log(store, child, event=now - timedelta(days=1), created=now - timedelta(days=90))
    excluded = _log(store, child, event=now - timedelta(days=90), created=now)
    _log(store, other, event=now, created=now)

    class Rag:
        def search(self, **_):
            pytest.fail("An unfiltered RAG neighbor must not bypass explicit date/axis filters")

    answer = ChildContextService(entity_index=store.index, rag_index=Rag(), provider=None).ask(
        child_id=str(child.id), query="최근 한 달 신체 활동 기록만 찾아줘",
    )
    assert answer.source_ids == [f"record:{wanted.id}"]
    assert f"record:{excluded.id}" not in answer.source_ids
