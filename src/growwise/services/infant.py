from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from growwise.domain import ResourceKind, ResourceRecord, Stage
from growwise.model import ModelProvider

CURRICULUM_SOURCE = "교육부고시 제2024-23호 2024 개정 표준보육과정(0~2세)"
CURRICULUM_EFFECTIVE_DATE = "2025-03-01"


class InfantCurriculumDomain(StrEnum):
    PHYSICAL_HEALTH = "신체운동·건강"
    COMMUNICATION = "의사소통"
    SOCIAL_RELATIONSHIPS = "사회관계"
    ART_EXPERIENCE = "예술경험"
    NATURE_INQUIRY = "자연탐구"


class ActivitySuggestion(BaseModel):
    title: str
    description: str
    materials: list[str] = Field(default_factory=list)
    observation_cue: str | None = None
    tags: list[str] = Field(default_factory=list)


class InfantActivitySuggestions(BaseModel):
    suggestions: list[ActivitySuggestion] = Field(default_factory=list, max_length=5)


class ObservationHint(BaseModel):
    domain: InfantCurriculumDomain
    cue: str
    rationale: str


class InfantObservationHints(BaseModel):
    source: str = CURRICULUM_SOURCE
    effective_date: str = CURRICULUM_EFFECTIVE_DATE
    diagnostic: bool = False
    hints: list[ObservationHint] = Field(default_factory=list, max_length=5)


class BoardBookRecommendation(BaseModel):
    resource_id: str | None = None
    title: str
    reason: str
    read_aloud_tip: str
    source: str = "local_library_or_offline_fallback"


class BoardBookRecommendations(BaseModel):
    recommendations: list[BoardBookRecommendation] = Field(default_factory=list, max_length=5)


class InfantActivityService:
    SYSTEM = """You support a parent of an infant (0-2 years) in GrowWise.
Suggest simple, low-pressure parent-child activities based on the supplied month-age
and recent observations.
Do not diagnose development, compare with peers, claim milestones are required,
or turn activities into tests.
Activities are invitations, not assignments. Prefer ordinary household materials
and direct interaction.
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


class InfantObservationHintService:
    """Parent-facing observation prompts aligned to the five official 0-2 curriculum domains.

    These prompts intentionally do not reproduce milestone tables or turn curriculum content into
    a diagnostic checklist. They help a parent notice the child's self-directed interests and
    interactions in ordinary life.
    """

    SYSTEM = f"""Create non-diagnostic parent observation hints for an infant aged 0-2.
