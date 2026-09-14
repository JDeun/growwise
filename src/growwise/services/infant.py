from __future__ import annotations

from pydantic import BaseModel, Field

from growwise.model import ModelProvider


class ActivitySuggestion(BaseModel):
    title: str
    description: str
    materials: list[str] = Field(default_factory=list)
    observation_cue: str | None = None
    tags: list[str] = Field(default_factory=list)


class InfantActivitySuggestions(BaseModel):
    suggestions: list[ActivitySuggestion] = Field(default_factory=list, max_length=5)


class InfantActivityService:
    SYSTEM = """You support a parent of an infant (0-2 years) in GrowWise.
Suggest simple, low-pressure parent-child activities based on the supplied month-age and recent observations.
Do not diagnose development, compare with peers, claim milestones are required, or turn activities into tests.
Activities are invitations, not assignments. Prefer ordinary household materials and direct interaction.
Observation cues should help the parent notice interest or response without scoring the child.
Return concise Korean when the input is Korean."""

    def __init__(self, provider: ModelProvider | None = None) -> None:
        self.provider = provider

    def suggest(
        self,
        *,
        age_months: int | None,
        recent_observations: list[str],
        interests: list[str],
        limit: int = 3,
    ) -> InfantActivitySuggestions:
        if self.provider is None:
            return self._fallback(interests=interests, limit=limit)

        context = {
            "age_months": age_months,
            "recent_observations": recent_observations[-8:],
            "interests": interests,
            "requested_count": limit,
        }
        try:
            result = self.provider.generate_structured(
                system=self.SYSTEM,
                user=str(context),
                schema=InfantActivitySuggestions,
            )
            result.suggestions = result.suggestions[:limit]
            return result
        except Exception:
            return self._fallback(interests=interests, limit=limit)

    def _fallback(self, *, interests: list[str], limit: int) -> InfantActivitySuggestions:
        topic = interests[0] if interests else "주변 사물"
        candidates = [
            ActivitySuggestion(
                title="천천히 함께 살펴보기",
                description=f"{topic}와 관련된 안전한 사물이나 그림을 가까이에서 함께 살펴봅니다.",
                observation_cue="무엇을 오래 바라보거나 손을 뻗는지 가볍게 관찰합니다.",
                tags=["관찰", "상호작용"],
            ),
            ActivitySuggestion(
                title="소리와 반응 주고받기",
                description="부모가 짧은 소리나 말을 들려주고 아이의 반응 뒤에 잠시 기다립니다.",
                observation_cue="표정, 몸짓, 소리로 주고받으려는 순간이 있는지 봅니다.",
                tags=["언어노출", "상호작용"],
            ),
            ActivitySuggestion(
                title="안전한 촉감 탐색",
                description="부드럽고 안전한 서로 다른 재질 두세 가지를 손으로 만져봅니다.",
                observation_cue="선호하거나 반복해서 만지는 재질이 있는지 봅니다.",
                tags=["감각", "탐색"],
            ),
        ]
        return InfantActivitySuggestions(suggestions=candidates[:limit])
