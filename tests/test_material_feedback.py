from __future__ import annotations

import pytest

import growwise.api.background_write_routes as background_routes
from growwise.domain import ChildProfile, LearningLog, LearningRecordKind, Stage
from growwise.services.material_feedback import MaterialFeedbackService
from growwise.storage import EntityStore


def _store(tmp_path) -> EntityStore:
    return EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")


def test_material_feedback_uses_only_same_child_material_use_logs(tmp_path) -> None:
    store = _store(tmp_path)
    child = ChildProfile(nickname="아이 A", stage=Stage.ELEMENTARY, age_months=108)
    sibling = ChildProfile(nickname="아이 B", stage=Stage.ELEMENTARY, age_months=120)
    store.save(child)
    store.save(sibling)

    store.save(
        LearningLog(
            child_id=child.id,
            record_kind=LearningRecordKind.OBSERVATION,
            parent_observation="일반 관찰은 자료 사용 피드백으로 섞이면 안 된다.",
        )
    )
    store.save(
        LearningLog(
            child_id=sibling.id,
            record_kind=LearningRecordKind.MATERIAL_USE,
            title="형제 자료",
            parent_observation="다른 아이의 결과도 섞이면 안 된다.",
            interest="다른 아이 관심",
        )
    )
    material_log = LearningLog(
        child_id=child.id,
        record_kind=LearningRecordKind.MATERIAL_USE,
        title="달 관찰 활동",
        parent_observation="그림자의 모양을 오래 비교했다.",
        child_question="왜 매일 모양이 달라져?",
        interest="달의 모양 변화",
        difficulty_note="날짜 순서로 배열하는 부분은 어려워했다.",
        next_activity="며칠 동안 같은 시각에 달을 다시 관찰한다.",
    )
    store.save(material_log)

    snapshot = MaterialFeedbackService(store.index).snapshot(child_id=str(child.id))

    assert [item.log_id for item in snapshot.items] == [material_log.id]
    goal = snapshot.generation_goal("관찰을 이어간다")
    assert goal is not None
    assert "개인화 원칙" in goal
    assert "달의 모양 변화" not in goal
    assert "날짜 순서" not in goal
    assert "왜 매일" not in goal

    guide = snapshot.with_parent_guide("# 기존 부모 교안\n")
    assert "그림자의 모양을 오래 비교했다." in guide
    assert "왜 매일 모양이 달라져?" in guide
    assert "달의 모양 변화" in guide
    assert "날짜 순서로 배열하는 부분은 어려워했다." in guide
    assert "며칠 동안 같은 시각에 달을 다시 관찰한다." in guide
    assert "일반 관찰은" not in guide
    assert "다른 아이의 결과" not in guide


def test_feedback_parent_guide_block_is_replaced_not_duplicated(tmp_path) -> None:
    store = _store(tmp_path)
    child = ChildProfile(nickname="아이", stage=Stage.PRESCHOOL_3_5, age_months=60)
    store.save(child)
    store.save(
        LearningLog(
            child_id=child.id,
            record_kind=LearningRecordKind.MATERIAL_USE,
            title="색 놀이",
            parent_observation="파란색을 여러 번 골랐다.",
        )
    )
    snapshot = MaterialFeedbackService(store.index).snapshot(child_id=str(child.id))

    once = snapshot.with_parent_guide("# 부모 교안")
    twice = snapshot.with_parent_guide(once)

    assert twice.count("growwise-material-feedback:start") == 1
    assert twice.count("파란색을 여러 번 골랐다.") == 1


def test_background_material_generation_closes_loop_without_leaking_raw_feedback(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    child = ChildProfile(nickname="아이", stage=Stage.ELEMENTARY, age_months=108)
    store.save(child)
    store.save(
        LearningLog(
            child_id=child.id,
            record_kind=LearningRecordKind.MATERIAL_USE,
            title="이전 수학 놀이",
            parent_observation="부모만 보는 구체 관찰 문장",
            child_question="이것도 반으로 나눌 수 있어?",
            interest="반으로 나누기",
            difficulty_note="세 묶음으로 나누는 것은 어려워했다.",
            next_activity="간식을 둘로 나누는 놀이를 이어간다.",
        )
    )
    monkeypatch.setattr(background_routes, "_init_review", lambda _material: None)
    monkeypatch.setattr(
        background_routes,
        "queue_material_enhancement",
        lambda *, material, store: None,
    )

    request = background_routes.BackgroundMaterialRequest(
        kind="math_activity",
        topic="생활 속 나누기",
        goal="실물로 나누는 방법을 탐색한다",
    )
    material = background_routes.generate_material_background(child.id, request, store)

    assert "개인화 원칙" in material.content_markdown
    assert "부모만 보는 구체 관찰 문장" not in material.content_markdown
    assert "세 묶음으로 나누는 것은 어려워했다." not in material.content_markdown
    assert "부모만 보는 구체 관찰 문장" in material.parent_guide_markdown
    assert "간식을 둘로 나누는 놀이를 이어간다." in material.parent_guide_markdown
    assert material.request_goal == "실물로 나누는 방법을 탐색한다"
