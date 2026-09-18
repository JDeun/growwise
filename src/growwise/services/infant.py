from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from growwise.domain import ResourceKind, ResourceRecord, Stage
from growwise.model import ModelProvider

CURRICULUM_SOURCE = "교육부고시 제2024-23호 2024 개정 표준보육과정(0~2세)"
CURRICULUM_EFFECTIVE_DATE = "2025-03-01"

# Automatic public book lookup must never forward arbitrary parent-entered interest text. Only
# these generic education topics may leave the device. Unknown/free-form text falls back to a
# generic infant-picture-book query.
_BOOK_DISCOVERY_TOPICS: tuple[str, ...] = (
    "동물",
    "고양이",
    "강아지",
    "공룡",
    "자동차",
    "기차",
    "탈것",
    "우주",
    "별",
    "달",
    "자연",
    "나무",
    "꽃",
    "바다",
    "물고기",
    "곤충",
    "음악",
    "노래",
    "색깔",
    "숫자",
    "모양",
    "음식",
    "과일",
    "가족",
    "친구",
    "감정",
    "몸",
    "목욕",
    "잠",
    "animals",
    "cats",
    "dogs",
    "dinosaurs",
    "vehicles",
    "space",
    "nature",
    "music",
    "colors",
    "numbers",
    "shapes",
)


class InfantCurriculumDomain(StrEnum):
    PHYSICAL_HEALTH = "신체운동·건강"
    COMMUNICATION = "의사소통"
    SOCIAL_RELATIONSHIPS = "사회관계"
    ART_EXPERIENCE = "예술경험"
    NATURE_INQUIRY = "자연탐구"


_SuggestionText = Annotated[str, Field(min_length=1, max_length=4_000)]
_SuggestionItem = Annotated[str, Field(min_length=1, max_length=500)]
_SuggestionTag = Annotated[str, Field(min_length=1, max_length=200)]


class ActivitySuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: _SuggestionText
    materials: list[_SuggestionItem] = Field(default_factory=list, max_length=20)
    observation_cue: str | None = Field(default=None, max_length=4_000)
    tags: list[_SuggestionTag] = Field(default_factory=list, max_length=100)


class InfantActivitySuggestions(BaseModel):
    suggestions: list[ActivitySuggestion] = Field(default_factory=list, max_length=5)


class ObservationHint(BaseModel):
    domain: InfantCurriculumDomain
    cue: _SuggestionText
    rationale: _SuggestionText


class InfantObservationHints(BaseModel):
    source: str = Field(default=CURRICULUM_SOURCE, max_length=500)
    effective_date: str = Field(default=CURRICULUM_EFFECTIVE_DATE, max_length=32)
    diagnostic: bool = False
    hints: list[ObservationHint] = Field(default_factory=list, max_length=5)


