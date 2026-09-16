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
_INDEPENDENT_CONTEXT_KINDS = {
    LearningRecordKind.READING_REFLECTION,
    LearningRecordKind.DIARY,
    LearningRecordKind.INSTITUTION,
    LearningRecordKind.SELF_STUDY,
    LearningRecordKind.ASSIGNMENT,
    LearningRecordKind.OTHER,
}
_RECORD_KIND_LABELS = {
    LearningRecordKind.READING_REFLECTION: "독서·독서감상",
    LearningRecordKind.DIARY: "일기",
    LearningRecordKind.INSTITUTION: "학교·학원·교육기관",
    LearningRecordKind.SELF_STUDY: "자율학습",
    LearningRecordKind.ASSIGNMENT: "과제·프로젝트",
    LearningRecordKind.OTHER: "기타 학습",
}


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
    learner_work: str | None
    process: str | None
    child_question: str | None
    interest: str | None
    difficulty_note: str | None
    next_activity: str | None


@dataclass(frozen=True)
class IndependentLearningItem:
    log_id: UUID
    kind: LearningRecordKind
    title: str | None
    subject: str | None
    institution: str | None
    summary: str | None
    process: str | None
    has_learner_work: bool
    interest: str | None
    difficulty_note: str | None
    next_activity: str | None


@dataclass(frozen=True)
class MaterialFeedbackSnapshot:
    items: tuple[MaterialFeedbackItem, ...] = ()
    learning_items: tuple[IndependentLearningItem, ...] = ()

    @property
    def has_feedback(self) -> bool:
        return bool(self.items or self.learning_items)

    def generation_goal(self, requested_goal: str | None) -> str | None:
        """Add generalized continuity signals without exposing raw parent/learner text.

        The generated goal may be sent to a model, but raw parent and learner text is not.
        """
        if not self.has_feedback:
            return requested_goal

        signals: list[str] = []
        if any(item.interest for item in self.items):
            signals.append("최근 활동에서 흥미가 기록된 요소를 선택적으로 이어간다")
        if any(item.learner_work for item in self.items):
            signals.append(
                "최근 아이 산출물이 있으면 정답을 복제하지 않고 사고 과정을 확장하는 선택 질문을 둔다"
            )
        if any(item.process for item in self.items):
            signals.append(
                "최근 활동 과정이 기록돼 있으면 같은 풀이를 강요하지 않고 다른 방법을 설명할 기회를 둔다"
            )
        if any(item.child_question for item in self.items):
            signals.append("최근 아이 질문을 이어갈 수 있는 열린 질문을 둔다")
        if any(item.difficulty_note for item in self.items):
            signals.append("최근 어려움이 기록된 부분은 더 작은 단계와 힌트로 시작한다")
        if any(item.next_activity for item in self.items):
            signals.append("이전 기록의 다음 활동 연결점을 부모가 선택해 이어갈 수 있게 한다")

        kinds = {item.kind for item in self.learning_items}
        if LearningRecordKind.READING_REFLECTION in kinds:
            signals.append("최근 독서·감상 경험과 연결할 수 있는 선택 질문을 둔다")
        if kinds & {LearningRecordKind.INSTITUTION, LearningRecordKind.ASSIGNMENT}:
            signals.append("최근 학교·기관·과제 경험과 연결하되 이미 배웠다고 단정하지 않는다")
        if LearningRecordKind.SELF_STUDY in kinds:
            signals.append("최근 자율학습 흐름을 부모가 선택적으로 이어갈 수 있게 한다")
        if LearningRecordKind.DIARY in kinds:
            signals.append(
                "최근 일상 기록과 연결 가능성을 열어두되 개인 글 내용을 직접 재사용하지 않는다"
            )
        if any(item.has_learner_work for item in self.learning_items):
            signals.append(
                "별도 학습의 아이 산출물이 있으면 원문을 복제하지 않고 표현·풀이 과정을 확장한다"
            )
        if any(item.process for item in self.learning_items):
            signals.append(
                "별도 학습 과정이 기록돼 있으면 한 가지 방식으로 단정하지 않고 다른 접근을 열어둔다"
            )
        if any(item.interest for item in self.learning_items):
            signals.append("별도 학습 기록에 흥미가 남아 있으면 관련 선택지를 제공한다")
        if any(item.difficulty_note for item in self.learning_items):
            signals.append("별도 학습에서 어려움이 기록된 경우 더 작은 단계와 힌트를 제공한다")
        if any(item.next_activity for item in self.learning_items):
            signals.append("별도 학습 기록의 다음 연결점을 부모가 선택할 수 있게 한다")

        signals = list(dict.fromkeys(signals))
        if not signals:
            signals.append(
                "최근 실제 활동과 별도 학습 기록을 참고해 부모가 난이도와 진행 속도를 "
                "조절할 수 있게 한다"
            )

        default_goal = "주제를 함께 탐색하고 아이의 반응과 사고 과정을 관찰한다."
        base = (requested_goal or default_goal).strip()
        return f"{base} 개인화 원칙: {'; '.join(signals)}."

    def with_parent_guide(self, guide: str) -> str:
        """Replace the bounded local continuity block in the parent-only guide."""
        without_existing = _FEEDBACK_BLOCK_RE.sub("\n", guide).rstrip()
        if not self.has_feedback:
            return without_existing

        sections = [_FEEDBACK_BLOCK_START]
        if self.items:
            sections.extend(
                [
                    "## 최근 실제 활동에서 이어갈 점",
                    (
                        "아래 내용은 이전에 부모가 저장한 실제 활동 결과입니다. 진단·평가가 아니라 "
                        "이번 활동의 난이도와 연결점을 조절하는 참고로만 사용합니다."
                    ),
                ]
            )
            for item in self.items:
                title = item.title or "이전 활동"
                sections.append(f"### {title}")
                if item.observation:
                    sections.append(f"- 부모 관찰: {item.observation}")
                if item.learner_work:
                    sections.append(f"- 아이 답변·산출물: {item.learner_work}")
                if item.process:
                    sections.append(f"- 활동 과정: {item.process}")
                if item.child_question:
                    sections.append(f"- 아이 질문·반응: {item.child_question}")
                if item.interest:
                    sections.append(f"- 흥미를 보인 점: {item.interest}")
                if item.difficulty_note:
                    sections.append(f"- 어려워한 점: {item.difficulty_note}")
                if item.next_activity:
                    sections.append(f"- 다음에 이어볼 것: {item.next_activity}")

        if self.learning_items:
            sections.extend(
                [
                    "## 최근 별도 학습 기록에서 이어갈 점",
                    (
                        "아래 내용은 독서·일기·학교·학원·자율학습 등에서 부모가 저장한 요약입니다. "
                        "아이의 원문은 이 교안에 복제하지 않으며, 연결 아이디어로만 사용합니다."
                    ),
                ]
            )
            for learning_item in self.learning_items:
                label = _RECORD_KIND_LABELS.get(learning_item.kind, "별도 학습")
                title = learning_item.title or label
                sections.append(f"### {label} · {title}")
                if learning_item.subject:
                    sections.append(f"- 과목·영역: {learning_item.subject}")
                if learning_item.institution:
                    sections.append(f"- 기관: {learning_item.institution}")
                if learning_item.summary:
                    sections.append(f"- 부모 요약: {learning_item.summary}")
                if learning_item.process:
                    sections.append(f"- 학습 과정: {learning_item.process}")
                if learning_item.has_learner_work:
                    sections.append("- 아이 산출물: 저장됨 · 원문은 이 교안에 복제하지 않음")
                if learning_item.interest:
                    sections.append(f"- 흥미를 보인 점: {learning_item.interest}")
                if learning_item.difficulty_note:
                    sections.append(f"- 어려워한 점: {learning_item.difficulty_note}")
                if learning_item.next_activity:
                    sections.append(f"- 다음에 이어볼 것: {learning_item.next_activity}")

        sections.extend(
            [
                (
                    "> 이 연속성 정보는 아이에게 그대로 제시하거나 능력 판단에 사용하지 않고, "
                    "부모가 활동을 조절하는 데만 사용합니다."
                ),
                _FEEDBACK_BLOCK_END,
            ]
        )
        return f"{without_existing}\n\n" + "\n".join(sections) + "\n"


