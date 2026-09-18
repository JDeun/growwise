from __future__ import annotations

import sqlite3

from uuid6 import uuid7

from growwise.domain import ResourceKind, ResourceRecord
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.rag.index import _normalize_query_terms


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



def test_rag_query_terms_are_deduplicated_and_bounded() -> None:
    query = " ".join(["반복어", "반복어", *[f"term-{index}" for index in range(1000)]])
    terms = _normalize_query_terms(query)

    assert len(terms) == 32
    assert terms[0] == "반복어"
    assert len(set(terms)) == len(terms)
    assert all(len(term) <= 128 for term in terms)


def test_corrupt_rag_projection_is_recreated_from_disposable_state(tmp_path) -> None:
    path = tmp_path / "rag.sqlite3"
    path.write_bytes(b"not-a-sqlite-database")

    index = HybridRagIndex(path)
    resource = ResourceRecord(
        kind=ResourceKind.NOTE,
        title="복구 확인",
        content="고양이 관찰 기록",
    )
    ResourceIngestor(index).ingest(resource, strict=True)

    hits = index.search(query="고양이", child_id=None, limit=10)
    assert [item["resource_id"] for item in hits] == [str(resource.id)]



def test_shared_visibility_queries_survive_low_sqlite_variable_limit(tmp_path) -> None:
    class LowVariableRagIndex(HybridRagIndex):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 512)
            return connection

    owner_id = uuid7()
    viewer_id = uuid7()
    index = LowVariableRagIndex(tmp_path / "rag.sqlite3")
    resource = ResourceRecord(
        kind=ResourceKind.NOTE,
        title="대규모 공유 범위",
        child_id=owner_id,
        content="고양이 공유 검색 한도 검증",
    )
    ResourceIngestor(index).ingest(resource, strict=True)

    shared_ids = [f"missing-{item}" for item in range(1_200)]
    shared_ids.append(str(resource.id))
    hits = index.search(
        query="고양이",
        child_id=str(viewer_id),
        shared_resource_ids=shared_ids,
        limit=10,
    )

    assert [item["resource_id"] for item in hits] == [str(resource.id)]



def test_rag_search_tolerates_corrupt_tags_json(tmp_path) -> None:
    path = tmp_path / "rag.sqlite3"
    index = HybridRagIndex(path)
    resource = ResourceRecord(
        kind=ResourceKind.NOTE,
        title="손상 태그 복구",
        content="고양이 관찰 기록",
    )
    ResourceIngestor(index).ingest(resource, strict=True)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE rag_chunks SET tags_json = ? WHERE resource_id = ?",
            ("{not-json", str(resource.id)),
        )

    hits = index.search(query="고양이", child_id=None, limit=10)

    assert [item["resource_id"] for item in hits] == [str(resource.id)]
    assert hits[0]["tags"] == []
