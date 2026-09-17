from __future__ import annotations

from uuid6 import uuid7

from growwise.domain import ResourceKind, ResourceRecord
from growwise.rag import HybridRagIndex, ResourceIngestor


def test_lexical_search_preserves_explicit_shared_resource_visibility(tmp_path) -> None:
    owner_id = uuid7()
    viewer_id = uuid7()
    index = HybridRagIndex(tmp_path / "rag.sqlite3")
    resource = ResourceRecord(
        kind=ResourceKind.NOTE,
        title="고양이 관찰 자료",
        child_id=owner_id,
        content="고양이를 관찰하며 꼬리 움직임을 기록했다.",
    )
    ResourceIngestor(index).ingest(resource, strict=True)

    hidden = index.search(
        query="고양이",
        child_id=str(viewer_id),
        shared_resource_ids=(),
        limit=10,
    )
    assert hidden == []

    shared = index.search(
        query="고양이",
        child_id=str(viewer_id),
        shared_resource_ids=(str(resource.id),),
        limit=10,
    )
    assert [item["resource_id"] for item in shared] == [str(resource.id)]


def test_lexical_search_keeps_korean_stem_recall(tmp_path) -> None:
    child_id = uuid7()
    index = HybridRagIndex(tmp_path / "rag.sqlite3")
    resource = ResourceRecord(
        kind=ResourceKind.NOTE,
        title="동물 기록",
        child_id=child_id,
        content="고양이를 오래 관찰했다.",
    )
    ResourceIngestor(index).ingest(resource, strict=True)

    hits = index.search(query="고양이", child_id=str(child_id), limit=10)
    assert any(item["resource_id"] == str(resource.id) for item in hits)
