import sqlite3

import pytest

from growwise.maintenance import DATA_MAINTENANCE, StaleDataGeneration
from growwise.services import ConversationSession, ConversationTurn, SQLiteConversationStore


def test_conversation_store_round_trip_and_child_scope(tmp_path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    first = ConversationSession(child_id="child-a", title="동물 관심")
    first.turns.append(ConversationTurn(role="user", content="최근 동물 관심 기록은?"))
    store.save(first)

    second = ConversationSession(child_id="child-b", title="다른 아이")
    store.save(second)

    loaded = store.get(first.id)
    assert loaded is not None
    assert loaded.child_id == "child-a"
    assert loaded.title == "동물 관심"
    assert loaded.turns[0].content == "최근 동물 관심 기록은?"

    child_a_sessions = store.list_for_child("child-a")
    assert [session.id for session in child_a_sessions] == [first.id]


def test_conversation_store_updates_and_deletes(tmp_path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    session = ConversationSession(child_id="child-a")
    store.save(session)
    session.turns.append(ConversationTurn(role="user", content="후속 질문"))
    store.save(session)

    loaded = store.get(session.id)
    assert loaded is not None
    assert len(loaded.turns) == 1
    assert store.delete(session.id) is True
    assert store.get(session.id) is None


def test_pre_restore_conversation_store_is_generation_fenced(tmp_path) -> None:
    path = tmp_path / "conversations.sqlite3"
    old_store = SQLiteConversationStore(path)
    session = ConversationSession(child_id="child-a", title="복원 전")
    old_store.save(session)

    with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
        pass

    with pytest.raises(StaleDataGeneration):
        old_store.get(session.id)
    with pytest.raises(StaleDataGeneration):
        old_store.save(session)

    fresh_store = SQLiteConversationStore(path)
    assert fresh_store.get(session.id) is not None
    fresh_session = ConversationSession(child_id="child-a", title="복원 후")
    fresh_store.save(fresh_session)
    assert fresh_store.get(fresh_session.id) is not None



def test_delete_for_child_uses_fk_cascade_without_session_id_expansion(tmp_path) -> None:
    class LowVariableConversationStore(SQLiteConversationStore):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 128)
            return connection

    path = tmp_path / "conversations.sqlite3"
    store = LowVariableConversationStore(path)
    child_id = "child-bulk"
    sessions = [
        (
            f"session-{index}",
            child_id,
            "{}",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        )
        for index in range(600)
    ]
    turns = [
        (
            session_id,
            f"turn-{index}",
            "user",
            "질문",
            "[]",
            "2026-01-01T00:00:00+00:00",
        )
        for index, (session_id, *_rest) in enumerate(sessions)
    ]
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executemany(
            """
            INSERT INTO conversation_sessions (
                id, child_id, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            sessions,
        )
        connection.executemany(
            """
            INSERT INTO conversation_turns (
                session_id, turn_key, role, content, source_ids_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            turns,
        )

    assert store.delete_for_child(child_id) == 600
    with sqlite3.connect(path) as connection:
        session_count = connection.execute(
            "SELECT COUNT(*) FROM conversation_sessions WHERE child_id = ?",
            (child_id,),
        ).fetchone()
        turn_count = connection.execute("SELECT COUNT(*) FROM conversation_turns").fetchone()
    assert session_count is not None and session_count[0] == 0
    assert turn_count is not None and turn_count[0] == 0
