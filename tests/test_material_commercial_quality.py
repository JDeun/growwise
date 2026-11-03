from __future__ import annotations

import pytest

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import (
    MaterialDraft,
    MaterialGenerationService,
    MaterialQualityGate,
    MaterialSourceEvidence,
)

KINDS = list(MaterialKind)
STAGES = list(Stage)


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("kind", KINDS)
def test_deterministic_materials_meet_publication_contract(
    stage: Stage,
    kind: MaterialKind,
) -> None:
    child = ChildProfile(name="아이", nickname="아이", stage=stage, interests=["자연"])

    material = MaterialGenerationService(provider=None).generate(
        child=child,
        kind=kind,
        topic="계절의 변화",
        goal="관찰한 차이를 자신의 방식으로 설명한다.",
    )

    quality = MaterialQualityGate().assess_published(
        title=material.title,
        content_markdown=material.content_markdown,
        parent_guide_markdown=material.parent_guide_markdown,
        source_refs=material.source_refs,
    )
    assert quality.ready, quality.issues
    assert "## 오늘의 목표" in material.content_markdown
    assert "## 예상 시간" in material.content_markdown
    assert "## 준비물" in material.content_markdown
    assert "## 막힐 때 힌트" in material.content_markdown
    assert "## 돌아보기" in material.content_markdown
    assert "## 더 해보기" in material.content_markdown
    assert "## 수업 개요" in material.parent_guide_markdown
    assert "## 질문·힌트 사다리" in material.parent_guide_markdown
    assert "## 난이도 조절" in material.parent_guide_markdown
    assert "## 안전·중단 기준" in material.parent_guide_markdown
    assert "## 사용 전 확인" in material.parent_guide_markdown
    assert stage.value not in material.content_markdown
    assert stage.value not in material.parent_guide_markdown


class _WeakProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema):
        return MaterialDraft(
            title="너무 짧은 초안",
            content_markdown="## 활동\n해 봅니다.",
            parent_guide_markdown="",
            source_refs=[],
        )


class _UsefulProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema):
        return MaterialDraft(
            title="물의 변화 과학 탐구",
            content_markdown=(
                "## 예측하기\n"
                "1. 얼음과 물을 보고 어떤 변화가 생길지 먼저 예상하고 그 이유를 말해 봅니다.\n\n"
                "## 관찰하기\n"
                "2. 같은 양의 얼음을 두 조건에 두고 "
                "한 번에 한 조건만 다르게 하여 변화를 관찰합니다.\n"
                "관찰한 모양과 시간을 기록하고 처음 예상과 "
                "어떤 점이 같거나 달랐는지 설명합니다.\n\n"
                "## 새 질문 만들기\n"
                "다음에는 무엇을 바꾸어 보면 좋을까요? 아이가 한 가지 질문을 고릅니다."
            ),
            parent_guide_markdown=(
                "## 진행 메모\n"
                "예측이 맞았는지 평가하기보다 어떤 근거로 예상했는지 먼저 듣고, "
                "관찰 결과가 다르면 생각이 어떻게 바뀌었는지 질문합니다."
            ),
            source_refs=["resource:science-1"],
        )


def test_weak_model_output_is_replaced_by_publication_quality_fallback() -> None:
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)

    material = MaterialGenerationService(provider=_WeakProvider()).generate(
        child=child,
        kind=MaterialKind.SCIENCE_INQUIRY,
        topic="물의 변화",
    )

    assert material.generator_mode == "template_quality_fallback"


def test_english_card_rejects_korean_only_instructions_even_with_valid_structure() -> None:
    class KoreanOnlyProvider(_UsefulProvider):
        pass

    material = MaterialGenerationService(provider=KoreanOnlyProvider()).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY),
        kind=MaterialKind.ENGLISH_CARD, topic="아침 인사",
    )
    assert material.generator_mode == "template_quality_fallback"
    # Fallback still supplies usable English; it cannot make the rejected model count as accepted.
    assert "Hello!" in material.content_markdown


def test_english_card_accepts_real_target_expression_and_modeled_turns() -> None:
    class EnglishProvider(_UsefulProvider):
        def generate_structured(self, **kwargs):
            draft = super().generate_structured(**kwargs)
            draft.content_markdown += (
                "\n역할 대화: 보호자 'Good morning!' → 아이 'Good morning!'\n"
                "아이가 먼저 인사할 상대나 동물을 선택하고 역할을 바꾸어 봅니다.\n"
            )
            return draft

    material = MaterialGenerationService(provider=EnglishProvider()).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY),
        kind=MaterialKind.ENGLISH_CARD, topic="아침 인사",
    )
    assert material.generator_mode == "llm_enhanced"
    assert "Good morning!" in material.content_markdown


