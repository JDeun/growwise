from pathlib import Path

import pytest
from fastapi import HTTPException

from growwise.api import resource_routes
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore


def _resource() -> ResourceRecord:
    return ResourceRecord(
        kind=ResourceKind.NOTE,
        title="Legacy resource",
        content="legacytoken evidence",
        provenance={"origin": "mutation-test"},
    )


def _request(title: str, content: str) -> resource_routes.ResourceUpdateRequest:
    return resource_routes.ResourceUpdateRequest(
        kind=ResourceKind.NOTE,
        title=title,
        content=content,
        provenance={"origin": "mutation-test"},
    )


def test_resource_update_and_delete_keep_markdown_sqlite_and_rag_in_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    original = _resource()
    path = store.save(original)
    ResourceIngestor(rag).ingest(original)
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)

    updated = resource_routes.update_resource(
        original.id,
        _request("Updated resource", "freshsignal evidence"),
        store,
    )

    assert updated.id == original.id
    assert updated.child_id == original.child_id
    assert updated.created_at == original.created_at
    assert updated.updated_at >= original.updated_at
    assert store.markdown.load(path, ResourceRecord).title == "Updated resource"
    assert store.index.get_entity(str(original.id), entity_type="resource")["title"] == (
        "Updated resource"
    )
    assert rag.search(query="legacytoken", child_id=None) == []
    assert rag.search(query="freshsignal", child_id=None)[0]["resource_id"] == str(original.id)

    result = resource_routes.delete_resource(original.id, store)

    assert result == {"deleted": True}
    assert not path.exists()
    assert store.index.get_entity(str(original.id), entity_type="resource") is None
    assert rag.search(query="freshsignal", child_id=None) == []


def test_shared_child_resource_is_read_only_outside_owner_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    owner = ChildProfile(name="원소유", nickname="원소유", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(name="공유아이", nickname="공유아이", stage=Stage.ELEMENTARY)
    store.save(owner)
    store.save(sibling)
    resource = ResourceRecord(
        child_id=owner.id,
        kind=ResourceKind.NOTE,
        title="함께 보는 자료",
        content="sharedtoken evidence",
        provenance={"origin": "mutation-test"},
    )
    store.save(resource)
    ResourceIngestor(rag).ingest(resource)
    EntityLinkService(store).share_with_children(source_id=resource.id, child_ids=[sibling.id])
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)

    with pytest.raises(HTTPException) as update_error:
        resource_routes.update_resource(
            resource.id,
            _request("형제가 바꾼 제목", "tampered evidence"),
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
    assert store.index.get_entity(str(resource.id), entity_type="resource") is not None
    assert len(store.index.list_entities(entity_type="entity_link")) == 1

    updated = resource_routes.update_resource(
        resource.id,
        _request("원소유가 바꾼 제목", "ownertoken evidence"),
        store,
        acting_child_id=owner.id,
    )
    assert updated.title == "원소유가 바꾼 제목"
    assert rag.search(query="ownertoken", child_id=str(owner.id))

    result = resource_routes.delete_resource(
        resource.id,
        store,
        acting_child_id=owner.id,
    )
    assert result == {"deleted": True}
    assert store.index.get_entity(str(resource.id), entity_type="resource") is None
    assert store.index.list_entities(entity_type="entity_link") == []


def test_resource_update_restores_old_rag_chunks_when_source_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    original = _resource()
    store.save(original)
    ResourceIngestor(rag).ingest(original)
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)

    def fail_save(_entity: ResourceRecord) -> Path:
        raise OSError("synthetic write failure")

    monkeypatch.setattr(store, "save", fail_save)

    with pytest.raises(OSError, match="synthetic write failure"):
        resource_routes.update_resource(
            original.id,
            _request("Uncommitted title", "uncommittedtoken"),
            store,
        )

    assert rag.search(query="legacytoken", child_id=None)[0]["resource_id"] == str(original.id)
    assert rag.search(query="uncommittedtoken", child_id=None) == []


def test_resource_delete_restores_rag_chunks_when_source_delete_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    original = _resource()
    path = store.save(original)
    ResourceIngestor(rag).ingest(original)
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)

    def fail_delete(_entity: ResourceRecord) -> bool:
        raise OSError("synthetic delete failure")

    monkeypatch.setattr(store, "delete", fail_delete)

    with pytest.raises(OSError, match="synthetic delete failure"):
        resource_routes.delete_resource(original.id, store)

    assert path.exists()
    assert rag.search(query="legacytoken", child_id=None)[0]["resource_id"] == str(original.id)
