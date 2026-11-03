from __future__ import annotations

import pytest

from growwise.domain import ChildProfile, MaterialKind, MaterialStatus, Stage
from growwise.generators import MaterialDraft, MaterialGenerationService
from growwise.generators.infant_safety import unsafe_infant_directions


@pytest.mark.parametrize("direction", [
    "아이가 재료를 입에 가져가거나 손으로 쥐는 등 자유롭게 탐색하도록 둡니다.",
    "나무 블록을 입에 넣어도 안전하니 충분히 탐색하게 합니다.",
    "물건을 입에 넣지 않게 하고 다른 재료는 입에 넣도록 합니다.",
    "작은 구슬을 쥐여 주며 소리 나는 모습을 살펴봅니다.",
    "작은 구슬을 쥐여 주고 동전은 사용하지 않습니다.",
    "긴 끈을 준비하여 아이에게 건네줍니다.",
    "Put the toy in the baby's mouth.",
    "Let the infant suck on the block.",
])
def test_positive_infant_hazard_directions_are_rejected(direction):
    assert unsafe_infant_directions(direction)


@pytest.mark.parametrize("direction", [
    "물건을 입에 넣지 않게 지켜봅니다.",
    "재료를 입에 가져가지 않도록 합니다.",
    "물건을 입에 넣지 마세요.",
    "물건을 입에 넣도록 유도하지 않습니다.",
    "물건을 입에 넣게 두지 않습니다.",
    "입에 넣으려 하면 치워 주세요.",
    "입에 가져가려 하면 물건을 치우고 목소리 놀이로 바꿉니다.",
    "작은 물건과 긴 끈은 사용하지 않습니다.",
    "배터리가 없는 큰 일체형 장난감을 보호자가 확인합니다.",
    "작은 부품·동전·자석은 아이 손이 닿지 않는 곳에 보관합니다.",
    "아이가 입으로 소리를 내는 모습을 관찰합니다.",
    "Do not put the object in the baby's mouth.",
])
def test_protective_or_neutral_infant_prose_is_not_mistaken_for_a_hazard(direction):
    assert not unsafe_infant_directions(direction)


class SafeProvider:
    def generate_structured(self, **kwargs):
        return MaterialDraft(
            title="목소리와 손동작 주고받기",
            content_markdown=(
                "## 작은 소리로 인사하기\n"
                "1. 보호자가 평평한 바닥 매트에서 편안한 자세의 아이 곁에 앉아 "
                "부드럽게 인사하고 반응을 기다립니다.\n"
                "2. 아이의 눈길이나 옹알이에 같은 리듬의 짧은 목소리로 응답합니다.\n"
                "아이는 어떤 소리에 시선을 머무르나요?\n"
                "## 손동작 관찰하기\n"
                "1. 보호자가 손을 천천히 움직이고 아이가 바라보는 방향을 기다립니다.\n"
                "어떤 움직임에서 표정이 달라졌나요? 피로하면 바로 멈춥니다."
            ),
            parent_guide_markdown=(
                "따라 하는 반응을 요구하지 않습니다. 물건을 입에 넣지 않게 합니다."
            ),
            source_refs=[],
        )


def _generate(provider):
    return MaterialGenerationService(provider=provider).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.INFANT_0_2, age_months=9),
        kind=MaterialKind.ACTIVITY_GUIDE, topic="소리와 움직임 살펴보기",
    )


def test_safe_infant_prose_passes_with_concrete_visible_and_parent_safety_guidance():
    material = _generate(SafeProvider())
    assert material.generator_mode == "llm_enhanced"
    assert material.status is MaterialStatus.REVIEW_PENDING
    assert "## 활동 전 안전" in material.content_markdown
    assert "평평한 바닥·매트" in material.content_markdown
    assert "연령 표시·크기·청결·파손" in material.content_markdown
    assert "물건을 입에 넣도록 유도하지 않습니다" in material.parent_guide_markdown


def test_unsafe_mouthing_in_model_notes_cannot_reach_publication():
    class UnsafeProvider(SafeProvider):
        def generate_structured(self, **kwargs):
            draft = super().generate_structured(**kwargs)
            draft.parent_guide_markdown = (
                "아이가 나무 블록을 입에 가져가거나 자유롭게 탐색하도록 둡니다."
            )
            return draft

    material = _generate(UnsafeProvider())
    assert material.generator_mode == "template_safety_fallback"
    assert "자유롭게 탐색하도록 둡니다" not in material.parent_guide_markdown
    assert "## 활동 전 안전" in material.content_markdown


@pytest.mark.parametrize("kind", list(MaterialKind))
def test_every_deterministic_infant_kind_has_concrete_safety_preparation(kind):
    material = MaterialGenerationService().generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.INFANT_0_2, age_months=9),
        kind=kind, topic="부모와 함께 탐색",
    )
    assert "작은 물건·분리 부품·끈은 치우고" in material.content_markdown
    assert "물건 없는 소리·표정 놀이" in material.parent_guide_markdown