class BoardBookRecommendation(BaseModel):
    resource_id: str | None = Field(default=None, max_length=120)
    discovery_candidate_id: str | None = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=500)
    reason: _SuggestionText
    read_aloud_tip: _SuggestionText
    source: str = Field(default="local_library_or_offline_fallback", max_length=160)
    source_name: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_048)


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
                description=(
                    f"{topic}와 관련된 안전한 사물이나 그림을 가까이에서 함께 살펴봅니다."
                ),
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
    """Parent-facing prompts aligned to the five official 0-2 curriculum domains."""

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
            forbidden = (
                "adhd",
                "autism",
                "diagnos",
                "자폐",
                "발달장애",
                "진단",
                "비정상",
                "또래보다",
                "또래 평균",
                "상위 ",
                "하위 ",
                "퍼센타일",
            )
            by_domain: dict[InfantCurriculumDomain, ObservationHint] = {}
            for hint in result.hints:
                text_value = f"{hint.cue} {hint.rationale}".casefold()
                if hint.domain in allowed and not any(
                    marker in text_value for marker in forbidden
                ):
                    by_domain[hint.domain] = hint
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
                    cue=(
                        "편안한 일상과 놀이에서 몸을 움직이거나 감각을 탐색하는 방식을 "
                        "살펴봅니다."
                    ),
                    rationale=(
                        "움직임의 성취 여부가 아니라 스스로 시도하고 쉬는 흐름을 기록합니다."
                    ),
                ),
                ObservationHint(
                    domain=InfantCurriculumDomain.COMMUNICATION,
                    cue=(
                        "소리, 표정, 몸짓, 말에 반응하거나 자기 방식으로 주고받는 순간을 "
                        "살펴봅니다."
                    ),
                    rationale=(
                        "말의 개수보다 사람과 의미를 주고받으려는 다양한 표현을 관찰합니다."
                    ),
                ),
                ObservationHint(
                    domain=InfantCurriculumDomain.SOCIAL_RELATIONSHIPS,
                    cue=(
                        "부모나 익숙한 사람과 시선·표정·행동을 주고받고 편안함을 찾는 "
                        "방식을 봅니다."
                    ),
                    rationale=(
                        "관계 행동을 또래와 비교하지 않고 현재 아이의 상호작용 맥락으로 "
                        "기록합니다."
                    ),
                ),
                ObservationHint(
                    domain=InfantCurriculumDomain.ART_EXPERIENCE,
                    cue=(
                        f"{topic}와 연결된 소리, 리듬, 색, 움직임 중 무엇에 관심을 두는지 "
                        "살펴봅니다."
                    ),
                    rationale=(
                        "결과물을 요구하지 않고 감각적 경험을 즐기거나 반복하는 모습을 "
                        "관찰합니다."
                    ),
                ),
                ObservationHint(
                    domain=InfantCurriculumDomain.NATURE_INQUIRY,
                    cue=(
                        "사물의 모양·질감·움직임이나 간단한 원인과 결과를 반복해서 탐색하는 "
                        "순간을 봅니다."
                    ),
                    rationale=(
                        "정답을 확인하기보다 아이가 스스로 발견하고 다시 시도하는 과정에 "
                        "주목합니다."
                    ),
                ),
            ]
        )


