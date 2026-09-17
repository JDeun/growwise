from pathlib import Path

import pytest
from fastapi import HTTPException

from growwise.api import link_routes
from growwise.domain import ActivityPlan, ChildProfile, Stage
from growwise.domain.links import EntityLinkRelation
from growwise.storage import EntityStore


def test_child_scope_can_only_be_extended_from_owner_child_context(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    owner = ChildProfile(name="원소유", nickname="원소유", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(name="공유아이", nickname="공유아이", stage=Stage.ELEMENTARY)
    third = ChildProfile(name="셋째", nickname="셋째", stage=Stage.ELEMENTARY)
    store.save(owner)
    store.save(sibling)
    store.save(third)
    activity = ActivityPlan(child_id=owner.id, title="함께 하는 활동")
    store.save(activity)

    first_link = link_routes.create_entity_link(
        link_routes.EntityLinkCreateRequest(
            source_id=activity.id,
            target_id=sibling.id,
            relation=EntityLinkRelation.CHILD_SCOPE,
            acting_child_id=owner.id,
        ),
        store,
    )
    assert first_link["target_id"] == str(sibling.id)

    with pytest.raises(HTTPException) as shared_context_error:
        link_routes.create_entity_link(
            link_routes.EntityLinkCreateRequest(
                source_id=activity.id,
                target_id=third.id,
                relation=EntityLinkRelation.CHILD_SCOPE,
                acting_child_id=sibling.id,
            ),
            store,
        )
    assert shared_context_error.value.status_code == 403
    assert shared_context_error.value.detail == "shared_entity_read_only"

    with pytest.raises(HTTPException) as missing_actor_error:
        link_routes.create_entity_link(
            link_routes.EntityLinkCreateRequest(
                source_id=activity.id,
                target_id=third.id,
                relation=EntityLinkRelation.CHILD_SCOPE,
            ),
            store,
        )
    assert missing_actor_error.value.status_code == 403

    second_link = link_routes.create_entity_link(
        link_routes.EntityLinkCreateRequest(
            source_id=activity.id,
            target_id=third.id,
            relation=EntityLinkRelation.CHILD_SCOPE,
            acting_child_id=owner.id,
        ),
        store,
    )
    assert second_link["target_id"] == str(third.id)
    assert len(store.index.list_entities(entity_type="entity_link")) == 2
