from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from growwise.api.dependencies import get_rag_index, get_store
from growwise.api.main import app
from growwise.domain import (
    ChildProfile,
    LearningLog,
    LearningWiki,
    ResourceKind,
    ResourceRecord,
    Stage,
)
from growwise.rag import HybridRagIndex
from growwise.rag.chunking import chunk_resource
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore


@pytest.fixture
def evidence(tmp_path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    owner = ChildProfile(nickname="합성 소유자", stage=Stage.ELEMENTARY, age_months=96)
    sibling = ChildProfile(nickname="합성 형제", stage=Stage.ELEMENTARY, age_months=96)
    store.save(owner)
    store.save(sibling)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_rag_index] = lambda: rag
    try:
        yield TestClient(app), store, rag, owner, sibling
    finally:
        app.dependency_overrides.pop(get_store, None)
        app.dependency_overrides.pop(get_rag_index, None)


def _read(client, child, source):
    return client.get(f"/v1/children/{child.id}/evidence", params={"source_id": source})


def _chunk(rag, entity):
    chunks = chunk_resource(
        resource_id=str(entity.id), child_id=None, title="obsolete cached title",
        text="obsolete cached body", source_url=None, source_name=None, tags=[],
    )
    rag.replace_resource(chunks)
    return f"chunk:{chunks[0].chunk_id}"


def test_current_original_body_and_event_date_are_bounded_and_not_html_rendered(evidence):
    client, store, _, owner, sibling = evidence
    occurred = datetime(2026, 10, 15, 12, tzinfo=UTC)
    log = LearningLog(
        child_id=owner.id, title="실제 저장한 합성 기록", occurred_at=occurred,
        parent_observation="<script>synthetic()</script>" + "가" * 9000,
        ai_hint="관찰할 두 대상을 비교하자는 힌트",
        child_reexplanation="바람의 방향이 달라서 움직임이 달랐다고 설명했다",
        evidence_checked=True,
    )
    store.save(log)
    for prefix in ("record", "graph"):
        response = _read(client, owner, f"{prefix}:{log.id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["title"] == log.title
        assert payload["occurred_at"].startswith("2026-10-15")
        assert "<script>synthetic()</script>" in payload["body"]  # JSON, escaped by React text.
        assert "관찰할 두 대상을 비교하자는 힌트" in payload["body"]
        assert "바람의 방향이 달라서" in payload["body"]
        assert "부모의 근거 확인 기록: 확인함" in payload["body"]
        assert "경험·기록 시각:" not in payload["body"]
        assert "기록 유형:" not in payload["body"]
        assert len(payload["body"]) <= 12_000
        assert payload["source_url"] is None
        assert _read(client, sibling, f"{prefix}:{log.id}").status_code == 404
    large = ResourceRecord(child_id=owner.id, kind=ResourceKind.NOTE, title="긴 합성 원문",
                           content="다" * 50_000 + "END_NOT_SENT")
    store.save(large)
    body = _read(client, owner, f"resource:{large.id}").json()["body"]
    assert 11_900 < len(body) <= 12_000
    assert "END_NOT_SENT" not in body


def test_display_translates_typed_metadata_without_rewriting_authored_text(evidence):
    from growwise.api.evidence_routes import _display_body

    authored = "내가 쓴 material_use / concept / 2026-10-15T12:00:00Z는 그대로 남긴다"
    body = _display_body({
        "title": "header title", "record_kind": "material_use", "state": "review",
        "mistake_type": "concept", "parent_observation": authored,
        "created_at": "2026-10-15T12:00:00Z",
    })
    assert authored in body
    assert "학습 상태: 복습 필요" in body
    assert "실수 유형: 개념" in body
    assert "header title" not in body
    assert "경험·기록 시각:" not in body
    client, store, _, owner, _ = evidence
    resource = ResourceRecord(child_id=owner.id, kind=ResourceKind.NOTE, title="본문 없는 원본")
    store.save(resource)
    response = _read(client, owner, f"resource:{resource.id}")
    assert response.status_code == 200
    assert response.json()["body"] == "추가 본문이 없는 원본입니다."
    assert str(owner.id) not in response.json()["body"]


def test_chunk_cannot_use_stale_global_body_or_bypass_current_private_scope(evidence):
    client, store, rag, owner, sibling = evidence
    resource = ResourceRecord(kind=ResourceKind.BOOK, title="old shared title", content="old body")
    store.save(resource)
    citation = _chunk(rag, resource)
    resource.child_id = owner.id
    resource.title, resource.content = "current private title", "current original body"
    store.save(resource)  # Deliberately leave the formerly-global chunk stale.
    assert _read(client, sibling, citation).status_code == 404
    response = _read(client, owner, citation)
    assert response.status_code == 200
    assert response.json()["title"] == "current private title"
    assert "current original body" in response.json()["body"]
    assert "obsolete cached" not in response.text
    store.delete(resource)
    assert _read(client, owner, citation).status_code == 404


def test_shared_original_is_unavailable_after_grant_revocation(evidence):
    client, store, rag, owner, sibling = evidence
    resource = ResourceRecord(child_id=owner.id, kind=ResourceKind.NOTE, title="공유 근거",
                              content="합성 관찰 내용")
    store.save(resource)
    links = EntityLinkService(store)
    grant = links.share_with_children(source_id=resource.id, child_ids=[sibling.id])[0]
    citation = _chunk(rag, resource)
    assert _read(client, sibling, citation).status_code == 200
    assert links.delete(grant.id)
    assert _read(client, sibling, citation).status_code == 404
    assert _read(client, sibling, f"resource:{resource.id}").status_code == 404


def test_derived_wiki_and_profile_are_never_presented_as_original_evidence(evidence):
    client, store, rag, owner, _ = evidence
    wiki = LearningWiki(child_id=owner.id, source_fingerprint="a" * 64,
                        content_markdown="derived summary must not masquerade as original")
    store.save(wiki)
    for citation in (f"record:{wiki.id}", f"graph:{wiki.id}", _chunk(rag, wiki),
                     f"record:{owner.id}", "record:../../private", "https://example.invalid"):
        response = _read(client, owner, citation)
        assert response.status_code == 404
        assert "derived summary" not in response.text
        assert owner.nickname not in response.text


@pytest.mark.parametrize("url,expected", [
    ("https://example.org/public", "https://example.org/public"),
    ("javascript:alert(1)", None),
    ("file:///private/secret", None),
    ("https://synthetic:password@example.org", None),
    ("https://example.org/\nunsafe", None),
])
def test_only_safe_external_source_url_is_returned(evidence, url, expected):
    client, store, _, owner, _ = evidence
    resource = ResourceRecord(child_id=owner.id, kind=ResourceKind.WEB,
                              title="링크 근거", content="합성 원문", source_url=url)
    store.save(resource)
    response = _read(client, owner, f"resource:{resource.id}")
    assert response.status_code == 200
    assert response.json()["source_url"] == expected
