from typing import TypeVar

from pydantic import BaseModel

from growwise.services import ObservationEnricher, ObservationEnrichment


def test_object_photo_cannot_become_unsupported_ability_tags() -> None:
    class Provider:
        def generate_structured(self, **_kwargs):
            return ObservationEnrichment(
                tags=["색상", "기하학적 모양", "분별력", "높은 집중력", "관찰력"],
            )

    result = ObservationEnricher(Provider()).enrich(  # type: ignore[arg-type]
        "흰 배경 위에 빨간 사각형, 파란 원, 노란 삼각형이 놓여 있다.",
    )
    assert result.tags == ["색상", "기하학적 모양"]


def test_parent_named_activity_topic_is_preserved_without_allowing_diagnosis() -> None:
    class Provider:
        def generate_structured(self, **_kwargs):
            return ObservationEnrichment(tags=["기억력 놀이", "자폐 진단"])

    result = ObservationEnricher(Provider()).enrich(  # type: ignore[arg-type]
        "부모가 기억력 놀이를 제안했고 아이가 짝을 맞추어 보았다. 자폐 진단 이야기는 하지 않았다.",
    )
    assert result.tags == ["기억력 놀이"]

T = TypeVar("T", bound=BaseModel)


class FakeProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        return schema.model_validate(
            {
                "tags": ["책", "시각관찰"],
                "interest": "그림책",
                "difficulty_note": None,
                "next_activity": "같은 책을 다시 보여주고 시선 이동을 관찰",
            }
        )


def test_observation_enricher_returns_metadata_only() -> None:
    result = ObservationEnricher(FakeProvider()).enrich("그림책의 고양이 그림을 오래 바라봄")

    assert isinstance(result, ObservationEnrichment)
    assert result.tags == ["책", "시각관찰"]
    assert result.interest == "그림책"
