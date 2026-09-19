from __future__ import annotations

from datetime import date

from growwise.curriculum import curriculum_targets_for, curriculum_targets_for_child
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, Stage
from growwise.generators import MaterialEditService, MaterialGenerationService


def child(stage: Stage) -> ChildProfile:
    return ChildProfile(name="테스트", nickname="테스트", stage=stage, age_months=48)


def test_early_years_mapping_uses_current_frameworks_without_fake_standard_codes() -> None:
    infant = curriculum_targets_for(Stage.INFANT_0_2, MaterialKind.READING_ACTIVITY)
    preschool = curriculum_targets_for(Stage.PRESCHOOL_3_5, MaterialKind.SCIENCE_INQUIRY)

    assert [target.domain for target in infant] == ["의사소통", "예술경험"]
    assert all(target.source_ref == "교육부고시 제2024-23호" for target in infant)
    assert preschool[0].domain == "자연탐구"
    assert preschool[0].source_ref.startswith("교육부고시 제2019-189호")
    assert all(target.standard_codes == [] for target in [*infant, *preschool])
    assert all(target.mapping_id.startswith("gw:kr:") for target in [*infant, *preschool])


def test_school_mapping_is_distinct_by_material_kind_and_effective_grade() -> None:
    reference = date(2026, 9, 19)
    elementary = ChildProfile(name="초등", stage=Stage.ELEMENTARY, grade=5)
    middle = ChildProfile(name="중등", stage=Stage.MIDDLE, grade=8)
    math = curriculum_targets_for_child(
        elementary,
        MaterialKind.MATH_ACTIVITY,
        on_date=reference,
    )
    science = curriculum_targets_for_child(
        elementary,
        MaterialKind.SCIENCE_INQUIRY,
        on_date=reference,
    )
    field_trip = curriculum_targets_for_child(
        middle,
        MaterialKind.FIELD_TRIP,
        on_date=reference,
    )

    assert math[0].domain == "수학"
    assert science[0].domain == "과학"
    assert field_trip[0].domain == "사회·통합"
    assert "2022-rev-2024-3" in math[0].mapping_id
    assert "2022-rev-2024-3" in field_trip[0].mapping_id
    school_targets = [*math, *science, *field_trip]
    assert all(
        target.source_ref == "국가교육위원회고시 제2024-3호"
        for target in school_targets
    )
    assert {target.grade for target in math} == {5}
    assert {target.grade for target in field_trip} == {8}


def test_stage_only_middle_mapping_marks_transition_uncertainty() -> None:
    targets = curriculum_targets_for(
        Stage.MIDDLE,
        MaterialKind.READING_ACTIVITY,
        on_date=date(2026, 9, 19),
    )

    assert targets[0].revision == "transition-unresolved"
    assert targets[0].resolution_precision == "stage_transition"
    assert targets[0].transition_note


def test_generation_embeds_and_persists_curriculum_alignment() -> None:
    material = MaterialGenerationService().generate(
        child=child(Stage.PRESCHOOL_3_5),
        kind=MaterialKind.MATH_ACTIVITY,
        topic="간식 나누기",
    )

    assert [target.domain for target in material.curriculum_targets] == ["자연탐구"]
    assert "교육과정 연결: 자연탐구" in material.content_markdown
    assert "적용 교육과정:" in material.content_markdown
    assert "기준 고시:" in material.content_markdown


def test_parent_edit_preserves_curriculum_targets() -> None:
    original = MaterialGenerationService().generate(
        child=child(Stage.ELEMENTARY),
        kind=MaterialKind.READING_ACTIVITY,
        topic="그림책",
    )

    edited = MaterialEditService().create_version(
        material=original,
        title="부모 편집본",
        content_markdown="# 부모 편집본\n\n내용",
    )

    assert edited.curriculum_targets == original.curriculum_targets
    assert edited.curriculum_targets is not original.curriculum_targets


def test_legacy_material_without_curriculum_field_remains_loadable() -> None:
    current = MaterialGenerationService().generate(
        child=child(Stage.ELEMENTARY),
        kind=MaterialKind.WRITING_PROMPT,
        topic="내가 만든 동물",
    )
    payload = current.model_dump(mode="json")
    payload.pop("curriculum_targets")

    legacy = GeneratedMaterial.model_validate(payload)

    assert legacy.curriculum_targets == []
