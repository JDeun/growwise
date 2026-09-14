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
