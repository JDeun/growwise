from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field
from uuid6 import uuid7

from growwise.model import ModelProvider

from .context import ChildContextService, ContextAnswer


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    source_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid7()))
    child_id: str
    title: str | None = None
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RewrittenQuery(BaseModel):
    query: str


class ConversationService:
    """Bounded-memory query workspace; conversation history is never treated as evidence."""

    REWRITE_SYSTEM = """Rewrite the latest GrowWise follow-up question as a standalone
retrieval query. Use conversation history only to resolve references such as '그중',
'그거', or omitted subjects. Do not add facts that were not present in the user's turns.
Return only the rewritten query."""

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
        recent = session.turns[-self.max_history_turns :]
        history = "\n".join(f"{turn.role}: {turn.content}" for turn in recent)
        try:
            rewritten = self.provider.generate_structured(
                system=self.REWRITE_SYSTEM,
                user=f"History:\n{history}\n\nLatest question: {question}",
                schema=RewrittenQuery,
            )
            return rewritten.query.strip() or question
        except Exception:
            return question
