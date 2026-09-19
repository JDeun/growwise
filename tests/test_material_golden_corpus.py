from __future__ import annotations

import itertools

import pytest

from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import (
    MaterialGenerationService,
    MaterialQualityGate,
    MaterialSourceEvidence,
)

_TOPICS = [
    ("계절의 변화", "관찰한 차이를 자신의 말로 설명한다."),
    ("우리 동네 지도", "공간과 위치 관계를 표현한다."),
    ("물의 상태 변화", "예측과 관찰 결과를 비교한다."),
    ("이야기 속 선택", "근거를 들어 자신의 생각을 말한다."),
]
_CASES = list(itertools.product(Stage, MaterialKind, range(len(_TOPICS))))


@pytest.mark.parametrize(
    ("stage", "kind", "topic_index"),
    _CASES,
    ids=lambda value: value.value if hasattr(value, "value") else str(value),
)
def test_140_case_commercial_material_golden_corpus(
    stage: Stage,
    kind: MaterialKind,
    topic_index: int,
) -> None:
    topic, goal = _TOPICS[topic_index]
    child = ChildProfile(
        nickname="합성아이",
        stage=stage,
        interests=["자연", "독서"],
    )
    source_ref = f"golden:{stage.value}:{kind.value}:{topic_index}"
    evidence = MaterialSourceEvidence(
        source_ref=source_ref,
        title=f"{topic} 합성 근거 자료",
        excerpt=f"{topic} 활동에서 관찰과 설명을 연결하는 방법을 다룹니다.",
        source_name="GrowWise golden corpus",
        author="Synthetic",
        license_note="Synthetic test fixture",
    )

    material = MaterialGenerationService(provider=None).generate(
        child=child,
        kind=kind,
        topic=topic,
        goal=goal,
        source_refs=[source_ref],
        source_evidence=[evidence],
    )

    assessment = MaterialQualityGate().assess_published(
        title=material.title,
        content_markdown=material.content_markdown,
        parent_guide_markdown=material.parent_guide_markdown,
        source_refs=material.source_refs,
    )
    assert assessment.ready, (
        stage.value,
        kind.value,
        topic,
        assessment.issues,
    )
    assert material.status.value == "review_pending"
    assert source_ref in material.content_markdown
    assert source_ref in material.parent_guide_markdown
    assert "## 오늘의 목표" in material.content_markdown
    assert "## 준비물" in material.content_markdown
    assert "## 돌아보기" in material.content_markdown
    assert "## 수업 개요" in material.parent_guide_markdown
    assert "## 질문·힌트 사다리" in material.parent_guide_markdown
    assert "## 사용 전 확인" in material.parent_guide_markdown

    combined = f"{material.title}\n{material.content_markdown}\n{material.parent_guide_markdown}"
    for unsafe_diagnostic in ("자폐 진단", "ADHD 진단", "정상/비정상 판정", "발달 지연으로 판정"):
        assert unsafe_diagnostic not in combined


def test_golden_corpus_size_is_intentionally_broad() -> None:
    assert len(_CASES) == 140
