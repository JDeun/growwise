from pathlib import Path

import pytest

from growwise.api import resource_routes
from growwise.domain import ResourceKind, ResourceRecord
from growwise.rag import HybridRagIndex, ResourceIngestor
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
