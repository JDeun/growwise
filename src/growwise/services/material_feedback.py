from __future__ import annotations

import html
import re
from dataclasses import dataclass
from uuid import UUID

from growwise.domain import LearningLog, LearningRecordKind
from growwise.storage.sqlite import SQLiteProjection

_FEEDBACK_BLOCK_START = "<!-- growwise-material-feedback:start -->"
_FEEDBACK_BLOCK_END = "<!-- growwise-material-feedback:end -->"
_FEEDBACK_BLOCK_RE = re.compile(
    rf"\n*{re.escape(_FEEDBACK_BLOCK_START)}.*?{re.escape(_FEEDBACK_BLOCK_END)}\n*",
    re.DOTALL,
)


def _inline(value: str | None, *, limit: int) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return None
    # Keep parent-authored text visibly literal inside Markdown instead of allowing it to create
    # headings, links, emphasis, or HTML. This is presentation hardening, not semantic filtering.
    escaped = html.escape(normalized[:limit], quote=True)
    for marker in ("\\", "`", "*", "_", "[", "]"):
        escaped = escaped.replace(marker, f"\\{marker}")
    return escaped


@dataclass(frozen=True)
class MaterialFeedbackItem:
    log_id: UUID
    title: str | None
    observation: str | None
    child_question: str | None
    interest: str | None
    difficulty_note: str | None
    next_activity: str | None


@dataclass(frozen=True)
class MaterialFeedbackSnapshot:
    items: tuple[MaterialFeedbackItem, ...] = ()

    @property
    def has_feedback(self) -> bool:
        return bool(self.items)

    def generation_goal(self, requested_goal: str | None) -> str | None:
        """Add only generalized scaffolding signals to model-visible/child-visible goal text.

        Raw observations, questions, difficulties, and next-activity notes stay out of this string.
        They are rendered only in the local parent guide below.
        """
        if not self.items:
            return requested_goal

        signals: list[str] = []
        if any(item.interest for item in self.items):
            signals.append("최근 활동에서 흥미가 기록된 요소를 선택적으로 이어간다")
        if any(item.child_question for item in self.items):
            signals.append("최근 아이 질문을 이어갈 수 있는 열린 질문을 둔다")
        if any(item.difficulty_note for item in self.items):
            signals.append("최근 어려움이 기록된 부분은 더 작은 단계와 힌트로 시작한다")
        if any(item.next_activity for item in self.items):
            signals.append("이전 기록의 다음 활동 연결점을 부모가 선택해 이어갈 수 있게 한다")
        if not signals:
            signals.append("최근 실제 활동 관찰을 참고해 부모가 난이도와 진행 속도를 조절할 수 있게 한다")

        base = (requested_goal or "주제를 함께 탐색하고 아이의 반응과 사고 과정을 관찰한다.").strip()
        return f"{base} 개인화 원칙: {'; '.join(signals)}."

    def with_parent_guide(self, guide: str) -> str:
        """Replace the generated feedback block with the bounded local feedback snapshot."""
        without_existing = _FEEDBACK_BLOCK_RE.sub("\n", guide).rstrip()
        if not self.items:
            return without_existing

        sections = [
            _FEEDBACK_BLOCK_START,
            "## 최근 실제 활동에서 이어갈 점",
            "아래 내용은 이전에 부모가 저장한 실제 활동 결과입니다. 진단·평가가 아니라 이번 활동의 난이도와 연결점을 조절하는 참고로만 사용합니다.",
        ]
        for item in self.items:
            title = item.title or "이전 활동"
            sections.append(f"### {title}")
            if item.observation:
                sections.append(f"- 부모 관찰: {item.observation}")
            if item.child_question:
                sections.append(f"- 아이 질문·반응: {item.child_question}")
            if item.interest:
                sections.append(f"- 흥미를 보인 점: {item.interest}")
            if item.difficulty_note:
                sections.append(f"- 어려워한 점: {item.difficulty_note}")
            if item.next_activity:
                sections.append(f"- 다음에 이어볼 것: {item.next_activity}")
        sections.extend(
            [
                "> 이 피드백은 아이에게 그대로 제시하거나 능력 판단에 사용하지 않고, 부모가 활동을 조절하는 데만 사용합니다.",
                _FEEDBACK_BLOCK_END,
            ]
        )
        return f"{without_existing}\n\n" + "\n".join(sections) + "\n"


class MaterialFeedbackService:
    """Build a bounded snapshot from recent printed/material-use outcomes for one child."""

    def __init__(self, index: SQLiteProjection) -> None:
        self.index = index

    def snapshot(self, *, child_id: str, limit: int = 5) -> MaterialFeedbackSnapshot:
        payloads = self.index.list_entities(
            entity_type="learning_log",
            child_id=child_id,
            limit=100,
        )
        logs = [LearningLog.model_validate(payload) for payload in payloads]
        material_logs = [
            log for log in logs if log.record_kind is LearningRecordKind.MATERIAL_USE
        ]
        material_logs.sort(key=lambda log: log.created_at, reverse=True)

        items: list[MaterialFeedbackItem] = []
        for log in material_logs[: max(0, min(limit, 10))]:
            observation = _inline(log.parent_observation, limit=900)
            child_question = _inline(log.child_question, limit=500)
            interest = _inline(log.interest, limit=500)
            difficulty_note = _inline(log.difficulty_note, limit=700)
            next_activity = _inline(log.next_activity, limit=700)
            title = _inline(log.title, limit=300)
            if not any((observation, child_question, interest, difficulty_note, next_activity)):
                continue
            items.append(
                MaterialFeedbackItem(
                    log_id=log.id,
                    title=title,
                    observation=observation,
                    child_question=child_question,
                    interest=interest,
                    difficulty_note=difficulty_note,
                    next_activity=next_activity,
                )
            )
        return MaterialFeedbackSnapshot(items=tuple(items))
