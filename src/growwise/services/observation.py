from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from growwise.domain import ExperienceAxis
from growwise.model import ModelProvider

_TagText = Annotated[str, Field(min_length=1, max_length=200)]


class ObservationEnrichment(BaseModel):
    tags: list[_TagText] = Field(default_factory=list, max_length=100)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list, max_length=20)
    interest: str | None = Field(default=None, max_length=2_000)
    difficulty_note: str | None = Field(default=None, max_length=4_000)
    next_activity: str | None = Field(default=None, max_length=4_000)


_FORBIDDEN_INTERPRETATION_MARKERS = (
    "adhd",
    "autism",
    "autistic",
    "disorder",
    "diagnos",
    "자폐",
    "발달장애",
    "장애로 보",
    "진단",
    "비정상",
    "정상 발달",
    "또래보다",
    "또래 평균",
    "상위 ",
    "하위 ",
    "퍼센타일",
)
_TRAIT_TAG_MARKERS = (
    "분별력", "집중력", "기억력", "창의력", "관찰력", "지능", "아이큐",
    "사회성", "외향성", "내향성", "잠재력", "영재", "천재",
)


def _contains_forbidden_interpretation(value: str | None) -> bool:
    if value is None:
        return False
    lowered = value.casefold()
    return any(marker in lowered for marker in _FORBIDDEN_INTERPRETATION_MARKERS)


def _sanitize(enrichment: ObservationEnrichment, observation: str) -> ObservationEnrichment:
    return enrichment.model_copy(
        update={
            "tags": [
                tag
                for tag in enrichment.tags
                if not _contains_forbidden_interpretation(tag)
                and not any(marker in tag and marker not in observation
                            for marker in _TRAIT_TAG_MARKERS)
            ],
            "interest": (
                None
                if _contains_forbidden_interpretation(enrichment.interest)
                else enrichment.interest
            ),
            "difficulty_note": (
                None
                if _contains_forbidden_interpretation(enrichment.difficulty_note)
                else enrichment.difficulty_note
            ),
            "next_activity": (
                None
                if _contains_forbidden_interpretation(enrichment.next_activity)
                else enrichment.next_activity
            ),
        }
    )


class ObservationEnricher:
    """Turn free-form parent notes into searchable metadata without changing the source note."""

    SYSTEM = """You organize a parent's observation about a child for GrowWise.
Return only conservative metadata grounded in the observation.
Do not diagnose development, infer disorders, rank against peers,
or infer stable personality traits.
Use short Korean tags when the observation is Korean. Keep uncertainty explicit.
Tags describe observed objects or activities, never inferred intelligence, ability or personality.
Do not turn a photograph of objects into evidence about a child's cognitive traits.
Choose experience_axes only when directly supported. Allowed values are:
physical, emotional_character, expression_art, thinking_inquiry, social,
reading, speaking, writing, math, exploration.
The parent's original observation remains authoritative; you are only producing metadata."""

    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    def enrich(self, observation: str) -> ObservationEnrichment:
        enrichment = self.provider.generate_structured(
            system=self.SYSTEM,
            user=observation,
            schema=ObservationEnrichment,
        )
        return _sanitize(enrichment, observation)
