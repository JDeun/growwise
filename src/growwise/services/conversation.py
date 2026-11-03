from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from uuid6 import uuid7

from growwise.domain import MaterialKind
from growwise.model import ModelProvider

from .context import ChildContextService, ContextAnswer
from .search import NaturalLanguageSearch
from .visibility import entity_visible_to_child

_ConversationContent = Annotated[str, Field(min_length=1, max_length=20_000)]
_ConversationSourceId = Annotated[str, Field(min_length=1, max_length=500)]
_MATERIAL_REQUEST_VERB = re.compile(r"(?:만들어|생성해|준비해)\s*(?:줘|주세요|줄래)")


def _requests_material(question: str) -> bool:
    previous_end = 0
    for verb in _MATERIAL_REQUEST_VERB.finditer(question):
        # Inspect disjoint prefixes: a noun must precede the verb on the same line. Keeping
        # whitespace in the verb pattern preserves requests such as '만들어\n주세요'.
        prefix = question[previous_end:verb.start()].rpartition("\n")[2]
        if any(noun in prefix for noun in ("활동", "자료", "카드")):
            return True
        previous_end = verb.end()
    return False


class MaterialAction(BaseModel):
    material_kind: MaterialKind
    topic: str = Field(min_length=1, max_length=500)
    source_refs: list[_ConversationSourceId] = Field(default_factory=list, max_length=20)
    needs_book_selection: bool = False


class MaterialActionAnswer(ContextAnswer):
    material_action: MaterialAction


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: _ConversationContent
    source_ids: list[_ConversationSourceId] = Field(default_factory=list, max_length=100)
    operation_key: str | None = Field(default=None, max_length=200)
    operation_hash: str | None = Field(default=None, min_length=64, max_length=64)
    insufficient_evidence: bool | None = None
    material_action: MaterialAction | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid7()), min_length=1, max_length=120)
    child_id: str = Field(min_length=1, max_length=120)
    title: str | None = Field(default=None, max_length=200)
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RewrittenQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class ConversationService:
    """Bounded-memory query workspace; conversation history is never treated as evidence."""

    REWRITE_SYSTEM = """Rewrite the latest GrowWise follow-up question as a standalone
retrieval query. Use only the supplied prior USER questions to resolve references such as
'그중', '그거', or omitted subjects. Never infer facts from prior assistant answers because
assistant text is not evidence. Do not broaden the child scope or add facts not present in the
user's questions. Return only the rewritten retrieval query."""

    def __init__(
        self,
        *,
        context_service: ChildContextService,
        provider: ModelProvider | None,
        max_history_turns: int = 6,
    ) -> None:
        self.context_service = context_service
        self.provider = provider
        self.max_history_turns = max_history_turns

    def ask(
        self,
        *,
        session: ConversationSession,
        question: str,
        limit: int = 8,
        operation_key: str | None = None,
        operation_hash: str | None = None,
    ) -> ContextAnswer:
        retrieval_query = self._rewrite(session=session, question=question)
        answer = self.context_service.ask(
            child_id=session.child_id,
            query=retrieval_query,
            limit=limit,
        )
        if _requests_material(question):
            source_refs: list[str] = []
            candidate_ids = [
                source_id.partition(":")[2]
                for source_id in answer.source_ids
                if source_id.partition(":")[0] in {"record", "graph", "resource"}
            ]
            candidate_ids.extend(
                str(resource["id"])
                for resource in NaturalLanguageSearch(
                    self.context_service.entity_index,
                )
                .search(
                    child_id=session.child_id,
                    query=retrieval_query,
                    entity_types=("resource",),
                    limit=8,
                )
                .results
            )
            for entity_id in candidate_ids:
                resource = self.context_service.entity_index.get_entity(
                    entity_id, entity_type="resource"
                )
                if (
                    resource
                    and resource.get("kind") == "book"
                    and entity_visible_to_child(
                        self.context_service.entity_index,
                        entity_id=entity_id,
                        child_id=session.child_id,
                        entity_type="resource",
                    )
                ):
                    source_refs.append(f"resource:{entity_id}")
            kind = next(
                (
                    kind
                    for word, kind in (
                        ("영어", MaterialKind.ENGLISH_CARD),
                        ("수학", MaterialKind.MATH_ACTIVITY),
                        ("과학", MaterialKind.SCIENCE_INQUIRY),
                        ("글쓰기", MaterialKind.WRITING_PROMPT),
                        ("탐방", MaterialKind.FIELD_TRIP),
                        ("여행", MaterialKind.FIELD_TRIP),
                        ("책", MaterialKind.READING_ACTIVITY),
                        ("독서", MaterialKind.READING_ACTIVITY),
                    )
                    if word in question
                ),
                MaterialKind.ACTIVITY_GUIDE,
            )
            action = MaterialAction(
                material_kind=kind,
                topic=retrieval_query[:500],
                source_refs=list(dict.fromkeys(source_refs))[:20],
                needs_book_selection="책" in question and not source_refs,
            )
            answer = MaterialActionAnswer(
                **answer.model_dump(),
                material_action=action,
            )
        session.turns.extend(
            [
                ConversationTurn(
                    role="user",
                    content=question,
                    operation_key=operation_key,
                    operation_hash=operation_hash,
                ),
                ConversationTurn(
                    role="assistant",
                    content=answer.answer,
                    source_ids=answer.source_ids,
                    operation_key=operation_key,
                    operation_hash=operation_hash,
                    insufficient_evidence=answer.insufficient_evidence,
                    material_action=getattr(answer, "material_action", None),
                ),
            ]
        )
        session.updated_at = datetime.now(UTC)
        return answer

    def _rewrite(self, *, session: ConversationSession, question: str) -> str:
        if NaturalLanguageSearch.explicit_plan(question, 8, date.today()).constrained:
            return question
        if self.provider is None or not session.turns:
            return question
        recent_user_turns = [turn for turn in session.turns if turn.role == "user"][
            -self.max_history_turns :
        ]
        if not recent_user_turns:
            return question
        history = "\n".join(f"user: {turn.content}" for turn in recent_user_turns)
        try:
            rewritten = self.provider.generate_structured(
                system=self.REWRITE_SYSTEM,
                user=f"Prior user questions:\n{history}\n\nLatest question: {question}",
                schema=RewrittenQuery,
            )
            return rewritten.query.strip() or question
        except Exception:
            return question
