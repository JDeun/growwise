from __future__ import annotations

from pathlib import Path

from growwise.domain import ChildProfile, LearningLog, ResourceKind, ResourceRecord, Stage
from growwise.domain.links import EntityLinkRelation
from growwise.services.entity_links import EntityLinkService
from growwise.services.graph_context import GraphContextExpander
from growwise.storage import EntityStore


def _store(tmp_path: Path) -> EntityStore:
    return EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")


def test_graph_expansion_excludes_other_child_private_neighbor(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = ChildProfile(name="첫째", nickname="첫째", stage=Stage.ELEMENTARY)
    second = ChildProfile(name="둘째", nickname="둘째", stage=Stage.ELEMENTARY)
    store.save(first)
    store.save(second)

    seed = LearningLog(child_id=first.id, parent_observation="공룡 화석을 궁금해했다.")
    private_neighbor = ResourceRecord(
        child_id=second.id,
        kind=ResourceKind.BOOK,
        title="둘째만의 공룡 책",
    )
    store.save(seed)
    store.save(private_neighbor)
    EntityLinkService(store).create(
        source_id=seed.id,
        target_id=private_neighbor.id,
        relation=EntityLinkRelation.RELATED,
    )

    expanded = GraphContextExpander(store.index).expand(
        child_id=str(first.id),
        seed_ids=[str(seed.id)],
    )

    assert expanded == []


def test_graph_expansion_includes_global_and_explicitly_shared_neighbors(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = ChildProfile(name="첫째", nickname="첫째", stage=Stage.ELEMENTARY)
    second = ChildProfile(name="둘째", nickname="둘째", stage=Stage.ELEMENTARY)
    store.save(first)
    store.save(second)

    seed = LearningLog(child_id=first.id, parent_observation="별자리를 찾아봤다.")
    global_resource = ResourceRecord(
        kind=ResourceKind.WEB,
        title="공용 별자리 자료",
    )
    shared_resource = ResourceRecord(
        child_id=second.id,
        kind=ResourceKind.BOOK,
        title="함께 보는 우주책",
    )
    store.save(seed)
    store.save(global_resource)
    store.save(shared_resource)

    links = EntityLinkService(store)
    links.create(
        source_id=seed.id,
        target_id=global_resource.id,
        relation=EntityLinkRelation.SUPPORTS,
    )
    links.create(
        source_id=seed.id,
        target_id=shared_resource.id,
        relation=EntityLinkRelation.RELATED,
    )
    links.share_with_children(source_id=shared_resource.id, child_ids=[first.id])

    expanded = GraphContextExpander(store.index).expand(
        child_id=str(first.id),
        seed_ids=[str(seed.id)],
    )

    ids = {item["id"] for item in expanded}
    assert ids == {str(global_resource.id), str(shared_resource.id)}
    relations = {item["id"]: item["graph_relation"] for item in expanded}
    assert relations[str(global_resource.id)] == "supports"
    assert relations[str(shared_resource.id)] == "related"


def test_child_scope_links_are_visibility_only_not_semantic_graph_edges(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = ChildProfile(name="첫째", nickname="첫째", stage=Stage.ELEMENTARY)
    second = ChildProfile(name="둘째", nickname="둘째", stage=Stage.ELEMENTARY)
    store.save(first)
    store.save(second)

    activity = ResourceRecord(
        child_id=first.id,
        kind=ResourceKind.NOTE,
        title="함께한 활동",
    )
    store.save(activity)
    EntityLinkService(store).share_with_children(source_id=activity.id, child_ids=[second.id])

    expanded = GraphContextExpander(store.index).expand(
        child_id=str(second.id),
        seed_ids=[str(activity.id)],
    )

    assert expanded == []
