from __future__ import annotations

from pathlib import Path

from growwise.api.contracts import ConversationTurnRequest
from growwise.api.conversation_routes import append_conversation_turn
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.idempotency import SQLiteIdempotencyStore
from growwise.services import ContextAnswer, ConversationSession, SQLiteConversationStore
from growwise.storage import EntityStore


class _Context:
    def __init__(self) -> None:
        self.calls = 0

    def ask(self, *, child_id: str, query: str, limit: int = 8) -> ContextAnswer:
        self.calls += 1
        return ContextAnswer(
            answer="재사용되어야 하는 저장 답변",
            source_ids=["record:1"],
            insufficient_evidence=True,
        )


def test_conversation_turn_retry_returns_persisted_exchange_without_duplicate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        embedding_features_enabled=False,
        vision_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)

    conversations = SQLiteConversationStore(settings.conversations_path)
    session = ConversationSession(child_id=str(child.id))
    conversations.save(session)
    idempotency = SQLiteIdempotencyStore(settings.idempotency_path)
    context = _Context()

    monkeypatch.setattr(
        "growwise.api.conversation_routes.get_conversation_store",
        lambda: conversations,
    )
    monkeypatch.setattr(
        "growwise.api.conversation_routes.get_idempotency_store",
        lambda: idempotency,
    )
    monkeypatch.setattr(
        "growwise.api.conversation_routes.build_child_context_service",
        lambda _store: context,
    )
    monkeypatch.setattr(
        "growwise.api.conversation_routes.get_model_provider",
        lambda: None,
    )

    request = ConversationTurnRequest(question="최근 기록을 알려줘", limit=8)
    first = append_conversation_turn(
        session.id,
        request,
        store,
        idempotency_key="conversation-retry",
    )
    # Simulate registry loss/rebuild after the response was lost. The persisted operation identity
    # in conversation_turns is independently sufficient to recover the exact exchange.
    idempotency.reset()
    second = append_conversation_turn(
        session.id,
        request,
        store,
        idempotency_key="conversation-retry",
    )

    assert context.calls == 1
    assert first == second
    assert second["answer"]["answer"] == "재사용되어야 하는 저장 답변"
    assert second["answer"]["source_ids"] == ["record:1"]
    assert second["answer"]["insufficient_evidence"] is True

    persisted = conversations.get(session.id)
    assert persisted is not None
    assert [turn.role for turn in persisted.turns] == ["user", "assistant"]
    assert {turn.operation_key for turn in persisted.turns} == {"conversation-retry"}