class BoardBookRecommendationService:
    """Prefer saved books, then privacy-bounded public candidates, then offline ideas."""

    def recommend(
        self,
        *,
        resources: list[ResourceRecord],
        interests: list[str],
        limit: int = 3,
        discovery_candidates: list[BoardBookRecommendation] | None = None,
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
                read_aloud_tip=(
                    "끝까지 읽기보다 아이가 오래 보는 그림에서 멈추고 짧게 말해 주세요."
                ),
                source="local_library",
                source_name=resource.source_name,
                source_url=resource.source_url,
            )
            for resource in scored[:limit]
        ]
        seen_titles = {item.title.casefold() for item in recommendations}

        candidates = discovery_candidates
        if candidates is None and len(recommendations) < limit:
            candidates = self._public_discovery_candidates(
                interests=interests,
                limit=limit - len(recommendations),
            )
        for candidate in candidates or []:
            if len(recommendations) >= limit:
                break
            title_key = candidate.title.casefold()
            if title_key in seen_titles:
                continue
            recommendations.append(
                candidate.model_copy(
                    update={"resource_id": None, "source": "public_discovery"}
                )
            )
            seen_titles.add(title_key)

        for fallback in self._fallback(interests=interests):
            if len(recommendations) >= limit:
                break
            title_key = fallback.title.casefold()
            if title_key in seen_titles:
                continue
            recommendations.append(fallback)
            seen_titles.add(title_key)

        return BoardBookRecommendations(recommendations=recommendations[:limit])

    @staticmethod
    def _generalized_book_query(interests: list[str]) -> str:
        searchable = " ".join(interests).casefold()
        topics: list[str] = []
        for topic in _BOOK_DISCOVERY_TOPICS:
            if topic.casefold() not in searchable or topic in topics:
                continue
            topics.append(topic)
            if len(topics) >= 2:
                break
        if not topics:
            return "영아 그림책"
        return " ".join([*topics, "그림책"])

    @classmethod
    def _public_discovery_candidates(
        cls,
        *,
        interests: list[str],
        limit: int,
    ) -> list[BoardBookRecommendation]:
        """Look up books with allow-listed generic topics only; never raw interest text."""
        from growwise.adapters import (
            Data4LibraryAdapter,
            ExternalAdapterError,
            SQLiteExternalCache,
        )
        from growwise.config import Settings

        settings = Settings()
        api_key = (settings.data4library_api_key or "").strip()
        if not api_key or limit <= 0:
            return []

        query = cls._generalized_book_query(interests)
        adapter = Data4LibraryAdapter(
            auth_key=api_key,
            cache=SQLiteExternalCache(settings.external_cache_path),
            endpoint=settings.data4library_endpoint,
            ttl_seconds=settings.data4library_cache_ttl_seconds,
        )
        try:
            result = adapter.search_books(
                keyword=query,
                page_size=min(8, max(3, limit * 2)),
                offline=False,
            )
        except ExternalAdapterError:
            return []

        recommendations: list[BoardBookRecommendation] = []
        for record in result.records:
            title = str(record.get("title") or "").strip()
            if not title:
                continue
            isbn = str(record.get("isbn13") or "").strip()
            source_key = isbn or title
            digest = hashlib.sha256(
                f"{result.source}\x1f{source_key}".encode()
            ).hexdigest()[:24]
            source_url = str(record.get("book_detail_url") or "").strip() or None
            recommendations.append(
                BoardBookRecommendation(
                    discovery_candidate_id=f"{result.source}:{digest}",
                    title=title,
                    reason=(
                        f"'{query}'와 연결된 공개 도서 후보입니다. 보드북 판형과 영아용 내용 "
                        "적합성은 상세 정보를 확인해 주세요."
                    ),
                    read_aloud_tip=(
                        "상세 정보를 확인한 뒤 아이가 오래 보는 그림에서 멈추고 짧게 "
                        "말해 주세요."
                    ),
                    source="public_discovery",
                    source_name=result.source,
                    source_url=source_url,
                )
            )
            if len(recommendations) >= limit:
                break
        return recommendations

    @staticmethod
    def _score(*, resource: ResourceRecord, interests: list[str]) -> tuple[int, int, int]:
        searchable = " ".join(
            [resource.title, resource.summary or "", *resource.tags]
        ).casefold()
        interest_hits = sum(
            1 for interest in interests if interest.casefold() in searchable
        )
        infant_stage = int(Stage.INFANT_0_2 in resource.stage_tags)
        metadata_depth = len(resource.tags) + int(bool(resource.summary))
        return interest_hits, infant_stage, metadata_depth

    @staticmethod
    def _reason(*, resource: ResourceRecord, interests: list[str]) -> str:
        searchable = " ".join(
            [resource.title, resource.summary or "", *resource.tags]
        ).casefold()
        matched = [
            interest for interest in interests if interest.casefold() in searchable
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
                read_aloud_tip=(
                    "그림을 가리키며 한두 단어로 말하고 아이의 반응을 기다려 주세요."
                ),
            ),
            BoardBookRecommendation(
                title="반복되는 말과 리듬이 있는 짧은 그림책",
                reason="반복되는 소리와 문장을 부모와 편안하게 주고받기 좋습니다.",
                read_aloud_tip=(
                    "문장을 외우게 하지 말고 반복 구간에서 표정과 소리를 함께 주고받아 "
                    "주세요."
                ),
            ),
            BoardBookRecommendation(
                title="일상 행동과 표정이 담긴 사진·그림책",
                reason="익숙한 사람·행동·표정을 실제 생활 경험과 연결해 보기 좋습니다.",
                read_aloud_tip=(
                    "아이에게 질문을 연속해서 하기보다 보이는 장면을 짧게 묘사해 주세요."
                ),
            ),
        ]
