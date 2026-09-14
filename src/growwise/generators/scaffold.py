from __future__ import annotations

from dataclasses import dataclass

from growwise.domain import MaterialKind


@dataclass(frozen=True)
class ScaffoldCheck:
    safe: bool
    violations: tuple[str, ...] = ()


class ScaffoldGuard:
    """Reject child-facing drafts that collapse support into answer-giving or rote pressure."""

    _DIRECT_ANSWER_MARKERS = (
        "정답은",
        "답은 ",
        "정답:",
        "answer is",
        "the answer is",
    )
    _ROTE_PRESSURE_MARKERS = (
        "외우세요",
        "암기하세요",
        "틀릴 때까지",
        "맞을 때까지 반복",
        "그대로 따라 쓰세요",
        "copy this exactly",
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
            marker in text for marker in self._DIRECT_ANSWER_MARKERS
        ):
            violations.append("direct_answer")
        if any(marker in text for marker in self._ROTE_PRESSURE_MARKERS):
            violations.append("rote_pressure")
        return ScaffoldCheck(safe=not violations, violations=tuple(violations))
