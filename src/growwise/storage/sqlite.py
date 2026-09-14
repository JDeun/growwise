from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import frontmatter
from pydantic import BaseModel


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

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
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
        self._upsert_payload(payload, source_path)

    def _upsert_payload(self, payload: dict, source_path: Path) -> None:
        with self._connect() as connection:
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

    def list_entities(self, *, entity_type: str, child_id: str | None = None) -> list[dict]:
        query = "SELECT payload_json FROM entities WHERE entity_type = ?"
        params: list[str] = [entity_type]
        if child_id is not None:
            query += " AND child_id = ?"
            params.append(child_id)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def rebuild(self, records_root: Path) -> int:
        with self._connect() as connection:
            connection.execute("DELETE FROM entities")

        count = 0
        for path in sorted(records_root.rglob("*.md")):
            post = frontmatter.load(path)
            payload = dict(post.metadata)
            required = {"id", "entity_type", "created_at", "updated_at"}
            if not required.issubset(payload):
                continue
            self._upsert_payload(payload, path)
            count += 1
        return count
