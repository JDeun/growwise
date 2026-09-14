import pytest

from growwise.domain import (
    ChildProfile,
    GeneratedMaterial,
    MaterialKind,
    MaterialStatus,
    Stage,
)
from growwise.generators import MaterialGenerationService
from growwise.review import InvalidMaterialTransition, MaterialReviewService


class FailingProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        raise RuntimeError("provider unavailable")

    def generate_structured(self, *, system: str, user: str, schema):
        raise RuntimeError("provider unavailable")


def test_material_generation_works_without_llm() -> None:
    child = ChildProfile(
        nickname="아이",
        stage=Stage.INFANT_0_2,
        age_months=9,
        interests=["동물"],
    )
    material = MaterialGenerationService(provider=None).generate(
        child=child,
        kind=MaterialKind.READING_ACTIVITY,
        topic="고양이 그림책",
        source_refs=["resource:book-1"],
    )

    assert material.status is MaterialStatus.REVIEW_PENDING
    assert material.generator_mode == "template"
    assert "고양이 그림책" in material.content_markdown
    assert material.source_refs == ["resource:book-1"]


def test_material_generation_falls_back_when_provider_fails() -> None:
    child = ChildProfile(nickname="아이", stage=Stage.PRESCHOOL_3_5)
    material = MaterialGenerationService(provider=FailingProvider()).generate(
        child=child,
        kind=MaterialKind.ACTIVITY_GUIDE,
        topic="색깔 찾기",
    )

    assert material.status is MaterialStatus.REVIEW_PENDING
    assert material.generator_mode == "template_fallback"
    assert material.content_markdown


def test_parent_review_gate_enforces_state_machine() -> None:
    child = ChildProfile(nickname="아이", stage=Stage.ELEMENTARY)
    material = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.READING_ACTIVITY,
        title="읽기 활동",
        content_markdown="# 읽기 활동",
        status=MaterialStatus.REVIEW_PENDING,
    )
    review = MaterialReviewService()

    assert review.can_export(material) is False
    review.transition(material, MaterialStatus.APPROVED, note="확인함")
    assert material.status is MaterialStatus.APPROVED
    assert review.can_export(material) is True

    with pytest.raises(InvalidMaterialTransition):
        review.transition(material, MaterialStatus.REJECTED)
