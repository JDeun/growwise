from typing import TypeVar

from pydantic import BaseModel

from growwise.services import ObservationEnricher, ObservationEnrichment

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