@pytest.mark.parametrize("stage", list(Stage))
def test_core_english_cards_provide_actual_stage_appropriate_expression_examples(stage) -> None:
    material = MaterialGenerationService().generate(
        child=ChildProfile(nickname="합성아이", stage=stage),
        kind=MaterialKind.ENGLISH_CARD, topic="함께하는 대화",
    )
    assert material.generator_mode == "template"
    assert "## 바로 써볼 기본 표현과 짧은 대화" in material.content_markdown
    assert "기본 예시" in material.content_markdown
    if stage is Stage.INFANT_0_2:
        assert "Hello!" in material.content_markdown
        assert "발음하기를 요구하지 않습니다" in material.content_markdown
    elif stage is Stage.HIGH:
        assert "What evidence supports that?" in material.content_markdown
    assert "## 오늘의 목표" in material.content_markdown
    assert "## 사용 전 확인" in material.parent_guide_markdown


@pytest.mark.parametrize("core, issue", [
    (
        "## 활동\n1. 얼음 두 조각을 같은 접시에 놓고 모양과 크기를 자세히 관찰합니다.\n"
        "2. 두 장소에서 같은 시간 동안 변화를 살펴보고 처음 예상과 비교해 봅니다.\n"
        "어떤 점이 같고 달랐나요? 관찰한 근거를 골라 자기 생각이 바뀐 이유도 설명해 봅니다.",
        "candidate_core_missing_structure",
    ),
    (
        "## 예측\n얼음과 물의 모양을 자세히 관찰하고 "
        "어느 쪽이 먼저 변할지 이유와 함께 예상합니다.\n"
        "## 설명\n두 장소에서 같은 시간 동안 변화를 살펴봅니다. "
        "처음 예상과 어떤 점이 같고 달랐나요?",
        "candidate_core_missing_executable_steps",
    ),
    (
        "## 관찰\n1. 얼음 두 조각을 같은 접시에 놓고 모양과 크기를 자세히 관찰합니다.\n"
        "2. 두 장소에서 같은 시간 동안 변화를 살펴보고 처음 예상과 비교해 봅니다.\n"
        "## 정리\n눈에 띄는 차이를 말하고 그 차이를 뒷받침하는 관찰 내용을 하나 골라 설명합니다.",
        "candidate_core_missing_question",
    ),
])
def test_incomplete_cores_fail_quality_review_before_parent_use(core: str, issue: str) -> None:
    result = MaterialQualityGate().assess_candidate_core(
        kind=MaterialKind.SCIENCE_INQUIRY, stage=Stage.ELEMENTARY, content_markdown=core,
    )
    assert issue in result.issues

    class IncompleteProvider:
        def generate_structured(self, *, schema, **kwargs):
            return MaterialDraft(title="미완성 탐구", content_markdown=core, source_refs=[])

    material = MaterialGenerationService(provider=IncompleteProvider()).generate(
        child=ChildProfile(nickname="테스트아이", stage=Stage.ELEMENTARY),
        kind=MaterialKind.SCIENCE_INQUIRY, topic="얼음 관찰",
    )
    assert material.generator_mode == "template_quality_fallback"
    assert material.status.value == "review_pending"


def test_useful_model_core_is_wrapped_in_stable_commercial_shell() -> None:
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)

    material = MaterialGenerationService(provider=_UsefulProvider()).generate(
        child=child,
        kind=MaterialKind.SCIENCE_INQUIRY,
        topic="물의 변화",
        goal="상태 변화를 관찰하고 근거를 말한다.",
        source_refs=["resource:science-1"],
        source_evidence=[
            MaterialSourceEvidence(
                source_ref="resource:science-1",
                title="물의 상태 변화 관찰 자료",
                excerpt="얼음이 녹는 동안 상태와 모양 변화를 관찰한다.",
            )
        ],
    )

    assert material.generator_mode == "llm_enhanced"
    assert "### 예측하기" in material.content_markdown
    assert "### 관찰하기" in material.content_markdown
    assert "## 맞춤 진행 메모" in material.parent_guide_markdown
    assert "어떤 근거로 예상했는지" in material.parent_guide_markdown
    assert "물의 상태 변화 관찰 자료 (`resource:science-1`)" in material.content_markdown
    assert "물의 상태 변화 관찰 자료 (`resource:science-1`)" in material.parent_guide_markdown


def test_candidate_gate_rejects_model_placeholder_artifacts() -> None:
    result = MaterialQualityGate().assess_candidate_core(
        kind=MaterialKind.READING_ACTIVITY,
        stage=Stage.ELEMENTARY,
        content_markdown=(
            "## 시작\nTODO: 질문을 채운다.\n\n"
            "## 활동\n아이와 내용을 살펴보고 관찰한 점을 설명합니다."
        ),
        parent_guide_markdown="## 진행 메모\n부모가 함께 관찰합니다.",
    )

    assert result.ready is False
    assert "candidate_core_contains_placeholder" in result.issues


def test_publication_gate_does_not_treat_source_title_as_model_placeholder() -> None:
    service = MaterialGenerationService(provider=None)
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)

    material = service.generate(
        child=child,
        kind=MaterialKind.READING_ACTIVITY,
        topic="프로젝트 계획",
        source_refs=["resource:todo"],
        source_evidence=[
            MaterialSourceEvidence(
                source_ref="resource:todo",
                title="TODO 프로젝트 관리 입문",
                excerpt="프로젝트의 할 일을 구조화하는 방법을 설명한다.",
            )
        ],
    )

    assert material.generator_mode == "template"
    assert "TODO 프로젝트 관리 입문" in material.content_markdown
