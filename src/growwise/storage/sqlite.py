from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import frontmatter

from growwise.domain.models import EntityBase

from .markdown import MarkdownRepository, _decode_metadata
from .schema import UnsupportedSchemaVersion, validate_schema_version

_REQUIRED_RECORD_KEYS = ("id", "entity_type", "created_at", "updated_at")
_MAX_SEARCH_TERMS = 32
_MAX_SEARCH_TERM_CHARS = 128
_SQLITE_IN_CHUNK = 400
_PENDING_AI_WHERE = (
    "entity_type IN ('learning_log', 'generated_material') AND "
    "CASE WHEN json_valid(payload_json) THEN json_extract(payload_json, '$.ai_status') END "
    "IN ('queued', 'running')"
)
_PENDING_PHOTO_WHERE = (
    "entity_type = 'photo_activity_record' AND "
    "CASE WHEN json_valid(payload_json) THEN json_extract(payload_json, '$.status') END "
    "IN ('queued', 'processing')"
)


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

    def get_current_entity(self, entity_id: str, *, entity_type: str | None = None) -> dict | None:
        """Resolve an index pointer against its current Markdown source, failing closed.

        Close the SQLite read before taking the Markdown path lock: writers take that path lock
        before updating SQLite. A projection payload is never authoritative evidence here.
        """
        with self._connection() as connection:
            row = connection.execute(
                "SELECT entity_type, source_path FROM entities WHERE id = ?", (entity_id,),
            ).fetchone()
        if row is None or (entity_type is not None and row["entity_type"] != entity_type):
            return None
        path = Path(row["source_path"])
        with MarkdownRepository.lock_for(path):
            try:
                if (path.is_symlink() or not path.is_file()
                        or path.stat().st_size > 64 * 1024 * 1024):
                    return None
                post = frontmatter.loads(path.read_text(encoding="utf-8"))
                payload = _decode_metadata(dict(post.metadata))
                validate_schema_version(payload)
                if (not all(payload.get(key) for key in _REQUIRED_RECORD_KEYS)
                        or str(payload["id"]) != entity_id
                        or payload["entity_type"] != row["entity_type"]
                        or path.stem != entity_id or path.parent.name != row["entity_type"]):
                    return None
                return payload
            except Exception:
                # A malformed/unreadable source must never fall back to the old cached payload.
                return None

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
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_entities_pending_ai ON entities(id) "
                f"WHERE {_PENDING_AI_WHERE}"
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_entities_pending_photo ON entities(id) "
                f"WHERE {_PENDING_PHOTO_WHERE}"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entity_links_index (
                    link_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_entity_links_source_relation "
                "ON entity_links_index(source_id, relation)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_entity_links_target_relation "
                "ON entity_links_index(target_id, relation)"
            )
            self._backfill_entity_links_index(connection)

    @staticmethod
    def _sync_entity_link_index(connection: sqlite3.Connection, payload: dict) -> None:
        entity_id = str(payload["id"])
        connection.execute("DELETE FROM entity_links_index WHERE link_id = ?", (entity_id,))
        if str(payload.get("entity_type") or "") != "entity_link":
            return
        source_id = payload.get("source_id")
        target_id = payload.get("target_id")
        relation = payload.get("relation")
        if not source_id or not target_id or not relation:
            return
        connection.execute(
            """
            INSERT INTO entity_links_index (link_id, source_id, target_id, relation)
            VALUES (?, ?, ?, ?)
            """,
            (entity_id, str(source_id), str(target_id), str(relation)),
        )

    def _backfill_entity_links_index(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT entities.id, entities.payload_json, entities.source_path
            FROM entities
            LEFT JOIN entity_links_index AS links ON links.link_id = entities.id
            WHERE entities.entity_type = 'entity_link' AND links.link_id IS NULL
            """
        ).fetchall()
        for row in rows:
            payload = self._decode_projection_row(connection, row)
            if payload is not None:
                self._sync_entity_link_index(connection, payload)

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
        SQLiteProjection._sync_entity_link_index(connection, payload)

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
            if cursor.rowcount:
                connection.execute(
                    "DELETE FROM entity_links_index WHERE link_id = ?",
                    (entity_id,),
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
                connection.execute(
                    "DELETE FROM entity_links_index WHERE link_id = ?",
                    (str(row["id"]),),
                )
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
            """
            SELECT source_id
            FROM entity_links_index
            WHERE target_id = ? AND relation = 'child_scope'
            """,
            (child_id,),
        ).fetchall()
        return {str(row["source_id"]) for row in rows}

    def list_entity_links(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relation: str | None = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[str] = []
        if source_id is not None:
            clauses.append("links.source_id = ?")
            params.append(source_id)
        if target_id is not None:
            clauses.append("links.target_id = ?")
            params.append(target_id)
        if relation is not None:
            clauses.append("links.relation = ?")
            params.append(relation)

        sql = (
            "SELECT entities.id, entities.payload_json, entities.source_path "
            "FROM entity_links_index AS links "
            "JOIN entities ON entities.id = links.link_id"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY entities.updated_at DESC"

        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
            return [
                payload
                for row in rows
                if (payload := self._decode_projection_row(connection, row)) is not None
            ]

    def entity_links_touching(self, entity_ids: set[str]) -> list[dict]:
        if not entity_ids:
            return []
        by_id: dict[str, dict] = {}
        ordered = sorted(entity_ids)
        with self._connection() as connection:
            for id_chunk in self._chunks(ordered):
                placeholders = ",".join("?" for _ in id_chunk)
                for column in ("source_id", "target_id"):
                    rows = connection.execute(
                        "SELECT entities.id, entities.payload_json, entities.source_path "
                        "FROM entity_links_index AS links "
                        "JOIN entities ON entities.id = links.link_id "
                        f"WHERE links.{column} IN ({placeholders})",
                        list(id_chunk),
                    ).fetchall()
                    for row in rows:
                        payload = self._decode_projection_row(connection, row)
                        if payload is not None:
                            by_id.setdefault(str(payload["id"]), payload)
        return list(by_id.values())

    def pending_ai_entities(self, *, after_id: str = "") -> list[dict]:
        """Page only unfinished AI metadata, rather than scanning the family's full history."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, payload_json, source_path FROM entities INDEXED BY "
                f"idx_entities_pending_ai WHERE {_PENDING_AI_WHERE} "
                "AND id > ? ORDER BY id LIMIT 100",
                (after_id,),
            ).fetchall()
            return [
                payload
                for row in rows
                if (payload := self._decode_projection_row(connection, row)) is not None
            ]

    def pending_photo_entities(self, *, after_id: str = "") -> list[dict]:
        """Page unfinished photos only, including records whose disposable job was restored away."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, payload_json, source_path FROM entities INDEXED BY "
                f"idx_entities_pending_photo WHERE {_PENDING_PHOTO_WHERE} "
                "AND id > ? ORDER BY id LIMIT 100",
                (after_id,),
            ).fetchall()
            return [
                payload
                for row in rows
                if (payload := self._decode_projection_row(connection, row)) is not None
            ]

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
        child_id: str | None = None,
        limit: int | None = None,
        include_global: bool = False,
    ) -> list[dict]:
        if limit is not None and limit <= 0:
            return []
        clauses: list[str] = []
        params: list[str | int] = []
        if entity_type is not None:
            clauses.append("entity_type = ?")
            params.append(entity_type)
        if child_id is not None:
            scope = "child_id = ?"
            params.append(child_id)
            if include_global:
                scope += " OR child_id IS NULL"
            if entity_type is not None and entity_type != "entity_link":
                scope += (
                    " OR id IN (SELECT source_id FROM entity_links_index "
                    "WHERE target_id = ? AND relation = 'child_scope')"
                )
                params.append(child_id)
            clauses.append(f"({scope})")
        sql = "SELECT id, payload_json, source_path FROM entities"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        with self._connection() as connection:
            rows = connection.execute(sql, params).fetchall()
            payloads = [
                payload
                for row in rows
                if (payload := self._decode_projection_row(connection, row)) is not None
            ]
        return payloads

    def search_entities(
        self,
        *,
        child_id: str,
        query_text: str,
        entity_types: Sequence[str],
        limit: int | None = 20,
    ) -> list[dict]:
        """Deterministic child-scoped lexical search over owned and linked JSON payloads.

        Large child-scope graphs are queried in bounded chunks so SQLite host-parameter limits do
        not turn an authorization relation into a platform-dependent failure.
        """
        if not entity_types or (limit is not None and limit <= 0):
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
                    "CASE WHEN payload_json LIKE ? ESCAPE '\\' THEN 1 ELSE 0 END" for _ in terms
                )
                sql = (
                    "SELECT id, payload_json, source_path, updated_at, "
                    f"({score_sql}) AS match_score "
                    f"FROM entities WHERE {' AND '.join(clauses)} "
                    "ORDER BY match_score DESC, updated_at DESC LIMIT ?"
                )
                params: list[str | int] = [
                    *patterns,
                    *where_params,
                    limit if limit is not None else -1,
                ]
            else:
                sql = (
                    "SELECT id, payload_json, source_path, updated_at, "
                    "0 AS match_score FROM entities "
                    f"WHERE {' AND '.join(clauses)} "
                    "ORDER BY updated_at DESC LIMIT ?"
                )
                params = [*where_params, limit if limit is not None else -1]
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
                if limit is not None and len(payloads) >= limit:
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
            connection.execute("DELETE FROM entity_links_index")
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
