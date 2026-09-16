from __future__ import annotations

from pathlib import Path

from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.domain.study import (
    MistakeRecord,
    MistakeType,
    StudyPlan,
    StudyPlanItem,
    StudyReflection,
)
from growwise.rag import HybridRagIndex
from growwise.services.context import ChildContextService, _entity_text
from growwise.storage import EntityStore


def test_child_context_retrieves_secondary_study_records_without_cross_child_leakage(
    tmp_path: Path,
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        embedding_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="중학생", stage=Stage.MIDDLE, age_months=168)
    sibling = ChildProfile(nickname="고등학생", stage=Stage.HIGH, age_months=204)
    store.save(child)
    store.save(sibling)

    mistake = MistakeRecord(
        child_id=child.id,
        subject="수학",
        unit="일차함수",
        mistake_type=MistakeType.CONCEPT,
        learner_response="기울기를 y절편으로 설명했다.",
        corrected_understanding="기울기는 x 변화량에 대한 y 변화량이다.",
    )
    reflection = StudyReflection(
        child_id=child.id,
        subject="수학",
        unit="일차함수",
        difficult_point="식과 그래프를 바로 연결하는 부분이 어려웠다.",
        next_step="식과 그래프를 번갈아 설명해 본다.",
    )
    sibling_mistake = MistakeRecord(
        child_id=sibling.id,
        subject="수학",
        unit="일차함수",
        mistake_type=MistakeType.PROCESS,
        learner_response="다른 아이의 비공개 풀이",
    )
    store.save(mistake)
    store.save(reflection)
    store.save(sibling_mistake)

    service = ChildContextService(
        entity_index=store.index,
        rag_index=HybridRagIndex(settings.rag_index_path, embedding=None),
        provider=None,
    )
    answer = service.ask(child_id=str(child.id), query="일차함수", limit=8)

    assert answer.insufficient_evidence is False
    assert f"record:{mistake.id}" in answer.source_ids
    assert f"record:{reflection.id}" in answer.source_ids
    assert f"record:{sibling_mistake.id}" not in answer.source_ids

    mistake_payload = store.index.get_entity(str(mistake.id), entity_type="mistake_record")
    assert mistake_payload is not None
    evidence = _entity_text(mistake_payload)
    assert "단원·주제: 일차함수" in evidence
    assert "아이 답·풀이: 기울기를 y절편으로 설명했다." in evidence
    assert "다시 확인한 이해: 기울기는 x 변화량에 대한 y 변화량이다." in evidence


def test_study_plan_items_are_serialized_as_bounded_context_evidence(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="중학생", stage=Stage.MIDDLE, age_months=168)
    store.save(child)
    plan = StudyPlan(
        child_id=child.id,
        title="중간고사 복습",
        items=[
            StudyPlanItem(
                subject="수학",
                unit="일차함수",
                focus="식과 그래프의 대응을 다시 설명한다.",
            )
        ],
    )
    store.save(plan)

    payload = store.index.get_entity(str(plan.id), entity_type="study_plan")
    assert payload is not None
    evidence = _entity_text(payload)

    assert "제목: 중간고사 복습" in evidence
    assert "계획 항목 1: 수학 · 일차함수" in evidence
    assert "식과 그래프의 대응을 다시 설명한다." in evidence
    assert "상태=planned" in evidence
    assert len(evidence) <= 12_000
