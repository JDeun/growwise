from __future__ import annotations

from growwise.curriculum import curriculum_targets_for
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


def test_school_mapping_is_distinct_by_material_kind_and_stage() -> None:
    math = curriculum_targets_for(Stage.ELEMENTARY, MaterialKind.MATH_ACTIVITY)
    science = curriculum_targets_for(Stage.ELEMENTARY, MaterialKind.SCIENCE_INQUIRY)
    field_trip = curriculum_targets_for(Stage.MIDDLE, MaterialKind.FIELD_TRIP)

    assert math[0].domain == "수학"
    assert science[0].domain == "과학"
    assert field_trip[0].domain == "사회·통합"
    assert math[0].mapping_id == "gw:kr:2022:elementary:math-problem-solving"
    assert field_trip[0].mapping_id == "gw:kr:2022:middle:social-place-inquiry"
    school_targets = [*math, *science, *field_trip]
    assert all(target.source_ref == "교육부고시 제2022-33호" for target in school_targets)


def test_generation_embeds_and_persists_curriculum_alignment() -> None:
    material = MaterialGenerationService().generate(
        child=child(Stage.PRESCHOOL_3_5),
        kind=MaterialKind.MATH_ACTIVITY,
        topic="간식 나누기",
    )

    assert [target.domain for target in material.curriculum_targets] == ["자연탐구"]
    assert "교육과정 연결: 자연탐구" in material.content_markdown


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
