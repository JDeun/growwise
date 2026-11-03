"""RAG ranks pointers; only a current authorized Markdown snapshot may reach a model."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import frontmatter
import pytest
from fastapi.testclient import TestClient

from growwise.api import main as main_api
from growwise.api import resource_routes
from growwise.api.dependencies import get_rag_index, get_store
from growwise.api.main import app
from growwise.domain import ChildProfile, LearningLog, ResourceKind, ResourceRecord, Stage
from growwise.domain.links import EntityLink, EntityLinkRelation
from growwise.rag import GroundedRagService, HybridRagIndex, ResourceIngestor
from growwise.services.context import ChildContextService
from growwise.services.entity_links import EntityLinkService
from growwise.services.learning_wiki import LearningWikiService
from growwise.services.visibility import shared_source_ids
from growwise.storage import EntityStore

OLD = "SYNTHETIC_REMOVED_PRIVATE_TEXT"
QUERY = "별모래추적"


class Capture:
    def __init__(self, on_call=None):
        self.users = []
        self.on_call = on_call

    def generate_structured(self, *, system, user, schema):
        self.users.append(user)
        if self.on_call:
            self.on_call()
        return schema(answer="합성 근거 확인", insufficient_evidence=True)


@pytest.mark.parametrize("kind", ["context", "direct"])
@pytest.mark.parametrize("mutation", ["delete", "edit", "revoke", "raw_edit", "raw_revoke"])
def test_current_wiki_cannot_reintroduce_removed_or_revoked_originals(
    sources, kind, mutation,
):
    store, rag, owner, sibling, _resource = sources
    log = LearningLog(child_id=owner.id, parent_observation=f"{QUERY} {OLD}",
                      interest=f"{QUERY} {OLD}")
    store.save(log)
    grant = EntityLink(child_id=sibling.id, source_id=log.id, target_id=sibling.id,
                       relation=EntityLinkRelation.CHILD_SCOPE)
    store.save(grant)
    wiki_service = LearningWikiService(store, rag_index=rag)
    wiki = wiki_service.refresh(str(sibling.id))
    assert OLD in wiki.content_markdown
    capture = Capture()
    ask(sources, kind, capture, child=sibling)
    assert any(OLD in user for user in capture.users)
    if mutation == "delete":
        store.delete(log)
    elif mutation == "edit":
        store.save(log.model_copy(update={
            "parent_observation":"현재의 다른 관찰", "interest":None,
        }))
    elif mutation == "revoke":
        store.delete(grant)
    elif mutation == "raw_edit":
        path = store.markdown.path_for(log)
        post = frontmatter.loads(path.read_text(encoding="utf-8"))
        post["parent_observation"] = "현재의 다른 관찰"
        post["interest"] = None
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
    else:
        store.markdown.path_for(grant).unlink()
    capture = Capture()
    answer = ask(sources, kind, capture, child=sibling)
    assert all(OLD not in user for user in capture.users)
    assert f"record:{wiki.id}" not in getattr(answer, "source_ids", [])
    # Rebuilding the derived file also reads current originals/raw grants, not stale projections.
    rebuilt = wiki_service.refresh(str(sibling.id))
    assert OLD not in rebuilt.content_markdown


@pytest.fixture
def sources(tmp_path, monkeypatch):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    owner = ChildProfile(nickname="합성 소유자", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(nickname="합성 형제", stage=Stage.ELEMENTARY)
    store.save(owner)
    store.save(sibling)
    resource = ResourceRecord(child_id=owner.id, kind=ResourceKind.NOTE,
                              title=QUERY, content=f"{QUERY} {OLD}")
    store.save(resource)
    ResourceIngestor(rag).ingest(resource)
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)
    return store, rag, owner, sibling, resource


def ask(sources, kind, capture, *, child=None):
    store, rag, owner, _, _ = sources
    child_id = str((child or owner).id)
    if kind == "context":
        return ChildContextService(entity_index=store.index, rag_index=rag, provider=capture).ask(
            child_id=child_id, query=QUERY,
        )
    return GroundedRagService(index=rag, entity_index=store.index, provider=capture).ask(
        child_id=child_id, query=QUERY,
        shared_resource_ids=shared_source_ids(store.index, child_id),
    )


def unavailable(*args, **kwargs):
    raise RuntimeError("synthetic disposable projection failure")


@pytest.mark.parametrize("kind", ["context", "direct"])
@pytest.mark.parametrize("mutation", ["delete", "edit"])
def test_successful_mutation_with_failed_rag_cleanup_never_sends_removed_text(
    sources, monkeypatch, kind, mutation,
):
    store, rag, owner, _, resource = sources
    if mutation == "delete":
        monkeypatch.setattr(rag, "delete_resource", unavailable)
        assert resource_routes.delete_resource(resource.id, store, owner.id) == {"deleted": True}
    else:
        monkeypatch.setattr(rag, "replace_resource", unavailable)
        updated = resource_routes.update_resource(
            resource.id, resource_routes.ResourceUpdateRequest(
                kind=ResourceKind.NOTE, title="수정한 현재 자료", content="CURRENT_SAFE_TEXT",
            ), store, owner.id,
        )
        assert updated.content == "CURRENT_SAFE_TEXT"
    assert rag.search(query=QUERY, child_id=str(owner.id))  # Deliberately stale cache survives.
    capture = Capture()
    result = ask(sources, kind, capture)
    assert all(OLD not in user for user in capture.users)
    if mutation == "delete":
        assert result.insufficient_evidence and not capture.users
    else:
        assert len(capture.users) == 1 and "CURRENT_SAFE_TEXT" in capture.users[0]
        assert "수정한 현재 자료" in capture.users[0]


@pytest.mark.parametrize("kind", ["context", "direct"])
@pytest.mark.parametrize("mutation", ["delete", "edit", "revoke", "narrow"])
def test_source_changes_while_retrieval_is_pending_are_checked_after_retrieval(
    sources, monkeypatch, kind, mutation,
):
    store, rag, owner, sibling, resource = sources
    child = owner
    grant = None
    if mutation == "revoke":
        grant = EntityLinkService(store).share_with_children(
            source_id=resource.id, child_ids=[sibling.id],
        )[0]
        child = sibling
    elif mutation == "narrow":
        resource.child_id = None
        store.save(resource)
        ResourceIngestor(rag).ingest(resource)
        child = sibling
    searched, resume = Event(), Event()
    search = rag.search

    def delayed(**kwargs):
        hits = search(**kwargs)
        searched.set()
        assert resume.wait(5)
        return hits

    monkeypatch.setattr(rag, "search", delayed)
    capture = Capture()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(ask, sources, kind, capture, child=child)
        try:
            assert searched.wait(5)
            if mutation == "delete":
                store.delete(resource)
            elif mutation == "edit":
                resource.title, resource.content = "현재 자료", "CURRENT_SAFE_TEXT"
                store.save(resource)
            elif mutation == "revoke":
                assert grant is not None
                EntityLinkService(store).delete(grant.id)
            else:
                resource.child_id = owner.id
                store.save(resource)
        finally:
            resume.set()
        result = future.result(timeout=5)
    assert all(OLD not in user for user in capture.users)
    if mutation == "edit":
        assert "CURRENT_SAFE_TEXT" in capture.users[0]
    else:
        assert result.insufficient_evidence and capture.users == []


@pytest.mark.parametrize("kind", ["context", "direct"])
def test_current_markdown_scope_and_grants_override_stale_entity_projection(sources, kind):
    store, _, owner, sibling, resource = sources
    grant = EntityLinkService(store).share_with_children(
        source_id=resource.id, child_ids=[sibling.id],
    )[0]
    # Simulate committed Markdown with an old disposable entity projection.
    store.markdown.path_for(grant).unlink()
    assert store.index.get_entity(str(grant.id)) is not None
    capture = Capture()
    assert ask(sources, kind, capture, child=sibling).insufficient_evidence
    assert capture.users == []
    resource.child_id = None
    store.save(resource)
    resource.child_id = owner.id
    store.markdown.save(resource)
    assert store.index.get_entity(str(resource.id))["child_id"] is None
    assert ask(sources, kind, capture, child=sibling).insufficient_evidence
    assert capture.users == []


@pytest.mark.parametrize("kind", ["context", "direct"])
def test_missing_or_corrupt_markdown_never_falls_back_to_index_or_rag(sources, kind):
    store, _, _, _, resource = sources
    path = store.markdown.path_for(resource)
    for content in ("---\n[unterminated YAML", "---\nentity_type: resource\n---\n"):
        path.write_text(content, encoding="utf-8")
        capture = Capture()
        assert ask(sources, kind, capture).insufficient_evidence
        assert capture.users == []
    path.unlink()
    assert ask(sources, kind, Capture()).insufficient_evidence


@pytest.mark.parametrize("kind", ["context", "direct"])
def test_snapshot_releases_write_locks_before_model_network_work(sources, kind):
    store, _, _, _, resource = sources
    completed = Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        def during_model():
            # This would deadlock if the evidence snapshot held source/path locks during a request.
            assert pool.submit(store.delete, resource).result(timeout=3)
            completed.set()

        capture = Capture(during_model)
        ask(sources, kind, capture)
        assert completed.is_set()
    assert len(capture.users) == 1  # Authorized snapshot preceded deletion.
    assert OLD in capture.users[0]
    later = Capture()
    assert ask(sources, kind, later).insufficient_evidence
    assert later.users == []


def test_original_reader_uses_current_markdown_and_rejects_stale_scope(sources):
    store, rag, owner, sibling, resource = sources
    resource.child_id = None
    store.save(resource)
    resource.child_id, resource.content = owner.id, "CURRENT_SAFE_TEXT"
    store.markdown.save(resource)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_rag_index] = lambda: rag
    try:
        with TestClient(app) as client:
            for prefix, identifier in (("resource", str(resource.id)),
                                       ("chunk", f"{resource.id}:0")):
                route = f"/v1/children/{sibling.id}/evidence"
                response = client.get(route, params={"source_id": f"{prefix}:{identifier}"})
                assert response.status_code == 404
                response = client.get(f"/v1/children/{owner.id}/evidence", params={
                    "source_id": f"{prefix}:{identifier}",
                })
                assert response.status_code == 200
                assert "CURRENT_SAFE_TEXT" in response.json()["body"]
                assert OLD not in response.text
    finally:
        app.dependency_overrides.pop(get_store, None)
        app.dependency_overrides.pop(get_rag_index, None)


def test_actual_rag_api_composes_current_markdown_instead_of_cached_body(sources, monkeypatch):
    store, rag, owner, _, resource = sources
    resource.content = "CURRENT_SAFE_TEXT"
    store.markdown.save(resource)  # Neither disposable entity projection nor RAG is refreshed.
    capture = Capture()
    monkeypatch.setattr(main_api, "get_rag_index", lambda: rag)
    monkeypatch.setattr(main_api, "get_model_provider", lambda: capture)
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.post("/v1/rag/ask", json={
                "question": QUERY, "child_id": str(owner.id),
            })
            assert response.status_code == 200, response.text
            assert len(capture.users) == 1
            assert "CURRENT_SAFE_TEXT" in capture.users[0]
            assert OLD not in capture.users[0]
    finally:
        app.dependency_overrides.pop(get_store, None)


@pytest.mark.parametrize("field,value", [
    ("id", "00000000-0000-4000-8000-000000000000"),
    ("entity_type", "learning_log"),
    ("schema_version", 999999),
])
def test_source_identity_type_or_schema_mismatch_cannot_authorize_old_rag_text(
    sources, field, value,
):
    store, _, _, _, resource = sources
    path = store.markdown.path_for(resource)
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    post.metadata[field] = value
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    for kind in ("context", "direct"):
        capture = Capture()
        assert ask(sources, kind, capture).insufficient_evidence
        assert capture.users == []
