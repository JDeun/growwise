from __future__ import annotations

from pathlib import Path

from growwise.api.material_result_routes import MaterialResultRequest, record_material_result
from growwise.config import Settings
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, MaterialStatus, Stage
from growwise.services.material_quest import ensure_material_quest, material_quest_ref
from growwise.storage import EntityStore


def _approved(tmp_path: Path) -> tuple[EntityStore, ChildProfile, GeneratedMaterial]:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        embedding_features_enabled=False,
        vision_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    material = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.READING_ACTIVITY,
        title="읽고 질문하기",
        content_markdown="# 읽기 활동",
        status=MaterialStatus.APPROVED,
        generator_mode="deterministic_template",
    )
    store.save(material)
    return store, child, material


def test_ensure_material_quest_is_idempotent_and_links_material(tmp_path: Path) -> None:
    store, child, material = _approved(tmp_path)

    first = ensure_material_quest(store=store, material=material)
    second = ensure_material_quest(store=store, material=material)

    assert first.id == second.id
    assert first.child_id == child.id
    assert first.source_refs == [material_quest_ref(material.id)]
    quests = [
        item
        for item in store.index.list_entities(entity_type="activity_plan", child_id=str(child.id))
        if material_quest_ref(material.id) in item.get("source_refs", [])
    ]
    assert len(quests) == 1
    supports = [
        item
        for item in store.index.list_entities(entity_type="entity_link")
        if item["source_id"] == str(material.id)
        and item["target_id"] == str(first.id)
        and item["relation"] == "supports"
    ]
    assert len(supports) == 1


def test_result_without_activity_id_reuses_existing_material_quest(tmp_path: Path) -> None:
    store, child, material = _approved(tmp_path)
    quest = ensure_material_quest(store=store, material=material)

    first = record_material_result(
        material.id,
        MaterialResultRequest(
            outcome="partial",
            observation="앞부분을 먼저 해봤다.",
        ),
        store,
    )
    second = record_material_result(
        material.id,
        MaterialResultRequest(
            outcome="completed",
            observation="나머지까지 마쳤다.",
        ),
        store,
    )

    assert first.activity.id == quest.id
    assert second.activity.id == quest.id
    quests = [
        item
        for item in store.index.list_entities(entity_type="activity_plan", child_id=str(child.id))
        if material_quest_ref(material.id) in item.get("source_refs", [])
    ]
    assert len(quests) == 1
    result_logs = [
        item
        for item in store.index.list_entities(entity_type="learning_log", child_id=str(child.id))
        if item.get("activity_plan_id") == str(quest.id)
    ]
    assert len(result_logs) == 2
