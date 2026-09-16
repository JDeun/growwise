from pathlib import Path

import pytest
from fastapi import HTTPException

from growwise.api import link_routes, resource_routes
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.domain.links import EntityLinkRelation
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore


def _children(store: EntityStore) -> tuple[ChildProfile, ChildProfile, ChildProfile]:
    owner = ChildProfile(name="첫째", nickname="첫째", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(name="둘째", nickname="둘째", stage=Stage.ELEMENTARY)
    third = ChildProfile(name="셋째", nickname="셋째", stage=Stage.ELEMENTARY)
    for child in (owner, sibling, third):
        store.save(child)
    return owner, sibling, third


def _update_request(title: str) -> resource_routes.ResourceUpdateRequest:
    return resource_routes.ResourceUpdateRequest(
        kind=ResourceKind.NOTE,
        title=title,
        content="공유 자료 내용",
        provenance={"origin": "ownership-test"},
    )


def test_shared_resource_is_read_only_outside_owner_context_and_delete_cleans_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)
    owner, sibling, _third = _children(store)
    resource = ResourceRecord(
        child_id=owner.id,
        kind=ResourceKind.NOTE,
        title="공유 과학 노트",
        content="화산 실험 관찰 자료",
        provenance={"origin": "ownership-test"},
    )
    store.save(resource)
    ResourceIngestor(rag).ingest(resource)
    EntityLinkService(store).share_with_children(
        source_id=resource.id,
        child_ids=[sibling.id],
    )

    with pytest.raises(HTTPException) as update_error:
        resource_routes.update_resource(
            resource.id,
            _update_request("둘째가 바꾸려는 제목"),
            store,
            sibling.id,
        )
    assert update_error.value.status_code == 403
    assert update_error.value.detail == "shared_resource_read_only"

    updated = resource_routes.update_resource(
        resource.id,
        _update_request("첫째가 수정한 제목"),
        store,
        owner.id,
    )
    assert updated.title == "첫째가 수정한 제목"

    with pytest.raises(HTTPException) as delete_error:
        resource_routes.delete_resource(resource.id, store, sibling.id)
    assert delete_error.value.status_code == 403
    assert delete_error.value.detail == "shared_resource_read_only"
    assert store.index.get_entity(str(resource.id), entity_type="resource") is not None

    assert resource_routes.delete_resource(resource.id, store, owner.id) == {"deleted": True}
    assert store.index.get_entity(str(resource.id), entity_type="resource") is None
    assert store.index.list_entities(entity_type="entity_link") == []


def test_shared_child_cannot_reshare_or_remove_owner_scope_link(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    owner, sibling, third = _children(store)
    resource = ResourceRecord(
        child_id=owner.id,
        kind=ResourceKind.NOTE,
        title="가족 공용 후보 자료",
        content="원본은 첫째 소유",
    )
    store.save(resource)

    created = link_routes.create_entity_link(
        link_routes.EntityLinkCreateRequest(
            source_id=resource.id,
            target_id=sibling.id,
            relation=EntityLinkRelation.CHILD_SCOPE,
            acting_child_id=owner.id,
        ),
        store,
    )

    with pytest.raises(HTTPException) as reshare_error:
        link_routes.create_entity_link(
            link_routes.EntityLinkCreateRequest(
                source_id=resource.id,
                target_id=third.id,
                relation=EntityLinkRelation.CHILD_SCOPE,
                acting_child_id=sibling.id,
            ),
            store,
        )
    assert reshare_error.value.status_code == 403
    assert reshare_error.value.detail == "shared_entity_read_only"

    with pytest.raises(HTTPException) as unlink_error:
        link_routes.delete_entity_link(created["id"], store, sibling.id)
    assert unlink_error.value.status_code == 403
    assert unlink_error.value.detail == "shared_entity_read_only"

    assert link_routes.delete_entity_link(created["id"], store, owner.id) == {"deleted": True}
