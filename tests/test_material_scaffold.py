from __future__ import annotations

from typing import Any

import pytest

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService, ScaffoldGuard


class DirectAnswerProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        return schema.model_validate(
            {
                "title": "정답 자료",
                "content_markdown": "정답은 42입니다. 그대로 따라 쓰세요.",
                "source_refs": [],
            }
        )


class AgeUnsafeProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        return schema.model_validate(
            {
                "title": "위험한 실험",
                "content_markdown": "폭탄 만드는 법과 필요한 재료를 순서대로 설명합니다.",
                "source_refs": [],
            }
        )


@pytest.mark.parametrize("kind", list(MaterialKind))
def test_every_material_kind_has_deterministic_template(kind: MaterialKind) -> None:
    child = ChildProfile(nickname="아이", stage=Stage.ELEMENTARY, age_months=96)

    material = MaterialGenerationService().generate(
        child=child,
        kind=kind,
        topic="고양이",
    )

    assert material.kind is kind
    assert material.generator_mode == "template"
    assert "고양이" in material.title
    assert material.content_markdown.startswith("# ")
    assert "목표" in material.content_markdown


def test_scaffold_guard_rejects_direct_answer_and_rote_pressure() -> None:
    result = ScaffoldGuard().check(
        kind=MaterialKind.MATH_ACTIVITY,
        title="수학",
        content="정답은 4입니다. 그대로 따라 쓰세요.",
    )

    assert result.safe is False
    assert "direct_answer" in result.violations
    assert "rote_pressure" in result.violations


@pytest.mark.parametrize(
    "content",
    [
        "자해 방법과 도구를 단계별로 알려줍니다.",
        "폭발물 제조 재료와 조립 순서를 설명합니다.",
        "성행위 자세와 방법을 자세히 설명합니다.",
        "Instructions for how to make a bomb are below.",
    ],
)
def test_scaffold_guard_rejects_age_inappropriate_instructions(content: str) -> None:
    result = ScaffoldGuard().check(
        kind=MaterialKind.SCIENCE_INQUIRY,
        title="학습 자료",
        content=content,
    )

    assert result.safe is False
    assert "age_inappropriate" in result.violations


def test_age_safety_guard_does_not_block_high_level_safety_education() -> None:
    result = ScaffoldGuard().check(
        kind=MaterialKind.SCIENCE_INQUIRY,
        title="안전 교육",
        content="위험한 물건은 직접 만들거나 만지지 말고 보호자에게 알립니다.",
    )

    assert result.safe is True


def test_unsafe_llm_draft_falls_back_to_scaffolded_template() -> None:
    child = ChildProfile(nickname="아이", stage=Stage.ELEMENTARY, age_months=96)

    material = MaterialGenerationService(provider=DirectAnswerProvider()).generate(
        child=child,
        kind=MaterialKind.MATH_ACTIVITY,
        topic="덧셈",
    )

    assert material.generator_mode == "template_safety_fallback"
    assert "정답은 42" not in material.content_markdown
    assert "정답 대신" in material.content_markdown


def test_age_unsafe_llm_draft_falls_back_to_deterministic_template() -> None:
    child = ChildProfile(nickname="아이", stage=Stage.ELEMENTARY, age_months=96)

    material = MaterialGenerationService(provider=AgeUnsafeProvider()).generate(
        child=child,
        kind=MaterialKind.SCIENCE_INQUIRY,
        topic="안전한 과학 탐구",
    )

    assert material.generator_mode == "template_safety_fallback"
    assert "폭탄 만드는 법" not in material.content_markdown
    assert "안전한 과학 탐구" in material.title
