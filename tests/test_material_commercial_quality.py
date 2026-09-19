from __future__ import annotations

import pytest

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import (
    MaterialGenerationService,
    MaterialQualityGate,
    MaterialSourceEvidence,
)

KINDS = list(MaterialKind)
STAGES = list(Stage)


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("kind", KINDS)
def test_deterministic_materials_meet_publication_contract(stage: Stage, kind: MaterialKind) -> None:
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
        return schema(
            title="너무 짧은 초안",
            content_markdown="## 활동\n해 봅니다.",
            parent_guide_markdown="",
            source_refs=[],
        )


class _UsefulProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema):
        return schema(
            title="물의 변화 과학 탐구",
            content_markdown=(
                "## 예측하기\n"
                "얼음과 물을 보고 어떤 변화가 생길지 먼저 예상하고 그 이유를 말해 봅니다.\n\n"
                "## 관찰하기\n"
                "같은 양의 얼음을 두 조건에 두고 한 번에 한 조건만 다르게 하여 변화를 관찰합니다.\n"
                "관찰한 모양과 시간을 기록하고 처음 예상과 어떤 점이 같거나 달랐는지 설명합니다.\n\n"
                "## 새 질문 만들기\n"
                "다음에는 무엇을 바꾸어 보면 좋을지 아이가 한 가지 질문을 고릅니다."
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
    assert "## 오늘의 목표" in material.content_markdown
    assert "## 사용 전 확인" in material.parent_guide_markdown


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


def test_publication_gate_rejects_placeholder_artifacts() -> None:
    result = MaterialQualityGate().assess_published(
        title="자료",
        content_markdown=(
            "## 오늘의 목표\nTODO\n"
            "## 예상 시간\n10분\n"
            "## 준비물\n- 종이\n"
            "## 활동 자료\n내용\n"
            "## 막힐 때 힌트\n힌트\n"
            "## 돌아보기\n회고\n"
            "## 더 해보기\n확장"
        ),
        parent_guide_markdown=(
            "## 수업 개요\n내용\n"
            "## 핵심 목표\n내용\n"
            "## 준비 체크리스트\n내용\n"
            "## 진행 시나리오\n내용\n"
            "## 활동 중 부모가 할 일\n내용\n"
            "## 질문·힌트 사다리\n내용\n"
            "## 관찰할 것\n내용\n"
            "## 난이도 조절\n내용\n"
            "## 안전·중단 기준\n내용\n"
            "## 활동 후 GrowWise에 남길 것\n내용\n"
            "## 근거·출처\n내용\n"
            "## 사용 전 확인\n내용"
        ),
        source_refs=[],
    )

    assert result.ready is False
    assert "published_contains_placeholder" in result.issues
