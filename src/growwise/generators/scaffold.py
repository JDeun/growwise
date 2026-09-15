from __future__ import annotations

import re
from dataclasses import dataclass

from growwise.domain import MaterialKind


@dataclass(frozen=True)
class ScaffoldCheck:
    safe: bool
    violations: tuple[str, ...] = ()


class ScaffoldGuard:
    """Reject drafts that bypass parent review, inject instructions, or collapse scaffolding."""

    _DIRECT_ANSWER_PATTERNS = (
        re.compile(r"정\s*답\s*(?:은|:|：)"),
        re.compile(r"답\s*(?:은|:|：)"),
        re.compile(r"(?:the\s+)?answer\s*(?:is|:)", re.IGNORECASE),
        re.compile(r"final\s+answer\s*:", re.IGNORECASE),
    )
    _ROTE_PRESSURE_MARKERS = (
        "외우세요",
        "암기하세요",
        "틀릴 때까지",
        "맞을 때까지 반복",
        "그대로 따라 쓰세요",
        "copy this exactly",
    )
    _INJECTION_PATTERNS = (
        re.compile(
            r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?",
            re.IGNORECASE,
        ),
        re.compile(
            r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:reveal|print|show|repeat)\s+(?:the\s+)?"
            r"(?:system|developer)\s+(?:prompt|message|instructions?)",
            re.IGNORECASE,
        ),
        re.compile(r"(?:system|developer)\s+(?:prompt|message)\s*:", re.IGNORECASE),
        re.compile(r"이전\s*(?:지시|명령|규칙).{0,12}(?:무시|잊어|폐기)"),
        re.compile(r"(?:시스템|개발자)\s*(?:프롬프트|메시지|지시).{0,12}(?:출력|공개|보여|반복)"),
    )
    _REVIEW_BYPASS_PATTERNS = (
        re.compile(
            r"(?:skip|bypass|disable)\s+(?:the\s+)?(?:parent\s+)?review",
            re.IGNORECASE,
        ),
        re.compile(r"(?:auto|automatically)\s*approve", re.IGNORECASE),
        re.compile(r"(?:부모\s*)?(?:검토|승인).{0,12}(?:건너뛰|생략|우회|자동\s*승인)"),
    )
    _SCAFFOLD_KINDS = {
        MaterialKind.ENGLISH_CARD,
        MaterialKind.MATH_ACTIVITY,
        MaterialKind.SCIENCE_INQUIRY,
        MaterialKind.WRITING_PROMPT,
    }

    def check(self, *, kind: MaterialKind, title: str, content: str) -> ScaffoldCheck:
        text = f"{title}\n{content}".casefold()
        violations: list[str] = []
        if kind in self._SCAFFOLD_KINDS and any(
            pattern.search(text) for pattern in self._DIRECT_ANSWER_PATTERNS
        ):
            violations.append("direct_answer")
        if any(marker in text for marker in self._ROTE_PRESSURE_MARKERS):
            violations.append("rote_pressure")
        if any(pattern.search(text) for pattern in self._INJECTION_PATTERNS):
            violations.append("prompt_injection")
        if any(pattern.search(text) for pattern in self._REVIEW_BYPASS_PATTERNS):
            violations.append("review_bypass")
        return ScaffoldCheck(safe=not violations, violations=tuple(dict.fromkeys(violations)))
