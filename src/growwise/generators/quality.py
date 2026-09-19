from __future__ import annotations

import re
from dataclasses import dataclass

from growwise.domain import MaterialKind, Stage

_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+\S")
_PLACEHOLDER_RE = re.compile(
    r"(?i)(?:\bTODO\b|\bTBD\b|\[insert[^\]]*\]|여기에\s*(?:입력|작성)|placeholder)"
)
_CANDIDATE_INTERNAL_MARKERS = (
    "generation_guidance",
    "internal generation guidance",
    "infant_0_2",
    "preschool_3_5",
)

_REQUIRED_CONTENT_HEADINGS = (
    "오늘의 목표",
    "예상 시간",
    "준비물",
    "활동 자료",
    "막힐 때 힌트",
    "돌아보기",
    "더 해보기",
)
_REQUIRED_GUIDE_HEADINGS = (
    "수업 개요",
    "핵심 목표",
    "준비 체크리스트",
    "진행 시나리오",
    "활동 중 부모가 할 일",
    "질문·힌트 사다리",
    "관찰할 것",
    "난이도 조절",
    "안전·중단 기준",
    "활동 후 GrowWise에 남길 것",
    "근거·출처",
    "사용 전 확인",
)


@dataclass(frozen=True, slots=True)
class MaterialQualityResult:
    ready: bool
    issues: tuple[str, ...]


class MaterialQualityGate:
    """Deterministic publication-quality gate layered after safety validation.

    This is intentionally not an AI score. It checks whether the generated artifact has the
    minimum instructional structure required for a parent to use and review it reliably.
    """

    def assess_candidate_core(
        self,
        *,
        kind: MaterialKind,
        stage: Stage,
        content_markdown: str,
        parent_guide_markdown: str = "",
    ) -> MaterialQualityResult:
        del kind
        text = content_markdown.strip()
        generated_text = f"{content_markdown}\n{parent_guide_markdown}"
        issues: list[str] = []
        del stage
        substantive = re.sub(r"(?m)^#{1,6}\s+.*$", "", text).strip()
        if len(substantive) < 12:
            issues.append("candidate_core_too_short")
        if len(_HEADING_RE.findall(text)) < 1:
            issues.append("candidate_core_missing_structure")
        if _PLACEHOLDER_RE.search(generated_text):
            issues.append("candidate_core_contains_placeholder")
        folded = generated_text.casefold()
        if any(marker in folded for marker in _CANDIDATE_INTERNAL_MARKERS):
            issues.append("candidate_core_exposes_internal_metadata")
        return MaterialQualityResult(ready=not issues, issues=tuple(issues))

    def assess_published(
        self,
        *,
        title: str,
        content_markdown: str,
        parent_guide_markdown: str,
        source_refs: list[str],
    ) -> MaterialQualityResult:
        issues: list[str] = []
        if len(title.strip()) < 2:
            issues.append("title_too_short")

        for heading in _REQUIRED_CONTENT_HEADINGS:
            if f"## {heading}" not in content_markdown:
                issues.append(f"content_missing:{heading}")
        for heading in _REQUIRED_GUIDE_HEADINGS:
            if f"## {heading}" not in parent_guide_markdown:
                issues.append(f"guide_missing:{heading}")

        if source_refs and "## 참고 자료" not in content_markdown:
            issues.append("content_missing_sources")
        if len(content_markdown.strip()) < 500:
            issues.append("content_too_short")
        if len(parent_guide_markdown.strip()) < 1_000:
            issues.append("guide_too_short")

        return MaterialQualityResult(ready=not issues, issues=tuple(issues))
