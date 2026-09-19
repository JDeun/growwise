from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

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
    LearningLog,
    LearningRecordKind,
    MaterialKind,
    MaterialStatus,
    Stage,
)
from growwise.domain.photo import PhotoActivityRecord, PhotoRecordStatus
from growwise.idempotency import SQLiteIdempotencyStore
from growwise.services.entity_links import EntityLinkService
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


def _committed_photo_record(
    store: EntityStore,
    child: ChildProfile,
    *,
    observation: str = "실제 활동 사진을 부모가 검토했다.",
) -> PhotoActivityRecord:
    photo_log = LearningLog(
        child_id=child.id,
        record_kind=LearningRecordKind.PHOTO_ACTIVITY,
        parent_observation=observation,
        tags=["사진기록"],
    )
    store.save(photo_log)
    record = PhotoActivityRecord(
        child_id=child.id,
        photo_asset_ids=[uuid4()],
        generated_observation=observation,
        generation_mode="manual_photo_diary",
        status=PhotoRecordStatus.COMMITTED,
        learning_log_id=photo_log.id,
    )
    store.save(record)
    return record


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


def test_material_result_links_reviewed_photo_evidence_without_copying_image(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    child, material = _approved_material(store)
    photo = _committed_photo_record(store, child)

    result = record_material_result(
        material.id,
        MaterialResultRequest(
            observation="활동지를 마친 뒤 결과 사진도 함께 남겼다.",
            photo_record_ids=[photo.id],
        ),
        store,
    )

    links = store.index.list_entities(entity_type="entity_link")
    evidence_links = [
        item
        for item in links
        if item["source_id"] == str(photo.id)
        and item["target_id"] == str(result.learning_log.id)
        and item["relation"] == "documents"
    ]
    assert len(evidence_links) == 1
    assert evidence_links[0]["label"] == "활동 결과 사진 기록"
    assert store.index.get_entity(str(photo.id), entity_type="photo_activity_record") is not None


def test_material_result_rejects_unreviewed_photo_evidence(tmp_path: Path) -> None:
    store = _store(tmp_path)
    child, material = _approved_material(store)
    draft = PhotoActivityRecord(
        child_id=child.id,
        photo_asset_ids=[uuid4()],
        generated_observation="아직 부모 검토 전인 사진 기록",
        generation_mode="manual_photo_diary",
        status=PhotoRecordStatus.DRAFT,
    )
    store.save(draft)

    with pytest.raises(HTTPException) as exc_info:
        record_material_result(
            material.id,
            MaterialResultRequest(
                observation="검토되지 않은 사진은 결과 증거로 확정하지 않는다.",
                photo_record_ids=[draft.id],
            ),
            store,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "photo_record_must_be_committed"


def test_material_result_rejects_corrupted_photo_learning_log_reference(tmp_path: Path) -> None:
    store = _store(tmp_path)
    child, material = _approved_material(store)
    wrong_log = LearningLog(
        child_id=child.id,
        record_kind=LearningRecordKind.OBSERVATION,
        parent_observation="사진 기록이 아닌 일반 관찰",
    )
    store.save(wrong_log)
    corrupted_photo = PhotoActivityRecord(
        child_id=child.id,
        photo_asset_ids=[uuid4()],
        generated_observation="겉보기에는 확정 사진 기록",
        generation_mode="manual_photo_diary",
        status=PhotoRecordStatus.COMMITTED,
        learning_log_id=wrong_log.id,
    )
    store.save(corrupted_photo)

    with pytest.raises(HTTPException) as exc_info:
        record_material_result(
            material.id,
            MaterialResultRequest(
                observation="손상된 참조는 결과 증거로 사용하지 않는다.",
                photo_record_ids=[corrupted_photo.id],
            ),
            store,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "photo_record_learning_log_mismatch"


def test_material_result_photo_evidence_respects_child_scope_visibility(tmp_path: Path) -> None:
    store = _store(tmp_path)
    child, material = _approved_material(store)
    sibling = ChildProfile(name="형제", nickname="형제", stage=Stage.ELEMENTARY)
    store.save(sibling)
    sibling_photo = _committed_photo_record(store, sibling, observation="형제와 함께 한 활동 사진")

    with pytest.raises(HTTPException) as exc_info:
        record_material_result(
            material.id,
            MaterialResultRequest(
                observation="공유되지 않은 형제 사진은 사용할 수 없다.",
                photo_record_ids=[sibling_photo.id],
            ),
            store,
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "photo_record_not_found"

    EntityLinkService(store).share_with_children(
        source_id=sibling_photo.id,
        child_ids=[child.id],
    )
    result = record_material_result(
        material.id,
        MaterialResultRequest(
            observation="명시적으로 공유한 공동 활동 사진은 증거로 연결한다.",
            photo_record_ids=[sibling_photo.id],
        ),
        store,
    )
    evidence_links = [
        item
        for item in store.index.list_entities(entity_type="entity_link")
        if item["source_id"] == str(sibling_photo.id)
        and item["target_id"] == str(result.learning_log.id)
        and item["relation"] == "documents"
    ]
    assert len(evidence_links) == 1


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



def test_material_result_retry_repairs_links_without_duplicate_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    child, material = _approved_material(store)
    idempotency = SQLiteIdempotencyStore(tmp_path / "material-result-idempotency.sqlite3")
    monkeypatch.setattr(
        "growwise.api.material_result_routes.get_material_result_idempotency_store",
        lambda: idempotency,
    )

    original_create = EntityLinkService.create
    calls = 0

    def fail_second_link(self: EntityLinkService, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated crash during link fan-out")
        return original_create(self, **kwargs)

    monkeypatch.setattr(EntityLinkService, "create", fail_second_link)
    request = MaterialResultRequest(
        outcome=MaterialUseOutcome.COMPLETED,
        observation="부분 저장 뒤에도 같은 결과로 수렴해야 한다.",
    )

    with pytest.raises(OSError, match="simulated crash"):
        record_material_result(
            material.id,
            request,
            store,
            idempotency_key="material-result-retry",
        )

    logs = [
        LearningLog.model_validate(payload)
        for payload in store.index.list_entities(
            entity_type="learning_log",
            child_id=str(child.id),
        )
        if payload.get("record_kind") == LearningRecordKind.MATERIAL_USE.value
    ]
    assert len(logs) == 1
    reserved_log_id = logs[0].id

    monkeypatch.setattr(EntityLinkService, "create", original_create)
    recovered = record_material_result(
        material.id,
        request,
        store,
        idempotency_key="material-result-retry",
    )

    assert recovered.learning_log.id == reserved_log_id
    final_logs = [
        payload
        for payload in store.index.list_entities(
            entity_type="learning_log",
            child_id=str(child.id),
        )
        if payload.get("record_kind") == LearningRecordKind.MATERIAL_USE.value
    ]
    assert len(final_logs) == 1

    links = store.index.list_entities(entity_type="entity_link")
    relations = {
        item["relation"]
        for item in links
        if item.get("source_id") in {str(material.id), str(reserved_log_id)}
    }
    assert {"supports", "documents", "derived_from"}.issubset(relations)


def test_material_result_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/v1/materials/{material_id}/results" in paths
