from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from growwise.maintenance import DATA_MAINTENANCE

from .conversation import ConversationSession, ConversationTurn


class SQLiteConversationStore:
    """Durable conversation storage with append-only normalized turns.

    The legacy table stored the whole conversation as one JSON blob. GrowWise keeps that column for
    backward compatibility, but turns are now persisted independently. Concurrent callers that load
    the same session and append different exchanges therefore merge instead of last-writer-wins
    overwriting one another.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _turn_key(turn: ConversationTurn) -> str:
        canonical = json.dumps(
            turn.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    session_id TEXT NOT NULL,
                    turn_key TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn_key),
                    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_turn_order "
                "ON conversation_turns(session_id, created_at)"
            )
            self._migrate_legacy_turns(connection)

    def _migrate_legacy_turns(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            "SELECT id, payload_json FROM conversation_sessions"
        ).fetchall()
        for row in rows:
            try:
                session = ConversationSession.model_validate(json.loads(row["payload_json"]))
            except Exception:
                continue
            self._insert_turns(connection, session.id, session.turns)

    def _insert_turns(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        turns: list[ConversationTurn],
    ) -> None:
        for turn in turns:
            connection.execute(
                """
                INSERT OR IGNORE INTO conversation_turns (
                    session_id, turn_key, role, content, source_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    self._turn_key(turn),
                    turn.role,
                    turn.content,
                    json.dumps(turn.source_ids, ensure_ascii=False),
                    turn.created_at.isoformat(),
                ),
            )

    @staticmethod
    def _session_payload_without_turns(session: ConversationSession) -> str:
        payload = session.model_dump(mode="json")
        payload["turns"] = []
        return json.dumps(payload, ensure_ascii=False)

    def save(self, session: ConversationSession) -> None:
        with DATA_MAINTENANCE.mutation():
            self._save_uncoordinated(session)

    def _save_uncoordinated(self, session: ConversationSession) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO conversation_sessions (
                    id, child_id, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    child_id = conversation_sessions.child_id,
                    payload_json = CASE
                        WHEN excluded.updated_at >= conversation_sessions.updated_at
                        THEN excluded.payload_json
                        ELSE conversation_sessions.payload_json
                    END,
                    updated_at = CASE
                        WHEN excluded.updated_at > conversation_sessions.updated_at
                        THEN excluded.updated_at
                        ELSE conversation_sessions.updated_at
                    END
                """,
                (
                    session.id,
                    session.child_id,
                    self._session_payload_without_turns(session),
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
            self._insert_turns(connection, session.id, session.turns)
            connection.commit()

    @staticmethod
    def _turns_for(
        connection: sqlite3.Connection,
        session_id: str,
    ) -> list[ConversationTurn]:
        rows = connection.execute(
            """
            SELECT role, content, source_ids_json, created_at
            FROM conversation_turns
            WHERE session_id = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (session_id,),
        ).fetchall()
        return [
            ConversationTurn(
                role=row["role"],
                content=row["content"],
                source_ids=json.loads(row["source_ids_json"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    @classmethod
    def _session_from_row(
        cls,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> ConversationSession:
        session = ConversationSession.model_validate(json.loads(row["payload_json"]))
        session.turns = cls._turns_for(connection, session.id)
        # SQL ordering is authoritative even for migrated legacy payloads.
        session.updated_at = datetime.fromisoformat(row["updated_at"])
        return session

    def get(self, session_id: str) -> ConversationSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json, updated_at FROM conversation_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return self._session_from_row(connection, row)

    def list_for_child(self, child_id: str, *, limit: int = 50) -> list[ConversationSession]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json, updated_at FROM conversation_sessions
                WHERE child_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (child_id, limit),
            ).fetchall()
            return [self._session_from_row(connection, row) for row in rows]

    def delete(self, session_id: str) -> bool:
        with DATA_MAINTENANCE.mutation():
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM conversation_turns WHERE session_id = ?",
                    (session_id,),
                )
                cursor = connection.execute(
                    "DELETE FROM conversation_sessions WHERE id = ?",
                    (session_id,),
                )
                connection.commit()
            return cursor.rowcount > 0

    def delete_for_child(self, child_id: str) -> int:
        """Delete all sessions and turns for one child and return the session count."""
        with DATA_MAINTENANCE.mutation():
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    "SELECT id FROM conversation_sessions WHERE child_id = ?",
                    (child_id,),
                ).fetchall()
                session_ids = [row["id"] for row in rows]
                if session_ids:
                    placeholders = ",".join("?" for _ in session_ids)
                    connection.execute(
                        f"DELETE FROM conversation_turns WHERE session_id IN ({placeholders})",
                        session_ids,
                    )
                connection.execute(
                    "DELETE FROM conversation_sessions WHERE child_id = ?",
                    (child_id,),
                )
                connection.commit()
            return len(session_ids)

    def reset_for_restore(self) -> int:
        """Clear snapshot-scoped conversation state while caller owns maintenance."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT COUNT(*) FROM conversation_sessions").fetchone()
            count = int(row[0]) if row is not None else 0
            connection.execute("DELETE FROM conversation_turns")
            connection.execute("DELETE FROM conversation_sessions")
            connection.commit()
        return count
