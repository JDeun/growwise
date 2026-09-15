from __future__ import annotations

import pytest

from growwise.domain import ChildProfile, MaterialKind, MaterialStatus, Stage
from growwise.generators import MaterialGenerationService, ScaffoldGuard
from growwise.generators.templates import select_body, variant_index, variants_for

_STAGES = list(Stage)
_TOPICS = ["고양이", "물의 순환", "우리 동네 시장", "숫자 놀이", "봄꽃", "재활용"]


def _service() -> MaterialGenerationService:
    return MaterialGenerationService(provider=None)


def _child(stage: Stage) -> ChildProfile:
    age = 9 if stage is Stage.INFANT_0_2 else 96
    return ChildProfile(nickname="아이", stage=stage, age_months=age)


@pytest.mark.parametrize("kind", list(MaterialKind))
@pytest.mark.parametrize("stage", _STAGES)
def test_every_kind_and_stage_yields_nonempty_scaffolded_content(
    kind: MaterialKind, stage: Stage
) -> None:
    material = _service().generate(child=_child(stage), kind=kind, topic="고양이")

    assert material.status is MaterialStatus.REVIEW_PENDING
    assert material.generator_mode == "template"
    assert material.content_markdown.startswith("# ")
    assert "목표" in material.content_markdown
    assert "고양이" in material.content_markdown
    assert material.content_markdown.strip()


@pytest.mark.parametrize("kind", list(MaterialKind))
@pytest.mark.parametrize("stage", _STAGES)
def test_each_kind_stage_offers_multiple_variants(kind: MaterialKind, stage: Stage) -> None:
    variants = variants_for(kind, stage)

    assert len(variants) >= 2
    assert all("{topic}" in variant for variant in variants)


@pytest.mark.parametrize("kind", list(MaterialKind))
@pytest.mark.parametrize("stage", _STAGES)
def test_all_variants_pass_scaffold_guard(kind: MaterialKind, stage: Stage) -> None:
    guard = ScaffoldGuard()
    title = MaterialGenerationService._title(kind, "고양이")

    for topic in _TOPICS:
        for raw in variants_for(kind, stage):
            content = raw.replace("{topic}", topic)
            check = guard.check(kind=kind, title=title, content=content)
            assert check.safe, (kind, stage, topic, check.violations)


@pytest.mark.parametrize("kind", list(MaterialKind))
@pytest.mark.parametrize("stage", _STAGES)
def test_selection_is_deterministic(kind: MaterialKind, stage: Stage) -> None:
    for topic in _TOPICS:
        first = select_body(kind=kind, topic=topic, stage=stage)
        second = select_body(kind=kind, topic=topic, stage=stage)
        assert first == second


def test_generate_is_reproducible_for_same_inputs() -> None:
    service = _service()
    child = _child(Stage.ELEMENTARY)

    first = service.generate(child=child, kind=MaterialKind.SCIENCE_INQUIRY, topic="자석")
    second = service.generate(child=child, kind=MaterialKind.SCIENCE_INQUIRY, topic="자석")

    assert first.content_markdown == second.content_markdown


@pytest.mark.parametrize("kind", list(MaterialKind))
def test_variety_across_topics(kind: MaterialKind) -> None:
    stage = Stage.ELEMENTARY
    bodies = {select_body(kind=kind, topic=topic, stage=stage) for topic in _TOPICS}

    # With multiple variants and a stable topic hash, different topics reach different bodies.
    assert len(bodies) >= 2


@pytest.mark.parametrize("kind", list(MaterialKind))
def test_infant_pool_differs_from_older_stages(kind: MaterialKind) -> None:
    infant = variants_for(kind, Stage.INFANT_0_2)
    older = variants_for(kind, Stage.ELEMENTARY)

    assert infant != older
    assert set(infant).isdisjoint(older)

    body = select_body(kind=kind, topic="고양이", stage=Stage.INFANT_0_2)
    assert body not in {raw.replace("{topic}", "고양이") for raw in older}


def test_variant_index_is_stable_and_bounded() -> None:
    assert variant_index("고양이", Stage.ELEMENTARY, 3) == variant_index(
        "고양이", Stage.ELEMENTARY, 3
    )
    for count in (1, 2, 3, 5):
        assert 0 <= variant_index("주제", Stage.MIDDLE, count) < count
