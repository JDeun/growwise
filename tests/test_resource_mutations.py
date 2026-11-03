from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from growwise.api import link_routes, resource_routes
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.domain.links import EntityLinkRelation
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


def test_resource_projection_cleanup_failure_does_not_log_source_identifiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    resource = _resource()
    store.save(resource)

    class UnavailableProjection:
        def delete_resource(self, _resource_id):
            raise OSError("synthetic retrieval projection unavailable")

    monkeypatch.setattr(resource_routes, "get_resource_rag_index", UnavailableProjection)
    assert resource_routes.delete_resource(resource.id, store) == {"deleted": True}
    assert "source deletion remains authoritative" in caplog.text
    assert str(resource.id) not in caplog.text
    assert store.index.get_entity(str(resource.id), entity_type="resource") is None


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


def test_resource_request_bounds_match_domain_limits() -> None:
    with pytest.raises(ValidationError):
        resource_routes.ResourceUpdateRequest(
            kind=ResourceKind.NOTE,
            title="bounded",
            content="x" * 500_001,
        )

    with pytest.raises(ValidationError):
        resource_routes.ResourceUpdateRequest(
            kind=ResourceKind.NOTE,
            title="bounded",
            tags=["x" * 201],
        )

    with pytest.raises(ValidationError):
        resource_routes.ResourceUpdateRequest(
            kind=ResourceKind.NOTE,
            title="bounded",
            provenance={"": "invalid-key"},
        )

    with pytest.raises(ValidationError):
        resource_routes.ResourceUpdateRequest(
            kind=ResourceKind.NOTE,
            title="bounded",
            provenance={"origin": "x" * 4_001},
        )


def test_resource_update_revalidates_forged_request_before_source_write(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    original = _resource()
    path = store.save(original)

    # model_construct deliberately bypasses DTO validation to exercise the persistence boundary.
    forged = resource_routes.ResourceUpdateRequest.model_construct(
        kind=ResourceKind.NOTE,
        title="Forged update",
        summary=None,
        content="x" * 500_001,
        source_url=None,
        source_name=None,
        author=None,
        tags=[],
        stage_tags=[],
        provenance={"origin": "mutation-test"},
    )

    with pytest.raises(HTTPException) as error:
        resource_routes.update_resource(original.id, forged, store)

    assert error.value.status_code == 422
    persisted = store.markdown.load(path, ResourceRecord)
    assert persisted.title == original.title
    assert persisted.content == original.content
    indexed = store.index.get_entity(str(original.id), entity_type="resource")
    assert indexed is not None
    assert indexed["title"] == original.title


def test_resource_create_and_edit_persist_optional_metadata_and_scope(tmp_path, monkeypatch):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    child = ChildProfile(nickname="소유 아이", stage=Stage.ELEMENTARY)
    store.save(child)
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)
    monkeypatch.setattr(
        resource_routes,
        "get_resource_idempotency_store",
        lambda: resource_routes.SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3"),
    )
    created = resource_routes.create_resource(
        resource_routes.ResourceCreateRequest(
            kind=ResourceKind.BOOK,
            title="달 관찰",
            child_id=child.id,
            summary="달의 모양",
            content="함께 관찰",
            source_name="도서관",
            source_url="https://example.org/book",
            author="김작가",
            tags=["과학", "관찰"],
        ),
        store,
        idempotency_key=None,
    )
    assert created.child_id == child.id
    assert created.author == "김작가"
    assert store.markdown.load(store.markdown.path_for(created), ResourceRecord).tags == [
        "과학",
        "관찰",
    ]

    updated = resource_routes.update_resource(
        created.id,
        resource_routes.ResourceUpdateRequest(
            kind=ResourceKind.BOOK,
            title="달 관찰 수정",
            child_id=None,
            summary="수정 요약",
            content="함께 관찰",
            source_name="새 출처",
            source_url="https://example.org/new",
            author="이작가",
            tags=["자연"],
        ),
        store,
        acting_child_id=child.id,
    )
    persisted = store.markdown.load(store.markdown.path_for(updated), ResourceRecord)
    assert persisted.child_id is None
    assert persisted.summary == "수정 요약"
    assert persisted.source_name == "새 출처"
    assert persisted.source_url == "https://example.org/new"
    assert persisted.author == "이작가"
    assert persisted.tags == ["자연"]


