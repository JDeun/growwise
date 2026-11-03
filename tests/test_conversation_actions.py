import hashlib
import json
import sqlite3
from pathlib import Path

from growwise.api.conversation_routes import _existing_exchange
from growwise.domain import ChildProfile, MaterialKind, ResourceKind, ResourceRecord, Stage
from growwise.rag import HybridRagIndex
from growwise.services.context import ChildContextService
from growwise.services.conversation import (
    ConversationService,
    ConversationSession,
    ConversationTurn,
    MaterialActionAnswer,
)
from growwise.services.conversation_store import SQLiteConversationStore
from growwise.storage import EntityStore


def test_material_command_offers_a_scoped_draft_without_creating_one(tmp_path: Path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="합성 아이", stage=Stage.ELEMENTARY)
    other = ChildProfile(nickname="다른 합성 아이", stage=Stage.ELEMENTARY)
    book = ResourceRecord(kind=ResourceKind.BOOK, title="동물 그림책", child_id=child.id)
    for entity in (child, other, book):
        store.save(entity)
    service = ConversationService(
        context_service=ChildContextService(
            entity_index=store.index,
            rag_index=HybridRagIndex(tmp_path / "rag.sqlite3"),
            provider=None,
        ),
        provider=None,
    )
    session = ConversationSession(child_id=str(child.id))
    answer = service.ask(
        session=session,
        question="동물 책과 연결해 활동을 만들어줘",
        operation_key="action-request",
        operation_hash="a" * 64,
    )
    assert isinstance(answer, MaterialActionAnswer)
    assert answer.material_action.material_kind is MaterialKind.READING_ACTIVITY
    assert answer.material_action.source_refs == [f"resource:{book.id}"]
    assert session.turns[-1].material_action == answer.material_action
    conversations = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    conversations.save(session)
    restored = conversations.get(session.id)
    assert restored is not None
    assert restored.turns[-1].material_action == answer.material_action
    replay = _existing_exchange(
        session=restored, operation_key="action-request", operation_hash="a" * 64
    )
    assert replay is not None
    assert replay["answer"]["material_action"] == answer.material_action.model_dump(mode="json")
    assert store.index.list_entities(entity_type="generated_material") == []
    foreign = service.ask(
        session=ConversationSession(child_id=str(other.id)),
        question="동물 책과 연결해 활동을 만들어줘",
    )
    assert isinstance(foreign, MaterialActionAnswer)
    assert foreign.material_action.source_refs == []
    assert foreign.material_action.needs_book_selection


def test_explicit_search_filters_bypass_a_model_rewrite():
    class Provider:
        def generate_structured(self, **kwargs):
            raise AssertionError("explicit filters must not be rewritten")

    service = ConversationService(context_service=None, provider=Provider())
    session = ConversationSession(
        child_id="synthetic", turns=[ConversationTurn(role="user", content="아이 기록은?")]
    )
    query = "최근 한 달 신체 활동 기록만 찾아줘"
    assert service._rewrite(session=session, question=query) == query


def test_action_schema_upgrade_preserves_existing_turn_identity(tmp_path: Path):
    database = tmp_path / "conversations.sqlite3"
    conversations = SQLiteConversationStore(database)
    session = ConversationSession(
        child_id="synthetic", turns=[ConversationTurn(role="user", content="이전 버전의 질문")]
    )
    conversations.save(session)
    old_payload = session.turns[0].model_dump(mode="json", exclude={"material_action"})
    old_key = hashlib.sha256(
        json.dumps(
            old_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE conversation_turns SET turn_key = ?", (old_key,))
        connection.execute("ALTER TABLE conversation_turns DROP COLUMN material_action_json")
        connection.execute("PRAGMA user_version = 2")
    upgraded = SQLiteConversationStore(database)
    restored = upgraded.get(session.id)
    assert restored is not None
    restored.turns.append(ConversationTurn(role="assistant", content="새 답변"))
    upgraded.save(restored)
    assert [turn.content for turn in upgraded.get(session.id).turns] == [
        "이전 버전의 질문",
        "새 답변",
    ]
