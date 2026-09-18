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
_MAX_SEARCH_TERMS = 32
_MAX_SEARCH_TERM_CHARS = 128
_SQLITE_IN_CHUNK = 400


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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

    @staticmethod
    def _chunks(values: Sequence[str]) -> Iterator[Sequence[str]]:
        for offset in range(0, len(values), _SQLITE_IN_CHUNK):
            yield values[offset : offset + _SQLITE_IN_CHUNK]

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
        sql = "SELECT id, payload_json, source_path FROM entities WHERE id = ?"
        params: list[str] = [entity_id]
        if entity_type is not None:
            sql += " AND entity_type = ?"
            params.append(entity_type)
        with self._connection() as connection:
            row = connection.execute(sql, params).fetchone()
            if row is None:
                return None
            return self._decode_projection_row(connection, row)

    def _decode_projection_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict | None:
        try:
            payload = json.loads(row["payload_json"])
            if not isinstance(payload, dict):
                raise ValueError("projection payload must be an object")
            return payload
        except (TypeError, ValueError, json.JSONDecodeError):
            # SQLite is disposable. Recover one malformed row from its authoritative Markdown
            # source instead of turning a local index defect into an application-wide read failure.
            source_path = Path(str(row["source_path"]))
            payload = self._read_record(source_path)
            if payload is None:
                connection.execute("DELETE FROM entities WHERE id = ?", (str(row["id"]),))
                return None
            self._upsert_on(connection, payload, source_path)
            return payload

    def _child_scope_source_ids(
        self,
        connection: sqlite3.Connection,
        *,
        child_id: str,
    ) -> set[str]:
        rows = connection.execute(
            "SELECT id, payload_json, source_path FROM entities "
            "WHERE entity_type = 'entity_link' AND child_id = ?",
            (child_id,),
        ).fetchall()
        source_ids: set[str] = set()
        for row in rows:
            payload = self._decode_projection_row(connection, row)
            if (
                payload is not None
                and payload.get("relation") == "child_scope"
                and payload.get("source_id")
            ):
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
        sql = "SELECT id, payload_json, source_path FROM entities"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC"
        if limit is not None and not augment_child_scope:
            sql += " LIMIT ?"
            params.append(limit)

        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
            payloads = [
                payload
                for row in rows
                if (payload := self._decode_projection_row(connection, row)) is not None
            ]
            if augment_child_scope:
                assert child_id is not None
                assert entity_type is not None
                linked_ids = sorted(self._child_scope_source_ids(connection, child_id=child_id))
                if linked_ids:
                    by_id = {str(payload["id"]): payload for payload in payloads}
                    for id_chunk in self._chunks(linked_ids):
                        placeholders = ",".join("?" for _ in id_chunk)
                        linked_rows = connection.execute(
                            "SELECT id, payload_json, source_path FROM entities "
                            "WHERE entity_type = ? "
                            f"AND id IN ({placeholders})",
                            [entity_type, *id_chunk],
                        ).fetchall()
                        for row in linked_rows:
                            payload = self._decode_projection_row(connection, row)
                            if payload is not None:
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

        Large child-scope graphs are queried in bounded chunks so SQLite host-parameter limits do
        not turn an authorization relation into a platform-dependent failure.
        """
        if not entity_types or limit <= 0:
            return []

        terms: list[str] = []
        seen_terms: set[str] = set()
        for raw_term in query_text.split():
            term = raw_term.strip()[:_MAX_SEARCH_TERM_CHARS]
            if not term or term in seen_terms:
                continue
            seen_terms.add(term)
            terms.append(term)
            if len(terms) >= _MAX_SEARCH_TERMS:
                break

        normalized_types = tuple(dict.fromkeys(str(value) for value in entity_types))
        type_placeholders = ",".join("?" for _ in normalized_types)

        def run_scope_query(
            connection: sqlite3.Connection,
            *,
            scope_clause: str,
            scope_params: Sequence[str],
        ) -> list[sqlite3.Row]:
            clauses = [scope_clause, f"entity_type IN ({type_placeholders})"]
            where_params: list[str | int] = [*scope_params, *normalized_types]
            if terms:
                term_clauses = ["payload_json LIKE ? ESCAPE '\\'" for _ in terms]
                clauses.append("(" + " OR ".join(term_clauses) + ")")
                patterns = [f"%{_escape_like(term)}%" for term in terms]
                where_params.extend(patterns)
                score_sql = " + ".join(
                    "CASE WHEN payload_json LIKE ? ESCAPE '\\' THEN 1 ELSE 0 END"
                    for _ in terms
                )
                sql = (
                    f"SELECT id, payload_json, source_path, updated_at, ({score_sql}) AS match_score "
                    f"FROM entities WHERE {' AND '.join(clauses)} "
                    "ORDER BY match_score DESC, updated_at DESC LIMIT ?"
                )
                params: list[str | int] = [*patterns, *where_params, limit]
            else:
                sql = (
                    "SELECT id, payload_json, source_path, updated_at, 0 AS match_score FROM entities "
                    f"WHERE {' AND '.join(clauses)} "
                    "ORDER BY updated_at DESC LIMIT ?"
                )
                params = [*where_params, limit]
            return connection.execute(sql, params).fetchall()

        with self._connection() as connection:
            candidates = run_scope_query(
                connection,
                scope_clause="child_id = ?",
                scope_params=(child_id,),
            )
            linked_ids = sorted(self._child_scope_source_ids(connection, child_id=child_id))
            for id_chunk in self._chunks(linked_ids):
                placeholders = ",".join("?" for _ in id_chunk)
                candidates.extend(
                    run_scope_query(
                        connection,
                        scope_clause=f"id IN ({placeholders})",
                        scope_params=id_chunk,
                    )
                )

        # Each chunk contributes at most its local top-N. Anything lower cannot enter the global
        # top-N because that same chunk already contains N rows ranked above it.
        by_id: dict[str, sqlite3.Row] = {}
        for row in candidates:
            current = by_id.get(str(row["id"]))
            if current is None or (
                int(row["match_score"]),
                str(row["updated_at"]),
            ) > (
                int(current["match_score"]),
                str(current["updated_at"]),
            ):
                by_id[str(row["id"])] = row
        ranked = sorted(
            by_id.values(),
            key=lambda row: (int(row["match_score"]), str(row["updated_at"])),
            reverse=True,
        )
        payloads: list[dict] = []
        with self._connection() as connection:
            for row in ranked:
                payload = self._decode_projection_row(connection, row)
                if payload is not None:
                    payloads.append(payload)
                if len(payloads) >= limit:
                    break
        return payloads

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