class MaterialFeedbackService:
    """Build bounded continuity snapshots from outcomes and independent learning records."""

    def __init__(self, index: SQLiteProjection) -> None:
        self.index = index

    def snapshot(
        self,
        *,
        child_id: str,
        limit: int = 5,
        learning_limit: int = 5,
    ) -> MaterialFeedbackSnapshot:
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
            learner_work = _inline(log.learner_work, limit=1200)
            process = _inline(log.process, limit=900)
            child_question = _inline(log.child_question, limit=500)
            interest = _inline(log.interest, limit=500)
            difficulty_note = _inline(log.difficulty_note, limit=700)
            next_activity = _inline(log.next_activity, limit=700)
            title = _inline(log.title, limit=300)
            if not any(
                (
                    observation,
                    learner_work,
                    process,
                    child_question,
                    interest,
                    difficulty_note,
                    next_activity,
                )
            ):
                continue
            items.append(
                MaterialFeedbackItem(
                    log_id=log.id,
                    title=title,
                    observation=observation,
                    learner_work=learner_work,
                    process=process,
                    child_question=child_question,
                    interest=interest,
                    difficulty_note=difficulty_note,
                    next_activity=next_activity,
                )
            )

        independent_logs = [log for log in logs if log.record_kind in _INDEPENDENT_CONTEXT_KINDS]
        independent_logs.sort(key=lambda log: log.occurred_at or log.created_at, reverse=True)
        learning_items: list[IndependentLearningItem] = []
        for log in independent_logs[: max(0, min(learning_limit, 10))]:
            title = _inline(log.title, limit=300)
            subject = _inline(log.subject, limit=200)
            institution = _inline(log.institution, limit=300)
            summary = _inline(log.parent_observation, limit=900)
            process = _inline(log.process, limit=900)
            has_learner_work = bool(log.learner_work and log.learner_work.strip())
            interest = _inline(log.interest, limit=500)
            difficulty_note = _inline(log.difficulty_note, limit=700)
            next_activity = _inline(log.next_activity, limit=700)
            if not any(
                (
                    title,
                    subject,
                    institution,
                    summary,
                    process,
                    has_learner_work,
                    interest,
                    difficulty_note,
                    next_activity,
                )
            ):
                continue
            learning_items.append(
                IndependentLearningItem(
                    log_id=log.id,
                    kind=log.record_kind,
                    title=title,
                    subject=subject,
                    institution=institution,
                    summary=summary,
                    process=process,
                    has_learner_work=has_learner_work,
                    interest=interest,
                    difficulty_note=difficulty_note,
                    next_activity=next_activity,
                )
            )

        return MaterialFeedbackSnapshot(
            items=tuple(items),
            learning_items=tuple(learning_items),
        )