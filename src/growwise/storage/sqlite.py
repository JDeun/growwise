from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import frontmatter

from .markdown import StoredEntity, _decode_metadata
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

    def upsert(self, entity: StoredEntity, source_path: Path) -> None:
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
        return json.loads(row["payload_json"]) if row else None

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
        child_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[str | int] = []
        if entity_type is not None:
            clauses.append("entity_type = ?")
            params.append(entity_type)
        if child_id is not None:
            clauses.append("child_id = ?")
            params.append(child_id)

        sql = "SELECT payload_json FROM entities"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def rebuild(self, records_root: Path) -> int:
        with self._connection() as connection:
            connection.execute("DELETE FROM entities")

        indexed = 0
        for path in sorted(records_root.rglob("*.md")):
            post = frontmatter.load(path)
            payload = _decode_metadata(dict(post.metadata))
            validate_schema_version(payload)
            self._upsert_payload(payload, path)
            indexed += 1
        return indexed
