from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .conversation import ConversationSession


class SQLiteConversationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    id TEXT PRIMARY KEY,
                    child_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_child_updated "
                "ON conversation_sessions(child_id, updated_at DESC)"
            )

    def save(self, session: ConversationSession) -> None:
        payload = session.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_sessions (
                    id, child_id, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    child_id = excluded.child_id,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    session.id,
                    session.child_id,
                    json.dumps(payload, ensure_ascii=False),
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )

    def get(self, session_id: str) -> ConversationSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM conversation_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return ConversationSession.model_validate(json.loads(row["payload_json"]))

    def list_for_child(self, child_id: str, *, limit: int = 50) -> list[ConversationSession]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM conversation_sessions
                WHERE child_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (child_id, limit),
            ).fetchall()
        return [ConversationSession.model_validate(json.loads(row["payload_json"])) for row in rows]

    def delete(self, session_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversation_sessions WHERE id = ?",
                (session_id,),
            )
        return cursor.rowcount > 0