def test_narrowing_global_scope_revokes_child_grants_and_stale_global_rag(tmp_path, monkeypatch):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    owner = ChildProfile(nickname="현재 아이", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(nickname="다른 아이", stage=Stage.ELEMENTARY)
    store.save(owner)
    store.save(sibling)
    original = _resource()
    store.save(original)
    ResourceIngestor(rag).ingest(original)
    EntityLinkService(store).share_with_children(source_id=original.id, child_ids=[sibling.id])
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)
    # The old global chunks must disappear even when best-effort re-ingestion is unavailable.
    monkeypatch.setattr(
        rag, "replace_resource", lambda *_: (_ for _ in ()).throw(OSError("offline"))
    )
    resource_routes.update_resource(
        original.id,
        resource_routes.ResourceUpdateRequest(
            kind=original.kind,
            title=original.title,
            content=original.content,
            child_id=owner.id,
        ),
        store,
        acting_child_id=owner.id,
    )
    assert resource_routes.list_resources(store, child_id=sibling.id) == []
    assert (
        store.index.list_entity_links(
            source_id=str(original.id),
            relation=EntityLinkRelation.CHILD_SCOPE.value,
        )
        == []
    )
    assert rag.search(query="legacytoken", child_id=str(sibling.id)) == []
    assert store.index.get_entity(str(original.id))["child_id"] == str(owner.id)


def test_resource_scope_change_cannot_promote_a_shared_child_record_or_transfer_to_sibling(
    tmp_path,
    monkeypatch,
):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    owner = ChildProfile(nickname="소유 아이", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(nickname="다른 아이", stage=Stage.ELEMENTARY)
    store.save(owner)
    store.save(sibling)
    original = _resource().model_copy(update={"child_id": owner.id})
    store.save(original)
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: None)
    for target, actor in [(None, sibling.id), (sibling.id, owner.id)]:
        with pytest.raises(HTTPException) as error:
            resource_routes.update_resource(
                original.id,
                resource_routes.ResourceUpdateRequest(
                    kind=original.kind, title="forged", child_id=target
                ),
                store,
                acting_child_id=actor,
            )
        assert error.value.status_code == 403
    assert store.index.get_entity(str(original.id))["child_id"] == str(owner.id)


def test_concurrent_share_rechecks_owner_after_global_scope_is_narrowed(tmp_path, monkeypatch):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    owner = ChildProfile(nickname="소유 아이", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(nickname="공유 요청 아이", stage=Stage.ELEMENTARY)
    store.save(owner)
    store.save(sibling)
    original = _resource()
    store.save(original)
    ResourceIngestor(rag).ingest(original)
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)
    narrowing = Event()
    continue_narrowing = Event()
    checking_share_owner = Event()
    original_delete = rag.delete_resource
    original_owner_check = link_routes._require_child_scope_owner

    def paused_delete(resource_id):
        narrowing.set()
        assert continue_narrowing.wait(5)
        return original_delete(resource_id)

    def checked_owner(**kwargs):
        checking_share_owner.set()
        return original_owner_check(**kwargs)

    monkeypatch.setattr(rag, "delete_resource", paused_delete)
    monkeypatch.setattr(link_routes, "_require_child_scope_owner", checked_owner)
    with ThreadPoolExecutor(max_workers=2) as pool:
        narrow = pool.submit(
            resource_routes.update_resource,
            original.id,
            resource_routes.ResourceUpdateRequest(
                kind=original.kind,
                title=original.title,
                child_id=owner.id,
            ),
            store,
            acting_child_id=owner.id,
        )
        assert narrowing.wait(5)
        share = pool.submit(
            link_routes.create_entity_link,
            link_routes.EntityLinkCreateRequest(
                source_id=original.id,
                target_id=sibling.id,
                relation=EntityLinkRelation.CHILD_SCOPE,
                acting_child_id=sibling.id,
            ),
            store,
        )
        try:
            # Ownership cannot be checked against the still-global source while narrowing holds it.
            assert not checking_share_owner.wait(0.1)
        finally:
            continue_narrowing.set()
        assert narrow.result(timeout=5).child_id == owner.id
        with pytest.raises(HTTPException) as error:
            share.result(timeout=5)
        assert error.value.status_code == 403
    assert store.index.list_entity_links(source_id=str(original.id)) == []
