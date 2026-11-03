from uuid import UUID

from fastapi.testclient import TestClient

from growwise.api import link_routes, main, resource_routes
from growwise.domain import ChildProfile, Stage
from growwise.rag import HybridRagIndex
from growwise.storage import EntityStore


def test_child_resource_http_lists_include_globals_once_and_exclude_other_private_records(
    tmp_path,
    monkeypatch,
):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag = HybridRagIndex(tmp_path / "rag.sqlite3")
    first = ChildProfile(nickname="현재 아이", stage=Stage.ELEMENTARY)
    second = ChildProfile(nickname="다른 아이", stage=Stage.ELEMENTARY)
    store.save(first)
    store.save(second)
    monkeypatch.setitem(
        main.app.dependency_overrides, resource_routes.get_resource_store, lambda: store
    )
    monkeypatch.setitem(main.app.dependency_overrides, link_routes.get_link_store, lambda: store)
    monkeypatch.setattr(resource_routes, "get_resource_rag_index", lambda: rag)
    monkeypatch.setattr(
        resource_routes,
        "get_resource_idempotency_store",
        lambda: resource_routes.SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite3"),
    )
    client = TestClient(main.app)
    created = []
    for title, child_id in [
        ("모두의 참고 자료", None),
        ("첫째 비공개", str(first.id)),
        ("둘째 비공개", str(second.id)),
    ]:
        response = client.post(
            "/v1/resources", json={"kind": "note", "title": title, "child_id": child_id}
        )
        assert response.status_code == 200, response.text
        created.append(response.json())
    shared, first_private, second_private = created
    # A global record may also have a historical explicit grant; it still appears just once.
    grant = client.post(
        "/v1/links",
        json={
            "source_id": shared["id"],
            "target_id": str(first.id),
            "relation": "child_scope",
            "acting_child_id": str(first.id),
        },
    )
    assert grant.status_code == 200, grant.text

    for child, own, hidden in [
        (first, first_private, second_private),
        (second, second_private, first_private),
    ]:
        response = client.get("/v1/resources", params={"child_id": str(child.id)})
        assert response.status_code == 200, response.text
        identifiers = [item["id"] for item in response.json()]
        assert set(identifiers) == {shared["id"], own["id"]}
        assert identifiers.count(shared["id"]) == 1
        assert hidden["id"] not in identifiers

    # Keep the compatibility helper and the registered HTTP collection on the same policy.
    assert {item["id"] for item in main.list_resources(store, UUID(str(first.id)))} == {
        shared["id"],
        first_private["id"],
    }
    # Global visibility is opt-in: unrelated child-scoped projections retain their strict default.
    assert {
        item["id"]
        for item in store.index.list_entities(
            entity_type="resource",
            child_id=str(second.id),
        )
    } == {second_private["id"]}
