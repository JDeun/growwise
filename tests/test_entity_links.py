from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi import HTTPException

from growwise.api.main import (
    list_activity_observations,
    validate_activity_link,
    validate_material_source_refs,
)
from growwise.api.photo_routes import (
    PhotoCommitRequest,
    PhotoDraftRequest,
    PhotoUploadInput,
    commit_photo_record,
    create_photo_record,
)
from growwise.config import Settings
from growwise.domain import (
    ActivityPlan,
    ChildProfile,
    LearningLog,
    ResourceKind,
    ResourceRecord,
    Stage,
)
from growwise.domain.links import EntityLinkRelation
from growwise.services.entity_links import EntityLinkService
from growwise.services.privacy import ChildPurgeService
from growwise.storage import EntityStore

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
    )


def _children(store: EntityStore) -> tuple[ChildProfile, ChildProfile]:
    first = ChildProfile(name="첫째", nickname="첫째", stage=Stage.PRESCHOOL_3_5)
    second = ChildProfile(name="둘째", nickname="둘째", stage=Stage.PRESCHOOL_3_5)
    store.save(first)
    store.save(second)
    return first, second


def test_child_scope_link_reuses_one_entity_in_lists_and_search(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    first, second = _children(store)
    activity = ActivityPlan(child_id=first.id, title="가족 공원 산책")
    store.save(activity)

    link = EntityLinkService(store).create(
        source_id=activity.id,
        target_id=second.id,
        relation=EntityLinkRelation.CHILD_SCOPE,
    )

    second_activities = store.index.list_entities(
        entity_type="activity_plan",
        child_id=str(second.id),
    )
    assert [item["id"] for item in second_activities] == [str(activity.id)]
    assert second_activities[0]["child_id"] == str(first.id)

    results = store.index.search_entities(
        child_id=str(second.id),
        query_text="공원",
        entity_types=("activity_plan",),
    )
    assert [item["id"] for item in results] == [str(activity.id)]

    graph = EntityLinkService(store).backlinks(activity.id)
    assert graph["outgoing"][0]["link"]["id"] == str(link.id)
    assert graph["outgoing"][0]["entity"]["id"] == str(second.id)


def test_shared_activity_is_valid_for_sibling_observation_and_history(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    first, second = _children(store)
    third = ChildProfile(name="셋째", nickname="셋째", stage=Stage.PRESCHOOL_3_5)
    store.save(third)

    activity = ActivityPlan(child_id=first.id, title="함께 하는 과학 놀이")
    store.save(activity)
    EntityLinkService(store).share_with_children(source_id=activity.id, child_ids=[second.id])

    assert (
        validate_activity_link(
            store=store,
            child_id=second.id,
            activity_plan_id=activity.id,
        ).id
        == activity.id
    )
    with pytest.raises(HTTPException) as exc_info:
        validate_activity_link(
            store=store,
            child_id=third.id,
            activity_plan_id=activity.id,
        )
    assert exc_info.value.status_code == 409

    first_log = LearningLog(
        child_id=first.id,
        activity_plan_id=activity.id,
        parent_observation="첫째가 관찰했다.",
    )
    second_log = LearningLog(
        child_id=second.id,
        activity_plan_id=activity.id,
        parent_observation="둘째도 관찰했다.",
    )
    store.save(first_log)
    store.save(second_log)

    history = list_activity_observations(activity.id, store)
    assert {item["id"] for item in history} == {str(first_log.id), str(second_log.id)}


def test_shared_resource_is_valid_material_evidence_for_sibling(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    first, second = _children(store)
    third = ChildProfile(name="셋째", nickname="셋째", stage=Stage.PRESCHOOL_3_5)
    store.save(third)

    resource = ResourceRecord(
        child_id=first.id,
        kind=ResourceKind.NOTE,
        title="가족이 함께 읽는 공룡 자료",
        content="공룡 발자국을 비교하는 활동 메모",
    )
    store.save(resource)
    EntityLinkService(store).share_with_children(source_id=resource.id, child_ids=[second.id])
    ref = f"resource:{resource.id}"

    assert validate_material_source_refs(
        child_id=second.id,
        source_refs=[ref],
        store=store,
    ) == [ref]

    with pytest.raises(HTTPException) as exc_info:
        validate_material_source_refs(
            child_id=third.id,
            source_refs=[ref],
            store=store,
        )
    assert exc_info.value.status_code == 409


def test_purging_shared_target_removes_link_but_preserves_source(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    first, second = _children(store)
    activity = ActivityPlan(child_id=first.id, title="같이 읽는 책")
    store.save(activity)
    EntityLinkService(store).share_with_children(
        source_id=activity.id,
        child_ids=[second.id],
    )

    result = ChildPurgeService(settings).purge(str(second.id))

    assert result.links_deleted == 1
    assert store.index.get_entity(str(activity.id), entity_type="activity_plan") is not None
    assert store.index.list_entities(entity_type="entity_link") == []


def test_purging_source_owner_removes_sibling_scoped_backlink(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    first, second = _children(store)
    activity = ActivityPlan(child_id=first.id, title="함께 만든 일정")
    store.save(activity)
    EntityLinkService(store).share_with_children(
        source_id=activity.id,
        child_ids=[second.id],
    )

    result = ChildPurgeService(settings).purge(str(first.id))

    assert result.links_deleted == 1
    assert store.index.get_entity(str(activity.id), entity_type="activity_plan") is None
    assert store.index.list_entities(entity_type="entity_link") == []
    assert store.index.get_entity(str(second.id), entity_type="child_profile") is not None


def test_photo_diary_needs_no_ai_and_shares_one_record(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    first, second = _children(store)
    request = PhotoDraftRequest(
        files=[
            PhotoUploadInput(
                filename="day.png",
                mime_type="image/png",
                data_base64=base64.b64encode(_ONE_PIXEL_PNG).decode("ascii"),
            )
        ],
        manual_observation="오늘 둘이 블록을 높이 쌓았다.",
        ai_assist=False,
        shared_child_ids=[second.id],
    )

    created = create_photo_record(first.id, request, settings, store)
    record = created["record"]
    assert record["status"] == "draft"
    assert record["generation_mode"] == "manual_photo_diary"
    assert record["generated_observation"] == "오늘 둘이 블록을 높이 쌓았다."
    assert created["job"] is None

    second_records = store.index.list_entities(
        entity_type="photo_activity_record",
        child_id=str(second.id),
    )
    assert [item["id"] for item in second_records] == [record["id"]]

    committed = commit_photo_record(
        record_id=record["id"],
        request=PhotoCommitRequest(observation="오늘 둘이 블록을 높이 쌓았다."),
        settings=settings,
        store=store,
    )
    second_logs = store.index.list_entities(
        entity_type="learning_log",
        child_id=str(second.id),
    )
    assert [item["id"] for item in second_logs] == [committed["id"]]