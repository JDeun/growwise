from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from uuid6 import uuid7

from growwise.model import ModelProvider

from .context import ChildContextService, ContextAnswer

_ConversationContent = Annotated[str, Field(min_length=1, max_length=20_000)]
_ConversationSourceId = Annotated[str, Field(min_length=1, max_length=500)]


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: _ConversationContent
    source_ids: list[_ConversationSourceId] = Field(default_factory=list, max_length=100)
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

    def ask(self, *, session: ConversationSession, question: str, limit: int = 8) -> ContextAnswer:
        retrieval_query = self._rewrite(session=session, question=question)
        answer = self.context_service.ask(
            child_id=session.child_id,
            query=retrieval_query,
            limit=limit,
        )
        session.turns.extend(
            [
                ConversationTurn(role="user", content=question),
                ConversationTurn(
                    role="assistant",
                    content=answer.answer,
                    source_ids=answer.source_ids,
                ),
            ]
        )
        session.updated_at = datetime.now(UTC)
        return answer

    def _rewrite(self, *, session: ConversationSession, question: str) -> str:
        if self.provider is None or not session.turns:
            return question
        recent_user_turns = [
            turn
            for turn in session.turns
            if turn.role == "user"
        ][-self.max_history_turns :]
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
