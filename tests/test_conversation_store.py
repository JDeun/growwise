import sqlite3

import pytest
from pydantic import ValidationError

from growwise.maintenance import DATA_MAINTENANCE, StaleDataGeneration
from growwise.services import ConversationSession, ConversationTurn, SQLiteConversationStore
from growwise.services.conversation_store import (
    CURRENT_CONVERSATION_SCHEMA_VERSION,
    UnsupportedConversationSchema,
)


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



def test_delete_for_child_uses_fk_cascade_without_variable_expansion(tmp_path) -> None:
    class LowVariableConversationStore(SQLiteConversationStore):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 512)
            return connection

    store = LowVariableConversationStore(tmp_path / "conversations.sqlite3")
    with store._connection() as connection:
        sessions = [
            (
                f"session-{index}",
                "target-child",
                "{}",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            )
            for index in range(600)
        ]
        connection.executemany(
            """
            INSERT INTO conversation_sessions (id, child_id, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            sessions,
        )
        connection.executemany(
            """
            INSERT INTO conversation_turns (
                session_id, turn_key, role, content, source_ids_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"session-{index}",
                    f"turn-{index}",
                    "user",
                    "질문",
                    "[]",
                    "2026-01-01T00:00:00+00:00",
                )
                for index in range(600)
            ],
        )

    assert store.delete_for_child("target-child") == 600
    with store._connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversation_sessions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM conversation_turns").fetchone()[0] == 0



def test_conversation_persistence_models_reject_oversized_payloads() -> None:
    with pytest.raises(ValidationError):
        ConversationTurn(role="user", content="x" * 20_001)
    with pytest.raises(ValidationError):
        ConversationTurn(
            role="assistant",
            content="답변",
            source_ids=["source"] * 101,
        )
    with pytest.raises(ValidationError):
        ConversationTurn(
            role="assistant",
            content="답변",
            source_ids=["x" * 501],
        )
    with pytest.raises(ValidationError):
        ConversationSession(child_id="child", title="x" * 201)
    with pytest.raises(ValidationError):
        ConversationSession(child_id="x" * 121)



def test_conversation_store_stamps_current_schema_version(tmp_path) -> None:
    path = tmp_path / "conversations.sqlite3"
    SQLiteConversationStore(path)

    with sqlite3.connect(path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert version == CURRENT_CONVERSATION_SCHEMA_VERSION


def test_conversation_store_migrates_unversioned_legacy_turns(tmp_path) -> None:
    path = tmp_path / "legacy.sqlite3"
    legacy = ConversationSession(child_id="legacy-child", title="legacy")
    legacy.turns.append(ConversationTurn(role="user", content="legacy question"))
    payload = legacy.model_dump_json()

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE conversation_sessions (
                id TEXT PRIMARY KEY,
                child_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO conversation_sessions (
                id, child_id, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                legacy.id,
                legacy.child_id,
                payload,
                legacy.created_at.isoformat(),
                legacy.updated_at.isoformat(),
            ),
        )
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0

    migrated = SQLiteConversationStore(path)
    loaded = migrated.get(legacy.id)
    assert loaded is not None
    assert [turn.content for turn in loaded.turns] == ["legacy question"]

    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == CURRENT_CONVERSATION_SCHEMA_VERSION
        )
        assert connection.execute("SELECT COUNT(*) FROM conversation_turns").fetchone()[0] == 1


def test_conversation_store_validates_v1_snapshot_without_mutating_it(tmp_path) -> None:
    path = tmp_path / "v1-snapshot.sqlite3"
    session = ConversationSession(child_id="legacy-child", title="v1 snapshot")
    session.turns.append(ConversationTurn(role="user", content="legacy question"))

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE conversation_sessions (
                id TEXT PRIMARY KEY,
                child_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE conversation_turns (
                session_id TEXT NOT NULL,
                turn_key TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                source_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (session_id, turn_key)
            )
            """
        )
        payload = session.model_dump(mode="json")
        payload["turns"] = []
        connection.execute(
            """
            INSERT INTO conversation_sessions (
                id, child_id, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.child_id,
                __import__("json").dumps(payload, ensure_ascii=False, default=str),
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
            ),
        )
        turn = session.turns[0]
        connection.execute(
            """
            INSERT INTO conversation_turns (
                session_id, turn_key, role, content, source_ids_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                "legacy-turn",
                turn.role,
                turn.content,
                "[]",
                turn.created_at.isoformat(),
            ),
        )
        connection.execute("PRAGMA user_version = 1")

    assert SQLiteConversationStore.validate_snapshot(path) == 1
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(conversation_turns)").fetchall()
        }
        assert "operation_key" not in columns


def test_conversation_store_rejects_future_schema_without_mutation(tmp_path) -> None:
    path = tmp_path / "future.sqlite3"
    future_version = CURRENT_CONVERSATION_SCHEMA_VERSION + 1
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {future_version}")

    with pytest.raises(UnsupportedConversationSchema, match="newer than this GrowWise build"):
        SQLiteConversationStore(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == future_version
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        assert tables == []


def test_conversation_snapshot_rejects_future_schema(tmp_path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    SQLiteConversationStore(path)
    future_version = CURRENT_CONVERSATION_SCHEMA_VERSION + 1
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {future_version}")

    with pytest.raises(UnsupportedConversationSchema, match="newer than this GrowWise build"):
        SQLiteConversationStore.validate_snapshot(path)



def test_conversation_store_fails_closed_on_corrupt_legacy_row(tmp_path) -> None:
    path = tmp_path / "corrupt-legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE conversation_sessions (
                id TEXT PRIMARY KEY,
                child_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO conversation_sessions (
                id, child_id, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "broken-session",
                "child-a",
                "{not-json",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )

    with pytest.raises(ValueError, match="cannot be migrated"):
        SQLiteConversationStore(path)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