Use only these curriculum-domain labels from {CURRICULUM_SOURCE}:
{', '.join(domain.value for domain in InfantCurriculumDomain)}.
Do not compare with peers, score development, state required milestones, or imply diagnosis.
Phrase each cue as something the parent can notice during ordinary play and daily routines.
Return concise Korean when the input is Korean."""

    def __init__(self, provider: ModelProvider | None = None) -> None:
        self.provider = provider

    def suggest(
        self,
        *,
        age_months: int | None,
        recent_observations: list[str],
        interests: list[str],
    ) -> InfantObservationHints:
        fallback = self._fallback(interests=interests)
        if self.provider is None:
            return fallback

        context = {
            "age_months": age_months,
            "recent_observations": recent_observations[-8:],
            "interests": interests,
            "source": CURRICULUM_SOURCE,
        }
        try:
            result = self.provider.generate_structured(
                system=self.SYSTEM,
                user=str(context),
                schema=InfantObservationHints,
            )
            allowed = set(InfantCurriculumDomain)
            by_domain = {hint.domain: hint for hint in result.hints if hint.domain in allowed}
            result.hints = [by_domain.get(hint.domain, hint) for hint in fallback.hints]
            result.source = CURRICULUM_SOURCE
            result.effective_date = CURRICULUM_EFFECTIVE_DATE
            result.diagnostic = False
            return result
        except Exception:
            return fallback

    @staticmethod
    def _fallback(*, interests: list[str]) -> InfantObservationHints:
        topic = interests[0] if interests else "주변 경험"
        return InfantObservationHints(
            hints=[
                ObservationHint(
                    domain=InfantCurriculumDomain.PHYSICAL_HEALTH,
                    cue="편안한 일상과 놀이에서 몸을 움직이거나 감각을 탐색하는 방식을 살펴봅니다.",
                    rationale="움직임의 성취 여부가 아니라 스스로 시도하고 쉬는 흐름을 기록합니다.",
                ),
                ObservationHint(
                    domain=InfantCurriculumDomain.COMMUNICATION,
                    cue="소리, 표정, 몸짓, 말에 반응하거나 자기 방식으로 주고받는 순간을 살펴봅니다.",
                    rationale="말의 개수보다 사람과 의미를 주고받으려는 다양한 표현을 관찰합니다.",
                ),
                ObservationHint(
                    domain=InfantCurriculumDomain.SOCIAL_RELATIONSHIPS,
                    cue="부모나 익숙한 사람과 시선·표정·행동을 주고받고 편안함을 찾는 방식을 봅니다.",
                    rationale="관계 행동을 또래와 비교하지 않고 현재 아이의 상호작용 맥락으로 기록합니다.",
                ),
                ObservationHint(
                    domain=InfantCurriculumDomain.ART_EXPERIENCE,
                    cue=f"{topic}와 연결된 소리, 리듬, 색, 움직임 중 무엇에 관심을 두는지 살펴봅니다.",
                    rationale="결과물을 요구하지 않고 감각적 경험을 즐기거나 반복하는 모습을 관찰합니다.",
                ),
                ObservationHint(
                    domain=InfantCurriculumDomain.NATURE_INQUIRY,
                    cue="사물의 모양·질감·움직임이나 간단한 원인과 결과를 반복해서 탐색하는 순간을 봅니다.",
                    rationale="정답을 확인하기보다 아이가 스스로 발견하고 다시 시도하는 과정에 주목합니다.",
                ),
            ]
        )


class BoardBookRecommendationService:
    """Recommend local book resources first, with an offline category fallback."""

    def recommend(
        self,
        *,
        resources: list[ResourceRecord],
        interests: list[str],
        limit: int = 3,
    ) -> BoardBookRecommendations:
        books = [resource for resource in resources if resource.kind is ResourceKind.BOOK]
        scored = sorted(
            books,
            key=lambda resource: self._score(resource=resource, interests=interests),
            reverse=True,
        )
        recommendations = [
            BoardBookRecommendation(
                resource_id=str(resource.id),
                title=resource.title,
                reason=self._reason(resource=resource, interests=interests),
                read_aloud_tip="끝까지 읽기보다 아이가 오래 보는 그림에서 멈추고 짧게 말해 주세요.",
                source="local_library",
            )
            for resource in scored[:limit]
        ]
        if recommendations:
            return BoardBookRecommendations(recommendations=recommendations)
        return BoardBookRecommendations(recommendations=self._fallback(interests=interests)[:limit])

    @staticmethod
    def _score(*, resource: ResourceRecord, interests: list[str]) -> tuple[int, int, int]:
        searchable = " ".join(
            [resource.title, resource.summary or "", *resource.tags]
        ).casefold()
        interest_hits = sum(1 for interest in interests if interest.casefold() in searchable)
        infant_stage = int(Stage.INFANT_0_2 in resource.stage_tags)
        metadata_depth = len(resource.tags) + int(bool(resource.summary))
        return interest_hits, infant_stage, metadata_depth

    @staticmethod
    def _reason(*, resource: ResourceRecord, interests: list[str]) -> str:
        matched = [
            interest
            for interest in interests
            if interest.casefold()
            in " ".join([resource.title, resource.summary or "", *resource.tags]).casefold()
        ]
        if matched:
            return f"현재 관심사({', '.join(matched[:2])})와 연결되는 로컬 책 기록입니다."
        if Stage.INFANT_0_2 in resource.stage_tags:
            return "영아 단계로 태깅된 로컬 책 기록입니다."
        return "로컬 라이브러리에 저장된 책 중 메타데이터가 있는 항목입니다."

    @staticmethod
    def _fallback(*, interests: list[str]) -> list[BoardBookRecommendation]:
        topic = interests[0] if interests else "익숙한 사물"
        return [
            BoardBookRecommendation(
                title=f"{topic} 그림이 크게 보이는 보드북",
                reason="현재 관심사와 연결된 단순하고 선명한 그림을 함께 보기 좋습니다.",
                read_aloud_tip="그림을 가리키며 한두 단어로 말하고 아이의 반응을 기다려 주세요.",
            ),
            BoardBookRecommendation(
                title="반복되는 말과 리듬이 있는 짧은 그림책",
                reason="반복되는 소리와 문장을 부모와 편안하게 주고받기 좋습니다.",
                read_aloud_tip="문장을 외우게 하지 말고 반복 구간에서 표정과 소리를 함께 주고받아 주세요.",
            ),
            BoardBookRecommendation(
                title="일상 행동과 표정이 담긴 사진·그림책",
                reason="익숙한 사람·행동·표정을 실제 생활 경험과 연결해 보기 좋습니다.",
                read_aloud_tip="아이에게 질문을 연속해서 하기보다 보이는 장면을 짧게 묘사해 주세요.",
            ),
        ]
