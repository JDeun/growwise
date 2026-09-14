from __future__ import annotations

import sqlite3
from pathlib import Path

from growwise.services import ConversationSession


class ConversationSessionStore:
    """SQLite persistence for bounded multi-turn query sessions."""

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
                    title TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_child "
                "ON conversation_sessions(child_id, updated_at DESC)"
            )

    def save(self, session: ConversationSession) -> ConversationSession:
        payload = session.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_sessions (
                    id, child_id, title, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    session.id,
                    session.child_id,
                    session.title,
                    payload,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
        return session

    def get(self, session_id: str) -> ConversationSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM conversation_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return ConversationSession.model_validate_json(row["payload_json"])

    def list_for_child(self, child_id: str, limit: int = 50) -> list[ConversationSession]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM conversation_sessions
                WHERE child_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (child_id, limit),
            ).fetchall()
        return [ConversationSession.model_validate_json(row["payload_json"]) for row in rows]

    def delete(self, session_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversation_sessions WHERE id = ?",
                (session_id,),
            )
            return cursor.rowcount > 0
