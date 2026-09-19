from __future__ import annotations

import itertools

import pytest

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService, MaterialQualityGate


STAGE_MARKERS = {
    Stage.INFANT_0_2: "감각·움직임과 보호자와의 상호작용",
    Stage.PRESCHOOL_3_5: "유아가 놀이의 선택과 흐름을 주도",
    Stage.ELEMENTARY: "구체물과 실제 경험에서 시작",
    Stage.MIDDLE: "두 가지 이상의 근거를 비교",
    Stage.HIGH: "출처·가정·반례 또는 대안 해석",
}


@pytest.mark.parametrize("stage", list(Stage))
@pytest.mark.parametrize("kind", list(MaterialKind))
def test_every_material_family_exposes_stage_specific_instructional_contract(
    stage: Stage,
    kind: MaterialKind,
) -> None:
    child = ChildProfile(nickname="합성아이", stage=stage, interests=["자연", "독서"])
    material = MaterialGenerationService(provider=None).generate(
        child=child,
        kind=kind,
        topic="우리 동네의 변화",
    )

    assert "## 단계별 활동 기준" in material.content_markdown
    assert "## 단계별 진행 기준" in material.parent_guide_markdown
    assert STAGE_MARKERS[stage] in material.content_markdown
    assert STAGE_MARKERS[stage] in material.parent_guide_markdown


@pytest.mark.parametrize("kind", list(MaterialKind))
def test_same_topic_is_not_a_one_size_fits_all_material_across_stages(
    kind: MaterialKind,
) -> None:
    outputs = []
    guides = []
    for stage in Stage:
        child = ChildProfile(nickname="합성아이", stage=stage)
        material = MaterialGenerationService(provider=None).generate(
            child=child,
            kind=kind,
            topic="물의 변화",
        )
        outputs.append(material.content_markdown)
        guides.append(material.parent_guide_markdown)

    assert len(set(outputs)) == len(Stage)
    assert len(set(guides)) == len(Stage)


def test_preschool_writing_is_expression_first_not_conventional_writing_required() -> None:
    material = MaterialGenerationService(provider=None).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.PRESCHOOL_3_5),
        kind=MaterialKind.WRITING_PROMPT,
        topic="오늘 본 비",
    )

    assert "읽기·쓰기 수행을 강제하지 않으며" in material.content_markdown
    assert (
        "말과 그림" in material.content_markdown
        or "글쓰기가 부담되면" in material.content_markdown
    )
    assert "맞춤법" in material.content_markdown or "부모가 기록" in material.content_markdown


@pytest.mark.parametrize("stage", [Stage.MIDDLE, Stage.HIGH])
def test_secondary_science_requires_evidence_reasoning_and_limit_awareness(stage: Stage) -> None:
    material = MaterialGenerationService(provider=None).generate(
        child=ChildProfile(nickname="합성아이", stage=stage),
        kind=MaterialKind.SCIENCE_INQUIRY,
        topic="물의 온도와 증발",
    )

    combined = material.content_markdown + "\n" + material.parent_guide_markdown
    assert "근거" in combined
    assert "한계" in combined
    assert "가설" in combined or "주장" in combined
    assert "부모는 코치" in combined or "부모는 필요할 때만 검토자" in combined


def test_high_school_material_defaults_to_independent_critical_goal() -> None:
    material = MaterialGenerationService(provider=None).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.HIGH),
        kind=MaterialKind.READING_ACTIVITY,
        topic="기후 기사 비교",
    )

    assert "자료와 근거를 독립적으로 검토" in material.content_markdown
    assert "가정·대안·한계" in material.content_markdown
    assert "부모는 필요할 때만 검토자" in material.parent_guide_markdown


def test_publication_quality_gate_rejects_missing_stage_contract() -> None:
    material = MaterialGenerationService(provider=None).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY),
        kind=MaterialKind.MATH_ACTIVITY,
        topic="생활 속 비율",
    )
    broken_content = material.content_markdown.replace("## 단계별 활동 기준", "## 활동 안내", 1)

    assessment = MaterialQualityGate().assess_published(
        title=material.title,
        content_markdown=broken_content,
        parent_guide_markdown=material.parent_guide_markdown,
        source_refs=material.source_refs,
    )

    assert assessment.ready is False
    assert "content_missing:단계별 활동 기준" in assessment.issues


def test_stage_kind_matrix_is_intentionally_complete() -> None:
    cases = list(itertools.product(Stage, MaterialKind))
    assert len(cases) == 35
