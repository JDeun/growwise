from __future__ import annotations

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService


def test_material_always_includes_parent_guide_without_llm() -> None:
    child = ChildProfile(
        name="아이",
        nickname="아이",
        stage=Stage.PRESCHOOL_3_5,
        interests=["공룡"],
    )

    material = MaterialGenerationService(provider=None).generate(
        child=child,
        kind=MaterialKind.SCIENCE_INQUIRY,
        topic="공룡 발자국 비교",
        goal="크기와 모양의 차이를 관찰한다.",
    )

    assert material.generator_mode == "template"
    assert "공룡 발자국 비교" in material.content_markdown
    assert "# 부모용 교안" in material.parent_guide_markdown
    assert "## 활동 중 부모가 할 일" in material.parent_guide_markdown
    assert "## 관찰할 것" in material.parent_guide_markdown
    assert "## 활동 후 GrowWise에 남길 것" in material.parent_guide_markdown
    assert "진단" not in material.parent_guide_markdown
