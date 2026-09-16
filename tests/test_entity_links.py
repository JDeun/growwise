from __future__ import annotations

import base64
from pathlib import Path

from growwise.api.photo_routes import (
    PhotoCommitRequest,
    PhotoDraftRequest,
    PhotoUploadInput,
    commit_photo_record,
    create_photo_record,
)
from growwise.config import Settings
from growwise.domain import ActivityPlan, ChildProfile, Stage
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
