from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.storage import EntityStore


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



def test_child_scope_queries_scale_beyond_sqlite_variable_limit(tmp_path):
    from growwise.storage.sqlite import SQLiteProjection

    index = SQLiteProjection(tmp_path / "index.sqlite3")
    viewer = "viewer-child"
    owner = "owner-child"
    count = 1_200

    for position in range(count):
        resource_id = f"resource-{position}"
        index._upsert_payload(
            {
                "schema_version": 1,
                "id": resource_id,
                "entity_type": "resource",
                "child_id": owner,
                "created_at": "2026-09-18T00:00:00+00:00",
                "updated_at": f"2026-09-18T00:00:{position % 60:02d}+00:00",
                "title": f"needle shared resource {position}",
            },
            tmp_path / f"resource-{position}.md",
        )
        index._upsert_payload(
            {
                "schema_version": 1,
                "id": f"link-{position}",
                "entity_type": "entity_link",
                "child_id": viewer,
                "created_at": "2026-09-18T00:00:00+00:00",
                "updated_at": "2026-09-18T00:00:00+00:00",
                "relation": "child_scope",
                "source_id": resource_id,
            },
            tmp_path / f"link-{position}.md",
        )

    listed = index.list_entities(entity_type="resource", child_id=viewer)
    searched = index.search_entities(
        child_id=viewer,
        query_text="needle",
        entity_types=("resource",),
        limit=20,
    )

    assert len(listed) == count
    assert len(searched) == 20
