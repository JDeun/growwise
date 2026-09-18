from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .conversation import ConversationSession, ConversationTurn


class SQLiteConversationStore:
    """Durable conversation storage with append-only normalized turns.

    The legacy table stored the whole conversation as one JSON blob. GrowWise keeps that column for
    backward compatibility, but turns are now persisted independently. Concurrent callers that load
    the same session and append different exchanges therefore merge instead of last-writer-wins
    overwriting one another.
    """

    def __init__(self, path: Path) -> None:
        from growwise.maintenance import DATA_MAINTENANCE

        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data_generation = DATA_MAINTENANCE.generation
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        # sqlite3.Connection.__exit__ commits/rolls back but does not close the handle. That is
        # observable on Windows, where an open handle prevents backup snapshot unlink/replace.
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

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
        with self._connection() as connection:
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
        from growwise.maintenance import DATA_MAINTENANCE

        with DATA_MAINTENANCE.mutation(
            expected_generation=self._data_generation
        ), self._connect() as connection:
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
        from growwise.maintenance import DATA_MAINTENANCE

        with DATA_MAINTENANCE.mutation(
            expected_generation=self._data_generation
        ), self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json, updated_at FROM conversation_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return self._session_from_row(connection, row)

    def list_for_child(self, child_id: str, *, limit: int = 50) -> list[ConversationSession]:
        from growwise.maintenance import DATA_MAINTENANCE

        with DATA_MAINTENANCE.mutation(
            expected_generation=self._data_generation
        ), self._connect() as connection:
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
        from growwise.maintenance import DATA_MAINTENANCE

        with DATA_MAINTENANCE.mutation(
            expected_generation=self._data_generation
        ), self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM conversation_turns WHERE session_id = ?", (session_id,))
            cursor = connection.execute(
                "DELETE FROM conversation_sessions WHERE id = ?",
                (session_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def delete_for_child(self, child_id: str) -> int:
        """Delete all sessions and turns for one child and return the session count."""
        from growwise.maintenance import DATA_MAINTENANCE

        with DATA_MAINTENANCE.mutation(
            expected_generation=self._data_generation
        ), self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT id FROM conversation_sessions WHERE child_id = ?", (child_id,)
            ).fetchall()
            session_ids = [row["id"] for row in rows]
            if session_ids:
                placeholders = ",".join("?" for _ in session_ids)
                connection.execute(
                    f"DELETE FROM conversation_turns WHERE session_id IN ({placeholders})",
                    session_ids,
                )
            connection.execute("DELETE FROM conversation_sessions WHERE child_id = ?", (child_id,))
            connection.commit()
        return len(session_ids)

    def snapshot_to(self, destination: Path) -> int:
        """Write one transactionally consistent portable SQLite snapshot."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.unlink(missing_ok=True)
        with self._connection() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
        return self.validate_snapshot(destination)

    @classmethod
    def validate_snapshot(cls, path: Path) -> int:
        """Validate a conversation SQLite snapshot without mutating it."""

        if not path.is_file():
            raise ValueError("conversation snapshot is missing")
        uri = f"file:{path.absolute().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or str(integrity[0]).lower() != "ok":
                raise ValueError("conversation snapshot failed SQLite integrity check")
            tables = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            required = {"conversation_sessions", "conversation_turns"}
            if not required.issubset(tables):
                raise ValueError("conversation snapshot schema is incomplete")
            orphan = connection.execute(
                """
                SELECT COUNT(*)
                FROM conversation_turns AS turns
                LEFT JOIN conversation_sessions AS sessions
                  ON sessions.id = turns.session_id
                WHERE sessions.id IS NULL
                """
            ).fetchone()
            if orphan is not None and int(orphan[0]) != 0:
                raise ValueError("conversation snapshot contains orphan turns")
            rows = connection.execute(
                "SELECT id, child_id, payload_json, updated_at FROM conversation_sessions"
            ).fetchall()
            for row in rows:
                session = cls._session_from_row(connection, row)
                if session.id != row["id"] or session.child_id != row["child_id"]:
                    raise ValueError("conversation snapshot identity mismatch")
            return len(rows)
        except sqlite3.DatabaseError as exc:
            raise ValueError("conversation snapshot is not a valid SQLite database") from exc
        finally:
            connection.close()
