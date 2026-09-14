from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import frontmatter
from pydantic import BaseModel

from .markdown import _decode_metadata
from .schema import validate_schema_version


class SQLiteProjection:
    """Rebuildable search/index projection derived from Markdown SoT."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a transaction-scoped connection and always release the file handle."""
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    child_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_path TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_entities_type_child "
                "ON entities(entity_type, child_id)"
            )

    def upsert(self, entity: BaseModel, source_path: Path) -> None:
        payload = entity.model_dump(mode="json")
        validate_schema_version(payload)
        self._upsert_payload(payload, source_path)

    def _upsert_payload(self, payload: dict, source_path: Path) -> None:
        validate_schema_version(payload)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO entities (
                    id, entity_type, child_id, created_at, updated_at, source_path, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    entity_type=excluded.entity_type,
                    child_id=excluded.child_id,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    source_path=excluded.source_path,
                    payload_json=excluded.payload_json
                """,
                (
                    str(payload["id"]),
                    str(payload["entity_type"]),
                    str(payload["child_id"]) if payload.get("child_id") else None,
                    str(payload["created_at"]),
                    str(payload["updated_at"]),
                    str(source_path),
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )

    def get_entity(self, entity_id: str, *, entity_type: str | None = None) -> dict | None:
        sql = "SELECT payload_json FROM entities WHERE id = ?"
        params: list[str] = [entity_id]
        if entity_type is not None:
            sql += " AND entity_type = ?"
            params.append(entity_type)
        with self._connection() as connection:
            row = connection.execute(sql, params).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        validate_schema_version(payload)
        return payload

    def list_entities(self, *, entity_type: str, child_id: str | None = None) -> list[dict]:
        query = "SELECT payload_json FROM entities WHERE entity_type = ?"
        params: list[str] = [entity_type]
        if child_id is not None:
            query += " AND child_id = ?"
            params.append(child_id)
        query += " ORDER BY created_at DESC"
        with self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        payloads = [json.loads(row["payload_json"]) for row in rows]
        for payload in payloads:
            validate_schema_version(payload)
        return payloads

    def search_entities(
        self,
        *,
        child_id: str,
        query_text: str,
        entity_types: tuple[str, ...] = ("learning_log", "activity_plan"),
        limit: int = 20,
    ) -> list[dict]:
        """Simple local lexical retrieval with mandatory child isolation."""
        terms = [term.casefold() for term in query_text.split() if len(term.strip()) >= 2]
        if not terms:
            return []

        placeholders = ",".join("?" for _ in entity_types)
        sql = (
            "SELECT payload_json FROM entities "
            f"WHERE child_id = ? AND entity_type IN ({placeholders}) "
            "ORDER BY created_at DESC"
        )
        params: list[str] = [child_id, *entity_types]
        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()

        ranked: list[tuple[int, dict]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            validate_schema_version(payload)
            haystack = json.dumps(payload, ensure_ascii=False).casefold()
            score = sum(haystack.count(term) for term in terms)
            if score:
                ranked.append((score, payload))

        ranked.sort(key=lambda item: (item[0], item[1].get("created_at", "")), reverse=True)
        return [payload for _, payload in ranked[:limit]]

    def rebuild(self, records_root: Path) -> int:
        with self._connection() as connection:
            connection.execute("DELETE FROM entities")

        count = 0
        for path in sorted(records_root.rglob("*.md")):
            post = frontmatter.load(path)
            payload = _decode_metadata(dict(post.metadata))
            required = {"id", "entity_type", "created_at", "updated_at"}
            if not required.issubset(payload):
                continue
            validate_schema_version(payload)
            self._upsert_payload(payload, path)
            count += 1
        return count
