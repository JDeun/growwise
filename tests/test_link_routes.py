from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from growwise.api.link_routes import (
    EntityLinkCreateRequest,
    create_entity_link,
    delete_entity_link,
)
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.domain.links import EntityLinkRelation
from growwise.storage import EntityStore


def test_child_scope_link_can_only_be_managed_from_source_owner_context(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    owner = ChildProfile(name="원소유", nickname="원소유", stage=Stage.ELEMENTARY)
    shared_child = ChildProfile(name="공유아이", nickname="공유아이", stage=Stage.ELEMENTARY)
    third = ChildProfile(name="셋째", nickname="셋째", stage=Stage.ELEMENTARY)
    for child in (owner, shared_child, third):
        store.save(child)

    resource = ResourceRecord(
        child_id=owner.id,
        kind=ResourceKind.NOTE,
        title="원소유 자료",
    )
    store.save(resource)

    with pytest.raises(HTTPException) as sibling_create_error:
        create_entity_link(
            EntityLinkCreateRequest(
                source_id=resource.id,
                target_id=third.id,
                relation=EntityLinkRelation.CHILD_SCOPE,
                acting_child_id=shared_child.id,
            ),
            store,
        )
    assert sibling_create_error.value.status_code == 403
    assert sibling_create_error.value.detail == "shared_entity_read_only"

    created = create_entity_link(
        EntityLinkCreateRequest(
            source_id=resource.id,
            target_id=shared_child.id,
            relation=EntityLinkRelation.CHILD_SCOPE,
            acting_child_id=owner.id,
        ),
        store,
    )
    link_id = created["id"]

    with pytest.raises(HTTPException) as sibling_delete_error:
        delete_entity_link(
            link_id,
            store,
            acting_child_id=shared_child.id,
        )
    assert sibling_delete_error.value.status_code == 403
    assert sibling_delete_error.value.detail == "shared_entity_read_only"
    assert store.index.get_entity(str(link_id), entity_type="entity_link") is not None

    assert delete_entity_link(link_id, store, acting_child_id=owner.id) == {"deleted": True}
    assert store.index.get_entity(str(link_id), entity_type="entity_link") is None


def test_parent_wide_source_can_be_shared_without_child_owner(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    resource = ResourceRecord(
        child_id=None,
        kind=ResourceKind.NOTE,
        title="가족 공용 자료",
    )
    store.save(resource)

    created = create_entity_link(
        EntityLinkCreateRequest(
            source_id=resource.id,
            target_id=child.id,
            relation=EntityLinkRelation.CHILD_SCOPE,
            acting_child_id=None,
        ),
        store,
    )

    assert created["source_id"] == str(resource.id)
    assert created["target_id"] == str(child.id)
