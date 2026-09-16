from __future__ import annotations

from pathlib import Path

from growwise.api.main import app
from growwise.api.material_result_routes import (
    MaterialResultRequest,
    MaterialUseOutcome,
    list_material_results,
    record_material_result,
)
from growwise.config import Settings
from growwise.domain.models import (
    ActivityStatus,
    ChildProfile,
    ExperienceAxis,
    GeneratedMaterial,
    MaterialKind,
    MaterialStatus,
    Stage,
)
from growwise.services.growth import GrowthMapService
from growwise.storage import EntityStore


def _store(tmp_path: Path) -> EntityStore:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        embedding_features_enabled=False,
        vision_features_enabled=False,
    )
    return EntityStore(settings.records_dir, settings.index_path)


def _approved_material(store: EntityStore) -> tuple[ChildProfile, GeneratedMaterial]:
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    material = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.SCIENCE_INQUIRY,
        title="얼음 관찰 과학 탐구",
        content_markdown="# 얼음 관찰\n\n예측하고 관찰한다.",
        status=MaterialStatus.APPROVED,
        generator_mode="template",
    )
    store.save(material)
    return child, material


def test_printed_material_result_becomes_activity_and_learning_log(tmp_path: Path) -> None:
    store = _store(tmp_path)
    child, material = _approved_material(store)

    result = record_material_result(
        material.id,
        MaterialResultRequest(
            outcome=MaterialUseOutcome.COMPLETED,
            observation="얼음이 녹으면서 물이 생기는 모습을 오래 관찰했다.",
            process="처음 예상과 실제 모습을 비교했다.",
            child_question="왜 접시에도 물이 생겨?",
            interest="얼음이 작아지는 과정",
            difficulty_note="시간에 따른 변화를 말로 정리하는 것은 어려워했다.",
            next_activity="같은 크기의 얼음을 햇빛과 그늘에서 비교한다.",
            tags=["얼음", "관찰"],
            experience_axes=[ExperienceAxis.EXPLORATION, ExperienceAxis.THINKING_INQUIRY],
        ),
        store,
    )

    assert result.activity.status is ActivityStatus.COMPLETED
    assert result.activity.source_refs == [f"material:{material.id}"]
    assert result.learning_log.activity_plan_id == result.activity.id
    assert result.learning_log.process == "처음 예상과 실제 모습을 비교했다."
    assert result.learning_log.child_question == "왜 접시에도 물이 생겨?"
    assert "material-use" in result.learning_log.tags
    assert material.kind.value in result.learning_log.tags

    growth = GrowthMapService(store.index).project(
        child_id=str(child.id),
        stage=child.stage,
    )
    assert growth.total_logs_in_period == 1
    assert growth.tagged_logs_in_period == 1

    links = store.index.list_entities(entity_type="entity_link")
    relations = {item["relation"] for item in links}
    assert {"supports", "documents", "derived_from"}.issubset(relations)


def test_partial_result_keeps_material_activity_open_for_follow_up(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _, material = _approved_material(store)

    first = record_material_result(
        material.id,
        MaterialResultRequest(
            outcome=MaterialUseOutcome.PARTIAL,
            observation="앞부분만 해 보고 나머지는 다음에 이어가기로 했다.",
            experience_axes=[ExperienceAxis.EXPLORATION],
        ),
        store,
    )
    assert first.activity.status is ActivityStatus.ACTIVE

    second = record_material_result(
        material.id,
        MaterialResultRequest(
            outcome=MaterialUseOutcome.COMPLETED,
            observation="남은 관찰까지 마쳤다.",
            activity_plan_id=first.activity.id,
            experience_axes=[ExperienceAxis.EXPLORATION],
        ),
        store,
    )
    assert second.activity.id == first.activity.id
    assert second.activity.status is ActivityStatus.COMPLETED

    history = list_material_results(material.id, store)
    assert len(history) == 1
    assert history[0].activity.id == first.activity.id
    assert len(history[0].learning_logs) == 2


def test_material_result_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/v1/materials/{material_id}/results" in paths
