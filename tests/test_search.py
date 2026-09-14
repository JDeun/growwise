from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.services import NaturalLanguageSearch
from growwise.storage import EntityStore


def test_search_never_crosses_child_scope(tmp_path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    first = ChildProfile(nickname="first", stage=Stage.INFANT_0_2, age_months=9)
    second = ChildProfile(nickname="second", stage=Stage.INFANT_0_2, age_months=10)
    store.save(first)
    store.save(second)
    store.save(
        LearningLog(
            child_id=first.id,
            parent_observation="그림책의 고양이 그림을 오래 바라봄",
            tags=["책", "고양이"],
        )
    )
    store.save(
        LearningLog(
            child_id=second.id,
            parent_observation="고양이 장난감을 잡고 흔듦",
            tags=["고양이"],
        )
    )

    service = NaturalLanguageSearch(store.index)
    response = service.search(child_id=str(first.id), query="고양이", limit=10)

    assert len(response.results) == 1
    assert response.results[0]["child_id"] == str(first.id)
