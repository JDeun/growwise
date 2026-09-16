from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from growwise.api import link_routes, resource_routes
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.domain.links import EntityLinkRelation
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore


def _children(store: EntityStore) -> tuple[ChildProfile, ChildProfile]:
    owner = ChildProfile(name="소유아이", nickname="소유아이", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(name="공유아이", nickname="공유아이", stage=Stage.ELEMENTARY)
    store.save(owner)
    store.save(sibling)
    return owner, sibling


def _request(title: str) -> resource_routes.ResourceUpdateRequest:
    return resource_routes.ResourceUpdateRequest(
        kind=ResourceKind.NOTE,
        title=title,
        content=f"{title} 내용",
        provenance={"origin": "scope-test"},
    )


def test_shared_child_cannot_mutate_or_delete_owned_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    owner, sibling = _children(store)
    resource = ResourceRecord(
        child_id=owner.id,
        kind=ResourceKind.NOTE,
        title="원본 자료",
        content="원본 내용",
    )
    store.save(resource)
    ResourceIngestor(rag).ingest(resource)
    EntityLinkService(store).share_with_children(source_id=resource.id, child_ids=[sibling.id])
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)

    with pytest.raises(HTTPException) as update_error:
        resource_routes.update_resource(
            resource.id,
            _request("공유 아이의 수정 시도"),
            store,
            acting_child_id=sibling.id,
        )
    assert update_error.value.status_code == 403
    assert update_error.value.detail == "shared_resource_read_only"

    with pytest.raises(HTTPException) as delete_error:
        resource_routes.delete_resource(
            resource.id,
            store,
            acting_child_id=sibling.id,
        )
    assert delete_error.value.status_code == 403
    assert delete_error.value.detail == "shared_resource_read_only"

    stored = store.index.get_entity(str(resource.id), entity_type="resource")
    assert stored is not None
    assert stored["title"] == "원본 자료"
    assert len(store.index.list_entities(entity_type="entity_link")) == 1


def test_owner_can_mutate_and_delete_resource_and_cleanup_scope_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    owner, sibling = _children(store)
    resource = ResourceRecord(
        child_id=owner.id,
        kind=ResourceKind.NOTE,
        title="원본 자료",
        content="owner-token",
    )
    store.save(resource)
    ResourceIngestor(rag).ingest(resource)
    EntityLinkService(store).share_with_children(source_id=resource.id, child_ids=[sibling.id])
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)

    updated = resource_routes.update_resource(
        resource.id,
        _request("소유자가 수정함"),
        store,
        acting_child_id=owner.id,
    )
    assert updated.title == "소유자가 수정함"

    result = resource_routes.delete_resource(
        resource.id,
        store,
        acting_child_id=owner.id,
    )
    assert result == {"deleted": True}
    assert store.index.get_entity(str(resource.id), entity_type="resource") is None
    assert store.index.list_entities(entity_type="entity_link") == []


def test_parent_wide_resource_remains_mutable_from_child_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    _owner, sibling = _children(store)
    resource = ResourceRecord(
        child_id=None,
        kind=ResourceKind.NOTE,
        title="공용 자료",
        content="공용 내용",
    )
    store.save(resource)
    ResourceIngestor(rag).ingest(resource)
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)

    updated = resource_routes.update_resource(
        resource.id,
        _request("공용 자료 수정"),
        store,
        acting_child_id=sibling.id,
    )
    assert updated.title == "공용 자료 수정"


def test_child_scope_link_can_only_be_created_from_owner_context(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    owner, sibling = _children(store)
    third = ChildProfile(name="셋째", nickname="셋째", stage=Stage.ELEMENTARY)
    store.save(third)
    resource = ResourceRecord(
        child_id=owner.id,
        kind=ResourceKind.NOTE,
        title="공유 자료",
        content="공유 내용",
    )
    store.save(resource)

    with pytest.raises(HTTPException) as error:
        link_routes.create_entity_link(
            link_routes.EntityLinkCreateRequest(
                source_id=resource.id,
                target_id=third.id,
                relation=EntityLinkRelation.CHILD_SCOPE,
                acting_child_id=sibling.id,
            ),
            store,
        )
    assert error.value.status_code == 403
    assert error.value.detail == "shared_entity_read_only"

    created = link_routes.create_entity_link(
        link_routes.EntityLinkCreateRequest(
            source_id=resource.id,
            target_id=third.id,
            relation=EntityLinkRelation.CHILD_SCOPE,
            acting_child_id=owner.id,
        ),
        store,
    )
    assert created["source_id"] == str(resource.id)
    assert created["target_id"] == str(third.id)
