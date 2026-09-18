import sqlite3
from pathlib import Path

from uuid6 import uuid7

from growwise.domain import ChildProfile, LearningLog, ResourceKind, ResourceRecord, Stage
from growwise.domain.links import EntityLink, EntityLinkRelation
from growwise.storage import EntityStore, SQLiteProjection


def test_search_entities_is_child_scoped_and_ranks_keyword_hits(tmp_path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    first_child = ChildProfile(nickname="첫째", stage=Stage.INFANT_0_2, age_months=9)
    second_child = ChildProfile(nickname="둘째", stage=Stage.INFANT_0_2, age_months=10)
    store.save(first_child)
    store.save(second_child)

    strongest = LearningLog(
        child_id=first_child.id,
        parent_observation="고양이 그림을 보고 고양이 소리를 따라 하며 오래 관심을 보였다.",
    )
    partial = LearningLog(
        child_id=first_child.id,
        parent_observation="고양이 그림책을 잠깐 살펴봤다.",
    )
    other_child = LearningLog(
        child_id=second_child.id,
        parent_observation="고양이 소리를 여러 번 따라 했다.",
    )
    store.save(partial)
    store.save(strongest)
    store.save(other_child)

    results = store.index.search_entities(
        child_id=str(first_child.id),
        query_text="고양이 소리",
        entity_types=("learning_log",),
        limit=10,
    )

    assert [item["id"] for item in results] == [str(strongest.id), str(partial.id)]
    assert all(item["child_id"] == str(first_child.id) for item in results)


def test_search_entities_treats_like_wildcards_as_literals(tmp_path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)

    literal = LearningLog(
        child_id=child.id,
        parent_observation="rate%mark needle_under_score 패턴을 살펴봤다.",
    )
    ordinary = LearningLog(
        child_id=child.id,
        parent_observation="rateXmark needleXunderXscore 패턴을 살펴봤다.",
    )
    store.save(literal)
    store.save(ordinary)

    percent_results = store.index.search_entities(
        child_id=str(child.id),
        query_text="rate%mark",
        entity_types=("learning_log",),
        limit=10,
    )
    underscore_results = store.index.search_entities(
        child_id=str(child.id),
        query_text="needle_under_score",
        entity_types=("learning_log",),
        limit=10,
    )

    assert [item["id"] for item in percent_results] == [str(literal.id)]
    assert [item["id"] for item in underscore_results] == [str(literal.id)]


def test_search_entities_caps_query_term_expansion(tmp_path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)

    results = store.index.search_entities(
        child_id=str(child.id),
        query_text=" ".join(f"term{index}" for index in range(2_000)),
        entity_types=("learning_log",),
        limit=10,
    )

    assert results == []



def test_shared_projection_queries_survive_sqlite_variable_ceiling(tmp_path: Path) -> None:
    class LowVariableProjection(SQLiteProjection):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 512)
            return connection

    projection = LowVariableProjection(tmp_path / "index.sqlite3")
    viewer_id = uuid7()
    owner_id = uuid7()
    target_resource_id = None

    with projection._connection() as connection:
        for index in range(600):
            resource = ResourceRecord(
                child_id=owner_id,
                kind=ResourceKind.NOTE,
                title=f"공유 자료 {index}",
                content="needle shared content" if index == 599 else "ordinary shared content",
            )
            link = EntityLink(
                child_id=viewer_id,
                source_id=resource.id,
                target_id=viewer_id,
                relation=EntityLinkRelation.CHILD_SCOPE,
            )
            projection._upsert_on(
                connection,
                resource.model_dump(mode="json"),
                tmp_path / f"resource-{index}.md",
            )
            projection._upsert_on(
                connection,
                link.model_dump(mode="json"),
                tmp_path / f"link-{index}.md",
            )
            if index == 599:
                target_resource_id = str(resource.id)

    listed = projection.list_entities(
        entity_type="resource",
        child_id=str(viewer_id),
    )
    assert len(listed) == 600

    results = projection.search_entities(
        child_id=str(viewer_id),
        query_text="needle",
        entity_types=("resource",),
        limit=10,
    )
    assert target_resource_id is not None
    assert [item["id"] for item in results] == [target_resource_id]
