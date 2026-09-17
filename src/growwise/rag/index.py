from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from .chunking import ResourceChunk
from .embeddings import EmbeddingProvider
from .temporal import hierarchical_temporal_order, temporal_tier


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _fts_query(terms: list[str]) -> str:
    """Treat parent-entered text as literals and use token-prefix matching.

    Prefix matching matters for Korean because the unicode tokenizer may keep particles attached to
    a stem (for example ``고양이를``) while a parent naturally searches for ``고양이``.
    """
    return " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"*' for term in terms)


class HybridRagIndex:
    """SQLite-backed resource chunk index with lexical + optional vector scoring.

    Core-only lexical search uses an FTS5 candidate set instead of loading every visible chunk into
    Python. Child ownership, explicitly shared resources, provenance, and the temporal hierarchy are
    applied identically to the fallback scan. When vector embeddings are active, GrowWise still scans
    the full visible vector set to preserve semantic recall until a dedicated vector index exists.
    """

    def __init__(self, path: Path, embedding: EmbeddingProvider | None = None) -> None:
        self.path = path
        self.embedding = embedding
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_available = False
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    child_id TEXT,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_url TEXT,
                    source_name TEXT,
                    tags_json TEXT NOT NULL,
                    embedding_json TEXT,
                    recorded_at TEXT
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(rag_chunks)").fetchall()
            }
            if "recorded_at" not in columns:
                connection.execute("ALTER TABLE rag_chunks ADD COLUMN recorded_at TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_resource ON rag_chunks(resource_id)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_rag_child ON rag_chunks(child_id)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_child_time "
                "ON rag_chunks(child_id, recorded_at DESC)"
            )
            try:
                connection.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
                        chunk_id UNINDEXED,
                        resource_id UNINDEXED,
                        child_id UNINDEXED,
                        title,
                        text,
                        tags
                    )
                    """
                )
                # RAG is a disposable projection. Rebuilding the small lexical projection when the
                # index opens prevents FTS state from drifting after migrations or an interrupted
                # older writer.
                connection.execute("DELETE FROM rag_chunks_fts")
                connection.execute(
                    """
                    INSERT INTO rag_chunks_fts (
                        chunk_id, resource_id, child_id, title, text, tags
                    )
                    SELECT chunk_id, resource_id, child_id, title, text, tags_json
                    FROM rag_chunks
                    """
                )
                self._fts_available = True
            except sqlite3.OperationalError:
                # Embedded SQLite builds without FTS5 keep the previous safe scoped-scan behavior.
                self._fts_available = False
            connection.commit()
        finally:
            connection.close()

    def reset(self) -> None:
        """Clear the rebuildable RAG projection without replacing the SQLite file."""
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM rag_chunks")
            if self._fts_available:
                connection.execute("DELETE FROM rag_chunks_fts")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def delete_resource(self, resource_id: str) -> int:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM rag_chunks WHERE resource_id = ?", (resource_id,)
            )
            if self._fts_available:
                connection.execute(
                    "DELETE FROM rag_chunks_fts WHERE resource_id = ?", (resource_id,)
                )
            connection.commit()
            return cursor.rowcount
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def delete_child(self, child_id: str) -> int:
        """Delete every private RAG chunk belonging to one child."""
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute("DELETE FROM rag_chunks WHERE child_id = ?", (child_id,))
            if self._fts_available:
                connection.execute("DELETE FROM rag_chunks_fts WHERE child_id = ?", (child_id,))
            connection.commit()
            return cursor.rowcount
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def replace_resource(self, chunks: list[ResourceChunk]) -> int:
        if not chunks:
            return 0
        resource_id = chunks[0].resource_id
        if any(chunk.resource_id != resource_id for chunk in chunks):
            raise ValueError("replace_resource expects chunks from exactly one resource")

        vectors: list[list[float] | None] = [None] * len(chunks)
        if self.embedding is not None:
            try:
                embedded = self.embedding.embed_documents([chunk.text for chunk in chunks])
                vectors = list(embedded)
            except Exception:
                vectors = [None] * len(chunks)
        if len(vectors) != len(chunks):
            vectors = [None] * len(chunks)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM rag_chunks WHERE resource_id = ?", (resource_id,))
            if self._fts_available:
                connection.execute(
                    "DELETE FROM rag_chunks_fts WHERE resource_id = ?", (resource_id,)
                )
            for chunk, vector in zip(chunks, vectors, strict=True):
                tags_json = json.dumps(list(chunk.tags), ensure_ascii=False)
                connection.execute(
                    """
                    INSERT INTO rag_chunks (
                        chunk_id, resource_id, child_id, title, text,
                        source_url, source_name, tags_json, embedding_json, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.resource_id,
                        chunk.child_id,
                        chunk.title,
                        chunk.text,
                        chunk.source_url,
                        chunk.source_name,
                        tags_json,
                        json.dumps(vector) if vector is not None else None,
                        chunk.recorded_at,
                    ),
                )
                if self._fts_available:
                    connection.execute(
                        """
                        INSERT INTO rag_chunks_fts (
                            chunk_id, resource_id, child_id, title, text, tags
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk.chunk_id,
                            chunk.resource_id,
                            chunk.child_id,
                            chunk.title,
                            chunk.text,
                            tags_json,
                        ),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return len(chunks)

    @staticmethod
    def _normalized_shared_ids(shared_resource_ids: Iterable[str] | None) -> tuple[str, ...]:
        return tuple(dict.fromkeys(str(resource_id) for resource_id in shared_resource_ids or ()))

    @classmethod
    def _scoped_rows(
        cls,
        connection: sqlite3.Connection,
        *,
        child_id: str | None,
        shared_resource_ids: Iterable[str] | None,
    ) -> list[sqlite3.Row]:
        shared_ids = cls._normalized_shared_ids(shared_resource_ids)
        if shared_ids:
            placeholders = ",".join("?" for _ in shared_ids)
            return connection.execute(
                f"SELECT * FROM rag_chunks WHERE child_id IS NULL OR child_id = ? "
                f"OR resource_id IN ({placeholders})",
                (child_id, *shared_ids),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM rag_chunks WHERE child_id IS NULL OR child_id = ?",
            (child_id,),
        ).fetchall()

    def _lexical_candidates(
        self,
        connection: sqlite3.Connection,
        *,
        query_terms: list[str],
        child_id: str | None,
        shared_resource_ids: Iterable[str] | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        if not self._fts_available or not query_terms:
            return self._scoped_rows(
                connection,
                child_id=child_id,
                shared_resource_ids=shared_resource_ids,
            )

        shared_ids = self._normalized_shared_ids(shared_resource_ids)
        candidate_limit = max(200, limit * 20)
        if shared_ids:
            placeholders = ",".join("?" for _ in shared_ids)
            scope_sql = f"(c.child_id IS NULL OR c.child_id = ? OR c.resource_id IN ({placeholders}))"
            scope_params: tuple[object, ...] = (child_id, *shared_ids)
        else:
            scope_sql = "(c.child_id IS NULL OR c.child_id = ?)"
            scope_params = (child_id,)

        try:
            rows = connection.execute(
                f"""
                SELECT c.*
                FROM rag_chunks AS c
                JOIN rag_chunks_fts AS f ON f.chunk_id = c.chunk_id
                WHERE rag_chunks_fts MATCH ? AND {scope_sql}
                LIMIT ?
                """,
                (_fts_query(query_terms), *scope_params, candidate_limit),
            ).fetchall()
            if rows:
                return rows
            # Token boundaries differ across languages/builds. Preserve the original substring
            # recall when FTS finds nothing instead of turning an optimization into a recall loss.
            return self._scoped_rows(
                connection,
                child_id=child_id,
                shared_resource_ids=shared_ids,
            )
        except sqlite3.OperationalError:
            return self._scoped_rows(
                connection,
                child_id=child_id,
                shared_resource_ids=shared_ids,
            )

    def search(
        self,
        *,
        query: str,
        child_id: str | None,
        limit: int = 8,
        reference_date: date | None = None,
        shared_resource_ids: Iterable[str] | None = None,
    ) -> list[dict]:
        if limit <= 0:
            return []
        query_terms = [term.casefold() for term in query.split() if len(term.strip()) >= 2]
        query_vector: list[float] | None = None
        if self.embedding is not None:
            try:
                query_vector = self.embedding.embed_query(query)
            except Exception:
                query_vector = None
        if not query_terms and query_vector is None:
            return []

        connection = self._connect()
        try:
            # Semantic ranking still needs all visible vectors. Without a query vector, FTS5 keeps
            # the Python ranking set bounded while honoring normal ownership and explicit sharing.
            if query_vector is not None:
                rows = self._scoped_rows(
                    connection,
                    child_id=child_id,
                    shared_resource_ids=shared_resource_ids,
                )
            else:
                rows = self._lexical_candidates(
                    connection,
                    query_terms=query_terms,
                    child_id=child_id,
                    shared_resource_ids=shared_resource_ids,
                    limit=limit,
                )
        finally:
            connection.close()

        ranked: list[tuple[float, dict]] = []
        for row in rows:
            haystack = f"{row['title']} {row['text']} {row['tags_json']}".casefold()
            lexical = float(sum(haystack.count(term) for term in query_terms))
            vector_score = 0.0
            if query_vector is not None and row["embedding_json"]:
                try:
                    stored_vector = json.loads(row["embedding_json"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    stored_vector = []
                if isinstance(stored_vector, list):
                    vector_score = cosine_similarity(query_vector, stored_vector)
            if lexical <= 0 and vector_score <= 0:
                continue
            score = lexical + max(vector_score, 0.0) * 3.0
            payload = {
                "chunk_id": row["chunk_id"],
                "resource_id": row["resource_id"],
                "child_id": row["child_id"],
                "title": row["title"],
                "text": row["text"],
                "source_url": row["source_url"],
                "source_name": row["source_name"],
                "tags": json.loads(row["tags_json"]),
                "recorded_at": row["recorded_at"],
                "temporal_tier": temporal_tier(
                    row["recorded_at"], reference_date=reference_date
                ).name.lower(),
                "score": score,
                "lexical_score": lexical,
                "vector_score": vector_score,
            }
            ranked.append((score, payload))

        # Relevance order is preserved inside each time tier. Temporal preference never promotes an
        # irrelevant chunk because only positive lexical/vector matches reach this list.
        ranked.sort(key=lambda item: item[0], reverse=True)
        relevant = [payload for _, payload in ranked]
        return hierarchical_temporal_order(
            relevant,
            timestamp=lambda item: item.get("recorded_at"),
            limit=limit,
            reference_date=reference_date,
        )
