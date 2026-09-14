from __future__ import annotations

from pydantic import BaseModel, Field

from growwise.domain import ExperienceAxis
from growwise.model import ModelProvider


class ObservationEnrichment(BaseModel):
    tags: list[str] = Field(default_factory=list)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list)
    interest: str | None = None
    difficulty_note: str | None = None
    next_activity: str | None = None


class ObservationEnricher:
    """Turn free-form parent notes into searchable metadata without changing the source note."""

    SYSTEM = """You organize a parent's observation about a child for GrowWise.
Return only conservative metadata grounded in the observation.
Do not diagnose development, infer disorders, rank against peers,
or infer stable personality traits.
Use short Korean tags when the observation is Korean. Keep uncertainty explicit.
Choose experience_axes only when directly supported. Allowed values are:
physical, emotional_character, expression_art, thinking_inquiry, social,
reading, speaking, writing, math, exploration.
The parent's original observation remains authoritative; you are only producing metadata."""

    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    def enrich(self, observation: str) -> ObservationEnrichment:
        return self.provider.generate_structured(
            system=self.SYSTEM,
            user=observation,
            schema=ObservationEnrichment,
        )
