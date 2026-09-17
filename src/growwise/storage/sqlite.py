from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import frontmatter

from growwise.domain.models import EntityBase

from .markdown import _decode_metadata
from .schema import UnsupportedSchemaVersion, validate_schema_version

_REQUIRED_RECORD_KEYS = ("id", "entity_type", "created_at", "updated_at")


class SQLiteProjection:
    """Rebuildable search/index projection derived from Markdown SoT."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.last_rebuild_skipped: list[Path] = []
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")  # ride out transient contention
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
        try:
            self._create_schema()
        except sqlite3.OperationalError:
            # Locked / permission / disk-IO / disk-full are TRANSIENT and recoverable —
            # never delete a possibly-good index on them (that would silently wipe records
            # from queries). Fail loudly instead so the caller can retry.
            raise
        except sqlite3.DatabaseError:
            # Genuine corruption ("file is not a database" / "malformed"): the index is a
            # disposable projection, so discard it and rebuild from the Markdown SoT.
            if self.path.exists():
                self.path.unlink()
            self._create_schema()

    def _create_schema(self) -> None:
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

    def upsert(self, entity: EntityBase, source_path: Path) -> None:
        payload = entity.model_dump(mode="json")
        validate_schema_version(payload)
        self._upsert_payload(payload, source_path)

    def _upsert_payload(self, payload: dict, source_path: Path) -> None:
        validate_schema_version(payload)
        with self._connection() as connection:
            self._upsert_on(connection, payload, source_path)

    @staticmethod
    def _upsert_on(connection: sqlite3.Connection, payload: dict, source_path: Path) -> None:
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

    def delete_entity(self, entity_id: str, *, entity_type: str | None = None) -> bool:
        clauses = ["id = ?"]
        params: list[str] = [entity_id]
        if entity_type is not None:
            clauses.append("entity_type = ?")
            params.append(entity_type)
        with self._connection() as connection:
            cursor = connection.execute(
                f"DELETE FROM entities WHERE {' AND '.join(clauses)}",
                params,
            )
        return cursor.rowcount > 0

    def get_entity(self, entity_id: str, *, entity_type: str | None = None) -> dict | None:
        sql = "SELECT payload_json FROM entities WHERE id = ?"
        params: list[str] = [entity_id]
        if entity_type is not None:
            sql += " AND entity_type = ?"
            params.append(entity_type)
        with self._connection() as connection:
            row = connection.execute(sql, params).fetchone()
        return json.loads(row["payload_json"]) if row else None

    @staticmethod
    def _child_scope_source_ids(
        connection: sqlite3.Connection,
        *,
        child_id: str,
    ) -> set[str]:
        rows = connection.execute(
            "SELECT payload_json FROM entities WHERE entity_type = 'entity_link' AND child_id = ?",
            (child_id,),
        ).fetchall()
        source_ids: set[str] = set()
        for row in rows:
            payload = json.loads(row["payload_json"])
            if payload.get("relation") == "child_scope" and payload.get("source_id"):
                source_ids.add(str(payload["source_id"]))
        return source_ids

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

        augment_child_scope = (
            child_id is not None
            and entity_type is not None
            and entity_type != "entity_link"
        )
        sql = "SELECT payload_json FROM entities"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC"
        if limit is not None and not augment_child_scope:
            sql += " LIMIT ?"
            params.append(limit)

        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
            payloads = [json.loads(row["payload_json"]) for row in rows]
            if augment_child_scope:
                assert child_id is not None
                assert entity_type is not None
                linked_ids = self._child_scope_source_ids(connection, child_id=child_id)
                if linked_ids:
                    placeholders = ",".join("?" for _ in linked_ids)
                    linked_rows = connection.execute(
                        f"SELECT payload_json FROM entities WHERE entity_type = ? "
                        f"AND id IN ({placeholders})",
                        [entity_type, *sorted(linked_ids)],
                    ).fetchall()
                    by_id = {str(payload["id"]): payload for payload in payloads}
                    for row in linked_rows:
                        payload = json.loads(row["payload_json"])
                        by_id.setdefault(str(payload["id"]), payload)
                    payloads = sorted(
                        by_id.values(),
                        key=lambda payload: str(payload.get("updated_at") or ""),
                        reverse=True,
                    )
                    if limit is not None:
                        payloads = payloads[:limit]
        return payloads

    def search_entities(
        self,
        *,
        child_id: str,
        query_text: str,
        entity_types: Sequence[str],
        limit: int = 20,
    ) -> list[dict]:
        """Deterministic child-scoped lexical search over owned and linked JSON payloads.

        This remains available when all LLM and embedding features are disabled. ``child_scope``
        links extend visibility without copying the source document. Results are ranked by the
        number of query terms present in the payload, then by recency.
        """
        if not entity_types or limit <= 0:
            return []

        terms = list(
            dict.fromkeys(term.strip() for term in query_text.split() if term.strip())
        )[:_MAX_SEARCH_TERMS]
        type_placeholders = ",".join("?" for _ in entity_types)

        with self._connection() as connection:
            linked_ids = self._child_scope_source_ids(connection, child_id=child_id)
            scope_params: list[str | int] = [child_id]
            if linked_ids:
                linked_placeholders = ",".join("?" for _ in linked_ids)
                scope_clause = f"(child_id = ? OR id IN ({linked_placeholders}))"
                scope_params.extend(sorted(linked_ids))
            else:
                scope_clause = "child_id = ?"

            clauses = [scope_clause, f"entity_type IN ({type_placeholders})"]
            where_params: list[str | int] = [*scope_params, *entity_types]

            if terms:
                term_clauses = ["payload_json LIKE ? ESCAPE '\\'" for _ in terms]
                clauses.append("(" + " OR ".join(term_clauses) + ")")
                patterns = [_literal_like_pattern(term) for term in terms]
                where_params.extend(patterns)
                score_sql = " + ".join(
                    "CASE WHEN payload_json LIKE ? ESCAPE '\\' THEN 1 ELSE 0 END"
                    for _ in terms
                )
                sql = (
                    f"SELECT payload_json, ({score_sql}) AS match_score FROM entities "
                    f"WHERE {' AND '.join(clauses)} "
                    "ORDER BY match_score DESC, updated_at DESC LIMIT ?"
                )
                params: list[str | int] = [*patterns, *where_params, limit]
            else:
                sql = (
                    "SELECT payload_json, 0 AS match_score FROM entities "
                    f"WHERE {' AND '.join(clauses)} "
                    "ORDER BY updated_at DESC LIMIT ?"
                )
                params = [*where_params, limit]

            rows = connection.execute(sql, params).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def rebuild(self, records_root: Path) -> int:
        # Atomic: clear + repopulate in ONE transaction, so a hard error mid-rebuild
        # (e.g. UnsupportedSchemaVersion) rolls back and leaves the prior index intact
        # instead of an emptied one.
        self.last_rebuild_skipped = []
        records = sorted(records_root.rglob("*.md"))
        indexed = 0
        with self._connection() as connection:
            connection.execute("DELETE FROM entities")
            for path in records:
                payload = self._read_record(path)
                if payload is None:
                    continue
                self._upsert_on(connection, payload, path)
                indexed += 1
        return indexed

    def _read_record(self, path: Path) -> dict | None:
        """Load one Markdown record, quarantining corrupt/partial files.

        A truncated or unparseable record is skipped (and reported via
        ``last_rebuild_skipped``) so one bad file cannot abort recovery of the
        rest. A recognised-but-unsupported ``schema_version`` is a hard error and
        propagates, since that signals data written by an incompatible build.
        """
        try:
            post = frontmatter.load(path)
            payload = _decode_metadata(dict(post.metadata))
            validate_schema_version(payload)
        except UnsupportedSchemaVersion:
            raise
        except Exception:
            self.last_rebuild_skipped.append(path)
            return None
        if not all(payload.get(key) for key in _REQUIRED_RECORD_KEYS):
            self.last_rebuild_skipped.append(path)
            return None
        return payload
