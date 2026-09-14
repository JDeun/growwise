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
